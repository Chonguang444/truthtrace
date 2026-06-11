"""
IFCN (International Fact-Checking Network) 标准兼容

确保 TruthTrace 的事实核查输出符合 IFCN 规范要求：
https://ifcncodeofprinciples.poynter.org/

IFCN 要求的 ClaimReview 扩展字段：
- itemReviewed.creator: 谣言主张的原始作者/发布者
- itemReviewed.appearance: 主张出现的 URL/媒体列表
- author: 核查方信息 (非匿名)
- reviewRating: 标准化评级 (True/False/Misleading等)
- image: 核查结果的可分享图片

兼容 Google Fact Check, Schema.org ClaimReview, IFCN 三方标准。
"""

from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field


# =============================================================================
# IFCN 要求的标准评级映射
# =============================================================================

IFCN_RATING_VALUES = {
    # 标准 IFCN/ClaimReview 评级
    "True": {
        "label": "真实",
        "label_en": "True",
        "numerical": 5,
        "ifcn_category": "accurate",
        "description": "经核查，该主张与事实一致。",
    },
    "Mostly True": {
        "label": "大部分真实",
        "label_en": "Mostly True",
        "numerical": 4,
        "ifcn_category": "mostly_accurate",
        "description": "经核查，该主张基本属实，但存在一定程度的简化或缺少重要限定条件。",
    },
    "Mixture": {
        "label": "部分真实部分虚假",
        "label_en": "Mixture",
        "numerical": 3,
        "ifcn_category": "mixed",
        "description": "经核查，该主张包含真实和虚假的混合信息。",
    },
    "Misleading": {
        "label": "误导性",
        "label_en": "Misleading",
        "numerical": 2,
        "ifcn_category": "misleading",
        "description": "经核查，该主张虽然可能包含部分事实，但整体呈现方式具有误导性。",
    },
    "Missing Context": {
        "label": "缺少关键背景",
        "label_en": "Missing Context",
        "numerical": 1,
        "ifcn_category": "missing_context",
        "description": "经核查，该主张缺少关键的背景信息，单独呈现会误导受众。",
    },
    "Mostly False": {
        "label": "大部分虚假",
        "label_en": "Mostly False",
        "numerical": 0,
        "ifcn_category": "mostly_inaccurate",
        "description": "经核查，该主张的大部分内容不属实。",
    },
    "False": {
        "label": "虚假",
        "label_en": "False",
        "numerical": -1,
        "ifcn_category": "inaccurate",
        "description": "经核查，该主张与事实不符。",
    },
    "Unverifiable": {
        "label": "无法验证",
        "label_en": "Unverifiable",
        "numerical": -2,
        "ifcn_category": "unverifiable",
        "description": "经核查，该主张目前无法通过公开信息验证，不代表其为真或假。",
    },
    "Satire": {
        "label": "讽刺/恶搞",
        "label_en": "Satire",
        "numerical": -3,
        "ifcn_category": "satire",
        "description": "该内容为讽刺或恶搞，并非真实的事实主张。",
    },
    "Outdated": {
        "label": "过时信息",
        "label_en": "Outdated",
        "numerical": 1,
        "ifcn_category": "outdated",
        "description": "该主张基于过时的信息，当前事实已发生变化。",
    },
}


# =============================================================================
# IFCN ClaimReview 生成
# =============================================================================

