"""
LLM 增强分析引擎 — 两级分析架构

架构:
L1: 10个正则引擎 (当前) → 快速、免费、覆盖常见模式
L2: Claude API 深度分析 (新增) → 对L1高评分案例进行语义深度分析

L1 vs L2 分工:
- L1: 模式匹配 + 统计检测 + 结构分析 — 能找到"表面"问题
- L2: 隐含讽刺/反讽理解 + 间接引用识别 + 复杂句法推理 + 跨句推理链

原则:
- LLM 只做"分析"不做"判定" — 最终判定仍由确定性规则做出
- L2 不替代 L1 — L1 的结果是 L2 的输入
- L2 在 L1 评分高时才触发 — 减少成本和延迟
- L2 的输出被记录为额外的分析维度 — 不直接决定 verdict
"""

from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field

from app.engine.types import Confidence

logger = logging.getLogger("truthtrace.llm")


# =============================================================================
# LLM 分析结果类型
# =============================================================================

@dataclass
class LLMAnalysisResult:
    """LLM 深度分析结果"""
    # 语义理解
    surface_meaning: str = ""         # 表面含义
    implied_meaning: str = ""         # 隐含含义
    irony_sarcasm_detected: bool = False  # 是否检测到反讽/讽刺
    irony_explanation: str = ""

    # 修辞分析
    rhetorical_devices: list[str] = field(default_factory=list)   # 修辞手法
    emotional_manipulation_techniques: list[str] = field(default_factory=list)  # 情感操纵技巧

    # 引用分析
    citations_verified: list[dict] = field(default_factory=list)      # 可验证的引用
    citations_unverifiable: list[dict] = field(default_factory=list)  # 无法验证的引用
    citations_misleading: list[dict] = field(default_factory=list)    # 误导性引用

    # 推理分析
    hidden_premises: list[str] = field(default_factory=list)  # 隐含前提
    logical_gaps: list[str] = field(default_factory=list)     # 逻辑缺口
    fallacies_found: list[str] = field(default_factory=list)  # LLM识别的谬误

    # 整体评估
    semantic_risk_score: float = 0.0   # 0-100 语义层面的操纵风险
    analysis_quality: str = ""         # "high" / "moderate" / "low"
    model_used: str = ""               # 使用的模型
    tokens_used: int = 0

    # 不确定性
    llm_caveats: str = ("大型语言模型分析可能存在偏见和幻觉。"
                        "此分析仅作为辅助参考，不能替代人工判断。"
                        "最终的事实判定应基于可验证的证据而非LLM输出。")

    def to_dict(self) -> dict:
        return {
            "surface_meaning": self.surface_meaning,
            "implied_meaning": self.implied_meaning,
            "irony_sarcasm_detected": self.irony_sarcasm_detected,
            "irony_explanation": self.irony_explanation,
            "rhetorical_devices": self.rhetorical_devices,
            "emotional_manipulation_techniques": self.emotional_manipulation_techniques,
            "citations_verified": self.citations_verified,
            "citations_unverifiable": self.citations_unverifiable,
            "citations_misleading": self.citations_misleading,
            "hidden_premises": self.hidden_premises,
            "logical_gaps": self.logical_gaps,
            "fallacies_found": self.fallacies_found,
            "semantic_risk_score": self.semantic_risk_score,
            "analysis_quality": self.analysis_quality,
            "model_used": self.model_used,
            "tokens_used": self.tokens_used,
            "llm_caveats": self.llm_caveats,
        }


# =============================================================================
# L2 分析触发条件
# =============================================================================

def should_trigger_llm(l1_analysis: dict) -> bool:
    """
    判断是否应该触发 LLM 深度分析。

    触发条件 (满足任一):
    - L1 失真风险 HIGH
    - L1 逻辑谬误 ≥ 3 处
    - L1 叙事操纵评分 > 60
    - L1 统计滥用风险 > 50
    - L1 综合可信度 < 40
    """
    if not l1_analysis:
        return False

    # 失真风险
    distortion = l1_analysis.get("distortion_analysis", {})
    if distortion.get("overall_risk") == "high":
        return True

    # 逻辑谬误数量
    fallacy = l1_analysis.get("fallacy_analysis", {})
    if fallacy.get("fallacy_count", 0) >= 3:
        return True

    # 叙事操纵评分
    narrative = l1_analysis.get("narrative_analysis", {})
    if narrative.get("manipulation_score", 0) > 60:
        return True

    # 统计滥用
    statistical = l1_analysis.get("statistical_analysis", {})
    if statistical.get("risk_score", 0) > 50:
        return True

    # 综合可信度
    if l1_analysis.get("credibility_score", 100) < 40:
        return True

    return False


