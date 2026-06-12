"""
TruthTrace 统一推理管线 — 10 大引擎整合

管线流程:
1. 失真检测 → 7种失真模式
2. 逻辑谬误检测 → 12种谬误
3. 统计素养检测 → 8种统计滥用
4. 拼接式造谣检测 → 5种逻辑拼接模式
5. 溯源深度分析 → 5层溯源
6. 领域知识验证 → 6大领域
7. 叙事框架识别 → 12种叙事框架
8. 模态梯度检测 → 5种漂移模式
9. 综合判定 → 可信度评分 + 判定
10. 辟谣建议 + 不确定性声明
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone

logger = logging.getLogger("truthtrace.reasoning")
from typing import Optional

from app.engine.types import (
    AnalysisResult, Verdict, Confidence,
    DistortionType, FallacyType, NarrativeType,
    ReasoningStep, Evidence, EvidenceType, EvidenceQuality,
)
from app.engine.distortion import detect_distortions
from app.engine.fallacy import detect_fallacies
from app.engine.statistical import detect_statistical_abuse
from app.engine.composite import detect_composite_fabrication
from app.engine.trace_depth import analyze_trace
from app.engine.domain_verifier import analyze_domain
from app.engine.narrative import detect_narratives
from app.engine.modality import detect_modality_drift
from app.engine.media_verifier import run_media_verification


# =============================================================================
# 综合判定逻辑
# =============================================================================

def _compute_verdict(
    distortion_risk: Confidence,
    fallacy_count: int,
    source_credibility: float,
    refuted_claims: list,
    manipulation_score: float,
    stat_risk: float = 0.0,
    composite_risk: float = 0.0,
    drift_score: float = 0.0,
    total_claims: int = 0,
) -> tuple[Verdict, float]:
    """综合各维度计算最终判定和可信度评分"""

    base = 50.0

    # 失真扣分
    if distortion_risk == Confidence.HIGH:
        base -= 30
    elif distortion_risk == Confidence.MODERATE:
        base -= 15

    # 逻辑谬误扣分
    base -= min(25.0, fallacy_count * 5.0)

    # 统计滥用扣分
    base -= stat_risk * 0.2

    # 拼接风险扣分
    base -= composite_risk * 0.2

    # 模态漂移扣分
    base -= drift_score * 0.15

    # 来源可信度加权
    base = base * 0.4 + source_credibility * 0.6

    # 被反驳主张扣分
    base -= min(30.0, len(refuted_claims) * 10.0)

    # 叙事操纵扣分
    if manipulation_score > 60:
        base -= 10
    elif manipulation_score > 30:
        base -= 5

    if total_claims > 0:
        verified_ratio = len(refuted_claims) / total_claims
        if verified_ratio < 0.2:
            base += 5

    score = max(0.0, min(100.0, base))

    if score >= 80:
        verdict = Verdict.LIKELY_TRUE
    elif score >= 60:
        verdict = Verdict.LIKELY_TRUE
    elif score >= 40:
        verdict = Verdict.MISLEADING
    elif score >= 20:
        verdict = Verdict.LIKELY_FALSE
    else:
        verdict = Verdict.FALSE

    return verdict, round(score, 1)


def _build_correction(
    verdict: Verdict,
    distortions: list,
    fallacies: list,
    refuted_claims: list,
    domain: str,
    narratives: list,
) -> tuple[str, list[str]]:
    """构建辟谣建议和参考文献列表"""

    correction_parts = []
    references = []

    # 失真说明
    if distortions:
        distortion_types = set(m.distortion_type for m in distortions)
        labels = []
        for dt in distortion_types:
            if dt == DistortionType.SOURCE_FABRICATION:
                labels.append("信息来源无法核实")
                references.append("请要求提供可查证的具体来源链接")
            elif dt == DistortionType.CONTEXT_STRIPPING:
                labels.append("关键语境/限定条件被省略")
                references.append("请查看原始信息的完整版本")
            elif dt == DistortionType.MISQUOTATION:
                labels.append("引用的信息/研究/数据可能被误读")
                references.append("请查证被引用的原始材料")
            elif dt == DistortionType.EMOTIONAL_MANIPULATION:
                labels.append("内容包含明显的情感操纵手法")
            elif dt == DistortionType.AUTHORITY_ABUSE:
                labels.append("存在虚假权威背书的迹象")
        correction_parts.append("该信息存在以下问题: " + "；".join(labels))

    # 逻辑谬误
    if fallacies:
        top_fallacies = fallacies[:3]
        fallacy_hints = [f.correction_hint for f in top_fallacies if f.correction_hint]
        if fallacy_hints:
            correction_parts.append("逻辑谬误提醒: " + fallacy_hints[0])
            references.append(fallacy_hints[0])

    # 被反驳的主张
    if refuted_claims:
        correction_parts.append(
            f"以下{len(refuted_claims)}条主张与已知事实不符或缺乏证据支撑"
        )
        for claim in refuted_claims[:3]:
            ref = claim.get("verification", {}).get("explanation", "")
            if ref:
                correction_parts.append(f"  • {claim['text'][:80]}... → {ref[:120]}")

    # 叙事框架
    if narratives and len(narratives) >= 2:
        correction_parts.append(
            "该信息嵌入了多种操纵性叙事框架。即使部分事实可能准确，"
            "叙事框架可能扭曲读者对事实的理解。建议剥离叙事外壳，关注可验证的具体事实。"
        )

    # 总体建议
    if verdict in (Verdict.FALSE, Verdict.LIKELY_FALSE):
        correction_parts.insert(0, "⚠️ 该信息经分析存在严重问题，建议不要采信或传播。")
    elif verdict == Verdict.MISLEADING:
        correction_parts.insert(0, "⚠️ 该信息存在误导性元素，建议进一步核实后再采信。")
    elif verdict in (Verdict.LIKELY_TRUE, Verdict.TRUE):
        correction_parts.insert(0, "该信息经初步分析未被发现重大问题，但自动分析存在局限性，建议结合人工判断。")
    else:
        correction_parts.insert(0, "无法对该信息做出确定判断，建议查阅权威来源进行人工核实。")

    correction = "\n\n".join(correction_parts)
    return correction, references


def _build_uncertainty_statement(
    verdict: Verdict,
    confidence: Confidence,
    depth_achieved: str,
    unverified_claims: list,
    limitations: list,
) -> str:
    """构建不确定性声明 — 诚实告诉用户我们不知道什么"""

    parts = []

    if confidence in (Confidence.LOW, Confidence.UNCERTAIN):
        parts.append("本分析基于有限的可用数据，置信度较低，仅供参考。")

    if depth_achieved == "L1_surface":
        parts.append("溯源分析仅达到L1(表面溯源)级别，未能进行更深层的发布者身份和利益分析。")

    if unverified_claims:
        parts.append(f"有{len(unverified_claims)}条主张因超出当前知识库范围而无法验证。这不意味着它们正确或错误。")

    if limitations:
        parts.extend(limitations)

    if not parts:
        parts.append("所有分析结论均基于可获取的证据。自动分析系统存在固有局限，本报告不构成最终的事实判断。")

    return " | ".join(parts)


# =============================================================================
# Step 0: 辟谣意图检测
# =============================================================================

_DEBUNK_MARKERS_TITLE = [
    "辟谣", "别信", "假的", "谣言", "骗人", "不实", "揭秘", "破解",
    "真相", "辟谣", "澄清", "还原", "别被骗", "别信了", "别再传",
    "辟谣贴", "辟谣视频", "事实核查", "打假",
    "伪知识", "伪科普", "辟谣帖", "别再被骗", "不要再信",
    "千万别信", "别被忽悠", "不要被骗", "这些谣言", "谣言合集",
    "假科普", "辟谣科普", "的真相", "骗了多少人",
]
_DEBUNK_MARKERS_CONTENT = [
    "但事实上", "实际上", "其实是", "其实是假的", "并非如此",
    "真相是", "错了", "不实", "辟谣", "正确说法是",
    "实际情况", "这是谣言", "这是假的", "这是错误",
    "其实", "并不是", "这是误解", "误区", "错误的是",
    "正确的", "科学的", "被误解", "真相来了",
    "不要被误导", "别信", "醒醒吧", "别再上当",
    "根本没有", "恰恰相反", "恰恰", "错得离谱",
    "这才是真相", "权威解释", "专家辟谣",
    "没有任何研究能证明", "没有任何证据表明",
    "目前没有证据", "科学研究表明", "实际上并没有",
    "没有任何科学依据", "纯属谣言", "完全是谣言",
]


def _detect_debunking_intent(title: str = "", text: str = "") -> bool:
    """
    检测内容是否为辟谣意图 (而非传播谣言)。

    多信号加权判断:
    1. 标题含辟谣标识词 (权重 3)
    2. 内容前半部分含辟谣转折词 (权重 2)
    3. 内容后半部分含辟谣总结词 (权重 1)
    加权总分 >= 3 → 判定为辟谣内容
    """
    score = 0

    # 标题检测
    if title:
        for marker in _DEBUNK_MARKERS_TITLE:
            if marker in title:
                score += 3
                break

    if not text:
        return score >= 3

    # 内容前半部分 (前500字) — 通常在陈述谣言后转折
    first_half = text[:500] if len(text) > 500 else text
    for marker in _DEBUNK_MARKERS_CONTENT[:12]:  # 转折词
        if marker in first_half:
            score += 2
            break

    # 内容后半部分 (后500字) — 通常在做总结和正确信息
    if len(text) > 500:
        second_half = text[-500:]
        for marker in _DEBUNK_MARKERS_CONTENT[12:]:
            if marker in second_half:
                score += 1
                break

    # 内容级辟谣模式检测: "第X个...错误/假/辟谣" (枚举式辟谣视频的标准格式)
    import re as _re
    if _re.search(r'(?:第[一二三四五六七八九十\d]+[个条]|[1-9]\\.).{1,20}(?:错误|假|辟谣|不对|骗人|谣言)', text[:500]):
        score += 3

    # 特殊规则: 辟谣视频的常见开头模式
    debunk_openings = [
        "今天我来辟谣", "今天我们来揭秘", "关于XX的真相",
        "你可能被骗了", "这个视频告诉你真相",
    ]

    # P0-4: 悬疑揭秘格式识别 (B站第二轮视频的主要格式)
    # 特点: 标题含"真相/揭秘/到底/背后"，开头陈述传说/谣言（用"据说/传说/网络上流传"），
    # 中间转折("但事实上/实际上/真相是")，结尾揭示结论
    mystery_reveal_patterns = [
        r'(?:真相|揭秘|到底|背后|漏洞|打假).{0,20}(?:是|到底|究竟|原来)',
        r'(?:据说|传说|流传|传闻|网络.{0,5}传).{0,50}(?:但|然而|不过|实际上).{0,20}(?:真相|事实|其实|并)',
    ]
    for mp in mystery_reveal_patterns:
        if _re.search(mp, text[:800]):
            score += 2
            break

    # 内容开头暗示在"讲述传说/恐怖故事"而非传播谣言
    storytelling_openers = [
        "今天给大家讲", "今天和大家聊聊", "相信很多人都听说过",
        "这是一个非常有名的", "今天我们来聊聊", "这是一个流传",
    ]
    for opener in storytelling_openers:
        if opener[:6] in text[:300]:
            # 后续有转折词说明在辟谣
            if any(m in text[300:800] for m in ["但事实上", "实际上", "其实", "真相是", "然而"]):
                score += 2
                break
    for opening in debunk_openings:
        if opening[:8] in text[:200]:
            score += 3
            break

    return score >= 3


# =============================================================================
# 主推理管线
# =============================================================================

async def run_reasoning_pipeline(
    url: str = "",
    title: str = "",
    text: str = "",
    # 溯源数据
    content_hash: str = "",
    url_chain: list[str] | None = None,
    page_published_at: Optional[datetime] = None,
    author: str = "",
    author_id: str = "",
    platform: str = "",
    has_verified_badge: bool = False,
    account_age_days: Optional[int] = None,
    follower_count: int = 0,
    version_hashes: list[str] | None = None,
    edit_history_available: bool = False,
    propagation_pattern: str = "",
    commercial_links: list[str] | None = None,
    bot_likelihood: float = 0.0,
    prior_credibility_scores: list[float] | None = None,
) -> AnalysisResult:
    """
    执行完整的 6 步推理管线。

    输入一条信息的所有可用数据，输出一份包含完整推理链的分析报告。

    每步分析产生一个 ReasoningStep，记录在 reasoning_chain 中。
    """

    result = AnalysisResult(
        input_url=url,
        input_title=title,
        analyzed_at=datetime.now(timezone.utc),
    )
    chain = result.reasoning_chain
    step_counter = [0]  # mutable counter for nested functions

    def add_step(description: str, conclusion: str, confidence: Confidence,
                 evidence: list | None = None, counter_evidence: list | None = None,
                 uncertainty: str = ""):
        step_counter[0] += 1
        chain.append(ReasoningStep(
            step_id=step_counter[0],
            description=description,
            conclusion=conclusion,
            confidence=confidence,
            evidence=evidence or [],
            counter_evidence=counter_evidence or [],
            uncertainty_note=uncertainty,
        ))

    # -----------------------------------------------------------------------
    # Step 0: 意图检测 — 判断内容是"辟谣"还是"传谣"
    # -----------------------------------------------------------------------
    is_debunking = _detect_debunking_intent(title=title, text=text)

    if is_debunking:
        add_step(
            "执行内容意图检测",
            "检测到辟谣意图标志 — 内容在驳斥谣言而非传播谣言。将调整检测阈值以避免误判辟谣者为传谣者。",
            Confidence.HIGH,
            uncertainty="自动意图检测基于关键词模式。如有误判，人工复核即可。",
        )

    # -----------------------------------------------------------------------
    # Step 1: 信息失真检测
    # -----------------------------------------------------------------------
    distortion_result = detect_distortions(text=text, title=title)
    result.distortion_analysis = distortion_result

    if distortion_result.matches:
        add_step(
            "执行7种信息失真模式检测",
            f"检测到{len(distortion_result.matches)}处失真模式匹配，总风险等级: {distortion_result.overall_risk.value}",
            distortion_result.overall_risk,
            evidence=[Evidence(
                description=m.description,
                source_url=url,
                source_type=EvidenceType.PRIMARY_SOURCE,
                quality=EvidenceQuality.MEDIUM,
                quote=m.evidence_snippet,
            ) for m in distortion_result.matches[:5]],
            uncertainty="模式匹配基于正则表达式，存在误报可能。每处匹配需要人工结合上下文最终判断。",
        )
    else:
        add_step(
            "执行7种信息失真模式检测",
            "未检测到明显的信息失真模式",
            Confidence.LOW,
        )

    # -----------------------------------------------------------------------
    # Step 2: 逻辑谬误检测
    # -----------------------------------------------------------------------
    fallacy_result = detect_fallacies(text=text, title=title)
    result.fallacy_analysis = fallacy_result

    if fallacy_result.matches:
        add_step(
            "执行12种逻辑谬误检测",
            f"检测到{fallacy_result.fallacy_count}处潜在逻辑谬误",
            Confidence.MODERATE if fallacy_result.fallacy_count >= 3 else Confidence.LOW,
            evidence=[Evidence(
                description=f"{m.description} → 纠偏提示: {m.correction_hint[:100]}",
                source_url=url,
                quote=m.evidence_snippet,
            ) for m in fallacy_result.matches[:5]],
            uncertainty="逻辑谬误检测基于文本模式匹配，可能存在误报。高置信度的匹配也应人工复核。",
        )
    else:
        add_step(
            "执行12种逻辑谬误检测",
            "未检测到明显的逻辑谬误",
            Confidence.LOW,
        )

    # -----------------------------------------------------------------------
    # Step 2.5: 统计素养检测
    # -----------------------------------------------------------------------
    stat_result = detect_statistical_abuse(text=text, title=title)
    result.statistical_analysis = stat_result

    if stat_result.matches:
        add_step(
            "执行8种统计滥用模式检测",
            f"检测到{len(stat_result.matches)}处统计滥用匹配 | 风险评分: {stat_result.risk_score:.0f}/100",
            Confidence.HIGH if stat_result.risk_score > 40 else Confidence.MODERATE,
            evidence=[Evidence(description=m.education, source_url=url, quote=m.evidence_snippet)
                      for m in stat_result.matches[:3]],
            uncertainty="统计滥用检测基于文本模式匹配。数据本身可能真实，但解读方式可能存在误导。",
        )
    else:
        add_step("执行8种统计滥用模式检测", "未检测到明显的统计滥用", Confidence.LOW)

    # -----------------------------------------------------------------------
    # Step 2.6: 拼接式造谣检测
    # -----------------------------------------------------------------------
    composite_result = detect_composite_fabrication(text=text, title=title)
    result.composite_analysis = composite_result

    if composite_result.matches:
        add_step(
            "执行5种拼接式造谣模式检测",
            f"检测到{len(composite_result.matches)}处逻辑拼接匹配 | 风险评分: {composite_result.composite_risk_score:.0f}/100",
            Confidence.MODERATE if composite_result.composite_risk_score > 25 else Confidence.LOW,
            evidence=[Evidence(description=f"逻辑缺口: {m.leap_gap[:200]}", source_url=url, quote=m.evidence_snippet)
                      for m in composite_result.matches[:3]],
            uncertainty="拼接式造谣是最难检测的操纵形式——每小块可能都是真的，但组合逻辑有问题。",
        )
    else:
        add_step("执行5种拼接式造谣模式检测", "未检测到明显的逻辑拼接", Confidence.LOW)

    # -----------------------------------------------------------------------
    # Step 3: 溯源深度分析
    # -----------------------------------------------------------------------
    # 从文本中推断叙事框架（用于 L4）
    from app.engine.narrative import detect_narratives as _detect_narratives
    narrative_preview = _detect_narratives(text=text) if text else None

    trace_result = analyze_trace(
        url=url,
        text=text,
        title=title,
        content_hash=content_hash,
        url_chain=url_chain,
        page_published_at=page_published_at,
        author=author,
        author_id=author_id,
        platform=platform,
        has_verified_badge=has_verified_badge,
        account_age_days=account_age_days,
        follower_count=follower_count,
        version_hashes=version_hashes,
        edit_history_available=edit_history_available,
        narrative_type=narrative_preview.dominant_narrative if narrative_preview else None,
        propagation_pattern=propagation_pattern,
        commercial_links=commercial_links,
        bot_likelihood=bot_likelihood,
        prior_credibility_scores=prior_credibility_scores,
    )
    result.trace_analysis = trace_result

    add_step(
        f"执行溯源深度分析 (达到: {trace_result.depth_achieved.value})",
        f"最早来源: {trace_result.earliest_source_url[:80] if trace_result.earliest_source_url else '未知'} | "
        f"来源可信度: {trace_result.source_credibility_score:.0f} | "
        f"发现内容篡改: {'是' if trace_result.content_tampering_detected else '否'}",
        Confidence.MODERATE if trace_result.source_credibility_score >= 40 else Confidence.LOW,
        uncertainty="溯源深度的限制: " + "; ".join(
            (trace_result.details.get("L1") or {}).get("limitations", []) +
            (trace_result.details.get("L2") or {}).get("limitations", []) +
            (trace_result.details.get("L3") or {}).get("limitations", [])
        )[:3],
    )

    # -----------------------------------------------------------------------
    # Step 4: 领域知识验证
    # -----------------------------------------------------------------------
    domain_result = analyze_domain(text=text, title=title)
    result.domain_analysis = domain_result

    add_step(
        f"执行领域知识验证 (识别领域: {domain_result.domain.value})",
        f"提取{len(domain_result.claims)}条主张 | "
        f"被反驳: {len(domain_result.refuted_claims)} | "
        f"无法验证: {len(domain_result.unverified_claims)} | "
        f"知识缺口: {len(domain_result.knowledge_gaps)}条",
        Confidence.MODERATE if domain_result.refuted_claims else Confidence.LOW,
        evidence=[Evidence(
            description=f"领域: {domain_result.domain.value}",
            source_url="",
            source_type=EvidenceType.EXPERT_CONSENSUS,
            quality=EvidenceQuality.MEDIUM,
            quote="; ".join(domain_result.knowledge_gaps[:2]),
        )] if domain_result.knowledge_gaps else [],
        uncertainty=f"知识验证仅限于系统内置的知识库，不能覆盖所有领域。{len(domain_result.unverified_claims)}条主张超出当前知识范围。" if domain_result.unverified_claims else "",
    )

    # -----------------------------------------------------------------------
    # Step 5: 叙事框架识别
    # -----------------------------------------------------------------------
    if narrative_preview is None:
        narrative_preview = _detect_narratives(text=text)
    result.narrative_analysis = narrative_preview

    if narrative_preview.matches:
        add_step(
            "执行8种操纵性叙事框架检测",
            f"检测到{len(narrative_preview.matches)}处叙事框架匹配 | "
            f"主导叙事: {narrative_preview.dominant_narrative.value if narrative_preview.dominant_narrative else '无'} | "
            f"操纵性评分: {narrative_preview.manipulation_score:.0f}/100",
            Confidence.MODERATE if narrative_preview.manipulation_score > 40 else Confidence.LOW,
            evidence=[Evidence(
                description=f"叙事标记: {', '.join(m.markers[:3])}",
                source_url=url,
                quote=m.reasoning[:200],
            ) for m in narrative_preview.matches[:3]],
            uncertainty="叙事框架检测仅识别信息呈现方式，不等同于事实判断。即使被检测到特定叙事框架，信息本身可能仍然部分或全部属实。",
        )
    else:
        add_step(
            "执行8种操纵性叙事框架检测",
            "未检测到明显的操纵性叙事",
            Confidence.LOW,
        )

    # -----------------------------------------------------------------------
    # Step 5.5: 模态梯度漂移
    # -----------------------------------------------------------------------
    modality_result = detect_modality_drift(text=text, title=title)
    result.modality_analysis = modality_result

    if modality_result.matches:
        add_step(
            "执行5种模态梯度漂移检测",
            f"检测到{len(modality_result.matches)}处模态漂移 | 漂移评分: {modality_result.drift_score:.0f}/100",
            Confidence.MODERATE if modality_result.drift_score > 30 else Confidence.LOW,
            evidence=[Evidence(description=m.description, source_url=url, quote=m.evidence_snippet)
                      for m in modality_result.matches[:3]],
            uncertainty="模态漂移检测基于语言模式。推测→确定的漂移未必是有意的。",
        )

    # -----------------------------------------------------------------------
    # Step 5.6: LLM 增强分析 (如果 L1 高风险)
    # -----------------------------------------------------------------------
    llm_result = None
    try:
        # 构建 L1 摘要用于判断是否触发
        l1_summary = {
            "distortion_analysis": result.distortion_analysis.to_dict() if result.distortion_analysis else {},
            "fallacy_analysis": result.fallacy_analysis.to_dict() if result.fallacy_analysis else {},
            "statistical_analysis": result.statistical_analysis.to_dict() if result.statistical_analysis else {},
            "narrative_analysis": result.narrative_analysis.to_dict() if result.narrative_analysis else {},
            "modality_analysis": result.modality_analysis.to_dict() if result.modality_analysis else {},
        }
        from app.engine.llm_analyzer import should_trigger_llm, run_llm_analysis
        if should_trigger_llm(l1_summary):
            llm_result = await run_llm_analysis(
                title=title,
                text=text,
                l1_analysis=l1_summary,
            )
            result.llm_analysis = llm_result.to_dict() if llm_result else None
            if llm_result:
                add_step(
                    "执行 LLM 增强深度语义分析 (Claude API)",
                    f"语义层面操纵风险: {llm_result.semantic_risk_score:.0f}/100 | 质量: {llm_result.analysis_quality}",
                    Confidence.MODERATE,
                    evidence=[Evidence(description=f"LLM分析: 隐含含义={llm_result.implied_meaning[:100]}")],
                    uncertainty="LLM 分析可能存在偏见和幻觉。此分析仅作为参考，最终判定基于确定性规则。",
                )
    except Exception:
        pass  # LLM 失败不影响主流程

    # -----------------------------------------------------------------------
    # Step 6: 严格逻辑综合判定 (证据等级+因果链+假设检验+乘法评分)
    # -----------------------------------------------------------------------
    from app.engine.rigorous_logic import run_rigorous_analysis
    rigorous = await run_rigorous_analysis(
        title=title, text=text, url=url, author=author, platform=platform,
        existing_10engine_result=result.to_dict(),
    )

    result.credibility_score = rigorous.credibility_score

    # 辟谣意图调整: 如果检测到辟谣意图，上调可信度 +15~25 分
    # (因为辟谣内容在陈述谣言时会被引擎误判为传谣)
    result.is_debunking = is_debunking
    if is_debunking:
        adjustment = 20
        # 如果已经在中等可信度以上，保守上调
        if result.credibility_score >= 30:
            adjustment = 15
        result.credibility_score = min(100.0, result.credibility_score + adjustment)
        result.debunking_adjustment = adjustment

    # Map rigorous verdict back to our Verdict enum
    rv = rigorous.verdict
    v_map = {"true": Verdict.TRUE, "likely_true": Verdict.LIKELY_TRUE,
             "misleading": Verdict.MISLEADING, "likely_false": Verdict.LIKELY_FALSE,
             "false": Verdict.FALSE, "unverifiable": Verdict.UNVERIFIABLE}
    result.verdict = v_map.get(rv, Verdict.UNVERIFIABLE)
    result.confidence = Confidence(rigorous.confidence) if rigorous.confidence in Confidence._value2member_map_ else Confidence.MODERATE

    # Attach rigorous analysis extras
    result.logical_summary = rigorous.logical_summary
    result.evidence_hierarchy = rigorous.evidence_hierarchy
    result.causal_chains = rigorous.causal_chains
    result.source_claim_issues = rigorous.source_claim_issues
    result.risk_breakdown = rigorous.risk_breakdown

    # Correction
    correction_parts = [result.correction] if result.correction else []
    correction_parts.append(f"[严格逻辑框架] {rigorous.logical_summary}")
    for rec in rigorous.recommendations:
        correction_parts.append(f"  → {rec}")
    result.correction = "\n".join(correction_parts)
    if rigorous.recommendations:
        result.correction_references.extend(rigorous.recommendations)

    # Uncertainty statement
    all_limitations = (
        (trace_result.details.get("L1") or {}).get("limitations", []) +
        (trace_result.details.get("L2") or {}).get("limitations", []) +
        (trace_result.details.get("L3") or {}).get("limitations", [])
    )
    result.uncertainty_statement = _build_uncertainty_statement(
        verdict=result.verdict,
        confidence=result.confidence,
        depth_achieved=trace_result.depth_achieved.value,
        unverified_claims=domain_result.unverified_claims,
        limitations=all_limitations,
    )

    add_step(
        "执行严格逻辑综合判定 (7级证据+因果链+假设检验+乘法评分)",
        f"{rigorous.logical_summary}",
        result.confidence,
        uncertainty=result.uncertainty_statement,
    )

    # Record calibration data
    # -----------------------------------------------------------------------
    # Step 11: AI内容鉴伪检测 (新引擎)
    # -----------------------------------------------------------------------
    try:
        from app.engine.ai_detector import AIContentDetector
        ai_detector = AIContentDetector()
        ai_result = ai_detector.analyze(
            text=text, title=title,
            author_info={"username": author, "created_at": str(account_age_days) + " days ago" if account_age_days else None} if author else None,
        )
        result.ai_detection = ai_result.to_dict()
        if ai_result.matches:
            add_step(
                f"执行AI内容鉴伪检测 (AI文本/深度伪造/机器人发帖)",
                f"检测到{len(ai_result.matches)}个AI/操纵信号，风险评分: {ai_result.risk_score:.0f}/100 — {ai_result.summary}",
                Confidence.MODERATE if ai_result.risk_score >= 30 else Confidence.LOW,
                evidence=[Evidence(
                    description=m.description,
                    quote=m.evidence_snippet,
                    quality=EvidenceQuality.MEDIUM if m.confidence > 0.6 else EvidenceQuality.LOW,
                ) for m in ai_result.matches[:5]],
                uncertainty="AI检测只能提供线索，不能确定结论。高置信度水印标记(如DALL·E/Midjourney)是强信号。",
            )
    except Exception as e:
        logger.warning(f"AI检测引擎跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 12: RAG权威信源检索验证 (新引擎)
    # -----------------------------------------------------------------------
    try:
        from app.engine.rag_verifier import RAGVerifier
        rag = RAGVerifier()
        rag_result = rag.analyze(text=text, title=title, max_queries=5)
        result.rag_verification = rag_result.to_dict()
        if rag_result.total_claims > 0:
            add_step(
                "RAG权威信源检索验证 — 将主张与WHO/国家标准/学术论文实时比对",
                f"提取{rag_result.total_claims}条可验证主张: {rag_result.supported}条获支持, {rag_result.refuted}条被反驳, {rag_result.unverifiable}条无法验证。权威覆盖度: {rag_result.authority_score:.0f}/100",
                Confidence.HIGH if rag_result.supported > 0 or rag_result.refuted > 0 else Confidence.LOW,
                evidence=[Evidence(
                    description=f"[{v.verdict}] {v.claim[:80]} — {v.explanation[:100]}",
                    source_url=v.sources[0].url if v.sources else "",
                    quality=EvidenceQuality.HIGH if v.sources and v.sources[0].source_type in ("government","international","standard") else EvidenceQuality.MEDIUM,
                ) for v in rag_result.verified_claims[:5]],
                uncertainty="RAG检索结果依赖于可公开访问的权威数据源。部分主张可能需要订阅或专业数据库才能验证。",
            )
    except Exception as e:
        logger.warning(f"RAG验证引擎跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 13: 发布者风险画像 (新引擎)
    # -----------------------------------------------------------------------
    try:
        from app.engine.publisher_risk import PublisherRiskAnalyzer
        risk_analyzer = PublisherRiskAnalyzer()
        pub_profile = risk_analyzer.analyze(
            username=author, platform=platform, created_at=f"{account_age_days} days ago" if account_age_days else None,
            total_posts=0, verified_posts=0, disputed_posts=0,
            content_text=text,
        )
        result.publisher_profile = pub_profile.to_dict()
        risk_level = "high" if pub_profile.overall_risk < 35 else ("elevated" if pub_profile.overall_risk < 50 else ("moderate" if pub_profile.overall_risk < 65 else "low"))
        if pub_profile.risk_factors:
            add_step(
                "发布者风险画像分析 — 账号年龄/历史准确率/领域专注度/行为规律/传播动机",
                f"综合可信度: {pub_profile.overall_risk:.0f}/100 ({risk_level})。{len(pub_profile.risk_factors)}个风险因素: {'; '.join(pub_profile.risk_factors[:3])}",
                Confidence.MODERATE if pub_profile.risk_factors else Confidence.LOW,
                uncertainty="发布者画像分析基于有限的行为数据。'不确定就是不确定'——无数据维度保持中性50分。",
            )
    except Exception as e:
        logger.warning(f"发布者风险分析跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 14: 传播路径深度风险分析 (新引擎)
    # -----------------------------------------------------------------------
    try:
        from app.engine.propagation_risk import PropagationRiskAnalyzer
        prop_analyzer = PropagationRiskAnalyzer()
        url_chain_nodes = [
            {"id": u, "url": u, "platform": platform or "general", "published_at": (page_published_at.isoformat() if page_published_at else None)}
            for u in (url_chain or [])
        ] if url_chain else []
        prop_metrics = prop_analyzer.analyze(
            nodes=url_chain_nodes,
            content_hashes=[content_hash] if content_hash else [],
            original_hash=content_hash,
            first_seen_at=page_published_at.isoformat() if page_published_at else None,
            propagation_pattern=propagation_pattern,
            bot_likelihood=float(bot_likelihood),
        )
        result.propagation_risk = prop_metrics.to_dict()
        psi = prop_metrics.propagation_speed_index
        add_step(
            "传播路径深度风险分析 — 速度/变异/网络/异常检测",
            f"传播风险: {prop_metrics.risk_level}({prop_metrics.overall_risk_score:.0f}/100)。PSI={psi}/h, {prop_metrics.total_nodes}节点, {prop_metrics.amplifier_count}个引爆节点, 变异系数{prop_metrics.mutation_variation:.2f}",
            Confidence.HIGH if prop_metrics.overall_risk_score >= 40 else Confidence.MODERATE,
            evidence=[Evidence(
                description=f"传播速度指数: {psi}/h (正常<5)",
                quote=f"节点{prop_metrics.total_nodes}, 边{prop_metrics.total_edges}, 深度{prop_metrics.max_depth}",
                quality=EvidenceQuality.MEDIUM,
            )],
            uncertainty="传播路径分析依赖于可获取的公开数据。实际传播网络可能更复杂。",
        )
    except Exception as e:
        logger.warning(f"传播路径分析跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 15: 实时谣言预警与求真卡生成 (新引擎)
    # -----------------------------------------------------------------------
    try:
        from app.engine.rumor_alert import alert_from_analysis
        alert_result = alert_from_analysis(
            engine_analysis=result.to_dict(),
            propagation_metrics=result.propagation_risk,
            ai_detection=result.ai_detection,
            title=title or result.input_title,
        )
        result.rumor_alert = alert_result.to_dict()
        if alert_result.alert_level.value in ("red", "orange"):
            add_step(
                "实时谣言预警 — 多级阈值触发 + 求真卡生成",
                f"告警等级: {alert_result.alert_level.value.upper()}。{len(alert_result.triggers)}条规则触发。{len(alert_result.vulnerable_groups)}个易感群体: {', '.join(alert_result.vulnerable_groups)}",
                Confidence.HIGH if alert_result.alert_level.value == "red" else Confidence.MODERATE,
                evidence=[Evidence(
                    description=t.description,
                    quote=f"当前值 {t.value:.1f}, 阈值 {t.threshold}",
                    quality=EvidenceQuality.HIGH if t.severity.value == "red" else EvidenceQuality.MEDIUM,
                ) for t in alert_result.triggers[:5]],
                uncertainty="自动预警基于可量化的风险指标。所有告警均需人工审核后才能采取处置措施。",
            )
    except Exception as e:
        logger.warning(f"谣言预警跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 16: SatyaLens 引用完整性评分 (新引擎 P0)
    # -----------------------------------------------------------------------
    try:
        from app.engine.satyalens_score import SatyaLensScorer
        satyalens = SatyaLensScorer()
        sl_result = satyalens.analyze(
            text=text, title=title,
            cited_urls=url_chain or [],
            author_claims=(
                domain_result.claims if domain_result else []
            ),
        )
        result.satyalens_score = sl_result.to_dict()
        if sl_result.citations_found > 0 or sl_result.red_flags:
            add_step(
                "SatyaLens 引用完整性评分 — 评估引用链条的可验证性",
                f"{sl_result.summary}",
                Confidence.HIGH if sl_result.overall_integrity_score >= 0.7 else (
                    Confidence.MODERATE if sl_result.overall_integrity_score >= 0.4 else Confidence.LOW
                ),
                evidence=[Evidence(
                    description=f"可验证引用: {sl_result.citations_verifiable}/{sl_result.citations_found} | 引用链深度: L{sl_result.citation_chain_depth}",
                    source_url=url,
                    quality=EvidenceQuality.HIGH if sl_result.independent_corroboration else EvidenceQuality.MEDIUM,
                )] if sl_result.citations_found > 0 else [],
                uncertainty=f"引用完整性评分仅评估引用可追溯性，不等于内容真实性判断。"
                          f"{len(sl_result.red_flags)}个引用质量问题被标记。" if sl_result.red_flags else "",
            )
    except Exception as e:
        logger.warning(f"SatyaLens 引用完整性引擎跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 17: Google Fact Check Tools API 交叉验证 (新引擎 P0)
    # -----------------------------------------------------------------------
    try:
        from app.engine.factcheck_api import FactCheckAPI
        from app.config import get_settings
        fc_api_key = get_settings().google_fact_check_api_key
        if fc_api_key:
            fc_api = FactCheckAPI(api_key=fc_api_key)
            fc_result = await fc_api.analyze(text=text, title=title, max_queries=5)
            result.fact_check_crossref = fc_result.to_dict()
            if fc_result.matched_claims > 0:
                add_step(
                    "Google Fact Check 第三方核查数据库交叉验证",
                    f"{fc_result.summary}",
                    Confidence.HIGH if fc_result.matched_claims >= 2 else Confidence.MODERATE,
                    evidence=[Evidence(
                        description=f"[{m.rating_normalized}] {m.publisher_name}: {m.textual_rating} — {m.snippet[:100]}",
                        source_url=m.fact_check_url,
                        quality=EvidenceQuality.HIGH,
                    ) for m in fc_result.matches[:5]],
                    uncertainty="Fact Check API 结果来自第三方核查机构 (Snopes/PolitiFact等)，其结论可能受核查机构自身偏见影响。",
                )
            elif fc_result.api_available:
                add_step(
                    "Google Fact Check 第三方核查数据库交叉验证",
                    f"未找到匹配的第三方核查结果 ({fc_result.total_claims_searched}条主张已搜索)",
                    Confidence.LOW,
                    uncertainty="未找到第三方核查 ≠ 信息属实。仅表示该主张尚未被主流事实核查机构覆盖。",
                )
        else:
            logger.info("Google Fact Check API key 未配置，跳过 Step 17")
    except Exception as e:
        logger.warning(f"Fact Check API 引擎跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 18: lmscan AI 文本统计特征检测 (新引擎 P1)
    # -----------------------------------------------------------------------
    try:
        from app.engine.lmscan_detector import LmscanDetector
        lmscan = LmscanDetector()
        lmscan_result = lmscan.analyze(text=text, title=title)
        result.lmscan_detection = lmscan_result.to_dict()
        if lmscan_result.feature_count_flagged > 0:
            add_step(
                "lmscan AI 文本统计特征检测 — 12 维度统计指纹分析",
                f"{lmscan_result.summary}",
                Confidence.HIGH if lmscan_result.confidence == "high" else (
                    Confidence.MODERATE if lmscan_result.confidence == "moderate" else Confidence.LOW
                ),
                evidence=[Evidence(
                    description=f"[{f.name}] 得分 {f.score:.2f} (阈值 {f.threshold})"
                    if f.flagged else f"[{f.name}] {f.detail[:80]}",
                    source_url=url,
                    quality=EvidenceQuality.MEDIUM if f.flagged else EvidenceQuality.LOW,
                ) for f in lmscan_result.features if f.flagged][:5],
                uncertainty="统计特征分析仅提供信号提示。短文本 (<200字) 结果不可靠。多检测器交叉验证后才能提高置信度。",
            )
    except Exception as e:
        logger.warning(f"lmscan AI 检测引擎跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 19: smellcheck AI 文本静态指纹检测 (新引擎 P1)
    # -----------------------------------------------------------------------
    try:
        from app.engine.smellcheck_detector import SmellcheckDetector
        smell = SmellcheckDetector()
        smell_result = smell.analyze(text=text, title=title)
        result.smellcheck_detection = smell_result.to_dict()
        if smell_result.total_flags > 0:
            add_step(
                "smellcheck AI 文本静态指纹检测 — 8 类字符级指纹分析",
                f"{smell_result.summary}",
                Confidence.MODERATE if smell_result.anomaly_score > 30 else Confidence.LOW,
                evidence=[Evidence(
                    description=f"[{f.category}] {f.description[:120]}",
                    source_url=url,
                    quality=EvidenceQuality.HIGH if f.severity == "high" else EvidenceQuality.MEDIUM,
                ) for f in smell_result.flags[:4]],
                uncertainty="字符级指纹异常可能来自合法来源 (富文本编辑器、排版软件)。需结合 lmscan 统计特征交叉验证。",
            )
    except Exception as e:
        logger.warning(f"smellcheck AI 指纹检测引擎跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 20: GraphRAG-Causal 因果图谱分析 (P2 — 因果链推理+谬误检测)
    # -----------------------------------------------------------------------
    try:
        from app.engine.causal_graph import analyze_causal_graph
        causal_result = analyze_causal_graph(
            text=text, title=title, url=url,
        )
        result.causal_graph_result = causal_result.to_dict()
        if causal_result.total_claims > 0 or causal_result.fallacies:
            add_step(
                "GraphRAG-Causal 因果图谱分析 — 因果主张提取+因果谬误检测+图谱传导",
                causal_result.summary,
                Confidence.HIGH if causal_result.overall_causal_quality < 40 else
                Confidence.MODERATE if causal_result.overall_causal_quality < 70 else Confidence.LOW,
                evidence=[Evidence(
                    description=f"因果图谱: {causal_result.total_claims}条主张, "
                                f"{len(causal_result.graph.get('nodes', []))}节点, "
                                f"{len(causal_result.graph.get('edges', []))}条边",
                    source_url=url,
                    quality=EvidenceQuality.MEDIUM,
                )],
                counter_evidence=[Evidence(
                    description=f.fallacy_type,
                    source_url=url,
                    quality=EvidenceQuality.LOW,
                ) for f in causal_result.fallacies[:3]],
                uncertainty="因果推理基于文本模式匹配。因果关系需要时间顺序+机制+排除混淆变量才能确认。",
            )
    except Exception as e:
        logger.warning(f"GraphRAG-Causal 因果图谱引擎跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 22: Correction Agent 叙事替代 (P2 — 辟谣替代叙事生成)
    # -----------------------------------------------------------------------
    try:
        from app.engine.correction_agent import generate_correction
        # 收集已检测到的失真和谬误类型
        detected_distortion_types = []
        if result.distortion_analysis:
            detected_distortion_types = [
                m.abuse_type if hasattr(m, 'abuse_type') else m.description[:30]
                for m in (result.distortion_analysis.matches or [])[:5]
            ]
        detected_fallacy_types = []
        if result.fallacy_analysis:
            detected_fallacy_types = [
                m.abuse_type if hasattr(m, 'abuse_type') else m.description[:30]
                for m in (result.fallacy_analysis.matches or [])[:5]
            ]

        correction = generate_correction(
            original_claim=(text or "")[:500],
            verified_facts=result.correction_references if result.correction_references else [],
            sources=[url] if url else [],
            distortion_types=detected_distortion_types,
            fallacy_types=detected_fallacy_types,
            credibility_score=result.credibility_score,
            title=title,
        )
        result.correction_alternative = correction.to_dict()

        # 将一句话辟谣添加到 correction 字段末尾
        if correction.short_correction:
            result.correction = (
                (result.correction or "") +
                f"\n\n[叙事替代] {correction.short_correction}"
            )
    except Exception as e:
        logger.warning(f"Correction Agent 叙事替代跳过: {e}")

    # 附加: 生成辟谣视频脚本
    try:
        from app.engine.debunk_script import generate_debunk_script
        script = generate_debunk_script(
            rumor_claim=(text or title)[:300],
            verified_facts=result.correction_references if result.correction_references else [],
            evidence_sources=[url] if url else [],
            cost_reasoning={
                "matched": result.cost_reasoning.get("matched", False) if result.cost_reasoning else False,
                "logic": result.cost_reasoning.get("logic", "") if result.cost_reasoning else "",
                "breakdown": result.cost_reasoning.get("breakdown", "") if result.cost_reasoning else "",
            } if result.cost_reasoning else {},
            tone="authoritative",
            duration_sec=60,
        )
        result.debunk_script = script
    except Exception:
        pass

    # -----------------------------------------------------------------------
    # Step 21: Sift Critic Agent 对抗审查 (P1 — 在所有引擎之后)
    # -----------------------------------------------------------------------
    try:
        from app.engine.llm_analyzer import run_critic_review
        critic = run_critic_review(result.to_dict())
        result.critic_review = critic.to_dict()
        if critic.inter_engine_agreement < 0.5 or critic.conflicting_findings or critic.false_positive_risks:
            add_step(
                "Sift Critic Agent 对抗审查 — 引擎间一致性 + 误报风险评估",
                f"{critic.reviewer_notes}",
                Confidence.HIGH if abs(critic.confidence_adjustment) >= 10 else Confidence.MODERATE,
                evidence=[Evidence(
                    description=f"引擎一致性: {critic.inter_engine_agreement:.0%} | 置信度调整: {critic.confidence_adjustment:+.0f}",
                    source_url="",
                    quality=EvidenceQuality.MEDIUM,
                )],
                counter_evidence=[Evidence(
                    description=risk,
                    source_url="",
                    quality=EvidenceQuality.LOW,
                ) for risk in critic.false_positive_risks[:3]],
                uncertainty=f"Critic Agent 审查是自动化信号分析。"
                          f"{'发现矛盾发现需人工复核。' if critic.conflicting_findings else ''}"
                          f"{'标记了误报风险。' if critic.false_positive_risks else ''}",
            )
    except Exception as e:
        logger.warning(f"Critic Agent 审查跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 23: 回音壁效应检测 (P0 — B站视频2发现)
    # -----------------------------------------------------------------------
    try:
        from app.engine.echo_chamber import detect_echo_chamber
        echo = detect_echo_chamber(
            content_text=text,
            references=[url] if url else [],
        )
        result.echo_chamber = echo.to_dict()
        if echo.echo_chamber_detected:
            add_step(
                "回音壁效应检测 — 追踪引用链，检测多源是否指向同一未核实出处",
                echo.assessment,
                Confidence.HIGH if echo.echo_chamber_score >= 60 else Confidence.MODERATE,
                uncertainty="回音壁检测基于文本中的引用模式。真实的信息生态比文本可检测的更复杂。",
            )
            # 回音壁效应 → 下调可信度
            if echo.echo_chamber_score >= 60:
                result.credibility_score = max(5.0, result.credibility_score - 10)
    except Exception as e:
        logger.warning(f"回音壁检测跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 23.5: 英文虚假信息补充评分 (english_patterns)
    # -----------------------------------------------------------------------
    try:
        from app.engine.english_patterns import score_english_misinfo
        ascii_chars = sum(1 for c in text if c.isascii() and c.isalpha())
        total_chars = max(1, sum(1 for c in text if c.isalpha()))
        if ascii_chars / total_chars > 0.3:  # 至少30%英文字符才运行
            en_score = score_english_misinfo(text)
            if en_score.get("match_count", 0) > 0:
                result.english_misinfo_score = en_score
                add_step(
                    "英文虚假信息补充检测",
                    f"检测到 {en_score['match_count']} 个英文虚假信息指标, 风险评分 {en_score['risk_score']:.0f}/100",
                    Confidence.HIGH if en_score["risk_score"] > 30 else Confidence.MODERATE,
                    evidence=[Evidence(
                        description=f"[{m.get('type', m.get('signal', 'en'))}] 匹配 {m.get('count', 1)} 次",
                        source_url="",
                        quality=EvidenceQuality.MEDIUM,
                    ) for m in en_score.get("matches", [])[:5]],
                    uncertainty="英文虚假信息检测基于模式匹配。不同语言/文化的网络表达差异可能导致误判。",
                )
    except Exception as e:
        logger.warning(f"英文虚假信息评分跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 24: 多语言溯源 (P0 — 检测是否涉及跨国信息)
    # -----------------------------------------------------------------------
    try:
        from app.engine.cross_lang_trace import detect_international_claim
        intl = detect_international_claim(text)
        result.cross_lang_trace = intl
        if intl.get("international_entities_found"):
            entities = [e["entity"] for e in intl["international_entities_found"][:5]]
            add_step(
                "多语言溯源 — 检测到涉及跨国信息",
                f"涉及实体: {', '.join(entities)}。建议在{', '.join(intl.get('languages_recommended',[]))}语言源中交叉验证。",
                Confidence.MODERATE,
                uncertainty="多语言搜索基于术语映射，翻译可能不完全准确。手动查验建议搜索词。",
            )
    except Exception as e:
        logger.warning(f"多语言溯源跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 25: 技术事实楔子 (P0 — 基于科学原理的不可辩驳事实)
    # -----------------------------------------------------------------------
    try:
        from app.engine.correction_agent import generate_tech_fact_wedge, generate_cost_reasoning
        tech_wedge = generate_tech_fact_wedge(text)
        cost_logic = generate_cost_reasoning(text)
        result.tech_fact_wedge = tech_wedge
        result.cost_reasoning = cost_logic
        if tech_wedge.get("matched"):
            add_step(
                f"技术事实楔子 — 基于{tech_wedge.get('category','科学')}原理的不可辩驳事实",
                tech_wedge.get("wedge", "")[:200],
                Confidence.HIGH,
                evidence=[Evidence(description=f"来源: {tech_wedge.get('source','')}", source_url="", quality=EvidenceQuality.HIGH)],
                uncertainty="技术事实基于公认的科学原理，但具体应用场景需要专业判断。",
            )
        if cost_logic.get("matched"):
            add_step(
                "成本逻辑推演 — 用经济常识击穿商业谣言",
                cost_logic.get("logic", "")[:200],
                Confidence.HIGH,
                uncertainty="成本数据基于市场价格估算，实际价格可能因地域/时间波动。",
            )
    except Exception as e:
        logger.warning(f"技术事实楔子跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 26: 造谣过程演示时间线 (P3 — 从B站视频3/8获得的灵感)
    # -----------------------------------------------------------------------
    try:
        from app.engine.rumor_timeline import generate_rumor_timeline
        timeline = generate_rumor_timeline(
            rumor_text=(text or title)[:500],
            detected_distortions=[
                m.abuse_type if hasattr(m, 'abuse_type') else m.description[:30]
                for m in (result.distortion_analysis.matches or [])[:5]
            ] if result.distortion_analysis else [],
            detected_fallacies=[
                m.abuse_type if hasattr(m, 'abuse_type') else m.description[:30]
                for m in (result.fallacy_analysis.matches or [])[:5]
            ] if result.fallacy_analysis else [],
        )
        result.rumor_timeline = timeline.to_dict()
        if timeline.steps:
            add_step(
                "造谣过程演示 — 展示信息如何被search→extract→distort→amplify",
                f"还原{len(timeline.steps)}步造谣操作。关键教训: {timeline.reveals[0] if timeline.reveals else ''}",
                Confidence.HIGH,
                uncertainty="时间线基于模式匹配重建，具体细节可能因实际传播路径而异。",
            )
    except Exception as e:
        logger.warning(f"造谣时间线跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 27: 注意力劫持评估 (P3 — 辟谣效果衡量)
    # -----------------------------------------------------------------------
    try:
        from app.engine.attention_metric import compute_attention_metric
        attn = compute_attention_metric(
            content_text=text,
            content_title=title,
        )
        result.attention_metric = attn.to_dict()
        if attn.risk_level in ("high", "medium"):
            add_step(
                "注意力效率评估 — 检测辟谣内容中的娱乐vs信息元素比",
                attn.assessment,
                Confidence.MODERATE,
                evidence=[Evidence(
                    description=f"注意力效率: {attn.attention_efficiency:.0%}",
                    quote=f"信息密度: {attn.information_density:.1f} vs 娱乐密度: {attn.entertainment_density:.1f}",
                    quality=EvidenceQuality.MEDIUM,
                )],
                uncertainty="注意力指标基于关键词密度计算，不能完全反映受众实际接收情况。",
            )
    except Exception as e:
        logger.warning(f"注意力评估跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 28: IFCN 标准兼容导出 (P4 — 国际事实核查网络标准)
    # -----------------------------------------------------------------------
    try:
        from app.engine.ifcn_compliance import create_ifcn_compliant_review
        ifcn_review = create_ifcn_compliant_review(
            claim_text=(text or title)[:300],
            truthtrace_verdict=result.verdict.value if hasattr(result.verdict, 'value') else str(result.verdict),
            credibility_score=result.credibility_score,
            review_summary=(result.correction or result.logical_summary or "")[:300],
            claim_url=url,
        )
        result.ifcn_review = ifcn_review
        add_step(
            "IFCN 标准兼容 — 生成国际事实核查网络标准化报告",
            f"IFCN评级: {ifcn_review['ifcn_rating']} | JSON-LD + Feed 格式就绪",
            Confidence.HIGH,
            uncertainty="IFCN兼容为自动化生成，人工审核后发布可提升合规等级。",
        )
    except Exception as e:
        logger.warning(f"IFCN兼容跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 28: 多领域专家知识库查询 (expert_kb)
    # -----------------------------------------------------------------------
    try:
        from app.engine.expert_kb import query_expert_kb
        kb_result = query_expert_kb(
            text=text, title=title,
            domain_narrowing=True, max_results=5,
        )
        if kb_result and kb_result.get("matches"):
            result.expert_kb = kb_result
            add_step(
                "多领域专家知识库交叉验证",
                f"在{len(kb_result.get('domains_matched', []))}个领域中匹配到{len(kb_result['matches'])}条相关知识",
                Confidence.MODERATE,
                evidence=[Evidence(
                    description=f"[{m.get('domain', '')}] {m.get('concept', '')}: {m.get('knowledge', '')[:120]}",
                    source_url=m.get('source_url', url),
                    quality=EvidenceQuality.HIGH,
                ) for m in kb_result["matches"][:3]],
                uncertainty="专家知识库提供领域常识参考，不替代实时核查。",
            )
    except Exception as e:
        logger.warning(f"专家知识库跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 29: 预揭露接种引擎 (prebunking — Inoculation Theory)
    # -----------------------------------------------------------------------
    try:
        from app.engine.prebunking import run_prebunking_check
        prebunk = run_prebunking_check(text=text, title=title)
        result.prebunking_result = prebunk.to_dict()
        if prebunk.detection_count > 0:
            add_step(
                f"预揭露批判思维提示 — 检测到 {prebunk.detection_count} 种操纵手法",
                prebunk.summary,
                Confidence.HIGH if prebunk.risk_level == "high" else (
                    Confidence.MODERATE if prebunk.risk_level == "medium" else Confidence.LOW
                ),
                evidence=[Evidence(
                    description=f"[{t['name']}] 置信度{t['confidence']:.0%} — {t['short_desc'][:80]}",
                    source_url="",
                    quality=EvidenceQuality.MEDIUM,
                ) for t in prebunk.techniques_detected[:3]],
                uncertainty="预揭露基于统计模式匹配。命名操纵手法本身增强批判思维——不触发心理防御。效果已被33项实验(N=37,075)元分析验证。",
            )
    except Exception as e:
        logger.warning(f"预揭露引擎跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 30: 溯源可信度指数 (credibility_index — Credibility Propagation)
    # -----------------------------------------------------------------------
    try:
        from app.engine.credibility_index import compute_credibility_index
        # 从 propagation_risk 或 graph 结果中提取节点和边
        nodes_data = result.propagation_risk or {}
        graph_nodes = []
        for src in (nodes_data.get("sources") or []):
            graph_nodes.append({
                "id": src.get("url", ""),
                "url": src.get("url", ""),
                "platform": src.get("platform", ""),
                "author": src.get("author", ""),
                "is_original": src.get("is_original", False),
                "role": "originator" if src.get("is_original") else "resharer",
            })
        cred_idx = compute_credibility_index(
            nodes=graph_nodes or [{"id": url, "url": url, "platform": "unknown"}],
            root_url=url,
        )
        result.credibility_index = cred_idx.to_dict()
        if cred_idx.total_nodes > 0:
            add_step(
                f"溯源可信度指数 — {cred_idx.total_nodes}个节点传播链分析",
                cred_idx.summary,
                Confidence.HIGH if cred_idx.chain_integrity_score >= 0.6 else Confidence.MODERATE,
                evidence=[Evidence(
                    description=f"链路完整性{cred_idx.chain_integrity_score:.0%} | 平均衰减{cred_idx.average_decay_rate:.1%} | 原始源{cred_idx.original_sources_count}/{cred_idx.total_nodes}",
                    source_url="",
                    quality=EvidenceQuality.HIGH if cred_idx.original_sources_count > 0 else EvidenceQuality.MEDIUM,
                )],
                uncertainty="可信度传导基于来源权威度、内容完整度、引用质量的三维度加权。传播衰减模型考虑了边类型、时间延迟和传播角色。",
            )
    except Exception as e:
        logger.warning(f"可信度指数跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 31: 知识图谱增强推理 (kg_reasoning — GraphCheck-style KG verification)
    # -----------------------------------------------------------------------
    try:
        from app.engine.kg_reasoning import run_kg_reasoning
        kg_result = run_kg_reasoning(text=text, title=title)
        result.kg_reasoning_result = kg_result.to_dict()
        if kg_result.edges:
            add_step(
                f"知识图谱增强推理 — {len(kg_result.nodes)}个实体/{len(kg_result.edges)}条关系",
                kg_result.summary,
                Confidence.HIGH if kg_result.kg_coverage_score >= 0.5 else Confidence.MODERATE,
                evidence=[Evidence(
                    description=f"验证{len(kg_result.verified_claims)}条/反驳{len(kg_result.refuted_claims)}条 | 多跳{kg_result.multi_hop_paths}路径 | 覆盖率{kg_result.kg_coverage_score:.0%}",
                    source_url="",
                    quality=EvidenceQuality.HIGH if kg_result.verified_claims else EvidenceQuality.MEDIUM,
                )],
                uncertainty="知识图谱基于已知领域知识。新兴话题或跨领域主张可能未覆盖。建议结合实时搜索交叉验证。",
            )
    except Exception as e:
        logger.warning(f"知识图谱推理跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 32: 个性化辟谣生成 (personalized_debunking — MURSE-style)
    # -----------------------------------------------------------------------
    try:
        from app.engine.personalized_debunking import generate_personalized_debunking
        # 从correction或rigorous_analysis获取验证事实
        verified = []
        if result.correction:
            verified.append(result.correction[:300])
        if hasattr(result, 'rigorous_analysis') and result.rigorous_analysis:
            verified.append(str(result.rigorous_analysis)[:300])
        persona_result = generate_personalized_debunking(
            rumor=title or text[:100],
            verified_facts=verified or ["该主张缺乏可靠科学证据支持"],
            query=title,
        )
        result.personalized_debunking_result = persona_result.to_dict()
        add_step(
            f"个性化辟谣生成 — {persona_result.tone_used}语气/预期效果提升{persona_result.confidence_boost:.0f}%",
            persona_result.headline,
            Confidence.MODERATE,
            evidence=[Evidence(
                description=f"画像: {persona_result.persona.cognitive_style.value}/{persona_result.persona.emotional_stance.value} | 策略: {persona_result.tone_used}",
                source_url="",
                quality=EvidenceQuality.MEDIUM,
            )],
            uncertainty="个性化辟谣基于用户画像推断。不同用户的认知风格和情感倾向可能需要不同的辟谣策略。实际效果需A/B测试验证。",
        )
    except Exception as e:
        logger.warning(f"个性化辟谣跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 33: 社区众包验证 (community_verify — Community Notes-style)
    # -----------------------------------------------------------------------
    try:
        from app.engine.community_verify import run_community_verification
        community_result = run_community_verification(event_id=getattr(result, 'event_id', ''))
        result.community_verification = community_result.to_dict()
        if community_result.total_contributors > 0:
            add_step(
                f"社区众包验证 — {community_result.total_contributors}位贡献者/{len(community_result.published_notes)}条注记",
                community_result.summary,
                Confidence.HIGH if community_result.consensus_verdict in ("supported", "refuted") else Confidence.MODERATE,
                uncertainty="社区验证基于自愿贡献者的众包意见，不代表绝对真相。桥接评分算法优先跨立场共识。",
            )
    except Exception as e:
        logger.warning(f"社区验证跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 34: 多模态深度伪造检测 (deepfake_detector)
    # -----------------------------------------------------------------------
    try:
        from app.engine.deepfake_detector import run_deepfake_check
        deepfake_result = run_deepfake_check(text=text)
        result.deepfake_detection = deepfake_result.to_dict()
        if deepfake_result.findings:
            add_step(
                f"多模态深度伪造检测 — {len(deepfake_result.findings)}个异常信号/风险{deepfake_result.risk_score:.0f}/100",
                deepfake_result.summary,
                Confidence.HIGH if deepfake_result.tampering_probability > 0.5 else Confidence.MODERATE,
                evidence=[Evidence(
                    description=f"[{f.category}] {f.finding_type}: {f.description[:100]}",
                    source_url="",
                    quality=EvidenceQuality.HIGH if f.severity in ("high", "critical") else EvidenceQuality.MEDIUM,
                ) for f in deepfake_result.findings[:3]],
                uncertainty="深度伪造检测基于静态度量分析。对于复杂的视频/音频伪造，需要专业取证工具进行深度分析。",
            )
    except Exception as e:
        logger.warning(f"深度伪造检测跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 35: 谣言生命周期追踪 (rumor_lifecycle — ISDR-M/SPIDR models)
    # -----------------------------------------------------------------------
    try:
        from app.engine.rumor_lifecycle import track_rumor_lifecycle
        lifecycle_result = track_rumor_lifecycle(rumor_text=title or text[:100])
        result.rumor_lifecycle = lifecycle_result.to_dict()
        add_step(
            f"谣言生命周期追踪 — 6阶段 · 存活{lifecycle_result.total_lifetime_hours:.0f}h",
            lifecycle_result.survival_rank,
            Confidence.MODERATE,
            evidence=[Evidence(
                description=f"诞生→潜伏→放大→高峰({lifecycle_result.peak_reach:,}人)→辟谣({lifecycle_result.time_to_debunk_hours:.0f}h)→衰退 | 辟谣效果{lifecycle_result.debuff_effectiveness:.0%}",
                source_url="",
                quality=EvidenceQuality.MEDIUM,
            )],
            uncertainty="生命周期追踪基于传播模型估算。实际传播数据需从各平台API实时采集。年度报告需累计数据。",
        )
    except Exception as e:
        logger.warning(f"谣言生命周期跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 36: 信息污染指数 (pollution_index — AQI-style public product)
    # -----------------------------------------------------------------------
    try:
        from app.engine.pollution_index import compute_pollution_index
        pollution_result = compute_pollution_index()
        result.pollution_index = pollution_result.to_dict()
        add_step(
            f"信息污染指数 — 综合{pollution_result.overall_ipi:.0f} ({pollution_result.risk_level})",
            f"覆盖{pollution_result.total_analyzed:,}条内容 · {len(pollution_result.platforms)}个平台 · {len(pollution_result.topics)}个话题",
            Confidence.MODERATE,
            evidence=[Evidence(
                description=f"最污染: {max(pollution_result.platforms, key=lambda p: p.ipi_score).platform if pollution_result.platforms else 'N/A'} | 最清洁: {min(pollution_result.platforms, key=lambda p: p.ipi_score).platform if pollution_result.platforms else 'N/A'}",
                source_url="",
                quality=EvidenceQuality.LOW,
            )],
            uncertainty="信息污染指数基于统计采样和基线估计。实时精确计算需要持续的数据采集和模型校准。",
        )
    except Exception as e:
        logger.warning(f"信息污染指数跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 37: 叙事战场分析 (narrative_battlefield — 竞争叙事可视化)
    # -----------------------------------------------------------------------
    try:
        from app.engine.narrative_battlefield import analyze_narrative_battlefield
        battlefield_result = analyze_narrative_battlefield(text=text, title=title)
        result.narrative_battlefield = battlefield_result.to_dict()
        if battlefield_result.narratives:
            add_step(
                f"叙事战场分析 — {len(battlefield_result.narratives)}个竞争叙事 · 道德模糊度{battlefield_result.moral_ambiguity_score:.0%}",
                battlefield_result.summary,
                Confidence.MODERATE,
                evidence=[Evidence(
                    description=f"主导叙事: {battlefield_result.dominant_narrative.narrative_label if battlefield_result.dominant_narrative else 'N/A'} | 冲突: {len(battlefield_result.narrative_conflicts)}对",
                    source_url="",
                    quality=EvidenceQuality.MEDIUM,
                )],
                uncertainty="叙事分析不判定哪个叙事'正确'。本分析仅展示叙事景观，帮助读者理解信息的多层复杂性。",
            )
    except Exception as e:
        logger.warning(f"叙事战场跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 38: AI核查教学评估 (teach_assistant — 5维度验证矩阵)
    # -----------------------------------------------------------------------
    try:
        from app.engine.teach_assistant import generate_teaching_lesson
        teaching_result = generate_teaching_lesson(claim=title or text[:100])
        result.teaching_result = teaching_result.to_dict()
        add_step(
            f"AI核查教学 — {len(teaching_result.steps)}步验证 · 技能等级: {teaching_result.certificate_level}",
            teaching_result.feedback,
            Confidence.LOW,
            evidence=[Evidence(
                description=f"技能评估: {', '.join(f'{k}:{v:.0%}' for k,v in teaching_result.skills_assessed.items())}" if teaching_result.skills_assessed else "",
                source_url="",
                quality=EvidenceQuality.LOW,
            )],
            uncertainty="教学评估基于用户自主验证的完整性。AI仅引导思维过程，不替代人的独立判断。",
        )
    except Exception as e:
        logger.warning(f"教学评估跳过: {e}")

    # -----------------------------------------------------------------------
    # Step 39: 区块链溯源存证 (blockchain_verify — SHA-256 chain)
    # -----------------------------------------------------------------------
    try:
        from app.engine.blockchain_verify import create_verification_chain
        import hashlib
        blockchain_result = create_verification_chain(
            event_id=hashlib.sha256((url + title).encode()).hexdigest()[:16],
            analysis_data=result.to_dict(),
        )
        result.blockchain_verification = blockchain_result.to_dict()
        add_step(
            f"区块链溯源存证 — {blockchain_result.chain_length}区块 · 验证强度: {blockchain_result.verification_strength}",
            blockchain_result.summary,
            Confidence.HIGH if blockchain_result.chain_valid else Confidence.LOW,
            evidence=[Evidence(
                description=f"创世哈希: {blockchain_result.genesis_hash[:16]}... | 最新: {blockchain_result.latest_hash[:16]}... | 链完整性: {'✅' if blockchain_result.chain_valid else '❌'}",
                source_url="",
                quality=EvidenceQuality.HIGH,
            )],
            uncertainty="基于SHA-256哈希链的防篡改存证。非完整区块链，不包含分布式共识机制。适用于证据保全和可验证溯源。",
        )
    except Exception as e:
        logger.warning(f"区块链存证跳过: {e}")

    try:
        from app.evolution.calibrator import get_calibrator
        get_calibrator().record_event(result.credibility_score, result.verdict.value, result.to_dict())
    except Exception:
        pass

    return result
