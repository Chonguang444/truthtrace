"""
反馈闭环编排管道 — 连通反馈→分类→误判发现→校准→回归测试→规则建议

这是 TruthTrace 自我进化的核心引擎。
每个用户反馈都是一次学习机会。

流程:
  用户提交反馈
    → 自动分类 (FeedbackClassifier)
    → 摄取到误判检测器 (MisjudgmentDetector)
    → 记录到校准器 (ScoreCalibrator)
    → 当积累≥50条新数据 → 触发校准
    → 校准后自动运行回归测试
    → 发现新误判模式 → 生成规则调整建议
    → 管理员审核 → 应用规则变更 (RuleVersionManager)
"""

from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("truthtrace.feedback_loop")


@dataclass
class LoopResult:
    """一次完整的反馈处理结果"""
    feedback_id: str = ""
    classification: str = ""
    matched_pattern: dict | None = None
    calibration_triggered: bool = False
    calibration_recommendation: str = ""
    regression_results: dict | None = None
    new_patterns_discovered: list = field(default_factory=list)
    rule_suggestions: list = field(default_factory=list)
    action_required: str = ""  # "none" / "review_pattern" / "review_rule_change"


class FeedbackLoopPipeline:
    """
    反馈闭环主管道。

    用法:
        pipeline = FeedbackLoopPipeline()
        result = await pipeline.process_feedback(feedback_dict)
        if result.action_required != "none":
            notify_admin(result)
    """

    def __init__(self):
        self._feedback_count = 0
        self._calibration_interval = 50  # 每50条反馈检查一次校准

    async def process_feedback(self, feedback: dict) -> LoopResult:
        """
        处理一条用户反馈 — 执行完整闭环。

        Args:
            feedback: 来自 /api/feedback 的反馈字典

        Returns:
            LoopResult 含分类、校准状态、新发现的模式
        """
        result = LoopResult(feedback_id=feedback.get("id", str(uuid.uuid4())))
        self._feedback_count += 1

        # === Step 1: 自动分类 ===
        from app.evolution import get_feedback_classifier
        classifier = get_feedback_classifier()
        classification = classifier.classify(feedback)
        result.classification = classification
        logger.info(f"[闭环] 反馈分类: {classification} (事件: {feedback.get('event_id', '?')[:8]})")

        # === Step 2: 摄取到误判检测器 ===
        from app.evolution import get_misjudgment_detector
        detector = get_misjudgment_detector()
        pattern = detector.ingest_feedback(feedback)
        if pattern:
            result.matched_pattern = pattern.to_dict()
            logger.info(f"[闭环] 匹配已知误判模式: {pattern.pattern_name}")

        # === Step 3: 记录到校准器 ===
        from app.evolution.calibrator import get_calibrator
        calibrator = get_calibrator()
        was_accurate = feedback.get("rating", "") == "helpful"
        calibrator.record_feedback(
            event_id=feedback.get("event_id", ""),
            was_accurate=was_accurate,
            dispute_type=classification,
        )

        # === Step 4: 检查是否需要校准 ===
        if self._feedback_count % self._calibration_interval == 0:
            snapshot = calibrator.maybe_calibrate()
            if snapshot:
                result.calibration_triggered = True
                result.calibration_recommendation = snapshot.recommendation
                logger.info(f"[闭环] 触发校准 (n={snapshot.total_events}): {snapshot.recommendation}")

                # === Step 5: 校准后自动回归测试 ===
                from app.evolution import run_regression_tests
                regression_result = await run_regression_tests()
                result.regression_results = regression_result
                result.calibration_recommendation = snapshot.recommendation

                if regression_result.get("failed", 0) > 0:
                    result.action_required = "review_pattern"
                    logger.warning(
                        f"[闭环] 回归测试失败: {regression_result['failed']} 个用例"
                    )

        # === Step 6: 批量检测新误判模式 ===
        if self._feedback_count % 20 == 0:
            # 从最近的 inaccurate 反馈中发现新模式
            from app.evolution import get_misjudgment_detector
            detector = get_misjudgment_detector()

            # 模拟收集最近的 inaccurate 反馈
            recent = [
                fb for event_feeds in _get_all_feedbacks().values()
                for fb in event_feeds[-50:]
                if fb.get("rating") == "inaccurate"
            ]
            if recent:
                new_patterns = detector.discover_patterns_from_batch(recent)
                if new_patterns:
                    result.new_patterns_discovered = [
                        p.to_dict() for p in new_patterns
                    ]
                    result.action_required = "review_pattern"
                    logger.warning(
                        f"[闭环] 发现 {len(new_patterns)} 个新误判模式!"
                    )

        return result

    async def run_full_cycle(self) -> dict:
        """运行完整的自我进化周期 (管理员手动触发或定时任务)"""
        logger.info("[闭环] 开始完整进化周期...")

        results = {
            "cycle_id": str(uuid.uuid4())[:8],
            "started_at": datetime.now(timezone.utc).isoformat(),
            "steps": {},
        }

        # 1. 收集所有未审核反馈
        feedbacks = _get_all_feedbacks()
        total_fb = sum(len(v) for v in feedbacks.values())
        results["total_feedbacks"] = total_fb

        # 2. 发现误判模式
        from app.evolution import get_misjudgment_detector
        detector = get_misjudgment_detector()
        all_fb = [fb for feeds in feedbacks.values() for fb in feeds]
        inaccurate_fb = [fb for fb in all_fb if fb.get("rating") == "inaccurate"]
        if inaccurate_fb:
            new_patterns = detector.discover_patterns_from_batch(inaccurate_fb)
            results["steps"]["patterns"] = {
                "discovered": len(new_patterns),
                "active": len(detector.get_active_patterns()),
            }

        # 3. 校准
        from app.evolution.calibrator import get_calibrator
        calibrator = get_calibrator()
        snap = calibrator.maybe_calibrate()
        if snap:
            results["steps"]["calibration"] = {
                "triggered": True,
                "recommendation": snap.recommendation,
                "accuracy": snap.feedback_accuracy,
                "dispute_rate": snap.disputed_rate,
            }

            # 4. 回归测试
            from app.evolution import run_regression_tests
            reg = await run_regression_tests()
            results["steps"]["regression"] = reg

        # 5. 知识库过期检查
        from app.evolution import get_knowledge_expiry_manager
        expiry_mgr = get_knowledge_expiry_manager()
        expired = expiry_mgr.check_expiry()
        results["steps"]["knowledge_expiry"] = {
            "needs_review": len(expired),
            "entries": expired,
        }

        results["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"[闭环] 完整周期完成: {results['steps']}")
        return results

    def status(self) -> dict:
        """返回闭环当前状态"""
        from app.evolution import (
            get_misjudgment_detector, get_rule_version_manager,
        )
        from app.evolution.calibrator import get_calibrator
        detector = get_misjudgment_detector()
        calibrator = get_calibrator()
        rule_mgr = get_rule_version_manager()

        c_snap = calibrator.snapshot()

        return {
            "feedback_pipeline": {
                "total_feedbacks_processed": self._feedback_count,
                "next_calibration_in": self._calibration_interval - (self._feedback_count % self._calibration_interval),
            },
            "calibrator": {
                "total_events_tracked": c_snap.total_events,
                "avg_score": c_snap.avg_score,
                "score_std": c_snap.score_std,
                "estimated_accuracy": c_snap.feedback_accuracy,
                "dispute_rate": round(c_snap.disputed_rate * 100, 1),
                "confidence": "adequate" if c_snap.total_events >= 100 else "gathering_data",
            },
            "misjudgment": {
                "active_patterns": len(detector.get_active_patterns()),
            },
            "rule_versions": {
                "modules": rule_mgr.get_current_versions(),
                "total_changes": len(rule_mgr.get_history()),
            },
        }


# =============================================================================
# 内部辅助: 访问反馈存储
# =============================================================================

def _get_all_feedbacks() -> dict[str, list[dict]]:
    """获取所有反馈 (访问 feedback.py 的内存存储)"""
    try:
        from app.api.feedback import _feedback_store
        return _feedback_store
    except ImportError:
        return {}


# =============================================================================
# 全局单例
# =============================================================================

_pipeline: FeedbackLoopPipeline | None = None


def get_feedback_loop() -> FeedbackLoopPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = FeedbackLoopPipeline()
    return _pipeline
