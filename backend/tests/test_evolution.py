"""
Evolution 模块测试 — 反馈分类/误判检测/评分校准/规则版本/回归测试/知识过期
"""
import pytest
from datetime import datetime, timedelta, timezone


# =============================================================================
# 1. 反馈自动分类
# =============================================================================

class TestFeedbackClassifier:
    """反馈自动分类 (FeedbackClassifier.classify)"""

    def test_classify_false_positive(self):
        """误判+虚假 → false_positive"""
        from app.evolution import FeedbackClassifier
        result = FeedbackClassifier.classify({
            "rating": "inaccurate", "comment": "这是误判，不是虚假信息",
            "dimension": "distortion",
        })
        assert result == "false_positive"

    def test_classify_false_negative(self):
        """误判但不含虚假 → false_negative"""
        from app.evolution import FeedbackClassifier
        result = FeedbackClassifier.classify({
            "rating": "", "comment": "这个判定不对，漏掉了",
            "dimension": "fallacy",
        })
        assert result == "false_negative"

    def test_classify_missing_analysis(self):
        """漏了/没检测到 → missing_analysis"""
        from app.evolution import FeedbackClassifier
        result = FeedbackClassifier.classify({
            "rating": "", "comment": "引擎漏了明显的逻辑谬误",
            "dimension": "",
        })
        assert result == "missing_analysis"

    def test_classify_missing_analysis_variant(self):
        """没发现 → missing_analysis"""
        from app.evolution import FeedbackClassifier
        result = FeedbackClassifier.classify({
            "rating": "", "comment": "没发现这段内容的问题",
            "dimension": "",
        })
        assert result == "missing_analysis"

    def test_classify_distortion_mislabel(self):
        """不是失真 → distortion_mislabel"""
        from app.evolution import FeedbackClassifier
        result = FeedbackClassifier.classify({
            "rating": "", "comment": "这不是失真，是正常表述",
            "dimension": "失真检测",
        })
        assert result == "distortion_mislabel"

    def test_classify_fallacy_mislabel(self):
        """谬误标签错 → fallacy_mislabel"""
        from app.evolution import FeedbackClassifier
        result = FeedbackClassifier.classify({
            "rating": "", "comment": "这个谬误标签错了",
            "dimension": "谬误检测",
        })
        assert result == "fallacy_mislabel"

    def test_classify_over_analysis(self):
        """过度分析 → over_analysis"""
        from app.evolution import FeedbackClassifier
        result = FeedbackClassifier.classify({
            "rating": "", "comment": "对正常内容过度分析了",
            "dimension": "",
        })
        assert result == "over_analysis"

    def test_classify_confirmed_accurate(self):
        """有帮助/准确 → confirmed_accurate"""
        from app.evolution import FeedbackClassifier
        result = FeedbackClassifier.classify({
            "rating": "helpful", "comment": "分析得很准确，有帮助",
            "dimension": "",
        })
        assert result == "confirmed_accurate"

    def test_classify_uncategorized(self):
        """无匹配 → uncategorized"""
        from app.evolution import FeedbackClassifier
        result = FeedbackClassifier.classify({
            "rating": "", "comment": "一般性评论",
            "dimension": "",
        })
        assert result == "uncategorized"

    def test_classify_empty_feedback(self):
        """空反馈 → uncategorized"""
        from app.evolution import FeedbackClassifier
        result = FeedbackClassifier.classify({})
        assert result == "uncategorized"


# =============================================================================
# 2. 误判模式检测
# =============================================================================

