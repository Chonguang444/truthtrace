"""
TruthTrace 严格逻辑推理框架 — 替代简单加法评分的7层证据体系

## 当前问题

之前的评分公式是线性加法: base=50 + distortion_weight + fallacy_weight + ...
这种设计的根本缺陷:
1. 将所有发现视为独立事件(实际失真之间存在因果链)
2. 没有证据等级概念("匿名网友说"和"GB2760原文"被同等对待)
3. 没有假设检验 — "如果声称X为真, 我们应该还能观察到Y"
4. 没有乘法风险 — "来源完全伪造"+"内容存在情感操纵" 的风险远超两者之和

## 新框架

### 7级证据金字塔
L7: 多源一致确认 (≥2个独立权威来源)
L6: 单一权威来源 (国标/法律/WHO报告/同行评审meta分析)
L5: 专家共识 (≥1个同行评审研究)
L4: 可靠二手来源 (主流媒体/官方机构)
L3: 有限证据 (单一研究/初步报告)
L2: 弱证据 (目击者/匿名来源/个人经历)
L1: 零证据 (无来源声称)

### 因果链分析
失真不是独立发生的。典型的因果链:
"来源不可验证" → "错误引用研究" → "忽略语境(剂量)" → "情感操纵" → "制造恐慌"
每一步为下一步提供了条件。

### 假设检验
对于每条核心主张, 检查:
- 如果此主张为真, 我们还应观察到什么?
- 我们是否确实观察到了那些?
- 是否存在另一种解释也能解释观察到的现象?

### 乘法风险模型
风险 = Σ(独立维度) × Π(连锁维度)
独立维度正常加法, 形成因果链的维度乘法加成。

### 源-主张一致性
当信息声称"引用来源A"时, 检查:
- 来源A是否真实存在
- 来源A是否确实说了被引用的内容
- 来源A的结论是否在被传播中被升级(条件→绝对)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import re
import logging

logger = logging.getLogger("truthtrace.logic")


# =============================================================================
# 7级证据金字塔
# =============================================================================

class EvidenceLevel(Enum):
    """证据等级 — 从最弱到最强"""
    NONE = 0           # 零证据: 无来源声称, 纯断言
    WEAK = 1           # 弱证据: 目击者/匿名来源/个人经历
    LIMITED = 2        # 有限: 单一研究/初步报告/预印本
    MODERATE = 3       # 中等: 可靠二手来源(主流媒体/官方机构)
    STRONG = 4         # 强: 专家共识, ≥1个同行评审研究
    AUTHORITATIVE = 5  # 权威: 单一权威来源(国标/法律/WHO/系统评价)
    CONVERGENT = 6     # 收敛: ≥2个独立权威来源交叉确认


def classify_evidence_level(claim: str, source: str, source_type: str = "") -> EvidenceLevel:
    """自动分类一条主张的证据等级"""
    if not source or source in ("未知", "unknown", "据传", "据说", "传闻"):
        return EvidenceLevel.NONE

    # L7: 多源确认
    if ";" in source and any(kw in source for kw in ("GB", "WHO", "JECFA", "FDA", "IPCC", "标准")):
        return EvidenceLevel.CONVERGENT

    # L6: 单一权威
    authority_markers = [
        "GB ", "国家标准", "WHO", "JECFA", "IARC", "FDA", "IPCC",
        "NMPA", "CFSA", "IMF", "BIS", "中华人民共和国", "全国人大",
        "国务院", "最高人民法院", "Meta分析", "系统评价", "Systematic Review",
    ]
    if any(m in source for m in authority_markers):
        return EvidenceLevel.AUTHORITATIVE

    # L5: 专家共识/研究
    research_markers = ["研究", "论文", "发表", "期刊", "DOI", "RCT", "双盲", "doi"]
    if any(m in source for m in research_markers):
        return EvidenceLevel.STRONG

    # L4: 可靠二手
    reliable_media = ["新华社", "人民日报", "央视", "Reuters", "AP", "BBC", "环球时报"]
    if any(m in source for m in reliable_media):
        return EvidenceLevel.MODERATE

    # L3: 有限
    if "调查" in source or "报告" in source or "统计" in source:
        return EvidenceLevel.LIMITED

    # L2: 弱
    if any(kw in source for kw in ("网友", "匿名", "爆料", "透露", "据说", "听说")):
        return EvidenceLevel.WEAK

    # 有来源但无法归类 → 默认有限
    return EvidenceLevel.LIMITED if source else EvidenceLevel.NONE


# =============================================================================
# 证据等级语义
# =============================================================================
EVIDENCE_LEVEL_DESCRIPTIONS = {
    EvidenceLevel.NONE: "该主张没有任何可验证的来源——这是一个裸断言。在严谨的逻辑体系中, 裸断言不能作为进一步推理的前提。",
    EvidenceLevel.WEAK: "只有匿名/模糊来源的声称。这类声称在逻辑上不能被采信, 但因为无法证伪, 也不能被直接驳回。",
    EvidenceLevel.LIMITED: "有来源但来源的可信度有限(单一调查/非同行评审报告/统计口径不明)。这类证据可以作为线索, 但不能单独支撑结论。",
    EvidenceLevel.MODERATE: "可靠二手来源。可以作为推理的依据, 但仍需要寻找一手来源进行交叉验证。",
    EvidenceLevel.STRONG: "同行评审的研究或权威机构的评估。作为推理依据是可靠的, 但需要注意研究的局限性和适用范围。",
    EvidenceLevel.AUTHORITATIVE: "国家标准/法律/国际组织正式报告。这类来源具有公认的权威性, 可以直接作为证据采纳。",
    EvidenceLevel.CONVERGENT: "多个独立权威来源交叉确认。这是可达到的最高证据等级——当2+个独立来源得出一致结论时, 该结论具有极高的可靠性。",
}


# =============================================================================
# 因果链分析
# =============================================================================

class DistortionCausalChain:
    """
    失真因果链分析 — 识别失真之间的因果关系

    典型因果链模式:
    1. 来源不可验证 → 错误引用研究 → 忽略语境 → 情感操纵
       (没有来源 → 可以随意曲解 → 脱离剂量谈毒性 → 制造恐慌)

    2. 错误引用 → 以偏概全 → 滑坡论证
       (引用A且曲解A → 扩展到所有情况 → 推导极端后果)

    3. 权威绑架 → 错误类比 → 虚假二分
       (虚假权威背书 → 不当类比 → 非黑即白)
    """

    # 已知的因果链模式 (前件→后件)
    CAUSAL_PATTERNS = [
        ("source_fabrication", "misquotation", "来源伪造使错误引用成为可能"),
        ("source_fabrication", "authority_abuse", "虚假来源常伴随虚假权威"),
        ("misquotation", "context_stripping", "错误引用后必然忽略原始语境"),
        ("context_stripping", "emotional_manipulation", "脱离语境后便于情感操纵"),
        ("emotional_manipulation", "fear_mongering", "情感操纵→恐惧营销是自然延伸"),
        ("false_cause", "slippery_slope", "虚假因果→滑坡论证是逻辑链条的延长"),
        ("cherry_picking", "false_balance", "选择性证据→虚假平衡是制造争议假象"),
        ("equivocation", "straw_man", "偷换概念后攻击稻草人是标准手法"),
    ]

    @classmethod
    def analyze(cls, detected_distortions: list[str],
                detected_fallacies: list[str]) -> list[dict]:
        """
        分析检测到的失真和谬误之间是否存在因果链。

        Returns: [
            {"chain": ["A→B→C"], "description": "...", "confidence": "high"},
        ]
        """
        all_detected = set(detected_distortions + detected_fallacies)
        chains_found = []

        for cause, effect, description in cls.CAUSAL_PATTERNS:
            cause_type = cause.split(".")[-1] if "." in cause else cause
            effect_type = effect.split(".")[-1] if "." in effect else effect

            # 模糊匹配 — 检查是否包含相关失真类型
            cause_found = any(cause_type in d for d in all_detected)
            effect_found = any(effect_type in d for d in all_detected)

            if cause_found and effect_found:
                chains_found.append({
                    "cause": cause, "effect": effect,
                    "description": f"{description}: {cause} → {effect}",
                    "confidence": "high" if cause_found and effect_found else "moderate",
                })

        # 尝试发现更长的连锁
        chains = [c["cause"] for c in chains_found] + [c["effect"] for c in chains_found]
        chain_paths = cls._find_chains(chains_found)

        return {
            "individual_links": chains_found,
            "chain_paths": chain_paths,
            "has_chain": len(chains_found) > 0,
            "assessment": cls._assess_chain_risk(chains_found),
        }

    @classmethod
    def _find_chains(cls, links: list[dict]) -> list[list[str]]:
        """从单独的因果对中发现长链"""
        if len(links) < 2:
            return []

        graphs = {}
        for link in links:
            cause = link["cause"]
            effect = link["effect"]
            if cause not in graphs:
                graphs[cause] = []
            graphs[cause].append(effect)

        paths = []
        for start in graphs:
            path = [start]
            current = start
            for _ in range(5):  # 最长5步
                if current in graphs and graphs[current][0] not in path:
                    current = graphs[current][0]
                    path.append(current)
                else:
                    break
            if len(path) >= 3:
                paths.append(path)

        return paths

    @classmethod
    def _assess_chain_risk(cls, links: list[dict]) -> str:
        if len(links) >= 3:
            return "检测到复杂的失真因果链——该信息的问题不是孤立的, 而是系统性地层层递进的。每一步失真为下一步创造了条件。这强烈暗示信息被有意构造而非偶然出错。"
        elif len(links) >= 2:
            return "检测到失真之间的因果关联——多个失真不是独立发生的, 而是逻辑上相互关联的。"
        elif len(links) == 1:
            return "检测到单一的因果关联。"
        return "未检测到失真的因果链——但失真之间仍可能存在未被识别的关联。"


# =============================================================================
# 假设检验框架
# =============================================================================

@dataclass
class HypothesisTest:
    """一条假设检验"""
    claim: str = ""
    if_true_prediction: str = ""
    observed: bool | None = None
    alternative_explanation: str = ""
    result: str = ""


class HypothesisTester:
    """
    假设检验 — 科学方法的核心

    对每条核心主张进行检验:
    1. 如果这个主张为真, 我们还应观察到什么?
    2. 这个预测是可以检验的吗?
    3. 我们是否观察到了预测的现象?
    4. 是否有另一种解释也能解释观察到的现象?
    """

    # 常见主张→可检验预测的映射
    CLAIM_PREDICTIONS = {
        # 食品安全
        "致癌": {
            "if_true": "长期大规模流行病学研究应一致显示发病率增加, 毒理学应确认致癌机制, 动物实验应呈剂量-效应关系",
            "alternative": "IARC分类≠确认致癌。2B类意味着'证据有限'。需要进行具体物质的毒理学评估。",
        },
        "添加剂": {
            "if_true": "如果某种添加剂在标准范围内使用有实际危害, WHO/JECFA的评估报告应该被修订, 各国监管机构应该采取行动",
            "alternative": "不同的食品安全标准体系有各自的历史和技术原因。'被禁用'不等于'有毒'。",
        },
        # 医疗
        "疫苗": {
            "if_true": "如果疫苗导致某疾病, 大规模(n>100万)的流行病学研究应一致显示风险增加, 且机制应在生物学上合理",
            "alternative": "不良事件≠不良反应。时间上的先后关系≠因果关系。需要RCT或大样本队列研究来建立因果。",
        },
        "治愈": {
            "if_true": "如果某疗法能'治愈'某疾病(非自限性疾病), 应有RCT证据, 效应量大, 结果可复现, 经同行评审发表",
            "alternative": "自发性缓解/安慰剂效应/同时接受了其他治疗/自然病程/选择性报告成功案例",
        },
        # 经济
        "崩溃": {
            "if_true": "如果经济即将崩溃, 应观察到: 外汇储备急剧下降, 主权CDS利差飙升, 资本大量外逃, 银行间流动性枯竭",
            "alternative": "经济指标的周期性波动≠崩溃。标准差范围内的波动是正常的。经济预测的准确性历来很低。",
        },
        # 环境
        "变暖": {
            "if_true": "如果全球变暖是骗局: 多个独立国家的卫星和地面数据应一致, IPCC参与科学家应站出来揭露, 化石燃料公司资助的研究应找到确凿反证",
            "alternative": "局部天气≠全球气候。97%+科学家共识不等于100%——科学中没有绝对但共识是压倒性的。",
        },
    }

    @classmethod
    def test_claim(cls, claim: str, domain: str = "general",
                   available_evidence: dict | None = None) -> HypothesisTest:
        """对一条主张进行假设检验"""
        test = HypothesisTest(claim=claim)

        # 匹配已知的主张类型
        for pattern, info in cls.CLAIM_PREDICTIONS.items():
            if pattern in claim:
                test.if_true_prediction = info["if_true"]
                test.alternative_explanation = info.get("alternative", "")

                # 检查是否有支持证据
                if available_evidence:
                    # 简化: 检查是否有权威来源
                    has_authoritative = any(
                        v.get("level") in ("authoritative", "convergent")
                        for v in available_evidence.values()
                        if isinstance(v, dict)
                    )
                    if has_authoritative:
                        test.observed = True
                        test.result = "supported_by_multiple_sources"
                    else:
                        test.observed = False
                        test.result = "insufficient_evidence"
                else:
                    test.result = "inconclusive—无法在当前信息条件下判断"

                return test

        # 未匹配到已知模式 — 给出通用的可检验预测
        test.if_true_prediction = f"如果'{claim[:60]}...'为真, 应能找到至少2个独立的、可验证的权威来源支持这一主张。这些来源应来自不同机构/研究者, 且在其专业领域内有公认资质。"
        test.result = "inconclusive—需要用户进一步提供证据或引用来源"
        return test

    @classmethod
    def batch_test(cls, claims: list[str], domain: str = "general") -> list[HypothesisTest]:
        """批量假设检验"""
        return [cls.test_claim(c, domain) for c in claims[:10]]

    @classmethod
    def overall_assessment(cls, tests: list[HypothesisTest]) -> str:
        """基于假设检验的综合评估"""
        if not tests:
            return "无可用假设检验"

        supported = sum(1 for t in tests if t.result and "support" in t.result)
        refuted = sum(1 for t in tests if t.result and "refute" in t.result)
        inconclusive = len(tests) - supported - refuted

        if supported >= 2:
            return f"{len(tests)}条主张中, {supported}条得到支撑——但需注意支撑与证实之间的区别。"
        elif refuted >= 2:
            return f"{len(tests)}条主张中, {refuted}条与已知证据不符——该信息的可信度存疑。"
        else:
            return f"{len(tests)}条主张中, {inconclusive}条缺乏足够证据进行判断。在当前信息条件下, 该信息无法被证实或证伪。"


# =============================================================================
# 乘法风险评分模型
# =============================================================================

class MultiplicativeRiskModel:
    """
    乘法风险评分 — 替代简单加法

    原理: 某些风险因素形成因果链时, 风险是乘法的而非加法的。

    独立维度(加法): 单独的失真匹配、谬误匹配
    因果链维度(乘法): 失真因果链、模态漂移链、拼接链

    score = 50 - (独立风险之和) × (1 + 因果链加成系数)
    """

    @classmethod
    def compute(cls,
                distortion_count: int = 0,
                fallacy_count: int = 0,
                stat_risk: float = 0.0,
                independent_risks: list[float] | None = None,
                causal_chain_count: int = 0,
                causal_chain_length: int = 0,
                modality_drift_score: float = 0.0,
                manipulation_score: float = 0.0,
                source_credibility: float = 50.0,
                evidence_average_level: float = 2.0,
                hypothesis_supported: int = 0,
                hypothesis_refuted: int = 0,
    ) -> tuple[float, dict]:
        """
        计算乘法风险评分。

        Returns: (final_score, breakdown_dict)
        """
        # ---- 独立风险 (加法) ----
        independent_penalty = 0.0

        # 失真 — 每个失真扣3分, 最多30
        independent_penalty += min(30.0, distortion_count * 3.0)

        # 谬误 — 每个谬误扣4分, 最多20
        independent_penalty += min(20.0, fallacy_count * 4.0)

        # 统计滥用
        independent_penalty += stat_risk * 0.15

        # 模态漂移
        independent_penalty += modality_drift_score * 0.1

        # ---- 因果链 (乘法) ----
        # 因果链越长, 乘法系数越大
        # 1条链+1.2x, 2条链+1.5x, ≥3条链+2.0x
        chain_multiplier = 1.0
        if causal_chain_count >= 3:
            chain_multiplier = 2.0
        elif causal_chain_count >= 2:
            chain_multiplier = 1.5
        elif causal_chain_count >= 1:
            chain_multiplier = 1.2

        # 因果链长度额外加成
        if causal_chain_length >= 4:
            chain_multiplier += 0.3
        elif causal_chain_length >= 3:
            chain_multiplier += 0.15

        # 叙事操纵大幅度加成
        if manipulation_score > 60:
            chain_multiplier += 0.5
        elif manipulation_score > 30:
            chain_multiplier += 0.2

        # ---- 计算惩罚 ----
        # 权威来源的内容特征(精确数字/引用格式)是正常的, 不是操纵信号
        # CONVERGENT(6): 多源确认 → 惩罚几乎为零 (相信权威来源)
        # AUTHORITATIVE(5): 国标/WHO → 惩罚极低
        # 匿名来源: 完整惩罚
        evidence_discount = 1.0
        if evidence_average_level >= 6:
            evidence_discount = 0.02      # 政府/WHO/多源确认 — 2%罚分
        elif evidence_average_level >= 5:
            evidence_discount = 0.08      # 权威单一来源 — 8%罚分
        elif evidence_average_level >= 4:
            evidence_discount = 0.25      # 强证据 — 25%罚分
        elif evidence_average_level >= 3:
            evidence_discount = 0.45      # 中等 — 45%罚分
        # else: 完整罚分(1.0)

        total_penalty = independent_penalty * chain_multiplier * evidence_discount

        # ---- 来源可信度和证据等级加权 ----
        if source_credibility >= 90:
            base_bonus = 30.0
        elif source_credibility >= 70:
            base_bonus = 18.0
        else:
            # 来源未知但也没有明显问题 → 保持中性, 不扣分不奖分
            base_bonus = 0.0

        # 如果独立扣分很低(内容本身无明显问题), 不应该判为虚假
        # 这是"不确定"和"虚假"之间的关键区分
        if independent_penalty < 5.0 and chain_multiplier < 1.1:
            # 内容本身没大问题 → 至少是中性(40+)
            base_bonus = max(base_bonus, 10.0)

        # ---- 来源和证据等级调整 ----
        # 权威来源上浮基准, 未知来源不惩罚 (惩罚由 pattern matches 驱动)
        credibility_bonus = 0.0
        if source_credibility >= 90 and evidence_average_level >= 5:
            credibility_bonus = 15.0        # 政府/WHO + 多源确认
        elif source_credibility >= 70:
            credibility_bonus = 8.0         # 学术/可靠媒体
        elif source_credibility >= 50:
            credibility_bonus = 3.0         # 网络媒体
        # else: 0.0 — 匿名/未知来源不奖励也不惩罚

        # ---- 假设检验调整 ----
        hypothesis_bonus = 0.0
        if hypothesis_supported >= 2:
            hypothesis_bonus += 5.0
        if hypothesis_refuted >= 2:
            total_penalty += 10.0

        # ---- 最终评分 ----
        base = 50.0
        adjusted_base = base + credibility_bonus
        final = adjusted_base - total_penalty + hypothesis_bonus
        final = max(0.0, min(100.0, final))

        # ---- 判定 ----
        # 证据等级影响判定阈值: 权威来源的阈值更低
        from app.engine.types import Verdict
        if evidence_average_level >= 5:     # 权威/收敛级
            true_threshold, misleading_threshold = 55, 35
        elif evidence_average_level >= 3:   # 中等/强
            true_threshold, misleading_threshold = 65, 40
        else:
            true_threshold, misleading_threshold = 75, 50

        if final >= true_threshold:
            verdict = Verdict.LIKELY_TRUE
        elif final >= misleading_threshold:
            verdict = Verdict.MISLEADING
        elif final >= 25:
            verdict = Verdict.LIKELY_FALSE
        else:
            verdict = Verdict.FALSE

        breakdown = {
            "base_score": 50.0,
            "independent_penalty": round(independent_penalty, 1),
            "chain_multiplier": round(chain_multiplier, 2),
            "total_penalty": round(total_penalty, 1),
            "source_credibility": round(source_credibility, 1),
            "evidence_avg_level": round(evidence_average_level, 1),
            "credibility_bonus": round(credibility_bonus, 1),
            "hypothesis_bonus": round(hypothesis_bonus, 1),
            "final_score": round(final, 1),
            "verdict": verdict.value,
        }

        return round(final, 1), breakdown


# =============================================================================
# 源-主张验证 (内置版本)
# =============================================================================

class SourceClaimVerifier:
    """
    快速检测: 信息中引用的来源是否真正支撑其主张

    虽然无法自动访问被引用的原始来源,
    但可以通过文本中的引用模式识别潜在的不一致:
    """

    @classmethod
    def check_citation_consistency(cls, text: str) -> list[dict]:
        """
        检测文本中的引用一致性。

        检测信号:
        1. 引用"研究表明"但没有具体研究名称
        2. 引用具体名称但主张中使用绝对化词汇(研究很少用"证实")
        3. 精确数字无误差范围
        4. 引用中包含了推测性词汇但结论是确定的
        """
        findings = []

        # 找到"研究X表明Y"的模式
        citations = re.findall(
            r'(?:根据|据|按照|依照)'
            r'((?:.{0,5})?(?:研究|报告|数据|统计|调查|标准|法规|论文)'
            r'(?:.{0,30})?)'
            r'(?:显示|表明|发现|指出|认为|确认|证实|证明)'
            r'(.{0,100}(?:[。！；\n]|$))',
            text
        )

        for source, claim in citations[:10]:
            source = source.strip()
            claim = claim.strip()

            # 检查引用是否有具体来源
            has_specific = bool(re.search(
                r'(?:GB\s*\d|WHO|JECFA|FDA|IPCC|标准|法规|条文|第\d|DOI|doi|PMID)',
                source, re.IGNORECASE
            ))

            # 检查主张中是否出现绝对化词汇
            has_certainty = bool(re.search(
                r'(?:证实|证明|肯定|必然|毫无疑问|100\%|百分之百|绝对)',
                claim
            ))

            # 检查主张中是否有精确数字
            has_precise_number = bool(re.search(r'\d{2,3}\.\d{2,}', claim))

            if not has_specific and len(source) < 5:
                findings.append({
                    "type": "blurry_citation",
                    "source": source,
                    "claim": claim[:80],
                    "issue": "引用了模糊的'研究/数据'但没有给出具体研究名称、链接或任何可验证的信息",
                    "severity": "high",
                })

            if has_certainty and not has_specific:
                findings.append({
                    "type": "certainty_without_source",
                    "source": source,
                    "claim": claim[:80],
                    "issue": f"使用'证实/证明/肯定'等确定性词汇, 但引用来源不明确",
                    "severity": "high",
                })

            if "推测" in source or "可能" in source or "或许" in source:
                if has_certainty:
                    findings.append({
                        "type": "speculation_to_certainty",
                        "source": source,
                        "claim": claim[:80],
                        "issue": "来源使用了推测性语言, 但结论是确定性的——科学中的不确定性在传播中被消除了",
                        "severity": "medium",
                    })

        return findings


# =============================================================================
# 时序推理
# =============================================================================

class TemporalReasoner:
    """
    时序推理 — 在时间维度上分析信息

    关键问题:
    1. 该主张在发出时, 发布者应该/可能知道什么?
    2. 之后出现的新信息是支持还是反驳了该主张?
    3. 是否存在利用事后信息包装为预知的操纵?
    """

    @classmethod
    def analyze_temporal(cls, published_at: Optional[datetime],
                         claims: list[str],
                         subsequent_evidence: list[dict] | None = None) -> dict:
        """
        时序分析。

        如果主张发表后出现了新的权威证据:
        - 如果新证据支持主张 → 主张的可信度上升
        - 如果新证据反驳主张 → 主张可能当时合理但已过时
        - 如果主张声称预知了后续事件 → 需要检查时间线
        """
        if not published_at:
            return {"assessment": "无发布时间信息, 无法进行时序推理"}

        now = datetime.now(timezone.utc)
        age_days = (now - published_at).days

        findings = []

        # 基本信息
        findings.append(f"信息发布于 {age_days} 天前 ({published_at.strftime('%Y-%m-%d')})")

        # 检查是否是旧闻翻新
        if age_days > 365 and any(kw in " ".join(claims) for kw in ("刚刚", "最新", "突发", "今天")):
            findings.append("⚠️ 信息使用了'刚刚/突发/最新'等时效性词汇但实际发布时间超过1年——旧闻翻新")

        # 检查是否有事后证据
        if subsequent_evidence:
            supporting = sum(1 for e in subsequent_evidence if e.get("supports", False))
            refuting = sum(1 for e in subsequent_evidence if not e.get("supports", False))
            if refuting > supporting:
                findings.append(f"后续证据: {refuting}条反驳 vs {supporting}条支持。该主张可能当时合理但已被更新的证据推翻。")
            elif supporting > refuting:
                findings.append(f"后续证据倾向于支持该主张 ({supporting}条 vs {refuting}条)")

        return {
            "published_at": published_at.isoformat(),
            "age_days": age_days,
            "findings": findings,
            "assessment": "; ".join(findings) if findings else "无显著的时序问题",
        }


# =============================================================================
# 综合推理引擎 (整合以上所有)
# =============================================================================

@dataclass
class RigorousAnalysis:
    """严格逻辑分析的综合输出"""
    # 原始10引擎结果
    engine_results: dict = field(default_factory=dict)

    # 新维度
    evidence_hierarchy: dict = field(default_factory=dict)     # 每条主张的证据等级
    causal_chains: dict = field(default_factory=dict)           # 失真因果链
    hypothesis_tests: list[HypothesisTest] = field(default_factory=list)
    source_claim_issues: list[dict] = field(default_factory=list)
    temporal_analysis: dict = field(default_factory=dict)
    risk_breakdown: dict = field(default_factory=dict)          # 乘法评分细节

    # 最终判定
    verdict: str = ""
    credibility_score: float = 50.0
    confidence: str = "moderate"

    # 逻辑摘要
    logical_summary: str = ""
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "evidence_hierarchy": self.evidence_hierarchy,
            "causal_chains": self.causal_chains,
            "hypothesis_tests": [
                {"claim": t.claim, "if_true": t.if_true_prediction,
                 "result": t.result, "alternative": t.alternative_explanation}
                for t in self.hypothesis_tests
            ],
            "source_claim_issues": self.source_claim_issues,
            "temporal_analysis": self.temporal_analysis,
            "risk_breakdown": self.risk_breakdown,
            "verdict": self.verdict,
            "credibility_score": self.credibility_score,
            "confidence": self.confidence,
            "logical_summary": self.logical_summary,
            "recommendations": self.recommendations,
        }


async def run_rigorous_analysis(
    title: str = "",
    text: str = "",
    url: str = "",
    author: str = "",
    platform: str = "",
    published_at: Optional[datetime] = None,
    existing_10engine_result: Optional[dict] = None,
    expert_domains: list[str] | None = None,
) -> RigorousAnalysis:
    """
    执行严格逻辑分析。

    这是替代简单加法评分的新推理入口。
    集成了: 证据等级 + 因果链 + 假设检验 + 源-主张验证 + 时序推理 + 乘法评分
    """
    analysis = RigorousAnalysis()

    # 1. 如果需要, 先运行10引擎
    engine_result = existing_10engine_result
    if not engine_result and text:
        from app.engine.reasoning import run_reasoning_pipeline
        r = await run_reasoning_pipeline(url=url, title=title, text=text,
                                         author=author, platform=platform)
        engine_result = r.to_dict()
        analysis.engine_results = engine_result
    else:
        analysis.engine_results = engine_result or {}

    # 2. 证据等级分析
    # 从引擎结果和文本中提取主张, 分类证据等级
    claims_sources = []
    # 从失真匹配中提取
    for m in engine_result.get("distortion_analysis", {}).get("matches", [])[:5]:
        if m.get("evidence_snippet"):
            claims_sources.append((m["evidence_snippet"][:100], m.get("description", "")))

    evidence_levels = {}
    for claim, desc in claims_sources:
        level = classify_evidence_level(claim, desc)
        evidence_levels[claim[:60]] = {
            "level": level.name,
            "level_num": level.value,
            "description": EVIDENCE_LEVEL_DESCRIPTIONS.get(level, ""),
        }

    # 计算平均证据等级 — 权威URL覆盖从模式匹配得到的低分
    if any(d in url for d in ("gov.cn", "who.int", "edu.cn", "un.org", "stats.gov.cn", "samr.gov.cn", "pubmed", "doi.org", "nature.com", "science.org")):
        avg_level = EvidenceLevel.CONVERGENT.value  # 官方政府来源+学术数据库 → 最高等级
    elif any(d in url for d in ("xinhuanet", "people.com", "cctv.com", "britannica.com")):
        avg_level = EvidenceLevel.AUTHORITATIVE.value
    elif not evidence_levels:
        avg_level = EvidenceLevel.LIMITED.value
    else:
        avg_level = sum(v["level_num"] for v in evidence_levels.values()) / len(evidence_levels)

    analysis.evidence_hierarchy = {
        "claims_analyzed": len(evidence_levels),
        "average_level": round(avg_level, 1),
        "average_level_label": ["零证据","弱","有限","中等","强","权威","收敛"][min(6, int(avg_level))],
        "details": evidence_levels,
    }

    # 3. 因果链分析
    all_distortions = [
        m.get("distortion_type", "") for m in
        engine_result.get("distortion_analysis", {}).get("matches", [])
    ]
    all_fallacies = [
        m.get("fallacy_type", "") for m in
        engine_result.get("fallacy_analysis", {}).get("matches", [])
    ]
    analysis.causal_chains = DistortionCausalChain.analyze(all_distortions, all_fallacies)

    # 4. 假设检验
    claims = [
        c["text"] for c in
        engine_result.get("domain_analysis", {}).get("claims", [])[:5]
    ]
    domain = engine_result.get("domain_analysis", {}).get("domain", "general")
    analysis.hypothesis_tests = HypothesisTester.batch_test(claims, domain)

    # 5. 源-主张验证
    analysis.source_claim_issues = SourceClaimVerifier.check_citation_consistency(text)

    # 6. 时序分析
    analysis.temporal_analysis = TemporalReasoner.analyze_temporal(published_at, claims)

    # 7. 乘法风险评分
    # 获取来源质量评分 (域名权威度 + 基本指标)
    actual_source_cred = 50.0
    if url:
        from urllib.parse import urlparse
        try:
            hostname = urlparse(url).hostname or ""
        except Exception:
            hostname = ""

        # 权威域名列表 — 直接高分, 不需要内容指标
        AUTHORITY_DOMAINS = {
            "gov.cn": 95, "stats.gov.cn": 98, "samr.gov.cn": 95, "nhc.gov.cn": 95,
            "who.int": 98, "un.org": 98, "worldbank.org": 95, "imf.org": 95,
            "ipcc.ch": 95, "wmo.int": 95, "edu.cn": 85, ".edu": 85,
            "nmpa.gov.cn": 95, "cfsa.net.cn": 90, "xinhuanet.com": 75,
            "people.com.cn": 75, "cctv.com": 75, "pubmed": 85, "doi.org": 85,
            "nature.com": 85, "science.org": 85, "springer": 80, "sciencedirect": 80,
        }
        for domain, authority in AUTHORITY_DOMAINS.items():
            if domain in hostname:
                actual_source_cred = float(authority)
                break
        if actual_source_cred == 50.0:
            # 非权威域名 → 使用质量评估器
            from app.quality import SourceQualityEvaluator
            source_quality = SourceQualityEvaluator.evaluate(url)
            actual_source_cred = source_quality.get("quality_score", 50)

    chain_links = analysis.causal_chains.get("individual_links", [])
    chain_paths = analysis.causal_chains.get("chain_paths", [])
    max_chain_len = max((len(p) for p in chain_paths), default=0)

    h_supported = sum(1 for t in analysis.hypothesis_tests if t.result and "support" in t.result)
    h_refuted = sum(1 for t in analysis.hypothesis_tests if t.result and "refute" in t.result)

    score, breakdown = MultiplicativeRiskModel.compute(
        distortion_count=len(all_distortions),
        fallacy_count=len(all_fallacies),
        stat_risk=engine_result.get("statistical_analysis", {}).get("risk_score", 0),
        causal_chain_count=len(chain_links),
        causal_chain_length=max_chain_len,
        modality_drift_score=engine_result.get("modality_analysis", {}).get("drift_score", 0),
        manipulation_score=engine_result.get("narrative_analysis", {}).get("manipulation_score", 0),
        source_credibility=actual_source_cred,  # 使用域名权威度, 不是分析中的来源分
        evidence_average_level=avg_level,
        hypothesis_supported=h_supported,
        hypothesis_refuted=h_refuted,
    )

    analysis.credibility_score = score
    analysis.verdict = breakdown["verdict"]
    analysis.risk_breakdown = breakdown

    from app.engine.types import Confidence

    # 8. 综合判断
    # 特殊处理: 当所有引擎均未发现问题, 且来源不是权威来源时:
    # 这不是"misleading", 而是"unverifiable" — 无法证实也无法证伪
    total_signals = sum([
        len(all_distortions), len(all_fallacies), len(statMatches if 'statMatches' in dir() else []),
        len(chain_links), len(analysis.source_claim_issues), h_refuted,
        h_supported,
    ])
    if total_signals == 0 and actual_source_cred < 70 and not analysis.hypothesis_tests:
        # 零信号 + 非权威来源 = 无法判断, 保持中性
        analysis.verdict = "unverifiable"
        analysis.credibility_score = 50.0
        analysis.confidence = Confidence.LOW.value
        analysis.logical_summary = "未检测到任何操纵信号, 但信息来自非权威来源。无法在当前条件下做出更确定的判断。"
        analysis.recommendations = ["该信息未显示明显的操纵迹象, 但来源的可靠性无法验证。建议在采信之前寻找权威来源进行交叉核实。"]
        return analysis

    factors_present = sum([
        len(all_distortions) > 0,
        len(all_fallacies) > 0,
        len(chain_links) > 0,
        len(analysis.source_claim_issues) > 0,
        h_refuted > 0,
    ])
    if factors_present >= 3:
        analysis.confidence = Confidence.HIGH.value
    elif factors_present >= 1:
        analysis.confidence = Confidence.MODERATE.value
    else:
        analysis.confidence = Confidence.LOW.value

    # 9. 逻辑摘要
    parts = []
    parts.append(f"证据等级: 平均{analysis.evidence_hierarchy['average_level_label']}({avg_level:.1f}/6)")
    if chain_links:
        parts.append(f"失真因果链: {len(chain_links)}条链接, 最长链{max_chain_len}步")
    if h_refuted > 0:
        parts.append(f"假设检验: {h_refuted}条主张缺乏证据支撑")
    if analysis.source_claim_issues:
        parts.append(f"引用问题: {len(analysis.source_claim_issues)}处")
    parts.append(f"评分: {score}/100 ({breakdown['verdict']})")

    analysis.logical_summary = " | ".join(parts)

    # 10. 建议
    analysis.recommendations = []
    if analysis.evidence_hierarchy["average_level"] < 2:
        analysis.recommendations.append("该信息依赖的证据等级很低——大多数主张缺乏可靠的来源支撑。建议在转发或采信之前寻找一手权威来源进行核实。")
    if chain_links:
        analysis.recommendations.append("检测到失真之间的因果链——这意味着该信息可能存在系统性的操纵, 而非偶然失误。")
    if h_refuted > 0:
        analysis.recommendations.append(f"有{h_refuted}条主张无法通过假设检验——这些主张缺乏可观测的证据支撑。")

    if not analysis.recommendations:
        analysis.recommendations.append("当前分析未发现显著的逻辑缺陷。但请注意: 缺乏检测到的缺陷不等于信息真实——这只是说系统没有发现明显的问题。")

    return analysis
