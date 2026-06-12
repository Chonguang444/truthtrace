"""
个性化辟谣引擎 (Personalized Debunking) — 第32号引擎

理论基础:
  - MURSE (Pang et al., 2026 EACL Industry): LLM驱动的个性化中文辟谣，2x用户偏好
  - 动机推理 (Amaddio, 2025): 信念一致性影响纠正接受度
  - 多层次信息操纵 (Lenk, 2026): 叙事框架与读者认知的匹配

核心原理:
  根据用户的认知特征、情感倾向和信息环境，生成最具说服力的辟谣文本。
  不是"一种辟谣给所有人"，而是"根据读者画像自适应"。

用户画像维度:
  - 认知风格: 分析型/直觉型
  - 情感倾向: 对话题的情感态度(愤怒/恐惧/好奇/怀疑)
  - 知识背景: 对该领域的了解程度
  - 信任倾向: 对权威/科学/政府/媒体的信任度
  - 阅读习惯: 长篇论证 vs 简洁结论 vs 数据图表
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CognitiveStyle(str, Enum):
    ANALYTICAL = "analytical"   # 分析型 — 偏好详细数据+逻辑链
    INTUITIVE = "intuitive"     # 直觉型 — 偏好类比+故事
    BALANCED = "balanced"       # 平衡型


class EmotionalStance(str, Enum):
    FEARFUL = "fearful"         # 恐惧 — 需要安全感
    ANGRY = "angry"             # 愤怒 — 需要公正感
    CURIOUS = "curious"         # 好奇 — 需要新知
    SKEPTICAL = "skeptical"     # 怀疑 — 需要透明度
    NEUTRAL = "neutral"         # 中性


class TrustProfile(str, Enum):
    TRUSTS_AUTHORITY = "authority"      # 信任权威
    TRUSTS_SCIENCE = "science"          # 信任科学
    TRUSTS_COMMUNITY = "community"      # 信任社区
    TRUSTS_NONE = "none"                # 普遍不信


@dataclass
class UserPersona:
    """用户画像"""
    cognitive_style: CognitiveStyle = CognitiveStyle.BALANCED
    emotional_stance: EmotionalStance = EmotionalStance.NEUTRAL
    trust_profile: TrustProfile = TrustProfile.TRUSTS_SCIENCE
    domain_knowledge: str = "general"   # 对该领域的了解: none/beginner/intermediate/expert
    preferred_length: str = "moderate"  # short/moderate/long
    preferred_format: str = "hybrid"    # text/data/story/hybrid

    def to_dict(self) -> dict:
        return {
            "cognitive_style": self.cognitive_style.value,
            "emotional_stance": self.emotional_stance.value,
            "trust_profile": self.trust_profile.value,
            "domain_knowledge": self.domain_knowledge,
            "preferred_length": self.preferred_length,
            "preferred_format": self.preferred_format,
        }


@dataclass
class PersonalizedDebunkingResult:
    """个性化辟谣结果"""
    persona: UserPersona = field(default_factory=UserPersona)
    headline: str = ""            # 针对画像优化的标题
    summary: str = ""             # 个性化摘要
    full_correction: str = ""     # 完整辟谣文本
    evidence_chain: list[str] = field(default_factory=list)  # 个性化证据链
    narrative_alternative: str = ""  # 个性化叙事替代
    tone_used: str = ""           # 实际使用的语气
    confidence_boost: float = 0.0 # 预期纠正效果提升(%)

    def to_dict(self) -> dict:
        return {
            "persona": self.persona.to_dict(),
            "headline": self.headline,
            "summary": self.summary,
            "full_correction": self.full_correction,
            "evidence_chain": self.evidence_chain,
            "narrative_alternative": self.narrative_alternative,
            "tone_used": self.tone_used,
            "confidence_boost": round(self.confidence_boost, 1),
        }


# =============================================================================
# 个性化辟谣策略库
# =============================================================================

DEBUNKING_STRATEGIES = {
    # 分析型 + 信任科学 → 详细数据+方法论透明
    (CognitiveStyle.ANALYTICAL, TrustProfile.TRUSTS_SCIENCE): {
        "headline_template": "数据告诉你: {rumor}的真相",
        "approach": "data_driven",
        "tone": "educational",
        "structure": ["研究回顾", "证据评估", "方法论说明", "结论"],
        "boost": 18.0,
    },
    # 分析型 + 信任权威 → 权威引用+机构背书
    (CognitiveStyle.ANALYTICAL, TrustProfile.TRUSTS_AUTHORITY): {
        "headline_template": "{authority}最新评估: {rumor}的事实核查",
        "approach": "authority_backed",
        "tone": "authoritative",
        "structure": ["权威机构结论", "决策依据", "常见误解"],
        "boost": 15.0,
    },
    # 直觉型 + 恐惧情绪 → 叙事替代+安全感
    (CognitiveStyle.INTUITIVE, EmotionalStance.FEARFUL): {
        "headline_template": "别怕，我们来拆解这个说法——{rumor}",
        "approach": "narrative_replacement",
        "tone": "empathetic",
        "structure": ["情绪确认", "谣言拆解", "真相故事", "安全感重建"],
        "boost": 22.0,
    },
    # 直觉型 + 愤怒情绪 → 公平感+正义叙事
    (CognitiveStyle.INTUITIVE, EmotionalStance.ANGRY): {
        "headline_template": "谁在利用你的愤怒？{rumor}背后的真相",
        "approach": "redirect_outrage",
        "tone": "empathetic",
        "structure": ["愤怒验证", "真正的欺骗者", "可以做什么"],
        "boost": 20.0,
    },
    # 怀疑型 → 极度透明+来源全公开
    (EmotionalStance.SKEPTICAL, TrustProfile.TRUSTS_NONE): {
        "headline_template": "这是我们的完整推理过程——关于{rumor}",
        "approach": "radical_transparency",
        "tone": "neutral",
        "structure": ["完整推理链", "每个来源可查", "不确定性声明", "你来判断"],
        "boost": 25.0,
    },
    # 好奇型 → 新知+有趣事实
    (EmotionalStance.CURIOUS, CognitiveStyle.BALANCED): {
        "headline_template": "你知道吗？关于{rumor}的有趣真相",
        "approach": "surprising_facts",
        "tone": "educational",
        "structure": ["有趣的反直觉事实", "科学原理", "常见误解"],
        "boost": 12.0,
    },
}

# 默认策略
DEFAULT_STRATEGY = {
    "headline_template": "事实核查: {rumor}",
    "approach": "balanced",
    "tone": "neutral",
    "structure": ["主张", "证据", "结论"],
    "boost": 10.0,
}


class PersonalizedDebunkingEngine:
    """个性化辟谣引擎"""

    @staticmethod
    def infer_persona(
        query: str = "",
        referrer: str = "",
        previous_interactions: list[str] | None = None,
    ) -> UserPersona:
        """从用户行为推断画像"""
        persona = UserPersona()

        # 从查询文本推断情感倾向
        fear_words = ["怕", "危险", "有毒", "致癌", "伤害", "死", "恐怖", "吓"]
        anger_words = ["骗", "坑", "害", "腐败", "黑心", "无良"]
        curious_words = ["为什么", "怎么", "真的吗", "是什么", "怎么做到的"]
        skeptical_words = ["辟谣", "假的吧", "不太信", "真的假的", "求证"]

        q_lower = query.lower()
        if any(w in q_lower for w in fear_words):
            persona.emotional_stance = EmotionalStance.FEARFUL
        elif any(w in q_lower for w in anger_words):
            persona.emotional_stance = EmotionalStance.ANGRY
        elif any(w in q_lower for w in curious_words):
            persona.emotional_stance = EmotionalStance.CURIOUS
        elif any(w in q_lower for w in skeptical_words):
            persona.emotional_stance = EmotionalStance.SKEPTICAL

        # 从查询推断认知风格
        analytical_words = ["数据", "研究", "证据", "实验", "统计", "论文"]
        if any(w in q_lower for w in analytical_words):
            persona.cognitive_style = CognitiveStyle.ANALYTICAL

        return persona

    @staticmethod
    def match_strategy(persona: UserPersona) -> dict:
        """匹配最佳辟谣策略"""
        # 优先精确匹配
        if persona.emotional_stance == EmotionalStance.SKEPTICAL:
            return DEBUNKING_STRATEGIES.get(
                (EmotionalStance.SKEPTICAL, TrustProfile.TRUSTS_NONE), DEFAULT_STRATEGY
            )

        for (key1, key2), strategy in DEBUNKING_STRATEGIES.items():
            if isinstance(key1, CognitiveStyle) and isinstance(key2, TrustProfile):
                if persona.cognitive_style == key1 and persona.trust_profile == key2:
                    return strategy
            if isinstance(key1, CognitiveStyle) and isinstance(key2, EmotionalStance):
                if persona.cognitive_style == key1 and persona.emotional_stance == key2:
                    return strategy
            if isinstance(key1, EmotionalStance) and isinstance(key2, CognitiveStyle):
                if persona.emotional_stance == key1 and persona.cognitive_style == key2:
                    return strategy

        return DEFAULT_STRATEGY

    @staticmethod
    def generate(
        rumor: str = "",
        verified_facts: list[str] | None = None,
        sources: list[str] | None = None,
        persona: UserPersona | None = None,
        query: str = "",
    ) -> PersonalizedDebunkingResult:
        """生成个性化辟谣文本"""
        if persona is None:
            persona = PersonalizedDebunkingEngine.infer_persona(query=query)

        strategy = PersonalizedDebunkingEngine.match_strategy(persona)
        result = PersonalizedDebunkingResult(
            persona=persona,
            tone_used=strategy["tone"],
            confidence_boost=strategy["boost"],
        )

        rumor_short = rumor[:60]

        # 个性化标题
        result.headline = strategy["headline_template"].format(
            rumor=rumor_short,
            authority="WHO/权威机构" if persona.trust_profile == TrustProfile.TRUSTS_AUTHORITY else "科学共识",
        )

        # 证据链 — 根据画像调整呈现顺序和方式
        if persona.cognitive_style == CognitiveStyle.ANALYTICAL:
            result.evidence_chain = [
                f"📊 数据: {fact}" for fact in (verified_facts or [])
            ]
        elif persona.cognitive_style == CognitiveStyle.INTUITIVE:
            result.evidence_chain = [
                f"💡 类比理解: {fact}" for fact in (verified_facts or [])
            ]
        else:
            result.evidence_chain = [
                f"✅ {fact}" for fact in (verified_facts or [])
            ]

        # 完整辟谣 — 按策略结构组织
        sections = []
        for section in strategy.get("structure", []):
            if section == "情绪确认" and persona.emotional_stance != EmotionalStance.NEUTRAL:
                emotion_map = {
                    EmotionalStance.FEARFUL: "你的担心是可以理解的——在面对健康/安全的不确定信息时，我们都会感到不安。",
                    EmotionalStance.ANGRY: "你的愤怒是有道理的——利用人们的信任和健康焦虑来牟利是不可接受的。",
                }
                sections.append(emotion_map.get(persona.emotional_stance, ""))
            elif section == "数据告诉你":
                sections.append(f"关于'{rumor_short}'，以下是关键事实:")
                for fact in (verified_facts or [])[:3]:
                    sections.append(f"• {fact}")
            elif section == "权威机构结论":
                sections.append("经核实，权威机构的科学评估如下:")
                for fact in (verified_facts or [])[:3]:
                    sections.append(f"• {fact}")
                if sources:
                    sections.append(f"\n来源: {', '.join(sources[:3])}")
            elif section == "谣言拆解":
                sections.append(f"这个说法的核心问题是:")
                sections.append(f"❌ '{rumor_short}' — 缺乏可靠科学证据支持")
            elif section == "真相故事":
                sections.append("真实情况是这样的:")
                for fact in (verified_facts or [])[:2]:
                    sections.append(f"✨ {fact}")
            elif section == "安全感重建":
                sections.append("你不必过度担心。科学的安全评估体系是:")
                for fact in (verified_facts or [])[:2]:
                    sections.append(f"🛡️ {fact}")
            elif section == "完整推理链":
                sections.append("以下是我们的完整验证过程:")
                for i, fact in enumerate((verified_facts or [])[:5], 1):
                    sections.append(f"{i}. 查证: {fact}")
                sections.append("\n⚠️ 不确定性声明: 以上基于现有最佳证据。科学认知是动态发展的。")
            elif section == "有趣的真相":
                sections.append(f"你知道吗？")
                for fact in (verified_facts or [])[:2]:
                    sections.append(f"🔍 {fact}")
            elif section == "主张":
                sections.append(f"主张: {rumor_short}")
            elif section == "证据":
                sections.append("核查结果:")
                for fact in (verified_facts or [])[:3]:
                    sections.append(f"• {fact}")
            elif section == "结论":
                sections.append(f"结论: '{rumor_short}' 缺乏科学证据支持。")

        result.full_correction = "\n\n".join(sections)
        result.summary = result.full_correction[:300]

        # 个性化叙事替代
        if persona.cognitive_style == CognitiveStyle.INTUITIVE:
            result.narrative_alternative = f"想象一下……{verified_facts[0] if verified_facts else ''}"
        else:
            result.narrative_alternative = f"科学共识是: {verified_facts[0] if verified_facts else ''}"

        return result


def generate_personalized_debunking(
    rumor: str = "",
    verified_facts: list[str] | None = None,
    sources: list[str] | None = None,
    query: str = "",
    persona: dict | None = None,
) -> PersonalizedDebunkingResult:
    """生成个性化辟谣 — 便捷函数"""
    user_persona = None
    if persona:
        user_persona = UserPersona(
            cognitive_style=CognitiveStyle(persona.get("cognitive_style", "balanced")),
            emotional_stance=EmotionalStance(persona.get("emotional_stance", "neutral")),
            trust_profile=TrustProfile(persona.get("trust_profile", "science")),
            domain_knowledge=persona.get("domain_knowledge", "general"),
        )
    return PersonalizedDebunkingEngine.generate(
        rumor=rumor, verified_facts=verified_facts or [],
        sources=sources or [], persona=user_persona, query=query,
    )