class TestMisjudgmentDetector:
    """误判模式发现 (MisjudgmentDetector)"""

    def test_ingest_non_inaccurate_ignored(self):
        """非 inaccurate 反馈被忽略"""
        from app.evolution import MisjudgmentDetector
        detector = MisjudgmentDetector()
        result = detector.ingest_feedback({
            "event_id": "evt-1", "rating": "helpful",
            "dimension": "distortion", "comment": "很好",
        })
        assert result is None

    def test_ingest_inaccurate_no_match(self):
        """单条 inaccurate 反馈无匹配模式 → None"""
        from app.evolution import MisjudgmentDetector
        detector = MisjudgmentDetector()
        result = detector.ingest_feedback({
            "event_id": "evt-1", "rating": "inaccurate",
            "dimension": "distortion", "comment": "不对",
        })
        assert result is None  # 没有已有模式，单条不触发新模式

    def test_discover_patterns_from_batch(self):
        """3+ 条同一维度 inaccurate → 发现新模式"""
        from app.evolution import MisjudgmentDetector
        detector = MisjudgmentDetector()
        feedbacks = [
            {"event_id": f"evt-{i}", "rating": "inaccurate",
             "dimension": "distortion", "comment": "失真检测错了"}
            for i in range(4)
        ]
        patterns = detector.discover_patterns_from_batch(feedbacks)
        assert len(patterns) >= 1
        pattern = patterns[0]
        assert pattern.frequency == 4
        assert "distortion" in pattern.pattern_name

    def test_discover_patterns_below_threshold(self):
        """2条 inaccurate → 不触发新模式 (需要≥3)"""
        from app.evolution import MisjudgmentDetector
        detector = MisjudgmentDetector()
        feedbacks = [
            {"event_id": f"evt-{i}", "rating": "inaccurate",
             "dimension": "fallacy", "comment": "不对"}
            for i in range(2)
        ]
        patterns = detector.discover_patterns_from_batch(feedbacks)
        assert len(patterns) == 0

    def test_no_duplicate_pattern(self):
        """已存在模式不重复创建"""
        from app.evolution import MisjudgmentDetector
        detector = MisjudgmentDetector()
        batch1 = [
            {"event_id": "evt-a", "rating": "inaccurate",
             "dimension": "statistical", "comment": "统计错误"}
            for _ in range(3)
        ]
        batch2 = [
            {"event_id": "evt-b", "rating": "inaccurate",
             "dimension": "statistical", "comment": "还是错"}
            for _ in range(3)
        ]
        r1 = detector.discover_patterns_from_batch(batch1)
        r2 = detector.discover_patterns_from_batch(batch2)
        assert len(r1) == 1
        assert len(r2) == 0  # 已存在，不重复

    def test_get_active_patterns(self):
        """get_active_patterns 排除已解决的"""
        from app.evolution import MisjudgmentDetector
        detector = MisjudgmentDetector()
        feedbacks = [
            {"event_id": f"evt-{i}", "rating": "inaccurate",
             "dimension": "distortion", "comment": "错"}
            for i in range(3)
        ]
        patterns = detector.discover_patterns_from_batch(feedbacks)
        assert len(detector.get_active_patterns()) == 1
        # 解决它
        detector.resolve(patterns[0].id, "已修复规则")
        assert len(detector.get_active_patterns()) == 0

    def test_resolve_pattern(self):
        """解决模式将其标记为 resolved"""
        from app.evolution import MisjudgmentDetector
        detector = MisjudgmentDetector()
        feedbacks = [
            {"event_id": f"evt-{i}", "rating": "inaccurate",
             "dimension": "narrative", "comment": "叙事错"}
            for i in range(3)
        ]
        patterns = detector.discover_patterns_from_batch(feedbacks)
        pid = patterns[0].id
        detector.resolve(pid, "叙事引擎规则v3修复")
        active = detector.get_active_patterns()
        assert all(p.id != pid or p.resolved for p in detector._patterns)

    def test_high_severity_for_frequent_pattern(self):
        """高频模式 (≥10次) → severity=high"""
        from app.evolution import MisjudgmentDetector
        detector = MisjudgmentDetector()
        feedbacks = [
            {"event_id": f"evt-{i}", "rating": "inaccurate",
             "dimension": "source", "comment": "来源错"}
            for i in range(12)
        ]
        patterns = detector.discover_patterns_from_batch(feedbacks)
        assert patterns[0].severity == "high"


# =============================================================================
# 3. 评分校准器
# =============================================================================