# =============================================================================
# L2: Claude API 深度语义分析
# =============================================================================

def _build_llm_prompt(title: str, text: str, l1_summary: dict) -> str:
    """构建 LLM 分析提示词"""
    # 将L1结果压缩为摘要
    l1_brief = json.dumps({
        "distortion_risk": l1_summary.get("distortion_analysis", {}).get("overall_risk"),
        "distortion_count": len(l1_summary.get("distortion_analysis", {}).get("matches", [])),
        "fallacy_count": l1_summary.get("fallacy_analysis", {}).get("fallacy_count", 0),
        "narrative_dominant": l1_summary.get("narrative_analysis", {}).get("dominant_narrative"),
        "manipulation_score": l1_summary.get("narrative_analysis", {}).get("manipulation_score"),
        "credibility_score": l1_summary.get("credibility_score"),
    }, ensure_ascii=False)

    return f"""你是一个信息验证助手。请对以下信息进行深度语义分析。

注意: 你只做分析，不做判定。你的分析结果将作为参考输入给另一个系统。

【信息标题】
{title}

【信息正文】
{text[:2000]}

【L1引擎初步分析结果】
{l1_brief}

请返回JSON格式的分析结果 (不要markdown代码块，纯JSON):
{{
  "surface_meaning": "信息的表面含义 (1-2句话)",
  "implied_meaning": "信息的隐含含义或暗示 (如果有的话，没有则写'无明显隐含含义')",
  "irony_sarcasm_detected": true/false,
  "irony_explanation": "如果有反讽/讽刺，解释具体是什么。没有则写'无'",
  "rhetorical_devices": ["识别到的修辞手法列表: 夸张/隐喻/排比/反问等"],
  "emotional_manipulation_techniques": ["识别到的情感操纵技巧: 恐惧诉求/道德绑架/受害者叙事等"],
  "citations_verifiable": [{{"claim": "具体主张", "source_hint": "指向什么来源"}}],
  "citations_unverifiable": [{{"claim": "具体主张", "why": "为什么无法验证"}}],
  "citations_misleading": [{{"claim": "具体主张", "issue": "为什么是误导性的"}}],
  "hidden_premises": ["论证中未明说但暗含的前提"],
  "logical_gaps": ["论证链条中的逻辑断裂"],
  "fallacies_found": ["识别到的逻辑谬误名称"],
  "semantic_risk_score": 0-100的数值 (语义层面的操纵风险),
  "analysis_quality": "high/moderate/low" (你对这次分析质量的信心)
}}"""


async def run_llm_analysis(
    title: str,
    text: str,
    l1_analysis: dict,
    api_key: str | None = None,
    model: str = "claude-sonnet-4-6",
) -> LLMAnalysisResult | None:
    """
    调用 Claude API 进行 L2 深度语义分析。

    Args:
        title: 信息标题
        text: 信息正文
        l1_analysis: L1 10引擎的完整分析结果
        api_key: Anthropic API key (不提供则从环境变量读取)
        model: 使用的模型

    Returns:
        LLMAnalysisResult 或 None (如果调用失败或API不可用)
    """
    if not should_trigger_llm(l1_analysis):
        logger.debug("L1 评分未达到 LLM 分析触发阈值")
        return None

    try:
        import os
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            logger.info("未设置 ANTHROPIC_API_KEY, 跳过 LLM 增强分析")
            return None

        import httpx
        prompt = _build_llm_prompt(title, text, l1_analysis)

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )

            if resp.status_code != 200:
                logger.warning(f"Claude API 返回 {resp.status_code}: {resp.text[:200]}")
                return None

            data = resp.json()
            content = data.get("content", [{}])[0].get("text", "")

            # 提取 JSON
            try:
                # 尝试直接解析
                parsed = json.loads(content)
            except json.JSONDecodeError:
                # 尝试从文本中提取 JSON 块
                import re
                match = re.search(r'\{[\s\S]*\}', content)
                if match:
                    try:
                        parsed = json.loads(match.group())
                    except json.JSONDecodeError:
                        logger.warning("无法解析 LLM 返回的 JSON")
                        return None
                else:
                    return None

            return LLMAnalysisResult(
                surface_meaning=parsed.get("surface_meaning", ""),
                implied_meaning=parsed.get("implied_meaning", ""),
                irony_sarcasm_detected=parsed.get("irony_sarcasm_detected", False),
                irony_explanation=parsed.get("irony_explanation", ""),
                rhetorical_devices=parsed.get("rhetorical_devices", []),
                emotional_manipulation_techniques=parsed.get("emotional_manipulation_techniques", []),
                citations_verifiable=parsed.get("citations_verifiable", []),
                citations_unverifiable=parsed.get("citations_unverifiable", []),
                citations_misleading=parsed.get("citations_misleading", []),
                hidden_premises=parsed.get("hidden_premises", []),
                logical_gaps=parsed.get("logical_gaps", []),
                fallacies_found=parsed.get("fallacies_found", []),
                semantic_risk_score=float(parsed.get("semantic_risk_score", 0)),
                analysis_quality=parsed.get("analysis_quality", "moderate"),
                model_used=model,
                tokens_used=int(data.get("usage", {}).get("output_tokens", 0)),
            )

    except ImportError:
        logger.info("httpx 不可用，跳过 LLM 分析")
        return None
    except Exception as e:
        logger.warning(f"LLM 分析失败: {e}")
        return None


