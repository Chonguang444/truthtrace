"""
TruthTrace 推理引擎 — 共享数据类型

所有引擎模块的输入/输出均使用这里定义的类型，
确保模块间数据一致性和可追溯性。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


# =============================================================================
# 证据与来源
# =============================================================================

class EvidenceType(str, Enum):
    """证据类型"""
    PRIMARY_SOURCE = "primary_source"        # 一手来源 (官方文件、论文原文)
    SECONDARY_SOURCE = "secondary_source"    # 二手来源 (媒体报道、引用)
    EXPERT_CONSENSUS = "expert_consensus"    # 专家共识
    OFFICIAL_DATA = "official_data"          # 官方数据 (统计局、WHO等)
    WITNESS_ACCOUNT = "witness_account"      # 目击者证词
    CIRCUMSTANTIAL = "circumstantial"        # 旁证


class EvidenceQuality(str, Enum):
    """证据质量等级"""
    HIGH = "high"           # 直接的一手来源，可交叉验证
    MEDIUM = "medium"       # 可靠的二手来源或单一一手来源
    LOW = "low"             # 可疑的来源或无法验证的信息
    UNVERIFIABLE = "unverifiable"  # 无法验证


@dataclass
class Evidence:
    """单条证据"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    source_url: str = ""
    source_type: EvidenceType = EvidenceType.PRIMARY_SOURCE
    quality: EvidenceQuality = EvidenceQuality.MEDIUM
    quote: str = ""        # 原文引用
    retrieved_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "source_url": self.source_url,
            "source_type": self.source_type.value,
            "quality": self.quality.value,
            "quote": self.quote,
            "retrieved_at": self.retrieved_at.isoformat() if self.retrieved_at else None,
        }


# =============================================================================
# 推理步骤 — 每步都可追溯
# =============================================================================

class Confidence(str, Enum):
    """置信度"""
    CERTAIN = "certain"        # >95% — 多个高质量来源一致确认
    HIGH = "high"              # 80-95% — 有强证据支持
    MODERATE = "moderate"      # 50-80% — 有一定证据但不够充分
    LOW = "low"                # 20-50% — 仅有线索，无法确认
    UNCERTAIN = "uncertain"    # <20% — 缺乏证据，无法判断


@dataclass
class ReasoningStep:
    """单步推理记录 — 完整推理链的最小单元"""
    step_id: int = 0
    description: str = ""                # 这一步骤做了什么判断
    conclusion: str = ""                 # 得出的中间结论
    confidence: Confidence = Confidence.MODERATE
    evidence: list[Evidence] = field(default_factory=list)  # 支撑证据
    counter_evidence: list[Evidence] = field(default_factory=list)  # 反面证据
    uncertainty_note: str = ""           # 明确标注不确定性来源

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "conclusion": self.conclusion,
            "confidence": self.confidence.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "counter_evidence": [e.to_dict() for e in self.counter_evidence],
            "uncertainty_note": self.uncertainty_note,
        }


# =============================================================================
# 7 种失真模式
# =============================================================================

class DistortionType(str, Enum):
    """信息失真的 7 种基本模式"""
    SOURCE_FABRICATION = "source_fabrication"     # 源头伪造: 无中生有
    CONTENT_TAMPERING = "content_tampering"       # 内容篡改: 剪辑/拼接/PS
    MISQUOTATION = "misquotation"                 # 错误引用: 引用的来源不支撑结论
    CONTEXT_STRIPPING = "context_stripping"       # 忽略语境: 去限定条件/前提
    EMOTIONAL_MANIPULATION = "emotional_manipulation"  # 情感操纵: 利用恐惧/愤怒
    AUTHORITY_ABUSE = "authority_abuse"           # 权威绑架: 虚假权威背书
    DECONTEXTUALIZATION = "decontextualization"   # 语境剥离: 脱离时间/空间/文化语境


# =============================================================================
# 逻辑谬误类型
# =============================================================================

class FallacyType(str, Enum):
    """12 种常见逻辑谬误"""
    FALSE_CAUSE = "false_cause"                    # 因果倒置/虚假因果
    SLIPPERY_SLOPE = "slippery_slope"             # 滑坡论证
    FALSE_DICHOTOMY = "false_dichotomy"            # 虚假二分/非黑即白
    EQUIVOCATION = "equivocation"                  # 偷换概念/概念漂移
    APPEAL_TO_EMOTION = "appeal_to_emotion"        # 诉诸情感
    APPEAL_TO_AUTHORITY = "appeal_to_authority"    # 诉诸虚假权威
    HASTY_GENERALIZATION = "hasty_generalization"  # 以偏概全/仓促归纳
    STRAW_MAN = "straw_man"                        # 稻草人谬误 (歪曲对方观点)
    RED_HERRING = "red_herring"                    # 转移话题
    BEGGING_THE_QUESTION = "begging_the_question"  # 循环论证
    FALSE_ANALOGY = "false_analogy"                # 错误类比
    CHERRY_PICKING = "cherry_picking"              # 选择性证据/樱桃采摘


# =============================================================================
# 叙事框架类型
# =============================================================================

