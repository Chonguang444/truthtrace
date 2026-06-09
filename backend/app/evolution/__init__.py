"""
自我进化引擎 — 从反馈中学习，防止随时间变烂

机制:
1. 反馈自动归类 — 将用户反馈归类为可处理的模式
2. 误判模式发现 — 从多个反馈中发现系统性误判
3. 规则版本管理 — 所有引擎规则变更可追溯可回滚
4. 回归测试 — 修复一个新问题后，验证旧问题没有复现
5. 知识库更新管道 — 权威来源变更时自动标记过期知识
6. 管理员审核 — 高风险变更需要手动确认

核心原则:
- 不自动修改判定规则 — 所有规则变更需要人工审核
- 反馈驱动改进 — 用户说"这是误判"比用户什么都不说要好
- 版本化管理 — 每条规则变更都有记录，可回滚
"""

from __future__ import annotations
import json
import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("truthtrace.evolution")


# =============================================================================
# 1. 反馈自动归类
# =============================================================================

class FeedbackClassifier:
    """
    将用户反馈自动归类为可处理的模式。

    分类:
    - false_positive: 引擎判定为虚假，但用户认为是真实
    - false_negative: 引擎判定为真实，但用户认为是虚假
    - distortion_mislabel: 失真检测标签错误
    - fallacy_mislabel: 逻辑谬误标签错误
    - missing_analysis: 引擎未能检测到明显的问题
    - over_analysis: 引擎对正常内容过度分析
    """

    @staticmethod
    def classify(feedback: dict) -> str:
        """分类一条用户反馈"""
        rating = feedback.get("rating", "")
        comment = feedback.get("comment", "")
        dimension = feedback.get("dimension", "")

        combined = f"{rating} {comment} {dimension}".lower()

        # 规则匹配
        if "误判" in combined or "不对" in combined or "不应该" in combined:
            if "虚假" in combined or "谣言" in combined:
                return "false_positive"
            return "false_negative"

        if "漏了" in combined or "没检测到" in combined or "没发现" in combined:
            return "missing_analysis"

        if "不是失真" in combined or "这不是" in combined or "标签错" in combined:
            if "失真" in combined:
                return "distortion_mislabel"
            if "谬误" in combined:
                return "fallacy_mislabel"
            return "distortion_mislabel"

        if "过度" in combined or "太严格" in combined or "正常内容" in combined:
            return "over_analysis"

        if "有帮助" in combined or "分析得好" in combined or "准确" in combined:
            return "confirmed_accurate"

        if rating == "inaccurate":
            return "false_negative"

        return "uncategorized"


# =============================================================================
# 2. 误判模式发现
# =============================================================================

@dataclass
class MisjudgmentPattern:
    """一个被发现的系统性误判模式"""
    id: str = ""
    pattern_name: str = ""
    description: str = ""
    affected_rules: list[str] = field(default_factory=list)
    example_event_ids: list[str] = field(default_factory=list)
    frequency: int = 0           # 出现次数
    severity: str = "medium"     # low / medium / high / critical
    discovered_at: Optional[datetime] = None
    resolved: bool = False
    resolution: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "pattern_name": self.pattern_name,
            "description": self.description, "frequency": self.frequency,
            "severity": self.severity, "resolved": self.resolved,
        }


class MisjudgmentDetector:
    """从反馈中自动发现系统性误判模式"""

    def __init__(self):
        self._patterns: list[MisjudgmentPattern] = []
        self._pattern_threshold = 3  # 同一模式出现3次触发告警

    def ingest_feedback(self, feedback: dict) -> Optional[MisjudgmentPattern]:
        """
        处理一条反馈，检查是否与已知模式匹配。

        如果同一维度被多次反馈为"不准确"，
        则可能是一个系统性误判模式。
        """
        event_id = feedback.get("event_id", "")
        dimension = feedback.get("dimension", "")
        rating = feedback.get("rating", "")
        comment = feedback.get("comment", "")

        if rating != "inaccurate":
            return None

        # 查找匹配的已知模式
        for pattern in self._patterns:
            if (dimension and any(r in pattern.affected_rules for r in [dimension])
                and not pattern.resolved):
                pattern.frequency += 1
                pattern.example_event_ids.append(event_id)
                logger.info(f"已知误判模式 '{pattern.pattern_name}' 又出现 (累计{pattern.frequency}次)")
                return pattern

        # 新模式的候选 — 需要积累到阈值
        # 简化: 检查同一维度的 inaccurate 反馈是否达到阈值
        # (完整实现需要聚类分析，这里做简化版)
        return None

    def discover_patterns_from_batch(self, feedbacks: list[dict]) -> list[MisjudgmentPattern]:
        """从一批反馈中发现新模式"""
        from collections import defaultdict

        # 按维度分组
        by_dimension: dict[str, list[dict]] = defaultdict(list)
        for f in feedbacks:
            if f.get("rating") == "inaccurate":
                dim = f.get("dimension", "general")
                by_dimension[dim].append(f)

        new_patterns = []
        for dim, items in by_dimension.items():
            if len(items) >= self._pattern_threshold:
                # 检查是否已有此模式
                existing = any(
                    p for p in self._patterns
                    if dim in p.affected_rules and not p.resolved
                )
                if not existing:
                    pattern = MisjudgmentPattern(
                        id=f"pattern_{dim}_{datetime.utcnow().strftime('%Y%m%d')}",
                        pattern_name=f"维度 '{dim}' 的系统性误判",
                        description=f"在 {len(items)} 个事件中，维度 '{dim}' 被用户反馈为不准确。",
                        affected_rules=[dim],
                        example_event_ids=[f.get("event_id", "") for f in items[:5]],
                        frequency=len(items),
                        severity="high" if len(items) >= 10 else "medium",
                        discovered_at=datetime.utcnow(),
                    )
                    self._patterns.append(pattern)
                    new_patterns.append(pattern)
                    logger.warning(f"发现新的误判模式: {pattern.pattern_name}")

        return new_patterns

    def get_active_patterns(self) -> list[MisjudgmentPattern]:
        return [p for p in self._patterns if not p.resolved]

    def resolve(self, pattern_id: str, resolution: str):
        for p in self._patterns:
            if p.id == pattern_id:
                p.resolved = True
                p.resolution = resolution


