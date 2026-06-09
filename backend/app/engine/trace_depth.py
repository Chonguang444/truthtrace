"""
5 层溯源深度引擎 — 从表面到利益的完整追溯

L1 表面溯源: 找到最早发帖 URL + 时间戳
L2 内容溯源: 检测内容是否被篡改/编辑/剪辑
L3 来源溯源: 分析发布者身份、历史行为、关联账号
L4 叙事溯源: 识别信息嵌入的叙事框架
L5 利益溯源: 分析传播背后的利益结构

每层都有明确的:
- 需要什么数据
- 做什么分析
- 输出什么结论
- 不确定时怎么说
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from app.engine.types import (
    TraceDepth, TraceAnalysis, Confidence, NarrativeType,
    Evidence, EvidenceType, EvidenceQuality,
)


# =============================================================================
# L1: 表面溯源 (SURFACE)
# =============================================================================

def trace_L1_surface(
    url: str,
    url_chain: list[str] | None = None,
    page_published_at: Optional[datetime] = None,
    earliest_reference_url: str = "",
    earliest_reference_time: Optional[datetime] = None,
) -> dict:
    """
    L1 表面溯源: 找到信息最早出现的位置和时间。

    输入:
    - url: 目标 URL
    - url_chain: URL 跳转链 (短链接→原始链接)
    - page_published_at: 页面发布时间
    - earliest_reference_url: 搜索到的最早引用 URL
    - earliest_reference_time: 最早引用的时间

    输出:
    - 最早已知来源 URL 和时间
    - URL 跳转链长度
    - 置信度评估
    """
    result = {
        "depth": TraceDepth.L1_SURFACE,
        "earliest_known_url": earliest_reference_url or url,
        "earliest_known_time": earliest_reference_time or page_published_at,
        "url_chain_length": len(url_chain) if url_chain else 0,
        "has_redirect_chain": bool(url_chain and len(url_chain) > 1),
        "confidence": Confidence.MODERATE,
        "limitations": [],
    }

    # 评估置信度
    if earliest_reference_url and earliest_reference_time:
        result["confidence"] = Confidence.HIGH
    elif page_published_at:
        result["confidence"] = Confidence.MODERATE
        result["limitations"].append("仅基于目标页面自身的时间戳，未进行全网搜索比对")
    else:
        result["confidence"] = Confidence.LOW
        result["limitations"].append("无法确定信息的首次发布时间")

    # URL 跳转链分析
    if url_chain and len(url_chain) > 3:
        result["limitations"].append(f"URL 经过了 {len(url_chain)} 次跳转，可能存在中间节点的信息篡改")

    return result


# =============================================================================
# L2: 内容溯源 (CONTENT)
# =============================================================================

def trace_L2_content(
    content_hash: str = "",
    content_length: int = 0,
    has_multiple_versions: bool = False,
    version_hashes: list[str] | None = None,
    edit_history_available: bool = False,
    metadata_stripped: bool = False,
) -> dict:
    """
    L2 内容溯源: 检测内容是否被篡改、剪辑、编辑。

    检测维度:
    - 内容指纹 (SimHash) 是否有多个版本
    - 是否有编辑历史
    - 元数据是否完整
    - 图片/视频是否经过处理

    注意: 在没有原文比对的情况下，只能做模式检测，
    不能断言"内容一定被篡改"。
    """
    result = {
        "depth": TraceDepth.L2_CONTENT,
        "content_integrity": "unknown",
        "tampering_indicators": [],
        "version_count": len(version_hashes) if version_hashes else 0,
        "edit_history_available": edit_history_available,
        "confidence": Confidence.MODERATE,
        "limitations": [],
    }

    # 多版本 = 内容可能被修改过
    if has_multiple_versions and version_hashes and len(version_hashes) > 1:
        result["content_integrity"] = "compromised"
        result["tampering_indicators"].append(
            f"检测到 {len(version_hashes)} 个不同版本的内容（不同 SimHash），可能存在内容修改"
        )
        result["confidence"] = Confidence.HIGH

    elif edit_history_available:
        result["content_integrity"] = "verifiable"
        result["confidence"] = Confidence.HIGH
    else:
        result["content_integrity"] = "unverified"
        result["limitations"].append("未获取到内容编辑历史，无法判断内容是否被修改")
        result["confidence"] = Confidence.LOW

    # 元数据检测
    if metadata_stripped:
        result["tampering_indicators"].append("检测到元数据被清除或缺失——可能是故意为之")
        result["confidence"] = Confidence.MODERATE

    # 长度极短 — 可能被裁切
    if 0 < content_length < 100:
        result["tampering_indicators"].append(
            f"内容长度仅 {content_length} 字符——可能是从更长内容中截取，需要查看完整原文"
        )

    return result


# =============================================================================
# L3: 来源溯源 (SOURCE)
# =============================================================================

def trace_L3_source(
    author: str = "",
    author_id: str = "",
    platform: str = "",
    author_history: list[dict] | None = None,
    account_age_days: Optional[int] = None,
    follower_count: int = 0,
    has_verified_badge: bool = False,
    related_accounts: list[str] | None = None,
    prior_credibility_scores: list[float] | None = None,
) -> dict:
    """
    L3 来源溯源: 分析发布者的可信度。

    分析维度:
    - 账号历史 (新号 vs 老号)
    - 发布频率和内容一致性
    - 是否有认证
    - 历史可信度记录
    - 关联账号（是否属于某个网络）

    注意: 新账号不直接等于不可信——需要更多证据。
    """
    result = {
        "depth": TraceDepth.L3_SOURCE,
        "author_credibility_score": 50.0,
        "indicators": [],
        "risk_factors": [],
        "confidence": Confidence.MODERATE,
        "limitations": [],
    }

    score = 50.0

    # 认证加分
    if has_verified_badge:
        score += 15
        result["indicators"].append("账号有平台认证标识")
    else:
        result["indicators"].append("账号无认证——无法确认身份真实性")

    # 账号年龄
    if account_age_days is not None:
        if account_age_days < 30:
            score -= 20
            result["risk_factors"].append(f"账号注册仅 {account_age_days} 天——新账号风险较高")
        elif account_age_days < 180:
            score -= 5
            result["risk_factors"].append(f"账号注册 {account_age_days} 天——相对较新")
        elif account_age_days > 365 * 3:
            score += 10
            result["indicators"].append(f"账号注册超过 {account_age_days//365} 年——长期活跃账号")

    # 历史可信度
    if prior_credibility_scores:
        avg = sum(prior_credibility_scores) / len(prior_credibility_scores)
        score = score * 0.6 + avg * 0.4  # 平滑融合
        if avg < 40:
            result["risk_factors"].append(f"该账号历史平均可信度较低 ({avg:.0f})")

    # 关联账号
    if related_accounts and len(related_accounts) > 5:
        result["risk_factors"].append(
            f"发现 {len(related_accounts)} 个关联账号——可能是协同操作网络"
        )
        if len(related_accounts) > 20:
            score -= 15

    # 粉丝数——极端值需注意（可能是买粉）
    if follower_count > 100000:
        result["indicators"].append(f"账号有 {follower_count:,} 关注者——影响力较大")
    elif follower_count < 10:
        result["indicators"].append("账号关注者极少——影响力有限")

    result["author_credibility_score"] = max(0.0, min(100.0, score))

    # 置信度
    if author_id and author_history is not None:
        result["confidence"] = Confidence.HIGH
    elif author:
        result["confidence"] = Confidence.MODERATE
    else:
        result["confidence"] = Confidence.LOW
        result["limitations"].append("无法识别发布者身份")

    return result


# =============================================================================
# L4: 叙事溯源 (NARRATIVE)
# =============================================================================

def trace_L4_narrative(
    narrative_type: Optional[NarrativeType] = None,
    narrative_confidence: Confidence = Confidence.MODERATE,
    narrative_markers: list[str] | None = None,
    text: str = "",
) -> dict:
    """
    L4 叙事溯源: 识别信息所嵌入的叙事框架。

    叙事框架是"信息的壳"——同一套事实可以被套入不同的叙事框架，
    从而产生完全不同的解读。

    例如: "某添加剂在一定剂量下安全" 这套事实可以:
    - 正常叙事: "添加剂在标准范围内安全"
    - 恐惧叙事: "他们往我们的食物里加化学物质!"
    """
    result = {
        "depth": TraceDepth.L4_NARRATIVE,
        "narrative_type": narrative_type.value if narrative_type else None,
        "narrative_confidence": narrative_confidence.value,
        "narrative_markers": narrative_markers or [],
        "is_embedded_in_narrative": narrative_type is not None,
        "neutrality_assessment": "neutral",
        "limitations": [],
    }

    if narrative_type:
        result["neutrality_assessment"] = "biased"
        result["limitations"].append(
            "信息被嵌入特定叙事框架中——即使事实本身准确，叙事框架可能扭曲读者的理解"
        )
    else:
        result["neutrality_assessment"] = "neutral"

    if not text:
        result["limitations"].append("未提供文本内容，无法进行完整的叙事分析")

    return result


# =============================================================================
# L5: 利益溯源 (INTEREST)
# =============================================================================

def trace_L5_interest(
    propagation_pattern: str = "",       # "organic" | "coordinated" | "amplified"
    commercial_links: list[str] | None = None,  # 商业利益关联
    political_affiliations: list[str] | None = None,  # 政治关联
    funding_sources: list[str] | None = None,  # 资金来源
    bot_likelihood: float = 0.0,        # 机器人概率 0-1
    coordinated_network_size: int = 0,  # 协同网络规模
) -> dict:
    """
    L5 利益溯源: 分析传播背后的利益结构。

    这是最深层的分析——"谁在推动这个信息的传播？谁从中获益？"

    警告: 利益分析是最容易产生猜测性结论的层级。
    本模块严格遵循"无证据不说话"原则。
    """
    result = {
        "depth": TraceDepth.L5_INTEREST,
        "propagation_pattern": propagation_pattern or "unknown",
        "interest_indicators": [],
        "confidence": Confidence.LOW,  # L5 天然置信度较低
        "caveat": "利益分析具有高度推测性。以下分析仅基于可获取的公开信息，存在大量未知因素。请谨慎对待任何将'谁获益'等同于'谁策划'的论断。",
        "limitations": [],
    }

    # 传播模式分析
    if bot_likelihood > 0.7:
        result["interest_indicators"].append(
            f"检测到高概率自动化传播行为 (bot_likelihood={bot_likelihood:.0%})"
        )
        result["propagation_pattern"] = "coordinated"
    elif coordinated_network_size > 3:
        result["interest_indicators"].append(
            f"发现 {coordinated_network_size} 个账号协同传播——可能是组织化推广"
        )
        result["propagation_pattern"] = "coordinated"

    # 商业利益
    if commercial_links:
        result["interest_indicators"].append(
            f"发现 {len(commercial_links)} 个商业利益关联: {', '.join(commercial_links[:5])}"
        )

    # 政治关联
    if political_affiliations:
        result["interest_indicators"].append(
            f"发现 {len(political_affiliations)} 个政治关联"
        )

    # 资金
    if funding_sources:
        result["interest_indicators"].append(
            f"发现资金来源: {', '.join(funding_sources[:3])}"
        )

    # 置信度调整
    found_indicators = len(result["interest_indicators"])
    if found_indicators >= 3:
        result["confidence"] = Confidence.MODERATE
    elif found_indicators >= 1:
        result["confidence"] = Confidence.LOW
    else:
        result["confidence"] = Confidence.UNCERTAIN
        result["interest_indicators"].append("未发现明确的利益关联证据")
        result["propagation_pattern"] = "organic"  # 表面看是自然传播

    return result


# =============================================================================
# 统一溯源分析: 根据可用数据执行尽可能深的分析
# =============================================================================

def analyze_trace(
    url: str = "",
    text: str = "",
    title: str = "",
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
    narrative_type: Optional[NarrativeType] = None,
    narrative_markers: list[str] | None = None,
    propagation_pattern: str = "",
    commercial_links: list[str] | None = None,
    bot_likelihood: float = 0.0,
    prior_credibility_scores: list[float] | None = None,
) -> TraceAnalysis:
    """
    根据可用数据执行最深层的溯源分析。

    数据越丰富，溯源深度越深。
    数据不足时诚实承认，不编造。
    """

    # L1: 始终可以执行
    l1 = trace_L1_surface(
        url=url,
        url_chain=url_chain,
        page_published_at=page_published_at,
    )

    # L2: 需要内容哈希
    if content_hash:
        l2 = trace_L2_content(
            content_hash=content_hash,
            content_length=len(text),
            has_multiple_versions=bool(version_hashes and len(version_hashes) > 1),
            version_hashes=version_hashes,
            edit_history_available=edit_history_available,
        )
    else:
        l2 = None

    # L3: 需要发布者信息
    if author or author_id:
        l3 = trace_L3_source(
            author=author,
            author_id=author_id,
            platform=platform,
            has_verified_badge=has_verified_badge,
            account_age_days=account_age_days,
            follower_count=follower_count,
            prior_credibility_scores=prior_credibility_scores,
        )
    else:
        l3 = None

    # L4: 需要文本内容
    if text and narrative_type:
        l4 = trace_L4_narrative(
            narrative_type=narrative_type,
            narrative_markers=narrative_markers or [],
            text=text,
        )
    else:
        l4 = None

    # L5: 需要传播模式数据
    if propagation_pattern or bot_likelihood > 0.3 or (commercial_links and len(commercial_links) > 0):
        l5 = trace_L5_interest(
            propagation_pattern=propagation_pattern,
            commercial_links=commercial_links,
            bot_likelihood=bot_likelihood,
        )
    else:
        l5 = None

    # 确定达到的深度
    if l5 and l5["confidence"] != Confidence.UNCERTAIN:
        depth_achieved = TraceDepth.L5_INTEREST
    elif l4 and l4["narrative_type"]:
        depth_achieved = TraceDepth.L4_NARRATIVE
    elif l3 and l3["confidence"] == Confidence.HIGH:
        depth_achieved = TraceDepth.L3_SOURCE
    elif l2 and l2["content_integrity"] != "unknown":
        depth_achieved = TraceDepth.L2_CONTENT
    else:
        depth_achieved = TraceDepth.L1_SURFACE

    # 构建分析结果
    return TraceAnalysis(
        depth_achieved=depth_achieved,
        earliest_source_url=url,
        earliest_timestamp=page_published_at,
        propagation_hop_count=len(url_chain) if url_chain else 0,
        content_tampering_detected=bool(l2 and l2.get("tampering_indicators")),
        source_credibility_score=(l3.get("author_credibility_score", 50.0) if l3 else 50.0),
        narrative_framework=narrative_type,
        interest_structure=(l5.get("propagation_pattern", "") if l5 else ""),
        details={
            "L1": l1,
            "L2": l2,
            "L3": l3,
            "L4": l4,
            "L5": l5,
        },
    )