@dataclass
class IFCNClaimReview:
    """符合 IFCN 标准的完整 ClaimReview"""

    # Required fields (Schema.org + IFCN)
    claim_text: str = ""                # 被核查的主张原文
    claim_date: str = ""                # 主张发布日期 (ISO 8601)
    claim_author: str = ""              # 主张原文作者/发布者
    claim_url: str = ""                 # 主张出现的 URL
    claim_language: str = "zh-CN"

    # Review fields (required)
    review_rating: str = "Unverifiable" # 核查评级 (见 IFCN_RATING_VALUES)
    review_summary: str = ""            # 核查说明 (建议 100-500 字)
    review_url: str = ""                # 核查报告 URL
    review_date: str = ""               # 核查日期 (ISO 8601)

    # Reviewer info (IFCN 要求非匿名)
    reviewer_name: str = "TruthTrace"
    reviewer_url: str = "https://truthtrace.app"
    reviewer_type: str = "Organization"  # Organization or Person
    reviewer_email: str = ""
    reviewer_country: str = "CN"

    # Evidence (IFCN 推荐)
    evidence_sources: list[dict] = field(default_factory=list)
    # [{"url": "...", "title": "...", "type": "government|academic|media|archive"}]

    # Correction fields (IFCN 推荐)
    correction_text: str = ""           # 辟谣建议
    correction_urls: list[str] = field(default_factory=list)  # 辟谣参考链接

    # IFCN 操作字段
    ifcn_code_version: str = "2.0"
    review_methodology: str = "automated"  # automated / human / hybrid
    review_tags: list[str] = field(default_factory=list)  # ["covid-19", "election-2024", ...]
    review_image_url: str = ""           # 可分享的核查结果图片 URL

    def to_claimreview_jsonld(self) -> dict:
        """生成 IFCN 兼容的 Schema.org ClaimReview JSON-LD"""
        rating_def = IFCN_RATING_VALUES.get(
            self.review_rating,
            IFCN_RATING_VALUES["Unverifiable"],
        )

        # Author/reviewer
        reviewer = {
            "@type": self.reviewer_type,
            "name": self.reviewer_name,
            "url": self.reviewer_url,
        }
        if self.reviewer_country:
            reviewer["address"] = {"addressCountry": self.reviewer_country}

        # Evidence
        evidence = []
        for i, src in enumerate(self.evidence_sources[:10]):
            evidence.append({
                "@type": "CreativeWork",
                "name": src.get("title", f"Source {i+1}"),
                "url": src.get("url", ""),
                "genre": src.get("type", "other"),
            })

        result = {
            "@context": "https://schema.org",
            "@type": "ClaimReview",
            # Claim
            "claimReviewed": self.claim_text[:500],
            "itemReviewed": {
                "@type": "Claim",
                "author": {
                    "@type": "Person" if self.claim_author else "Organization",
                    "name": self.claim_author or "未知来源",
                },
                "datePublished": self.claim_date,
                "appearance": {
                    "@type": "CreativeWork",
                    "url": self.claim_url,
                } if self.claim_url else None,
                "inLanguage": self.claim_language,
            },
            # Review
            "reviewRating": {
                "@type": "Rating",
                "ratingValue": rating_def["numerical"],
                "alternateName": self.review_rating,
                "bestRating": 5,
                "worstRating": -3,
                "description": rating_def["description"],
            },
            "url": self.review_url,
            "author": reviewer,
            "datePublished": self.review_date,
            "reviewBody": self.review_summary[:2000],
            # IFCN extensions
            "publisher": reviewer,
            "sdPublisher": reviewer,
            "sdDatePublished": self.review_date,
            "dateModified": self.review_date,
            # Evidence
            "citation": evidence if evidence else None,
        }

        # Remove None values recursively
        def _clean_none(obj):
            if isinstance(obj, dict):
                return {k: _clean_none(v) for k, v in obj.items() if v is not None}
            if isinstance(obj, list):
                return [_clean_none(v) for v in obj if v is not None]
            return obj

        return _clean_none(result)

    def to_ifcn_feed_entry(self) -> dict:
        """生成 IFCN 兼容的事实核查 Feed 条目"""
        return {
            "id": f"truthtrace-{abs(hash(self.claim_text[:100] + (self.review_date or '')))}",
            "url": self.review_url,
            "datePublished": self.review_date,
            "claimReviewed": self.claim_text[:300],
            "claimDate": self.claim_date,
            "claimAuthor": self.claim_author,
            "reviewRating": self.review_rating,
            "reviewSummary": self.review_summary[:300],
            "reviewer": {
                "name": self.reviewer_name,
                "url": self.reviewer_url,
                "type": self.reviewer_type,
            },
            "methodology": self.review_methodology,
            "ifcnCodeVersion": self.ifcn_code_version,
            "language": self.claim_language,
        }


# =============================================================================
# 便捷转换函数
# =============================================================================

def verdict_to_ifcn_rating(truthtrace_verdict: str) -> str:
    """TruthTrace 内部判定 → IFCN 标准评级"""
    mapping = {
        "true": "True",
        "likely_true": "Mostly True",
        "misleading": "Misleading",
        "likely_false": "Mostly False",
        "false": "False",
        "unverifiable": "Unverifiable",
    }
    return mapping.get(truthtrace_verdict, "Unverifiable")


def create_ifcn_compliant_review(
    claim_text: str,
    truthtrace_verdict: str,
    credibility_score: float,
    review_summary: str,
    claim_url: str = "",
    claim_author: str = "",
    claim_date: str = "",
    review_url: str = "",
    reviewer_name: str = "TruthTrace",
    evidence_sources: list[dict] | None = None,
) -> dict:
    """
    一站式 IFCN 兼容核查报告生成。

    用法:
        report = create_ifcn_compliant_review(
            claim_text="喝柠檬水可以治疗癌症",
            truthtrace_verdict="false",
            credibility_score=12.0,
            review_summary="经WHO、FDA确认...",
            claim_url="https://example.com/rumor",
        )
        jsonld = report["claimreview_jsonld"]
        feed = report["ifcn_feed"]
    """
    ifcn_rating = verdict_to_ifcn_rating(truthtrace_verdict)

    now = datetime.now(timezone.utc).isoformat()

    review = IFCNClaimReview(
        claim_text=claim_text,
        claim_date=claim_date or now,
        claim_author=claim_author,
        claim_url=claim_url,
        review_rating=ifcn_rating,
        review_summary=review_summary or f"经TruthTrace {truthtrace_verdict}引擎分析，可信度{credibility_score:.0f}/100",
        review_url=review_url or f"https://truthtrace.app/claims/{abs(hash(claim_text[:100]))}",
        review_date=now,
        reviewer_name=reviewer_name,
        evidence_sources=evidence_sources or [],
        correction_text=review_summary,
        review_methodology="automated",
    )

    return {
        "ifcn_rating": ifcn_rating,
        "claimreview_jsonld": review.to_claimreview_jsonld(),
        "ifcn_feed": review.to_ifcn_feed_entry(),
        "generated_at": now,
    }


def export_ifcn_feed(entries: list[dict]) -> dict:
    """批量导出为 IFCN 兼容的事实核查 Feed"""
    feed = {
        "@context": "https://ifcncodeofprinciples.poynter.org/schema/2.0",
        "type": "FactCheckFeed",
        "publisher": {
            "name": "TruthTrace",
            "url": "https://truthtrace.app",
            "country": "CN",
        },
        "dateModified": datetime.now(timezone.utc).isoformat(),
        "totalItems": len(entries),
        "itemListElement": entries,
    }
    return feed