_misjudgment_detector = MisjudgmentDetector()
_feedback_classifier = FeedbackClassifier()


# =============================================================================
# 3. 规则版本管理
# =============================================================================

@dataclass
class RuleVersion:
    """规则的版本记录"""
    module: str            # distortion / fallacy / narrative / statistical
    rule_id: str           # 规则标识符
    old_pattern: str       # 变更前的正则/规则
    new_pattern: str       # 变更后的正则/规则
    change_reason: str     # 变更原因 (引用反馈/误判模式ID)
    changed_by: str        # 谁做的变更
    version: int           # 递增版本号
    created_at: datetime = field(default_factory=datetime.utcnow)


class RuleVersionManager:
    """
    规则版本管理。

    每次规则变更都需要记录:
    - 变更了什么
    - 为什么变更 (关联到具体的误判模式或反馈)
    - 谁做的变更
    - 可以回滚到上一个版本
    """

    def __init__(self):
        self._history: list[RuleVersion] = []       # 变更历史
        self._module_versions: dict[str, int] = {}  # 各模块当前版本号
        self._rollbacks: list[RuleVersion] = []     # 回滚记录

    def record_change(self, module: str, rule_id: str,
                      old_pattern: str, new_pattern: str,
                      change_reason: str, changed_by: str = "system") -> RuleVersion:
        """记录一次规则变更"""
        current_version = self._module_versions.get(module, 1)
        self._module_versions[module] = current_version + 1

        entry = RuleVersion(
            module=module,
            rule_id=rule_id,
            old_pattern=old_pattern,
            new_pattern=new_pattern,
            change_reason=change_reason,
            changed_by=changed_by,
            version=current_version + 1,
        )
        self._history.append(entry)
        logger.info(f"规则变更: {module}.{rule_id} v{current_version} → v{current_version+1} ({change_reason})")
        return entry

    def rollback(self, module: str, rule_id: str) -> RuleVersion | None:
        """回滚到上一个版本"""
        relevant = [
            v for v in self._history
            if v.module == module and v.rule_id == rule_id and v not in self._rollbacks
        ]
        if not relevant:
            return None

        latest = relevant[-1]  # 最新的变更
        self._rollbacks.append(latest)
        logger.warning(f"规则回滚: {module}.{rule_id} → v{latest.version - 1}")
        return latest

    def get_history(self, module: str | None = None) -> list[RuleVersion]:
        """获取变更历史"""
        if module:
            return [v for v in self._history if v.module == module]
        return self._history

    def get_current_versions(self) -> dict:
        return dict(self._module_versions)


_rule_version_manager = RuleVersionManager()


# =============================================================================
# 4. 回归测试用例管理
# =============================================================================

@dataclass
class RegressionCase:
    """
    一个回归测试用例。

    每个已知的谣言类型/误判模式都有一条用例。
    修改引擎规则后，必须通过所有回归测试。
    """
    case_id: str = ""
    name: str = ""
    test_text: str = ""
    test_title: str = ""
    expected_verdict_range: tuple[float, float] = (0, 50)  # 期望的可信度评分范围
    expected_patterns: list[str] = field(default_factory=list)  # 期望命中的模式
    must_not_match: list[str] = field(default_factory=list)     # 绝对不能命中的模式
    real_world_source: str = ""  # 这个测试案例来自哪个真实事件
    tags: list[str] = field(default_factory=list)


