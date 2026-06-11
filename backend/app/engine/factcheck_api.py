"""
Google Fact Check Tools API 交叉验证引擎 — 第17号引擎

将文本中的主张与 Google Fact Check Tools 全球事实核查数据库交叉验证:
  1. 从文本中提取可核查的事实主张
  2. 调用 Google Fact Check Tools API 搜索相关核查
  3. 匹配主张与核查结果
  4. 返回核查裁决 (True/False/Misleading/Unverified)

行业参考:
  - Google Fact Check Tools API (factchecktools.googleapis.com)
  - ClaimReview Schema.org (聚合Snopes/PolitiFact/FactCheck.org等)
  - Sift Evidence Hunter Agent (Tavily + Google Fact Check)

核心原则:
  - API key 缺失时静默跳过,不阻塞管线
  - 所有核查结果附带来源URL和发布日期
  - "未找到匹配的核查"是正常结果,不表示信息为真或假
"""

from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote, urlencode

logger = logging.getLogger("truthtrace.factcheck")


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class FactCheckMatch:
    """单条事实核查匹配"""
    claim_text: str = ""                # 被核查的主张原文
    fact_check_url: str = ""            # 事实核查文章URL
    publisher_name: str = ""            # 核查发布者 (Snopes, PolitiFact, etc.)
    publisher_site: str = ""            # 核查发布者网站
    review_date: str = ""               # 核查日期
    textual_rating: str = ""            # 裁决文本 ("False", "Mostly True", etc.)
    rating_normalized: str = ""         # 标准化裁决: true/false/misleading/unverified
    match_confidence: float = 0.0       # 匹配置信度 0-1
    snippet: str = ""                   # 匹配片段

    def to_dict(self) -> dict:
        return {
            "claim_text": self.claim_text,
            "fact_check_url": self.fact_check_url,
            "publisher_name": self.publisher_name,
            "publisher_site": self.publisher_site,
            "review_date": self.review_date,
            "textual_rating": self.textual_rating,
            "rating_normalized": self.rating_normalized,
            "match_confidence": round(self.match_confidence, 2),
            "snippet": self.snippet,
        }


@dataclass
class FactCheckAnalysis:
    """事实核查分析完整结果"""
    matches: list[FactCheckMatch] = field(default_factory=list)
    total_claims_searched: int = 0
    matched_claims: int = 0
    fact_check_coverage: float = 0.0     # 0-1 覆盖比例
    truth_tally: dict = field(default_factory=dict)  # {true: N, false: N, ...}
    api_available: bool = False
    summary: str = ""
    searched_at: str = ""

    def to_dict(self) -> dict:
        return {
            "matches": [m.to_dict() for m in self.matches],
            "total_claims_searched": self.total_claims_searched,
            "matched_claims": self.matched_claims,
            "fact_check_coverage": round(self.fact_check_coverage, 2),
            "truth_tally": self.truth_tally,
            "api_available": self.api_available,
            "summary": self.summary,
            "searched_at": self.searched_at,
        }


# =============================================================================
# API 客户端
# =============================================================================

# 标准化裁决映射
RATING_NORMALIZATION = {
    # 真
    "true": "true", "mostly true": "true", "correct": "true",
    "accurate": "true", "confirmed": "true", "verified": "true",
    "事实": "true", "属实": "true", "真实": "true", "正确": "true",
    # 假
    "false": "false", "mostly false": "false", "incorrect": "false",
    "fake": "false", "false.": "false", "pants on fire": "false",
    "虚假": "false", "不实": "false", "谣言": "false", "假": "false",
    # 误导
    "misleading": "misleading", "partially false": "misleading",
    "half true": "misleading", "mixture": "misleading",
    "missing context": "misleading", "needs context": "misleading",
    "误导": "misleading", "部分属实": "misleading", "片面": "misleading",
    # 不可验证
    "unproven": "unverified", "unverified": "unverified",
    "unsupported": "unverified", "no evidence": "unverified",
    "无法验证": "unverified",
}