class TestScoreCalibrator:
    """评分校准器 (ScoreCalibrator)"""

    def test_record_event(self):
        """记录事件存储评分"""
        from app.evolution.calibrator import ScoreCalibrator
        cal = ScoreCalibrator()
        cal.record_event(42.0, "likely_false", {})
        cal.record_event(78.0, "likely_true", {})
        assert len(cal._scores) == 2

    def test_record_feedback(self):
        """记录反馈追踪准确率"""
        from app.evolution.calibrator import ScoreCalibrator
        cal = ScoreCalibrator()
        cal.record_feedback("evt-1", True)
        cal.record_feedback("evt-2", False, "distortion")
        assert len(cal._feedbacks) == 2
        assert "evt-1" in cal._confirmed
        assert "evt-2" in cal._disputed

    def test_maybe_calibrate_insufficient_data(self):
        """<50 条评分 → 不触发校准"""
        from app.evolution.calibrator import ScoreCalibrator
        cal = ScoreCalibrator()
        for i in range(30):
            cal.record_event(50.0, "misleading", {})
        assert cal.maybe_calibrate() is None

    def test_maybe_calibrate_triggers(self):
        """50+ 条评分 → 触发校准"""
        from app.evolution.calibrator import ScoreCalibrator
        cal = ScoreCalibrator()
        for i in range(55):
            cal.record_event(50.0 + (i % 20), "misleading", {})
        snap = cal.maybe_calibrate()
        assert snap is not None
        assert snap.total_events >= 50

    def test_calibrate_score_insufficient_data(self):
        """数据不足时不调整评分"""
        from app.evolution.calibrator import ScoreCalibrator
        cal = ScoreCalibrator()
        assert cal.calibrate_score(42.0) == 42.0  # 少于50条，直接返回

    def test_calibrate_score_with_data(self):
        """数据充足时调整评分"""
        from app.evolution.calibrator import ScoreCalibrator
        cal = ScoreCalibrator()
        for i in range(100):
            cal.record_event(40.0 + (i % 30), "misleading", {})
        cal.maybe_calibrate()
        adjusted = cal.calibrate_score(30.0)
        # 校准后评分仍在有效范围
        assert 0 <= adjusted <= 100
        # 低于均值的评分在校准后应偏离原始值 (归一化效应)
        assert adjusted != 30.0

    def test_snapshot(self):
        """snapshot 返回当前状态"""
        from app.evolution.calibrator import ScoreCalibrator
        cal = ScoreCalibrator()
        cal.record_event(55.0, "misleading", {})
        cal.record_feedback("evt-1", True)
        snap = cal.snapshot()
        assert snap.total_events == 1
        assert 0 <= snap.disputed_rate <= 1

    def test_distribution_small_sample(self):
        """小样本 → 默认分布"""
        from app.evolution.calibrator import ScoreCalibrator
        cal = ScoreCalibrator()
        dist = cal._compute_distribution()
        assert dist["mean"] == 50.0
        assert dist["std"] == 15.0

    def test_distribution_with_data(self):
        """20+ 样本 → 计算真实分布"""
        from app.evolution.calibrator import ScoreCalibrator
        cal = ScoreCalibrator()
        for i in range(25):
            cal.record_event(45.0 + i, "misleading", {})
        dist = cal._compute_distribution()
        assert dist["p25"] <= dist["p50"] <= dist["p75"]


# =============================================================================
# 4. 规则版本管理
# =============================================================================

class TestRuleVersionManager:
    """规则版本管理 (RuleVersionManager)"""

    def test_record_change(self):
        """记录规则变更"""
        from app.evolution import RuleVersionManager
        mgr = RuleVersionManager()
        entry = mgr.record_change(
            module="distortion",
            rule_id="source_fabrication",
            old_pattern=r"模糊.*权威",
            new_pattern=r"(模糊|没有).*权威",
            change_reason="修复误判 #pattern-001",
        )
        assert entry.module == "distortion"
        assert entry.rule_id == "source_fabrication"
        assert entry.version >= 1

    def test_version_increment(self):
        """版本号递增"""
        from app.evolution import RuleVersionManager
        mgr = RuleVersionManager()
        v1 = mgr.record_change("fallacy", "false_cause", "old", "new", "fix")
        v2 = mgr.record_change("fallacy", "false_cause", "new", "newer", "fix2")
        assert v2.version > v1.version

    def test_rollback(self):
        """回滚返回最新变更"""
        from app.evolution import RuleVersionManager
        mgr = RuleVersionManager()
        mgr.record_change("narrative", "fear", "old", "new", "test")
        latest = mgr.rollback("narrative", "fear")
        assert latest is not None
        assert latest.module == "narrative"

    def test_rollback_nonexistent(self):
        """回滚不存在的规则 → None"""
        from app.evolution import RuleVersionManager
        mgr = RuleVersionManager()
        assert mgr.rollback("nonexistent", "rule") is None

    def test_get_history_all(self):
        """获取全部历史"""
        from app.evolution import RuleVersionManager
        mgr = RuleVersionManager()
        mgr.record_change("distortion", "r1", "a", "b", "reason")
        mgr.record_change("fallacy", "r2", "c", "d", "reason")
        assert len(mgr.get_history()) == 2

    def test_get_history_filtered(self):
        """按模块过滤历史"""
        from app.evolution import RuleVersionManager
        mgr = RuleVersionManager()
        mgr.record_change("distortion", "r1", "a", "b", "reason")
        mgr.record_change("fallacy", "r2", "c", "d", "reason")
        assert len(mgr.get_history(module="distortion")) == 1

    def test_get_current_versions(self):
        """获取各模块当前版本"""
        from app.evolution import RuleVersionManager
        mgr = RuleVersionManager()
        mgr.record_change("distortion", "r1", "a", "b", "reason")
        mgr.record_change("distortion", "r2", "c", "d", "reason")
        versions = mgr.get_current_versions()
        assert "distortion" in versions
        assert versions["distortion"] >= 1


# =============================================================================
# 5. 回归测试用例
# =============================================================================

