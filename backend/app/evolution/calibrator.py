"""
自适应评分校准 — 基于积累的真实数据动态调整引擎阈值

原理:
引擎初始化的评分阈值是基于先验假设的。
随着实际案例的积累, 系统可以根据"已被证实的判定"和"用户反馈"来微调。

机制:
1. 动态基线 — 从历史数据的分布中学习"正常"评分范围
2. 置信度校准 — 将评分映射到实际的正确率
3. 误报率vs召回率平衡 — 根据用户反馈类型自动调整
4. 每个引擎维度的独立权重调整

重要: 校准是缓慢的、保守的。不会因为一两条反馈就大幅改变规则。
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Optional
from collections import deque, defaultdict

logger = logging.getLogger("truthtrace.calibrator")


# =============================================================================
# 校准参数
# =============================================================================

@dataclass
class CalibrationWeights:
    """各引擎维度的评分权重"""
    distortion_weight: float = 1.0      # 失真扣分权重
    fallacy_weight: float = 1.0          # 谬误扣分权重
    statistical_weight: float = 1.0      # 统计滥用扣分权重
    composite_weight: float = 1.0        # 拼接风险扣分权重
    source_weight: float = 0.6           # 来源可信度加权系数
    narrative_weight: float = 1.0        # 叙事操纵扣分权重
    drift_weight: float = 1.0            # 模态漂移扣分权重

    # 阈值
    false_threshold: float = 30.0       # <30 判定为 false
    likely_false_threshold: float = 45.0  # 30-45 为 likely_false
    misleading_threshold: float = 60.0    # 45-60 为 misleading
    likely_true_threshold: float = 75.0   # 60-75 为 likely_true

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class CalibrationSnapshot:
    """校准快照"""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_events: int = 0
    avg_score: float = 50.0
    score_std: float = 15.0
    false_rate: float = 0.0              # 判定为false的比例
    feedback_accuracy: float = 0.0       # 用户反馈为准确的比率
    disputed_rate: float = 0.0           # 被质疑的比例
    weights: CalibrationWeights = field(default_factory=CalibrationWeights)
    recommendation: str = ""


# =============================================================================
# 校准器
# =============================================================================

class ScoreCalibrator:
    """
    评分校准器

    用法:
      cal = ScoreCalibrator()
      cal.record_event(score=37.8, verdict="likely_false", ...)
      cal.record_feedback(event_id="...", was_accurate=True)
      adjusted = cal.calibrate_score(raw_score=42.0, engine_outputs={...})
    """

    def __init__(self):
        self._scores: deque[float] = deque(maxlen=1000)     # 历史评分
        self._feedbacks: deque[dict] = deque(maxlen=500)     # 反馈记录
        self._verdicts: defaultdict[str, int] = defaultdict(int)
        self._disputed: set[str] = set()
        self._confirmed: set[str] = set()
        self.weights = CalibrationWeights()
        self._calibration_count = 0
        self._last_calibration: Optional[datetime] = None

    # ---- 数据积累 ----
    def record_event(self, score: float, verdict: str, engine_outputs: dict):
        """记录一条分析结果"""
        self._scores.append(score)
        self._verdicts[verdict] += 1

    def record_feedback(self, event_id: str, was_accurate: bool, dispute_type: str = ""):
        """记录用户反馈"""
        self._feedbacks.append({
            "event_id": event_id, "accurate": was_accurate,
            "type": dispute_type, "at": datetime.now(timezone.utc).isoformat(),
        })
        if was_accurate:
            self._confirmed.add(event_id)
        else:
            self._disputed.add(event_id)

    # ---- 统计分析 ----
    def _compute_distribution(self) -> dict:
        if len(self._scores) < 20:
            return {"mean": 50.0, "std": 15.0, "p25": 35.0, "p50": 50.0, "p75": 65.0}

        import statistics
        scores = list(self._scores)
        sorted_s = sorted(scores)
        n = len(sorted_s)
        return {
            "mean": round(statistics.mean(scores), 1),
            "std": round(statistics.stdev(scores), 1) if n > 1 else 15.0,
            "p25": sorted_s[n // 4],
            "p50": sorted_s[n // 2],
            "p75": sorted_s[3 * n // 4],
        }

    def _compute_accuracy(self) -> dict:
        """从反馈中估计准确率"""
        recent = [f for f in self._feedbacks
                  if datetime.fromisoformat(f["at"]) > datetime.now(timezone.utc) - timedelta(days=30)]
        if len(recent) < 10:
            return {"estimated_accuracy": 0.8, "sample_size": len(recent), "confidence": "low"}

        accurate = sum(1 for f in recent if f["accurate"])
        acc = accurate / len(recent)
        return {
            "estimated_accuracy": round(acc, 3),
            "sample_size": len(recent),
            "confidence": "high" if len(recent) >= 50 else "moderate",
        }

    # ---- 校准 ----
    def maybe_calibrate(self) -> Optional[CalibrationSnapshot]:
        """当数据足够时自动校准 — 返回校准快照"""
        if len(self._scores) < 50:
            return None

        # 至少积累50条新数据才校准一次
        since_last = len(self._scores) - (self._calibration_count or 0)
        if since_last < 50:
            return None

        dist = self._compute_distribution()
        acc = self._compute_accuracy()

        # 调整阈值(保守)
        snap = CalibrationSnapshot(
            total_events=len(self._scores),
            avg_score=dist["mean"],
            score_std=dist["std"],
            feedback_accuracy=acc["estimated_accuracy"],
            disputed_rate=len(self._disputed) / max(1, len(self._scores)),
        )

        # --- 调优逻辑 ---
        recs = []

        # 如果实际分布中位数显著偏离50 — 整体偏移
        median = dist["p50"]
        if median < 40 and len(self._disputed) / max(1, len(self._confirmed)) > 2:
            recs.append(f"评分中位数({median})偏低且争议率高。建议上调所有阈值+5。")
            snap.weights.false_threshold = self.weights.false_threshold + 5
            snap.weights.likely_false_threshold = self.weights.likely_false_threshold + 5
            snap.weights.misleading_threshold = self.weights.misleading_threshold + 5
        elif median > 60 and len(self._scores) > 100:
            recs.append(f"评分中位数({median})偏高。建议下调阈值-3以提升敏感度。")
            snap.weights.false_threshold = self.weights.false_threshold - 3
            snap.weights.likely_false_threshold = self.weights.likely_false_threshold - 3

        # 误报率高 — 收紧阈值
        false_ratio = self._verdicts.get("false", 0) + self._verdicts.get("likely_false", 0)
        total = sum(self._verdicts.values()) or 1
        if false_ratio / total > 0.6 and acc["estimated_accuracy"] < 0.7:
            recs.append(f"高风险判定占比过高({false_ratio/total:.0%})且准确率低({acc['estimated_accuracy']:.0%})。建议降低失真扣分权重。")
            snap.weights.distortion_weight = max(0.3, self.weights.distortion_weight - 0.1)

        # 准确率高 — 可以稍微增加敏感度
        if acc["estimated_accuracy"] > 0.85 and acc["confidence"] == "high":
            recs.append("准确率较高，可以微调提升敏感度")
            snap.weights.distortion_weight = min(1.5, self.weights.distortion_weight + 0.05)

        snap.recommendation = " | ".join(recs) if recs else "当前校准稳定，无需调整"
        snap.weights = self.weights  # reflect current state (which may have been modified above)

        # 更新内部状态
        self._calibration_count = len(self._scores)
        self._last_calibration = datetime.now(timezone.utc)

        logger.info(f"校准完成 (n={len(self._scores)}): {snap.recommendation}")
        return snap

    def calibrate_score(self, raw_score: float) -> float:
        """应用校准调整评分"""
        # 基于历史分布的Z-score偏移校正
        dist = self._compute_distribution()
        if len(self._scores) < 50 or dist["std"] < 5:
            return raw_score

        # 将评分标准化到以50为中心的分布
        z = (raw_score - dist["mean"]) / max(1, dist["std"])
        calibrated = 50 + z * 15  # 映射到均值50, 标准差15的分布

        return max(0.0, min(100.0, calibrated))

    def snapshot(self) -> CalibrationSnapshot:
        dist = self._compute_distribution()
        acc = self._compute_accuracy()
        return CalibrationSnapshot(
            total_events=len(self._scores),
            avg_score=dist["mean"],
            score_std=dist["std"],
            feedback_accuracy=acc["estimated_accuracy"],
            disputed_rate=len(self._disputed) / max(1, len(self._scores)),
            weights=self.weights,
            recommendation="",
        )


_calibrator = ScoreCalibrator()


def get_calibrator() -> ScoreCalibrator:
    return _calibrator