class FactCheckAPI:
    """Google Fact Check Tools API 客户端"""

    BASE_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key.strip()
        self.available = bool(self.api_key)
        if not self.available:
            logger.info("Google Fact Check API key 未配置，引擎将跳过。"
                       "设置环境变量 GOOGLE_FACT_CHECK_API_KEY 以启用。")

    async def search_claims(
        self,
        query: str,
        language: str = "zh",
        limit: int = 5,
    ) -> list[FactCheckMatch]:
        """
        搜索事实核查数据库。

        Args:
            query: 搜索查询 (一条主张/关键词)
            language: 语言代码
            limit: 最大结果数
        """
        if not self.available:
            return []

        params = {
            "query": query[:500],       # API 限制
            "key": self.api_key,
            "pageSize": min(limit, 10),
        }
        if language:
            params["languageCode"] = language

        url = f"{self.BASE_URL}?{urlencode(params)}"

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.warning(f"Fact Check API 返回 {response.status_code}: {response.text[:200]}")
                    return []

                data = response.json()
                return self._parse_response(data, query)

        except ImportError:
            # httpx 不可用时的 fallback
            logger.warning("httpx 不可用，Fact Check API 无法调用")
            return []
        except Exception as e:
            logger.warning(f"Fact Check API 调用失败: {e}")
            return []

    def _parse_response(self, data: dict, query: str) -> list[FactCheckMatch]:
        """解析 API 响应"""
        matches: list[FactCheckMatch] = []
        claims = data.get("claims", [])

        for claim_data in claims:
            review = claim_data.get("claimReview", [{}])[0] if claim_data.get("claimReview") else {}

            textual_rating = review.get("textualRating", "")
            rating_lower = textual_rating.lower().strip()

            publisher = review.get("publisher", {})
            publisher_name = publisher.get("name", "")
            publisher_site = publisher.get("site", "")

            matches.append(FactCheckMatch(
                claim_text=claim_data.get("text", query)[:300],
                fact_check_url=review.get("url", ""),
                publisher_name=publisher_name,
                publisher_site=publisher_site,
                review_date=review.get("reviewDate", ""),
                textual_rating=textual_rating,
                rating_normalized=self._normalize_rating(rating_lower),
                match_confidence=self._compute_match_confidence(query, claim_data.get("text", "")),
                snippet=review.get("title", "")[:200],
            ))

        return matches

    # -------------------------------------------------------------------
    # 分析入口
    # -------------------------------------------------------------------

    async def analyze(
        self,
        text: str,
        title: str = "",
        language: str = "zh",
        max_queries: int = 5,
    ) -> FactCheckAnalysis:
        """
        对文本执行事实核查交叉验证。

        Args:
            text: 待分析文本
            title: 标题
            language: 语言 ("zh" / "en")
            max_queries: 最多发送多少条搜索查询
        """
        result = FactCheckAnalysis(
            searched_at=datetime.now(timezone.utc).isoformat(),
            api_available=self.available,
        )

        if not self.available:
            result.summary = "Google Fact Check API 未配置 (缺少 API key)。"
            return result

        # 1. 提取可搜索的主张
        claims = self._extract_searchable_claims(text, title)
        queries = claims[:max_queries]
        result.total_claims_searched = len(queries)

        if not queries:
            result.summary = "文本中未提取到可用于搜索的明确事实主张。"
            return result

        # 2. 并发搜索所有主张
        tasks = [self.search_claims(q, language=language, limit=3) for q in queries]
        all_results = await asyncio.gather(*tasks)

        # 3. 聚合结果
        seen_urls: set[str] = set()
        truth_tally: dict[str, int] = {"true": 0, "false": 0, "misleading": 0, "unverified": 0}

        for query_matches in all_results:
            for match in query_matches:
                if match.fact_check_url and match.fact_check_url not in seen_urls:
                    seen_urls.add(match.fact_check_url)
                    result.matches.append(match)
                    truth_tally[match.rating_normalized] = truth_tally.get(match.rating_normalized, 0) + 1

        result.matched_claims = len(result.matches)
        result.fact_check_coverage = len(result.matches) / max(len(queries), 1)
        result.truth_tally = truth_tally

        # 4. 生成摘要
        result.summary = self._build_summary(result, len(queries))

        return result

    # -------------------------------------------------------------------
    # 主张提取
    # -------------------------------------------------------------------

    @staticmethod
    def _extract_searchable_claims(text: str, title: str = "") -> list[str]:
        """从文本中提取可搜索的事实主张 (关键词/短语)"""
        claims: list[str] = []
        full_text = f"{title}。{text}" if title else text

        # 策略1: 提取包含数字的句子 (统计/数据主张)
        for match in re.finditer(r'[^。！？\n]{10,80}(?:\d+\.?\d*[万亿千百%倍]?)[^。！？\n]{5,40}', full_text):
            claim = match.group().strip()
            if len(claim) >= 15:
                claims.append(claim[:200])

        # 策略2: 提取包含"据"/"称"/"表示"的引用句
        for match in re.finditer(r'[^。！？\n]{0,30}(?:据|根据|按照)[^。！？\n]{10,60}', full_text):
            claim = match.group().strip()
            if len(claim) >= 15 and claim not in claims:
                claims.append(claim[:200])

        # 策略3: 提取"XX是YY"类断言句
        for match in re.finditer(r'[^。！？\n]{10,60}(?:是|不是|为|属于|等于)[^。！？\n]{5,40}', full_text):
            claim = match.group().strip()
            if len(claim) >= 15 and claim not in claims:
                claims.append(claim[:200])

        # 策略4: 用标题本身
        if title and len(title) >= 10 and title not in claims:
            claims.append(title[:200])

        # 去重，取前10条最长的
        seen = set()
        unique = []
        for c in sorted(claims, key=len, reverse=True):
            h = hashlib.md5(c.encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                unique.append(c)
                if len(unique) >= 10:
                    break

        return unique

    # -------------------------------------------------------------------
    # 辅助方法
    # -------------------------------------------------------------------

    @staticmethod
    def _normalize_rating(rating: str) -> str:
        """标准化裁决文本"""
        rating_lower = rating.lower().strip().rstrip(".")
        return RATING_NORMALIZATION.get(rating_lower, "unverified")

    @staticmethod
    def _compute_match_confidence(query: str, claim_text: str) -> float:
        """计算查询与核查主张的匹配置信度"""
        if not claim_text or not query:
            return 0.0

        query_words = set(query.lower().split())
        claim_words = set(claim_text.lower().split())

        if not query_words:
            return 0.0

        overlap = len(query_words & claim_words)
        jaccard = overlap / len(query_words | claim_words) if query_words | claim_words else 0.0

        # 加权: Jaccard × 长度惩罚
        length_penalty = min(len(query) / max(len(claim_text), 1), 1.0)
        return round(jaccard * 0.7 + length_penalty * 0.3, 2)

    @staticmethod
    def _build_summary(result: FactCheckAnalysis, total_searched: int) -> str:
        """生成人类可读的摘要"""
        if not result.api_available:
            return "Google Fact Check API 未配置。设置 GOOGLE_FACT_CHECK_API_KEY 环境变量以启用第三方事实核查交叉验证。"

        if result.matched_claims == 0:
            return f"已搜索{total_searched}条主张，未在第三方事实核查数据库中找到匹配结果。这不表示信息为真或假——仅表示尚未被 Snopes/PolitiFact/FactCheck.org 等机构核查。"

        parts = [f"搜索{total_searched}条主张，匹配{result.matched_claims}条第三方核查结果"]

        tally = result.truth_tally
        if tally.get("false", 0) > 0:
            parts.append(f"{tally['false']}条被判定为虚假")
        if tally.get("misleading", 0) > 0:
            parts.append(f"{tally['misleading']}条被判定为误导")
        if tally.get("true", 0) > 0:
            parts.append(f"{tally['true']}条被判定为真实")

        return " | ".join(parts)


# =============================================================================
# 便捷函数 — 直接用于管线
# =============================================================================

async def run_factcheck_analysis(
    text: str,
    title: str = "",
    language: str = "zh",
    api_key: str = "",
) -> FactCheckAnalysis:
    """运行事实核查交叉验证 — 管线便捷入口"""
    from app.config import get_settings

    key = api_key or get_settings().google_fact_check_api_key
    api = FactCheckAPI(api_key=key)
    return await api.analyze(text=text, title=title, language=language)