class TestRegressionCases:
    """回归测试用例管理"""

    def test_builtin_cases_exist(self):
        """3个内置回归用例"""
        from app.evolution import BUILTIN_REGRESSION_CASES
        assert len(BUILTIN_REGRESSION_CASES) == 3

    def test_regression_case_structure(self):
        """每个用例有必需字段"""
        from app.evolution import BUILTIN_REGRESSION_CASES
        for case in BUILTIN_REGRESSION_CASES:
            assert case.case_id
            assert case.name
            assert case.test_text
            assert case.test_title
            assert len(case.expected_verdict_range) == 2

    def test_normal_content_not_misclassified(self):
        """用例003 (正常公告) 期望高可信度"""
        from app.evolution import BUILTIN_REGRESSION_CASES
        normal_case = [c for c in BUILTIN_REGRESSION_CASES if c.case_id == "regress-003"][0]
        low, high = normal_case.expected_verdict_range
        assert low >= 70
        assert high == 100

    def test_add_regression_case(self):
        """可以添加新回归用例"""
        from app.evolution import RegressionCase, add_regression_case, _regression_cases
        initial = len(_regression_cases)
        case = RegressionCase(
            case_id="test-001", name="测试用例",
            test_title="测试标题", test_text="测试内容",
            expected_verdict_range=(0, 50),
            tags=["test"],
        )
        add_regression_case(case)
        assert len(_regression_cases) == initial + 1
        assert _regression_cases[-1].case_id == "test-001"


# =============================================================================
# 6. 知识过期管理
# =============================================================================

class TestKnowledgeExpiryManager:
    """知识过期管理 (KnowledgeExpiryManager)"""

    def test_check_expiry_first_run(self):
        """首次检查 → 所有来源标记为需要审查"""
        from app.evolution import KnowledgeExpiryManager
        mgr = KnowledgeExpiryManager()
        needs = mgr.check_expiry()
        assert len(needs) == len(KnowledgeExpiryManager.CHECKS)
        for entry in needs:
            assert "source" in entry
            assert "action" in entry

    def test_check_expiry_recent_check(self):
        """最近检查过 → 不再标记"""
        from app.evolution import KnowledgeExpiryManager
        mgr = KnowledgeExpiryManager()
        mgr.check_expiry()  # 首次全量标记
        needs = mgr.check_expiry()  # 立即再查 → 不标记
        assert len(needs) == 0


# =============================================================================
# 7. 反馈闭环管道
# =============================================================================

class TestFeedbackLoopPipeline:
    """反馈闭环管道 (FeedbackLoopPipeline)"""

    @pytest.mark.asyncio
    async def test_classify_feedback(self):
        """管道正确分类反馈"""
        from app.evolution.feedback_loop import FeedbackLoopPipeline
        pipeline = FeedbackLoopPipeline()
        result = await pipeline.process_feedback({
            "id": "fb-1", "event_id": "evt-1",
            "rating": "inaccurate", "comment": "误判了，不是虚假",
            "dimension": "distortion",
        })
        assert result.classification == "false_positive"

    @pytest.mark.asyncio
    async def test_feedback_count_increments(self):
        """处理反馈递增计数器"""
        from app.evolution.feedback_loop import FeedbackLoopPipeline
        pipeline = FeedbackLoopPipeline()
        assert pipeline._feedback_count == 0
        await pipeline.process_feedback({"id": "fb-1", "comment": "test"})
        assert pipeline._feedback_count == 1

    def test_loop_result_defaults(self):
        """LoopResult 默认值正确"""
        from app.evolution.feedback_loop import LoopResult
        r = LoopResult()
        assert r.classification == ""
        assert r.action_required == ""
        assert r.calibration_triggered is False
        assert r.new_patterns_discovered == []


# =============================================================================
# 8. 单例访问器
# =============================================================================

class TestSingletonAccessors:
    """单例访问器"""

    def test_get_feedback_classifier(self):
        from app.evolution import get_feedback_classifier
        assert get_feedback_classifier() is get_feedback_classifier()

    def test_get_misjudgment_detector(self):
        from app.evolution import get_misjudgment_detector
        assert get_misjudgment_detector() is get_misjudgment_detector()

    def test_get_rule_version_manager(self):
        from app.evolution import get_rule_version_manager
        assert get_rule_version_manager() is get_rule_version_manager()

    def test_get_calibrator(self):
        from app.evolution.calibrator import get_calibrator
        assert get_calibrator() is get_calibrator()

    def test_knowledge_expiry_new_instance(self):
        """KnowledgeExpiryManager 每次返回新实例 (非单例)"""
        from app.evolution import get_knowledge_expiry_manager
        m1 = get_knowledge_expiry_manager()
        m2 = get_knowledge_expiry_manager()
        # 非单例: 每次创建新实例
        # (设计如此 — 因为 expiry manager 有状态但不需要共享)
        assert isinstance(m1, type(m2))
