"""
Sift Correction Agent — 叙事替代策略引擎

辟谣不是简单地说"这是假的"。有效的辟谣需要:
1. 替代叙事 — 不仅指出错误，还提供"实际发生了什么"
2. 事实楔子 — 用一个无可辩驳的事实击穿整个虚假叙事框架
3. 认知桥梁 — 从受众已有认知出发，逐步引导至正确理解
4. 情感校准 — 根据受众情绪状态选择最有效的沟通语气

核心原理 (基于认知科学):
- 空白填补效应: 只说"不是真的"而不提供替代解释 → 受众会用原来的虚假信息填补空白
- 逆火效应: 直接攻击受众核心身份认同的信息 → 反而加深原有信念
- 真相三明治结构: 真相 → 警告 → 解释 → 真相(重复)

用法:
    from app.engine.llm_analyzer import CorrectionAgent
    agent = CorrectionAgent()
    correction = agent.generate(
        original_claim="...",
        verified_facts=["...", "..."],
        audience="general",
        tone="neutral",
    )
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("truthtrace.correction")


# =============================================================================
# 语气策略
# =============================================================================

class CorrectionTone:
    """辟谣语气策略"""
    NEUTRAL = "neutral"           # 客观中立 — 适合官方/权威发布
    AUTHORITATIVE = "authoritative"  # 权威坚定 — 适合机构/专家辟谣
    EMPATHETIC = "empathetic"     # 共情理解 — 适合对情绪化受众
    EDUCATIONAL = "educational"   # 教育启蒙 — 适合科普场景
    CONCISE = "concise"           # 简洁直接 — 适合社交媒体/短信


# 语气模板
TONE_TEMPLATES = {
    CorrectionTone.NEUTRAL: {
        "opening": "关于「{claim_summary}」的说法，经核实：",
        "truth_statement": "实际情况是：{facts}",
        "correction": "「{original}」这一说法{error_type}。{explanation}",
        "closing": "以上信息基于{source_count}个可验证的来源。如有疑问，可通过以下来源进一步核实。",
    },
    CorrectionTone.AUTHORITATIVE: {
        "opening": "⚠ 辟谣声明：关于「{claim_summary}」",
        "truth_statement": "经权威机构核实，事实如下：{facts}",
        "correction": "「{original}」— 此说法{error_type}。{explanation}",
        "closing": "本辟谣基于{source_count}个权威来源。请以权威信息为准，不造谣、不信谣、不传谣。",
    },
    CorrectionTone.EMPATHETIC: {
        "opening": "我们理解您对「{claim_summary}」的关注和担忧。",
        "truth_statement": "经过认真核实，我们了解到：{facts}",
        "correction": "您可能看到的「{original}」{error_type}。{explanation}",
        "closing": "关心这些问题是正常的。如果您有更多疑问，欢迎查阅以下来源了解更多。",
    },
    CorrectionTone.EDUCATIONAL: {
        "opening": "让我们一起来理解「{claim_summary}」背后的科学事实。",
        "truth_statement": "科学告诉我们：{facts}",
        "correction": "为什么「{original}」是不准确的？{explanation}",
        "closing": "学会分辨这类信息，是信息素养的重要一步。推荐阅读以下{source_count}个来源获取更多背景。",
    },
    CorrectionTone.CONCISE: {
        "opening": "❌ 「{claim_summary}」— 不属实",
        "truth_statement": "✅ 事实：{facts}",
        "correction": "{explanation}",
        "closing": "来源: {source_count}个可验证信源",
    },
}


# =============================================================================
# 错误类型分类
# =============================================================================

ERROR_TYPES = {
    "false": "与事实不符",
    "misleading": "存在误导性",
    "missing_context": "缺少关键背景信息",
    "outdated": "基于过时信息",
    "distorted": "信息被曲解/断章取义",
    "fabricated": "为编造信息",
    "unverifiable": "目前无法被验证",
    "opinion_as_fact": "将个人观点表述为事实",
}


def _classify_error(distortion_types: list[str], fallacy_types: list[str], credibility: float) -> str:
    """根据分析结果判断错误类型"""
    if credibility < 25:
        return "fabricated"
    if "source_fabrication" in distortion_types:
        return "fabricated"
    if "context_stripping" in distortion_types or "decontextualization" in distortion_types:
        return "missing_context"
    if "emotional_manipulation" in distortion_types:
        return "distorted"
    if credibility < 45:
        return "misleading"
    if credibility < 60:
        return "missing_context"
    return "unverifiable"


# =============================================================================
# 事实楔子生成
# =============================================================================

def _generate_fact_wedge(verified_facts: list[str], original_claim: str) -> str:
    """
    生成"事实楔子"——一个无可辩驳的事实，
    用于击穿整个虚假叙事的核心逻辑。
    """
    if not verified_facts:
        return ""

    # 选择与原始主张最相关的事实
    # 简化策略: 选择最短但最具体的事实
    best_fact = min(verified_facts, key=lambda f: len(f)) if verified_facts else ""

    if not best_fact:
        return ""

    return best_fact


# =============================================================================
# 真相三明治结构
# =============================================================================

def _build_truth_sandwich(
    truth: str,
    claim_summary: str,
    error_explanation: str,
    sources: list[str],
) -> str:
    """
    构建"真相三明治":
    1. 真相 (顶层) — 先建立正确的认知框架
    2. 警告 (中层) — 指出错误信息
    3. 真相 (底层) — 再次强化正确信息
    """
    sandwich = []

    # 顶层: 真相
    sandwich.append(f"【事实】{truth}")

    # 中层: 警告 + 解释
    sandwich.append(f"【注意】关于「{claim_summary}」的说法 — {error_explanation}")

    # 底层: 真相重复 + 来源
    if sources:
        sandwich.append(f"【核实】以上信息可在此验证: {sources[0]}")

    return "\n\n".join(sandwich)


# =============================================================================
# CorrectionAgent 主类
# =============================================================================

@dataclass
class CorrectionResult:
    """辟谣叙事替代的完整结果"""
    # 结构化辟谣内容
    short_correction: str = ""          # 一句话辟谣 (适合社交媒体)
    full_correction: str = ""           # 完整辟谣文本
    truth_sandwich: str = ""            # 真相三明治结构
    fact_wedge: str = ""                # 事实楔子

    # 元信息
    tone_used: str = CorrectionTone.NEUTRAL
    error_type: str = ""
    source_count: int = 0
    audience: str = "general"

    # 叙事替代
    alternative_narrative: str = ""      # "实际发生了什么"的叙事
    cognitive_bridge: str = ""           # 认知桥梁 (从误解到理解)

    def to_dict(self) -> dict:
        return {
            "short_correction": self.short_correction,
            "full_correction": self.full_correction,
            "truth_sandwich": self.truth_sandwich,
            "fact_wedge": self.fact_wedge,
            "tone_used": self.tone_used,
            "error_type": self.error_type,
            "source_count": self.source_count,
            "audience": self.audience,
            "alternative_narrative": self.alternative_narrative,
            "cognitive_bridge": self.cognitive_bridge,
        }


class CorrectionAgent:
    """
    辟谣叙事替代引擎。

    核心理念:
    1. 不只说"这是错的" — 说"实际是什么"
    2. 不攻击信谣者 — 理解关注点, 提供更好的信息
    3. 不陷入细节辩论 — 用一个核心事实击穿虚假框架
    4. 不创造信息真空 — 用正确信息填补
    """

    def __init__(self):
        self.name = "Sift Correction Agent"

    def generate(
        self,
        original_claim: str = "",
        verified_facts: list[str] | None = None,
        sources: list[str] | None = None,
        distortion_types: list[str] | None = None,
        fallacy_types: list[str] | None = None,
        credibility_score: float = 50.0,
        audience: str = "general",
        tone: str = CorrectionTone.NEUTRAL,
        title: str = "",
    ) -> CorrectionResult:
        """
        生成辟谣叙事替代。

        Args:
            original_claim: 原始虚假/误导性主张
            verified_facts: 经过验证的事实列表
            sources: 可信来源 URL 列表
            distortion_types: 检测到的失真类型
            fallacy_types: 检测到的谬误类型
            credibility_score: 原始主张的可信度评分 (0-100)
            audience: 目标受众 ("general", "parent", "professional", "youth")
            tone: 辟谣语气

        Returns:
            CorrectionResult 含多层辟谣内容
        """
        verified_facts = verified_facts or []
        sources = sources or []
        distortion_types = distortion_types or []
        fallacy_types = fallacy_types or []

        # 分类错误类型
        error_type = _classify_error(distortion_types, fallacy_types, credibility_score)
        error_desc = ERROR_TYPES.get(error_type, "需要进一步核实")

        # 提取主张摘要 (截取前80字)
        claim_summary = original_claim[:80] + ("…" if len(original_claim) > 80 else "")
        if not claim_summary:
            claim_summary = title[:80] if title else "该信息"

        # 生成事实楔子
        fact_wedge = _generate_fact_wedge(verified_facts, original_claim)

        # 汇总事实
        if verified_facts:
            facts_text = "；".join(verified_facts[:3])
        else:
            facts_text = "目前可验证的信息不足以支持或反驳该主张。建议查阅权威来源获取准确信息。"

        # 生成解释
        if distortion_types:
            dist_desc = "、".join(distortion_types[:3])
            explanation = f"该信息存在以下问题：{dist_desc}。"
        elif fallacy_types:
            fall_desc = "、".join(fallacy_types[:3])
            explanation = f"该信息的推理存在以下逻辑问题：{fall_desc}。"
        elif error_type == "fabricated":
            explanation = "该信息缺乏可验证的来源和事实依据。"
        elif error_type == "misleading":
            explanation = "该信息虽然可能包含部分事实，但整体呈现方式具有误导性。"
        else:
            explanation = "该信息的关键主张无法被现有证据验证。"

        # 选取语气模板
        tmpl = TONE_TEMPLATES.get(tone, TONE_TEMPLATES[CorrectionTone.NEUTRAL])
        source_count = len(sources)

        # 构建一句话辟谣
        short_correction = (
            f"关于「{claim_summary}」的说法{error_desc}。"
            f"{fact_wedge if fact_wedge else '请以权威来源信息为准。'}"
        )[:280]

        # 构建完整辟谣
        full_correction_parts = [
            tmpl["opening"].format(claim_summary=claim_summary),
            "",
            tmpl["truth_statement"].format(facts=facts_text),
            "",
            tmpl["correction"].format(
                original=claim_summary,
                error_type=error_desc,
                explanation=explanation,
            ),
        ]
        if sources:
            full_correction_parts.extend([
                "",
                "📚 可验证来源:",
                *[f"  {i+1}. {s}" for i, s in enumerate(sources[:5])],
            ])
        full_correction_parts.append(
            tmpl["closing"].format(source_count=source_count)
        )
        full_correction = "\n".join(full_correction_parts)

        # 构建真相三明治
        truth_sandwich = _build_truth_sandwich(
            truth=facts_text,
            claim_summary=claim_summary,
            error_explanation=explanation,
            sources=sources,
        )

        # 构建叙事替代
        alternative_narrative = self._build_alternative_narrative(
            original_claim=original_claim,
            verified_facts=verified_facts,
            error_type=error_type,
            audience=audience,
        )

        # 构建认知桥梁
        cognitive_bridge = self._build_cognitive_bridge(
            original_claim=original_claim,
            verified_facts=verified_facts,
            audience=audience,
        )

        return CorrectionResult(
            short_correction=short_correction,
            full_correction=full_correction,
            truth_sandwich=truth_sandwich,
            fact_wedge=fact_wedge,
            tone_used=tone,
            error_type=error_type,
            source_count=source_count,
            audience=audience,
            alternative_narrative=alternative_narrative,
            cognitive_bridge=cognitive_bridge,
        )

    def _build_alternative_narrative(
        self,
        original_claim: str,
        verified_facts: list[str],
        error_type: str,
        audience: str,
    ) -> str:
        """构建"实际发生了什么"的替代叙事"""
        if not verified_facts:
            return "目前没有足够的信息来构建完整的替代叙事。建议关注权威来源的后续更新。"

        facts_narrative = " ".join(verified_facts[:3])

        audience_bridge = {
            "general": "",
            "parent": "作为关心家人健康的您，",
            "professional": "从专业角度看，",
            "youth": "",
        }.get(audience, "")

        return f"{audience_bridge}实际情况是：{facts_narrative}"

    def _build_cognitive_bridge(
        self,
        original_claim: str,
        verified_facts: list[str],
        audience: str,
    ) -> str:
        """
        构建认知桥梁 — 从受众现有认知逐步引导至正确理解。

        关键: 不否定受众的关注点，而是提供更准确的满足该关注的信息。
        """
        # 识别受众可能的关注点
        concerns = []
        if re.search(r"(?:致癌|有毒|危害|危险|安全)", original_claim):
            concerns.append("安全担忧")
        if re.search(r"(?:孩子|儿童|宝宝|婴儿|学生)", original_claim):
            concerns.append("对孩子健康的关心")
        if re.search(r"(?:食品|饮食|吃|喝|食材)", original_claim):
            concerns.append("对食品安全的关注")
        if re.search(r"(?:政府|官方|国家|政策)", original_claim):
            concerns.append("对公共政策的关切")
        if re.search(r"(?:钱|价格|涨价|贵|免费)", original_claim):
            concerns.append("经济利益的顾虑")

        if not concerns:
            return ""

        concern_str = "、".join(concerns)
        bridge = f"我们理解您{concern_str}。"

        if verified_facts:
            bridge += f" 以下是基于可验证事实的信息：{'；'.join(verified_facts[:2])}。"

        return bridge


# =============================================================================
# 快速生成 (用于管线集成)
# =============================================================================



# =============================================================================
# 成本逻辑推演模块 (B站评论启示: 一句算账击穿谣言)
# =============================================================================

COST_KNOWLEDGE = {
    "plastic_rice": {
        "claim_patterns": ["塑料", "假大米", "塑料米", "合成米"],
        "real_material": "聚乙烯(PE)",
        "real_cost_per_ton": 9000,
        "fake_material": "大米",
        "fake_cost_per_ton": 3000,
        "logic": "如果真用塑料做大米，每吨成本9000元，而真大米每吨3000元。厂家用更贵的材料假冒更便宜的东西，在商业上完全不合理。",
        "humor": "愿意用聚乙烯冒充大米的厂家，不是骗子，是慈善家——花3倍成本给你送粮食。",
    },
    "gold_apple": {
        "claim_patterns": ["金苹果", "打蜡苹果", "苹果打蜡"],
        "real_material": "食用蜡(巴西棕榈蜡/虫胶)",
        "real_cost_per_kg": 0.5,
        "fake_material": "工业石蜡",
        "fake_cost_per_kg": 2,
        "logic": "食用蜡成本约0.5元/kg，工业石蜡2元/kg。用更贵的工业蜡代替食用蜡，既不省钱也不安全，没有任何商业动机。",
    },
    "fake_beef": {
        "claim_patterns": ["假牛肉", "合成牛肉", "人造牛肉"],
        "real_material": "牛肉",
        "real_cost_per_kg": 60,
        "fake_material": "大豆蛋白+添加剂+加工费",
        "fake_cost_per_kg": 80,
        "logic": "用大豆蛋白模拟牛肉口感需要复杂工艺，综合成本约80元/kg，而真牛肉60元/kg。假牛肉比真牛肉还贵，造假者图什么？",
    },
    "fake_egg": {
        "claim_patterns": ["假鸡蛋", "人造鸡蛋", "塑料鸡蛋"],
        "real_material": "鸡蛋",
        "real_cost_per_piece": 0.8,
        "fake_material": "海藻酸钠+氯化钙+色素+模具",
        "fake_cost_per_piece": 2.5,
        "logic": "制造一个仿真鸡蛋的物料和人工成本约2.5元，而真鸡蛋0.8元。造假是为了利润，赔钱的假货不存在。",
    },
}


def generate_cost_reasoning(claim_text: str) -> dict:
    """
    对产品/经济类谣言自动生成成本逻辑推演。

    用法:
        reasoning = generate_cost_reasoning("自热米饭的米是塑料做的")
        # => {"matched": True, "logic": "...", "humor": "..."}
    """
    for key, data in COST_KNOWLEDGE.items():
        for pattern in data["claim_patterns"]:
            if pattern in claim_text:
                return {
                    "matched": True,
                    "type": key,
                    "logic": data["logic"],
                    "humor": data["humor"],
                    "breakdown": f"{data['real_material']}: {data['real_cost_per_ton']}{'元/吨' if 'ton' in key else '元/kg' if 'kg' in data.get('real_material','') else '元'} vs {data['fake_material']}: {data['fake_cost_per_ton']}{'元/吨' if 'ton' in key else '元/kg' if 'kg' in data.get('fake_material','') else '元'}",
                }

    return {"matched": False}



# =============================================================================
# 技术事实楔子 (B站视频8启示: 红外物理原理可以击穿所有技术类谣言)
# =============================================================================

TECH_FACT_WEDGES = {
    "infrared_thermal": {
        "patterns": ["红外", "热成像", "红外线", "热象仪", "FLIR"],
        "wedge": "红外热成像依赖物体自身发出的红外辐射(热量)。没有体温的物体在红外画面中无法清晰成像。如果一段视频声称用红外线拍到了丧尸或鬼魂，那么视频中的异常物体必然有体温——是活人或发热设备，不是超自然存在。",
        "source": "Planck's Law + Stefan-Boltzmann Law",
        "category": "physics",
    },
    "radiation_non_ionizing": {
        "patterns": ["辐射", "电磁辐射", "5G辐射", "WiFi辐射", "手机辐射", "基站辐射"],
        "wedge": "辐射分两种：电离辐射(X光/伽马/核辐射)能破坏DNA致癌；非电离辐射(5G/WiFi/手机信号)能量太低无法破坏分子键。太阳紫外线比5G基站能量高几十万倍。ICNIRP确认5G辐射远低于安全限值。",
        "source": "ICNIRP Guidelines 2020 + WHO EMF Project",
        "category": "physics",
    },
    "dose_makes_poison": {
        "patterns": ["致癌", "有毒", "毒性", "剧毒", "中毒", "致死", "致命"],
        "wedge": "毒性取决于剂量。水喝太多也会水中毒。食品中的任何物质在安全剂量(ADI)以下都不会危害健康。脱离剂量谈毒性，就像说氧气有毒因为100%纯氧会损伤肺。",
        "source": "Paracelsus + JECFA/FDA ADI system",
        "category": "toxicology",
    },
    "correlation_not_causation": {
        "patterns": ["相关", "关联", "成正比", "正相关", "负相关"],
        "wedge": "两个事物同时出现不等于一个导致另一个。冰淇淋销量和溺水死亡都随夏天上升——不是因为冰淇淋导致溺水，而是混淆变量(气温)。要证明因果需要随机对照实验。",
        "source": "Bradford Hill Criteria (1965)",
        "category": "statistics",
    },
    "natural_fallacy": {
        "patterns": ["天然", "纯天然", "自然", "化学合成", "人工合成"],
        "wedge": "天然不等于安全(毒蘑菇是天然的)。化学合成不等于有毒(阿司匹林是合成的)。毒性取决于化学结构和剂量，不取决于天然还是合成。",
        "source": "Chemistry basics + IARC/WHO classification",
        "category": "chemistry",
    },
}


def generate_tech_fact_wedge(claim_text: str) -> dict:
    """基于物理/化学/生物原理生成技术事实楔子"""
    for key, data in TECH_FACT_WEDGES.items():
        for pattern in data["patterns"]:
            if pattern in claim_text:
                return {"matched": True, "type": key, "wedge": data["wedge"],
                        "source": data["source"], "category": data["category"]}
    return {"matched": False}


def generate_correction(
    original_claim: str = "",
    verified_facts: list[str] | None = None,
    sources: list[str] | None = None,
    distortion_types: list[str] | None = None,
    fallacy_types: list[str] | None = None,
    credibility_score: float = 50.0,
    tone: str = CorrectionTone.NEUTRAL,
    title: str = "",
) -> CorrectionResult:
    """快速生成辟谣替代叙事 (管线集成入口)"""
    agent = CorrectionAgent()

    # 根据可信度选择语气
    if credibility_score < 25:
        tone = CorrectionTone.AUTHORITATIVE
    elif credibility_score < 45:
        tone = tone or CorrectionTone.NEUTRAL

    return agent.generate(
        original_claim=original_claim,
        verified_facts=verified_facts,
        sources=sources,
        distortion_types=distortion_types,
        fallacy_types=fallacy_types,
        credibility_score=credibility_score,
        tone=tone,
        title=title,
    )