class NarrativeType(str, Enum):
    """常见操纵性叙事框架"""
    CONSPIRACY_THEORY = "conspiracy_theory"        # 阴谋论: "他们暗中操控一切"
    US_VS_THEM = "us_vs_them"                     # 对立叙事: "我们 vs 他们"
    VICTIMHOOD_NATIONALISM = "victimhood_nationalism"  # 受害者民族主义
    FEAR_MONGERING = "fear_mongering"             # 恐惧营销: 制造恐慌
    GOLDEN_AGE = "golden_age"                     # 辉煌过去叙事: "以前多好，现在多糟"
    SCIENTISM_ABUSE = "scientism_abuse"           # 伪科学包装: 用科学术语包装谬论
    WHATABOUTISM = "whataboutism"                 # "那XX又怎么说" 转移焦点
    DEMONIZATION = "demonization"                 # 妖魔化: 将对手描绘为邪恶
    MORAL_PANIC = "moral_panic"                   # 道德恐慌: 某群体/行为威胁社会
    PURIFICATION = "purification"                 # 净化叙事: "我们需要清除XX"
    TECHNOPHOBIA = "technophobia"                 # 技术恐惧: 新技术威胁论
    FALSE_BALANCE = "false_balance"               # 虚假平衡: 少数意见与共识等权


# =============================================================================
# 领域类型
# =============================================================================

class DomainType(str, Enum):
    """专业知识领域"""
    FOOD_SAFETY = "food_safety"          # 食品安全
    MEDICINE_HEALTH = "medicine_health"  # 医药健康
    ECONOMICS_FINANCE = "economics_finance"  # 经济金融
    LAW_REGULATION = "law_regulation"    # 法律法规
    ENVIRONMENT_CLIMATE = "environment_climate"  # 环境气候
    HISTORY = "history"                  # 历史事件
    TECH = "tech"                        # 科技
    EDUCATION = "education"              # 教育
    GENERAL = "general"                  # 一般/跨领域


# =============================================================================
# 溯源深度
# =============================================================================

class TraceDepth(str, Enum):
    """5 层溯源深度"""
    L1_SURFACE = "L1_surface"          # 表面溯源: 找到最早发帖URL+时间
    L2_CONTENT = "L2_content"          # 内容溯源: 检测篡改/剪辑
    L3_SOURCE = "L3_source"            # 来源溯源: 发布者身份+关联账号
    L4_NARRATIVE = "L4_narrative"      # 叙事溯源: 识别嵌入的叙事框架
    L5_INTEREST = "L5_interest"        # 利益溯源: 传播背后的利益结构


# =============================================================================
# 综合判定结果
# =============================================================================

class Verdict(str, Enum):
    """最终判定"""
    TRUE = "true"                  # 信息属实
    LIKELY_TRUE = "likely_true"   # 可能属实
    MISLEADING = "misleading"     # 误导性信息
    LIKELY_FALSE = "likely_false" # 可能虚假
    FALSE = "false"               # 确认为虚假
    UNVERIFIABLE = "unverifiable" # 无法验证


@dataclass
class AnalysisResult:
    """完整的分析结果 — 推理管线的最终输出"""
    # 基本信息
    analysis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    input_url: str = ""
    input_title: str = ""

    # 综合判定
    verdict: Verdict = Verdict.UNVERIFIABLE
    credibility_score: float = 50.0  # 0-100
    confidence: Confidence = Confidence.MODERATE

    # 各维度分析结果
    distortion_analysis: Optional[DistortionAnalysis] = None
    fallacy_analysis: Optional[FallacyAnalysis] = None
    trace_analysis: Optional[TraceAnalysis] = None
    domain_analysis: Optional[DomainAnalysis] = None
    narrative_analysis: Optional[NarrativeAnalysis] = None
    statistical_analysis: Optional["StatisticalAnalysis"] = None
    composite_analysis: Optional["CompositeAnalysis"] = None
    modality_analysis: Optional["ModalityAnalysis"] = None
    media_verification: Optional[dict] = None
    llm_analysis: Optional[dict] = None

    # 完整推理链
    reasoning_chain: list[ReasoningStep] = field(default_factory=list)

    # 辟谣建议
    correction: str = ""
    correction_references: list[str] = field(default_factory=list)

    # 不确定声明
    uncertainty_statement: str = ""

    analyzed_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "analysis_id": self.analysis_id,
            "input_url": self.input_url,
            "input_title": self.input_title,
            "verdict": self.verdict.value,
            "credibility_score": self.credibility_score,
            "confidence": self.confidence.value,
            "distortion_analysis": self.distortion_analysis.to_dict() if self.distortion_analysis else None,
            "fallacy_analysis": self.fallacy_analysis.to_dict() if self.fallacy_analysis else None,
            "trace_analysis": self.trace_analysis.to_dict() if self.trace_analysis else None,
            "domain_analysis": self.domain_analysis.to_dict() if self.domain_analysis else None,
            "narrative_analysis": self.narrative_analysis.to_dict() if self.narrative_analysis else None,
            "statistical_analysis": self.statistical_analysis.to_dict() if self.statistical_analysis else None,
            "composite_analysis": self.composite_analysis.to_dict() if self.composite_analysis else None,
            "modality_analysis": self.modality_analysis.to_dict() if self.modality_analysis else None,
            "media_verification": self.media_verification,
            "llm_analysis": self.llm_analysis,
            "reasoning_chain": [s.to_dict() for s in self.reasoning_chain],
            "correction": self.correction,
            "correction_references": self.correction_references,
            "uncertainty_statement": self.uncertainty_statement,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
        }