# =============================================================================
# Sift Critic Agent — 对抗审查 (P1)
# =============================================================================
# 在所有引擎完成后运行，审查引擎间一致性，标记潜在误报。

@dataclass
class CriticReview:
    """Critic Agent 审查结果"""
    inter_engine_agreement: float = 0.0      # 引擎间一致性 0-1
    conflicting_findings: list[dict] = field(default_factory=list)
    confidence_adjustment: float = 0.0       # 置信度调整 (-20 to +20)
    false_positive_risks: list[str] = field(default_factory=list)
    reviewer_notes: str = ""

    def to_dict(self) -> dict:
        return {
            "inter_engine_agreement": round(self.inter_engine_agreement, 2),
            "conflicting_findings": self.conflicting_findings,
            "confidence_adjustment": round(self.confidence_adjustment, 1),
            "false_positive_risks": self.false_positive_risks,
            "reviewer_notes": self.reviewer_notes,
        }


def run_critic_review(engine_results: dict) -> CriticReview:
    """
    Sift 式 Critic Agent 对抗审查。

    在所有引擎完成后运行，审查:
    1. 引擎间一致性 — 各引擎是否指向同一结论
    2. 矛盾发现 — 哪些引擎结论互相冲突
    3. 误报风险 — 哪些检测可能是假阳性
    4. 置信度校准 — 综合调整可信度
    """
    review = CriticReview()

    # 1. 收集各引擎的"方向"信号
    signals: list[tuple[str, float, str]] = []  # (engine_name, strength, direction)

    # 失真检测 → 有匹配=负面信号
    distortion = engine_results.get("distortion_analysis", {}) or {}
    if isinstance(distortion, dict):
        d_matches = len(distortion.get("matches", []))
        if d_matches > 0:
            risk = distortion.get("overall_risk", "moderate")
            risk_map = {"high": 0.9, "moderate": 0.5, "low": 0.2}
            signals.append(("distortion", risk_map.get(str(risk), 0.5) * min(d_matches, 5) / 5, "negative"))

    # 逻辑谬误
    fallacy = engine_results.get("fallacy_analysis", {}) or {}
    if isinstance(fallacy, dict):
        fc = fallacy.get("fallacy_count", 0)
        if fc > 0:
            signals.append(("fallacy", min(fc / 10, 1.0), "negative"))

    # 统计滥用
    stat = engine_results.get("statistical_analysis", {}) or {}
    if isinstance(stat, dict):
        sr = stat.get("risk_score", 0)
        if sr > 10:
            signals.append(("statistical", sr / 100, "negative"))

    # 域验证 → 有被反驳的主张
    domain = engine_results.get("domain_analysis", {}) or {}
    if isinstance(domain, dict):
        refuted = len(domain.get("refuted_claims", []))
        if refuted > 0:
            signals.append(("domain", min(refuted / 5, 1.0), "negative"))

    # AI 检测
    ai = engine_results.get("ai_detection", {}) or {}
    if isinstance(ai, dict):
        ai_score = ai.get("risk_score", 0)
        if ai_score > 20:
            signals.append(("ai_detection", ai_score / 100, "negative"))

    # lmscan
    lmscan = engine_results.get("lmscan_detection", {}) or {}
    if isinstance(lmscan, dict):
        lp = lmscan.get("ai_probability", 0)
        if lp > 0.3:
            signals.append(("lmscan", lp, "negative"))

    # smellcheck
    smell = engine_results.get("smellcheck_detection", {}) or {}
    if isinstance(smell, dict):
        sa = smell.get("anomaly_score", 0)
        if sa > 20:
            signals.append(("smellcheck", sa / 100, "negative"))

    # SatyaLens 引用完整性
    satyalens = engine_results.get("satyalens_score", {}) or {}
    if isinstance(satyalens, dict):
        si = satyalens.get("overall_integrity_score", 0.5)
        if si < 0.3:
            signals.append(("satyalens", 1.0 - si, "negative"))
        elif si > 0.7:
            signals.append(("satyalens", si, "positive"))

    # 2. 计算一致性
    negative_signals = [s for s in signals if s[2] == "negative"]
    positive_signals = [s for s in signals if s[2] == "positive"]

    # 引擎间一致性 = 同向信号强度 / 总信号强度
    neg_strengths = [s[1] for s in negative_signals]
    pos_strengths = [s[1] for s in positive_signals]
    total_strength = sum(neg_strengths) + sum(pos_strengths) + 0.001

    # 如果大部分信号同向 → 高一致性
    if neg_strengths and not pos_strengths:
        review.inter_engine_agreement = min(sum(neg_strengths) / len(neg_strengths), 1.0)
    elif pos_strengths and not neg_strengths:
        review.inter_engine_agreement = min(sum(pos_strengths) / len(pos_strengths), 1.0)
    else:
        # 正负信号都有 → 低一致性
        review.inter_engine_agreement = max(0, 1.0 - abs(
            sum(neg_strengths) - sum(pos_strengths)) / total_strength)

    # 3. 检测矛盾的发现
    if len(negative_signals) >= 2 and len(positive_signals) >= 1:
        review.conflicting_findings.append({
            "type": "polarity_conflict",
            "negative_engines": [s[0] for s in negative_signals],
            "positive_engines": [s[0] for s in positive_signals],
            "note": "部分引擎标记为问题内容，但其他引擎显示正面信号。这可能意味着特殊的边缘情况。",
        })

    # 4. 标记误报风险
    # 仅单个引擎标记为高 → 可能误报
    if len(negative_signals) == 1 and negative_signals[0][1] > 0.7:
        review.false_positive_risks.append(
            f"仅 '{negative_signals[0][0]}' 引擎给出高信号 ({negative_signals[0][1]:.2f})，"
            f"其他引擎未发现对应问题。建议人工复核。"
        )

    # 仅模式匹配引擎标记 → 可能误报
    pattern_engines = {"distortion", "fallacy", "statistical", "composite"}
    flagged_pattern = [s for s in negative_signals if s[0] in pattern_engines]
    if len(flagged_pattern) >= 2 and len(negative_signals) == len(flagged_pattern):
        review.false_positive_risks.append(
            "仅模式匹配引擎给出负面信号，深层语义引擎 (AI检测/引用完整性) 未发现异常。"
            "模式匹配可能在讽刺/反讽/幽默文本上产生误报。"
        )

    # 5. 置信度校准
    # 高一致性 → 提升置信度
    if review.inter_engine_agreement > 0.8 and len(signals) >= 3:
        review.confidence_adjustment = +10.0
    elif review.inter_engine_agreement > 0.6:
        review.confidence_adjustment = +5.0
    # 有冲突 → 降低
    if review.conflicting_findings:
        review.confidence_adjustment -= 10.0
    # 有误报风险 → 降低
    if review.false_positive_risks:
        review.confidence_adjustment -= 5.0 * len(review.false_positive_risks)

    # Clamp
    review.confidence_adjustment = max(-20.0, min(20.0, review.confidence_adjustment))

    # 6. 生成审查笔记
    parts = []
    if signals:
        parts.append(f"{len(signals)} 引擎发出信号 ("
                    f"{len(negative_signals)}负/{len(positive_signals)}正)")
    parts.append(f"引擎一致性: {review.inter_engine_agreement:.0%}")
    parts.append(f"置信度调整: {review.confidence_adjustment:+.0f}")
    if review.conflicting_findings:
        parts.append("⚠ 发现矛盾信号 — 建议人工复核")
    if review.false_positive_risks:
        parts.append("⚠ 存在误报风险")
    review.reviewer_notes = " | ".join(parts)

    return review
