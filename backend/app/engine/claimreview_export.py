"""
ClaimReview 结构化导出 — Schema.org ClaimReview + Google Fact Check 标记

生成符合以下标准的结构化事实核查数据:
- Schema.org ClaimReview (JSON-LD)
- Google Fact Check Tool 标记规范
- 可供搜索引擎直接索引的结构化辟谣数据

用法:
    from app.engine.claimreview_export import export_claimreview
    jsonld = export_claimreview(analysis_result, publisher_info)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ClaimReviewRecord:
    """一条 ClaimReview 记录"""
    # 主张信息
    claim_text: str = ""                    # 被核查的主张原文
    claim_author: str = ""                  # 主张提出者
    claim_date: str = ""                    # 主张发布日期 (ISO 8601)

    # 核查结果
    review_rating: str = ""                 # 核查评级 (见 RATING_MAP)
    review_text: str = ""                   # 核查说明
    review_url: str = ""                    # 核查报告 URL
    review_date: str = ""                   # 核查日期

    # 核查方信息
    publisher_name: str = "TruthTrace"     # 发布者名称
    publisher_url: str = ""                 # 发布者网站

    # 来源
    evidence_sources: list[dict] = field(default_factory=list)
    # [{"url": "...", "title": "...", "type": "government|academic|media|other"}]

    # 元数据
    language: str = "zh-CN"
    item_reviewed_type: str = "Claim"       # Schema.org 类型

    def to_dict(self) -> dict:
        return {
            "@context": "https://schema.org",
            "@type": "ClaimReview",
            "claimReviewed": self.claim_text[:500],
            "author": {
                "@type": "Organization" if not self.claim_author else "Person",
                "name": self.claim_author or "未知",
            },
            "datePublished": self.claim_date,
            "reviewRating": {
                "@type": "Rating",
                "ratingValue": rating_to_numeric(self.review_rating),
                "alternateName": self.review_rating,
            },
            "itemReviewed": {
                "@type": self.item_reviewed_type,
                "author": {
                    "@type": "Person",
                    "name": self.claim_author or "未知来源",
                },
                "datePublished": self.claim_date,
            },
            "url": self.review_url,
            "publisher": {
                "@type": "Organization",
                "name": self.publisher_name,
                "url": self.publisher_url,
            },
            "reviewBody": self.review_text[:2000],
        }

    def to_jsonld(self) -> str:
        """序列化为 JSON-LD script 标签内容"""
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


# =============================================================================
# 核查评级映射
# =============================================================================

# TruthTrace Verdict → Schema.org / Google Fact Check 评级
RATING_MAP = {
    "true": "True",
    "likely_true": "Mostly True",
    "misleading": "Misleading",
    "likely_false": "Mostly False",
    "false": "False",
    "unverifiable": "Unverifiable",
    "true but": "TrueBut",          # 事实正确但具有误导性
    "mixture": "Mixture",           # 部分真实部分虚假
    "satire": "Satire",             # 讽刺/恶搞
    "outdated": "Outdated",         # 过时信息
    "missing_context": "MissingContext",
    "edited": "Edited",             # 经过编辑/篡改的图像或视频
}

# 评级数值 (1=True, -1=False)
RATING_NUMERIC = {
    "True": 5, "Mostly True": 4, "Mixture": 3,
    "Misleading": 2, "MissingContext": 2,
    "Mostly False": 1, "False": 0,
    "Unverifiable": -1, "Satire": -1, "Outdated": 1,
    "TrueBut": 3, "Edited": 1,
}


def rating_to_numeric(rating: str) -> int:
    """将文字评级转换为数值"""
    return RATING_NUMERIC.get(rating, -1)


def verdict_to_rating(verdict: str) -> str:
    """TruthTrace 内部判定 → 标准化评级"""
    return RATING_MAP.get(verdict, "Unverifiable")


# =============================================================================
# 导出函数
# =============================================================================

def export_claimreview(
    claim_text: str = "",
    claim_author: str = "",
    claim_date: str = "",
    verdict: str = "unverifiable",
    credibility_score: float = 50.0,
    review_text: str = "",
    review_url: str = "",
    evidence_sources: list[dict] | None = None,
    publisher_name: str = "TruthTrace",
    publisher_url: str = "https://truthtrace.app",
    language: str = "zh-CN",
) -> ClaimReviewRecord:
    """
    导出标准 ClaimReview 记录。

    用法:
        record = export_claimreview(
            claim_text="喝柠檬水能治疗癌症",
            verdict="false",
            credibility_score=12.0,
            review_text="经过WHO、FDA及多项临床研究确认，柠檬水无治疗癌症的功效。",
            evidence_sources=[{"url": "https://...", "type": "government"}],
        )
        jsonld = record.to_jsonld()
    """
    rating = verdict_to_rating(verdict)

    return ClaimReviewRecord(
        claim_text=claim_text,
        claim_author=claim_author,
        claim_date=claim_date or datetime.now(timezone.utc).isoformat(),
        review_rating=rating,
        review_text=review_text or f"经TruthTrace多引擎分析，该主张可信度评分为{credibility_score:.0f}/100，判定为{rating}。",
        review_url=review_url,
        review_date=datetime.now(timezone.utc).isoformat(),
        publisher_name=publisher_name,
        publisher_url=publisher_url,
        evidence_sources=evidence_sources or [],
        language=language,
    )


def export_from_analysis_result(
    analysis_result: dict,
    publisher_name: str = "TruthTrace",
    publisher_url: str = "https://truthtrace.app",
) -> ClaimReviewRecord:
    """
    从 AnalysisResult.to_dict() 导出 ClaimReview。
    这是管线集成的便捷入口。
    """
    return export_claimreview(
        claim_text=analysis_result.get("input_title", ""),
        claim_author="",
        claim_date=analysis_result.get("analyzed_at", ""),
        verdict=analysis_result.get("verdict", "unverifiable"),
        credibility_score=analysis_result.get("credibility_score", 50.0),
        review_text=analysis_result.get("correction", ""),
        review_url=analysis_result.get("input_url", ""),
        publisher_name=publisher_name,
        publisher_url=publisher_url,
    )


def export_claimreview_list(
    analysis_results: list[dict],
    publisher_name: str = "TruthTrace",
    publisher_url: str = "https://truthtrace.app",
) -> list[dict]:
    """批量导出多条 ClaimReview 记录"""
    records = []
    for result in analysis_results:
        record = export_from_analysis_result(result, publisher_name, publisher_url)
        records.append(record.to_dict())
    return records