# =============================================================================
# 各分析模块的结果类型 (前向声明)
# =============================================================================

@dataclass
class DistortionMatch:
    """单条失真匹配结果"""
    distortion_type: DistortionType
    description: str
    confidence: Confidence
    evidence_snippet: str = ""  # 触发检测的原文片段
    reasoning: str = ""         # 为什么判定为这种失真

    def to_dict(self) -> dict:
        return {
            "distortion_type": self.distortion_type.value,
            "description": self.description,
            "confidence": self.confidence.value,
            "evidence_snippet": self.evidence_snippet,
            "reasoning": self.reasoning,
        }


@dataclass
class DistortionAnalysis:
    """失真分析结果"""
    matches: list[DistortionMatch] = field(default_factory=list)
    overall_risk: Confidence = Confidence.MODERATE
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "matches": [m.to_dict() for m in self.matches],
            "overall_risk": self.overall_risk.value,
            "summary": self.summary,
        }


@dataclass
class FallacyMatch:
    """单条逻辑谬误匹配"""
    fallacy_type: FallacyType
    description: str
    confidence: Confidence
    evidence_snippet: str = ""
    reasoning: str = ""
    correction_hint: str = ""  # 如何纠正这个谬误

    def to_dict(self) -> dict:
        return {
            "fallacy_type": self.fallacy_type.value,
            "description": self.description,
            "confidence": self.confidence.value,
            "evidence_snippet": self.evidence_snippet,
            "reasoning": self.reasoning,
            "correction_hint": self.correction_hint,
        }


@dataclass
class FallacyAnalysis:
    """逻辑谬误分析结果"""
    matches: list[FallacyMatch] = field(default_factory=list)
    fallacy_count: int = 0
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "matches": [m.to_dict() for m in self.matches],
            "fallacy_count": self.fallacy_count,
            "summary": self.summary,
        }


@dataclass
class TraceAnalysis:
    """溯源分析结果"""
    depth_achieved: TraceDepth = TraceDepth.L1_SURFACE
    earliest_source_url: str = ""
    earliest_timestamp: Optional[datetime] = None
    propagation_hop_count: int = 0
    content_tampering_detected: bool = False
    source_credibility_score: float = 50.0
    narrative_framework: Optional[NarrativeType] = None
    interest_structure: str = ""  # L5 分析结果
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "depth_achieved": self.depth_achieved.value,
            "earliest_source_url": self.earliest_source_url,
            "earliest_timestamp": self.earliest_timestamp.isoformat() if self.earliest_timestamp else None,
            "propagation_hop_count": self.propagation_hop_count,
            "content_tampering_detected": self.content_tampering_detected,
            "source_credibility_score": self.source_credibility_score,
            "narrative_framework": self.narrative_framework.value if self.narrative_framework else None,
            "interest_structure": self.interest_structure,
            "details": self.details,
        }


@dataclass
class DomainAnalysis:
    """领域知识分析结果"""
    domain: DomainType = DomainType.GENERAL
    claims: list[dict] = field(default_factory=list)  # 提取的主张列表
    verified_claims: list[dict] = field(default_factory=list)
    unverified_claims: list[dict] = field(default_factory=list)
    refuted_claims: list[dict] = field(default_factory=list)
    knowledge_gaps: list[str] = field(default_factory=list)  # 承认不知的领域

    def to_dict(self) -> dict:
        return {
            "domain": self.domain.value,
            "claims": self.claims,
            "verified_claims": self.verified_claims,
            "unverified_claims": self.unverified_claims,
            "refuted_claims": self.refuted_claims,
            "knowledge_gaps": self.knowledge_gaps,
        }


@dataclass
class NarrativeMatch:
    """叙事框架匹配"""
    narrative_type: NarrativeType
    description: str
    confidence: Confidence
    markers: list[str] = field(default_factory=list)  # 触发特征词/模式
    reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "narrative_type": self.narrative_type.value,
            "description": self.description,
            "confidence": self.confidence.value,
            "markers": self.markers,
            "reasoning": self.reasoning,
        }


@dataclass
class NarrativeAnalysis:
    """叙事框架分析结果"""
    matches: list[NarrativeMatch] = field(default_factory=list)
    dominant_narrative: Optional[NarrativeType] = None
    manipulation_score: float = 0.0  # 0-100 操纵性评分
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "matches": [m.to_dict() for m in self.matches],
            "dominant_narrative": self.dominant_narrative.value if self.dominant_narrative else None,
            "manipulation_score": self.manipulation_score,
            "summary": self.summary,
        }
