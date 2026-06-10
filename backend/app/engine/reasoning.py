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
    # Map rigorous verdict back to our Verdict enum
    rv = rigorous.verdict
    v_map = {"true": Verdict.TRUE, "likely_true": Verdict.LIKELY_TRUE,
             "misleading": Verdict.MISLEADING, "likely_false": Verdict.LIKELY_FALSE,
             "false": Verdict.FALSE, "unverifiable": Verdict.UNVERIFIABLE}
    result.verdict = v_map.get(rv, Verdict.UNVERIFIABLE)
    result.confidence = Confidence(rigorous.confidence) if hasattr(Confidence, rigorous.confidence) else Confidence.MODERATE

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

    try:
        from app.evolution.calibrator import get_calibrator
        get_calibrator().record_event(result.credibility_score, result.verdict.value, result.to_dict())
    except Exception:
        pass

    return result