# 内置回归测试用例 (基于已知的谣言模式)
BUILTIN_REGRESSION_CASES: list[RegressionCase] = [
    RegressionCase(
        case_id="regress-001",
        name="阿斯巴甜致癌恐慌",
        test_title="紧急！你每天都在吃的这个东西竟然致癌！速看！",
        test_text="阿斯巴甜是剧毒物质，国外早就禁了。研究表明它100%致癌。你还在喝无糖饮料吗？转发给你关心的人！",
        expected_verdict_range=(0, 30),
        expected_patterns=["source_fabrication", "emotional_manipulation", "context_stripping"],
        must_not_match=["true", "likely_true"],
        real_world_source="阿斯巴甜IARC分类引起的社会恐慌",
        tags=["food_safety", "fear_mongering"],
    ),
    RegressionCase(
        case_id="regress-002",
        name="疫苗自闭症谣言",
        test_title="不要再给孩子打疫苗了！研究证实疫苗导致自闭症！",
        test_text="一位医生透露，他接诊的自闭症患儿都打过疫苗。疫苗就是罪魁祸首！家长们都应该拒绝接种！",
        expected_verdict_range=(0, 25),
        expected_patterns=["source_fabrication", "false_cause", "appeal_to_emotion"],
        must_not_match=["true", "likely_true"],
        real_world_source="Wakefield (1998) 已被撤回的论文及其后续影响",
        tags=["medicine_health", "fear_mongering"],
    ),
    RegressionCase(
        case_id="regress-003",
        name="正常政府公告 (不应误判)",
        test_title="2024年第四季度食品安全监督抽检结果公告",
        test_text="根据食品安全法及其实施条例，国家市场监督管理总局组织开展了2024年第四季度食品安全监督抽检。共抽检样品15000批次，合格率98.5%。抽检结果已在总局官网公示。",
        expected_verdict_range=(70, 100),
        expected_patterns=[],
        must_not_match=["false", "likely_false", "misleading"],
        real_world_source="官方公告不应被误判为虚假",
        tags=["food_safety", "normal_content"],
    ),
]

_regression_cases: list[RegressionCase] = list(BUILTIN_REGRESSION_CASES)


async def run_regression_tests() -> dict:
    """
    运行所有回归测试。

    返回: {"passed": N, "failed": N, "failures": [...]}
    """
    from app.engine.reasoning import run_reasoning_pipeline

    results = {"passed": 0, "failed": 0, "failures": [], "ran_at": datetime.utcnow().isoformat()}

    for case in _regression_cases:
        try:
            r = await run_reasoning_pipeline(
                url=f"regression://{case.case_id}",
                title=case.test_title,
                text=case.test_text,
            )
            score = r.credibility_score

            # 检查是否在期望范围内
            low, high = case.expected_verdict_range
            if low <= score <= high:
                results["passed"] += 1
            else:
                results["failed"] += 1
                results["failures"].append({
                    "case_id": case.case_id,
                    "name": case.name,
                    "expected_range": f"{low}-{high}",
                    "actual_score": score,
                    "verdict": r.verdict.value,
                })

        except Exception as e:
            results["failed"] += 1
            results["failures"].append({
                "case_id": case.case_id,
                "name": case.name,
                "error": str(e),
            })

    logger.info(f"回归测试: {results['passed']}/{results['passed']+results['failed']} 通过")
    return results


def add_regression_case(case: RegressionCase):
    """添加新的回归测试用例 (基于已确认的误判)"""
    _regression_cases.append(case)
    logger.info(f"新增回归用例: {case.case_id} - {case.name}")


# =============================================================================
# 5. 知识库过期检测
# =============================================================================

class KnowledgeExpiryManager:
    """
    追踪知识库条目的时效性。

    当权威来源更新时（如GB2760修订、WHO发布新报告），
    自动标记相关知识条目为"需要审查"。
    """

    # 已知的权威来源更新检查
    CHECKS = [
        {"source": "GB 2760", "url": "https://std.samr.gov.cn/gb/", "check_interval_days": 180},
        {"source": "WHO Essential Medicines", "url": "https://www.who.int/publications/i/item/WHO-MHP-HPS-EML-2023", "check_interval_days": 365},
        {"source": "IPCC Reports", "url": "https://www.ipcc.ch/reports/", "check_interval_days": 365},
        {"source": "IARC Monographs", "url": "https://monographs.iarc.who.int/", "check_interval_days": 180},
    ]

    def __init__(self):
        self._last_checked: dict[str, datetime] = {}  # source → last check time
        self._expired_entries: list[dict] = []

    def check_expiry(self) -> list[dict]:
        """检查哪些知识可能需要更新"""
        now = datetime.utcnow()
        needs_review = []

        for check in self.CHECKS:
            last = self._last_checked.get(check["source"])
            if last is None or (now - last).days > check["check_interval_days"]:
                needs_review.append({
                    "source": check["source"],
                    "url": check["url"],
                    "last_checked": last.isoformat() if last else "从未检查",
                    "days_since_check": (now - last).days if last else "N/A",
                    "action": "请手动检查最新版本",
                })
                self._last_checked[check["source"]] = now

        self._expired_entries = needs_review
        return needs_review


# =============================================================================
# 导出公共接口
# =============================================================================

def get_misjudgment_detector() -> MisjudgmentDetector:
    return _misjudgment_detector


def get_feedback_classifier() -> FeedbackClassifier:
    return _feedback_classifier


def get_rule_version_manager() -> RuleVersionManager:
    return _rule_version_manager


def get_knowledge_expiry_manager() -> KnowledgeExpiryManager:
    return KnowledgeExpiryManager()
