"""
叙事战场可视化引擎 (Narrative Battlefield) — 第38号引擎

理论: 不判定"真假"——展示同一事件的多个竞争叙事景观

核心: 声称可以指称上"不假"但伦理上"有问题"，超越了传统的真/假二元判定
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import hashlib


@dataclass
class NarrativeFrame:
    narrative_id: str = ""
    narrative_label: str = ""       # 叙事标签, e.g. "防御性民族主义叙事"
    core_claim: str = ""            # 核心主张
    evidence_quality: float = 0.5   # 证据质量 0-1
    logical_coherence: float = 0.5  # 逻辑一致性 0-1
    ethical_assessment: str = ""    # 伦理评判
    emotional_appeal: str = ""      # 情感诉求
    target_audience: str = ""      # 目标受众
    spreaders: list[str] = field(default_factory=list)
    strength: float = 0.0          # 叙事传播力
    color: str = "#6b7280"

    def to_dict(self) -> dict:
        return {
            "narrative_id": self.narrative_id,
            "narrative_label": self.narrative_label,
            "core_claim": self.core_claim[:200],
            "evidence_quality": round(self.evidence_quality, 2),
            "logical_coherence": round(self.logical_coherence, 2),
            "ethical_assessment": self.ethical_assessment,
            "emotional_appeal": self.emotional_appeal,
            "target_audience": self.target_audience,
            "spreaders": self.spreaders[:5],
            "strength": round(self.strength, 2),
            "color": self.color,
        }


@dataclass
class NarrativeBattlefieldResult:
    event_title: str = ""
    event_url: str = ""
    narratives: list[NarrativeFrame] = field(default_factory=list)
    dominant_narrative: Optional[NarrativeFrame] = None
    contested_areas: list[dict] = field(default_factory=list)
    narrative_conflicts: list[dict] = field(default_factory=list)
    moral_ambiguity_score: float = 0.0
    summary: str = ""
    disclaimer: str = ""

    def to_dict(self) -> dict:
        return {
            "event_title": self.event_title,
            "event_url": self.event_url,
            "narratives": [n.to_dict() for n in self.narratives],
            "dominant_narrative": self.dominant_narrative.to_dict() if self.dominant_narrative else None,
            "contested_areas": self.contested_areas,
            "narrative_conflicts": self.narrative_conflicts[:5],
            "moral_ambiguity_score": round(self.moral_ambiguity_score, 2),
            "summary": self.summary,
            "disclaimer": self.disclaimer,
        }


# 叙事框架模板
NARRATIVE_TEMPLATES = {
    "victim_national": {
        "label": "受害者叙事(民族)",
        "core": "外部势力故意伤害本国利益",
        "ethical_concern": "可能过度简化国际关系的复杂性，将正常竞争/分歧框架化为恶意攻击",
        "emotion": "愤怒+悲情",
        "color": "#dc2626",
    },
    "hero_defender": {
        "label": "英雄守护叙事",
        "core": "本国/本群体在抵御不公正攻击",
        "ethical_concern": "可能将复杂问题道德化为'正义vs邪恶'，压制对自身行为的反思",
        "emotion": "自豪+愤怒",
        "color": "#2563eb",
    },
    "scientific_objective": {
        "label": "科学客观叙事",
        "core": "基于数据和科学证据的客观呈现",
        "ethical_concern": "可能忽略不能量化的伦理/情感维度，或选择性呈现数据",
        "emotion": "中性",
        "color": "#16a34a",
    },
    "fear_alert": {
        "label": "恐惧预警叙事",
        "core": "如果不立即采取行动将面临灾难",
        "ethical_concern": "可能夸大风险驱动恐慌行为，或为过度干预提供借口",
        "emotion": "恐惧",
        "color": "#ea580c",
    },
    "economic_interest": {
        "label": "经济利益叙事",
        "core": "争论的实质是经济资源/利益的争夺",
        "ethical_concern": "可能将非经济价值(健康/环境/文化)简化为经济计算",
        "emotion": "实用主义",
        "color": "#ca8a04",
    },
    "cultural_identity": {
        "label": "文化认同叙事",
        "core": "问题关乎文化传统/身份认同的存续",
        "ethical_concern": "可能将正常的文化演化框架化为'灭绝/污染'",
        "emotion": "焦虑+怀旧",
        "color": "#7c3aed",
    },
}


class NarrativeBattlefieldAnalyzer:
    """叙事战场分析器"""

    @staticmethod
    def detect_narratives(
        text: str = "",
        title: str = "",
        source_platform: str = "",
    ) -> NarrativeBattlefieldResult:
        """检测竞争叙事"""
        import re

        result = NarrativeBattlefieldResult(
            event_title=title,
            event_url="",
            disclaimer="⚠️ 本分析不判定哪个叙事是'正确的'。每个叙事可能包含部分真相，可能指称上不假但伦理上可争议。目的是展示叙事景观，帮助读者理解信息的多层复杂性。",
        )

        text_lower = text.lower()

        detected = []

        # 受害者叙事
        victim_signals = ["伤害", "侵犯", "打压", "制裁", "歧视", "欺负", "掠夺", "不公"]
        if any(w in text for w in victim_signals):
            n = NarrativeFrame(
                narrative_id=hashlib.md5("victim".encode()).hexdigest()[:8],
                narrative_label=NARRATIVE_TEMPLATES["victim_national"]["label"],
                core_claim=NARRATIVE_TEMPLATES["victim_national"]["core"],
                ethical_assessment=NARRATIVE_TEMPLATES["victim_national"]["ethical_concern"],
                emotional_appeal=NARRATIVE_TEMPLATES["victim_national"]["emotion"],
                color=NARRATIVE_TEMPLATES["victim_national"]["color"],
                evidence_quality=0.4,
                logical_coherence=0.5,
                strength=0.7,
            )
            detected.append(n)

        # 英雄守护叙事
        hero_signals = ["守护", "捍卫", "保护", "抗争", "反抗", "英雄", "保卫"]
        if any(w in text for w in hero_signals):
            n = NarrativeFrame(
                narrative_id=hashlib.md5("hero".encode()).hexdigest()[:8],
                narrative_label=NARRATIVE_TEMPLATES["hero_defender"]["label"],
                core_claim=NARRATIVE_TEMPLATES["hero_defender"]["core"],
                ethical_assessment=NARRATIVE_TEMPLATES["hero_defender"]["ethical_concern"],
                emotional_appeal=NARRATIVE_TEMPLATES["hero_defender"]["emotion"],
                color=NARRATIVE_TEMPLATES["hero_defender"]["color"],
                evidence_quality=0.5,
                logical_coherence=0.6,
                strength=0.65,
            )
            detected.append(n)

        # 恐惧预警叙事
        fear_signals = ["致癌", "有毒", "致命", "危险", "毁灭", "崩溃", "末日", "不可逆转"]
        if any(w in text for w in fear_signals):
            n = NarrativeFrame(
                narrative_id=hashlib.md5("fear".encode()).hexdigest()[:8],
                narrative_label=NARRATIVE_TEMPLATES["fear_alert"]["label"],
                core_claim=NARRATIVE_TEMPLATES["fear_alert"]["core"],
                ethical_assessment=NARRATIVE_TEMPLATES["fear_alert"]["ethical_concern"],
                emotional_appeal=NARRATIVE_TEMPLATES["fear_alert"]["emotion"],
                color=NARRATIVE_TEMPLATES["fear_alert"]["color"],
                evidence_quality=0.35,
                logical_coherence=0.45,
                strength=0.8,
            )
            detected.append(n)

        # 科学客观叙事
        science_signals = ["研究", "数据", "证据", "实验", "统计", "论文", "期刊", "WHO", "CDC"]
        if any(w in text for w in science_signals):
            n = NarrativeFrame(
                narrative_id=hashlib.md5("science".encode()).hexdigest()[:8],
                narrative_label=NARRATIVE_TEMPLATES["scientific_objective"]["label"],
                core_claim=NARRATIVE_TEMPLATES["scientific_objective"]["core"],
                ethical_assessment=NARRATIVE_TEMPLATES["scientific_objective"]["ethical_concern"],
                emotional_appeal=NARRATIVE_TEMPLATES["scientific_objective"]["emotion"],
                color=NARRATIVE_TEMPLATES["scientific_objective"]["color"],
                evidence_quality=0.75,
                logical_coherence=0.8,
                strength=0.5,
            )
            detected.append(n)

        # 经济利益叙事
        economic_signals = ["利益", "资本", "利润", "垄断", "市场", "钱", "损失"]
        if any(w in text for w in economic_signals):
            n = NarrativeFrame(
                narrative_id=hashlib.md5("economic".encode()).hexdigest()[:8],
                narrative_label=NARRATIVE_TEMPLATES["economic_interest"]["label"],
                core_claim=NARRATIVE_TEMPLATES["economic_interest"]["core"],
                ethical_assessment=NARRATIVE_TEMPLATES["economic_interest"]["ethical_concern"],
                emotional_appeal=NARRATIVE_TEMPLATES["economic_interest"]["emotion"],
                color=NARRATIVE_TEMPLATES["economic_interest"]["color"],
                evidence_quality=0.5,
                logical_coherence=0.6,
                strength=0.55,
            )
            detected.append(n)

        result.narratives = detected

        if detected:
            result.dominant_narrative = max(detected, key=lambda n: n.strength)

            # 叙事冲突
            for i, n1 in enumerate(detected):
                for n2 in detected[i+1:]:
                    if n1.narrative_label != n2.narrative_label:
                        result.narrative_conflicts.append({
                            "narrative_a": n1.narrative_label,
                            "narrative_b": n2.narrative_label,
                            "tension": f"'{n1.core_claim[:60]}' vs '{n2.core_claim[:60]}'",
                        })

            # 道德模糊度 = 竞争叙事越多越模糊
            result.moral_ambiguity_score = min(1.0, len(detected) * 0.2)

            result.summary = f"检测到 {len(detected)} 个竞争叙事: {', '.join(n.narrative_label for n in detected)}。"
            result.summary += f"主导叙事: {result.dominant_narrative.narrative_label}。"
            result.summary += f"道德模糊度: {result.moral_ambiguity_score:.0%}。"
        else:
            result.summary = "未检测到显著的竞争叙事框架。该内容可能以单一叙事呈现。"

        return result


def analyze_narrative_battlefield(
    text: str = "",
    title: str = "",
) -> NarrativeBattlefieldResult:
    return NarrativeBattlefieldAnalyzer.detect_narratives(text, title)
