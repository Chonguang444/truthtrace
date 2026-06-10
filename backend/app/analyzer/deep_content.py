"""
Deep Content Analyzer — 全文深度采集与交叉验证

解决"只采集标题/摘要，不深入全文"的核心问题。

三层深度采集:
  L1-页面全文: 爬取目标URL的完整正文、结构化数据、引用链接
  L2-引用追踪: 跟随页面中的引用链接，爬取每篇引用源的全部正文
  L3-交叉验证: 多源对比事实宣称，标注一致/矛盾/缺失

核心流程:
  提交URL → L1爬取全文 → 提取所有引用 → L2逐篇深入爬取
  → 多源交叉对比 → 一致性评分 → 送入10引擎分析
"""

from __future__ import annotations
import asyncio
import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("truthtrace.deep_content")

# =============================================================================
# 配置
# =============================================================================

DEEP_CONFIG = {
    "max_l1_content_chars": 100_000,   # L1 单页最大字符数
    "max_l2_pages": 8,                 # L2 最多爬取8篇引用源
    "max_l2_content_chars": 50_000,    # L2 单页最大字符数
    "request_timeout": 20,             # 单次请求超时(秒)
    "max_total_content": 300_000,      # 全文总上限
    "min_content_length": 200,         # 少于此不计入
    "similarity_threshold": 0.85,      # 内容去重阈值
    "max_text_per_page": 30_000,       # 单页提取正文上限
}


@dataclass
class PageContent:
    """单页完整采集结果"""
    url: str = ""
    final_url: str = ""
    title: str = ""
    full_text: str = ""                # 全部正文(已清洗)
    text_length: int = 0
    author: str = ""
    published_date: str = ""
    platform: str = ""
    content_hash: str = ""
    # 结构化提取
    claims: list[str] = field(default_factory=list)     # 文中所有事实宣称
    statistics: list[str] = field(default_factory=list) # 文中所有统计数据
    quotes: list[str] = field(default_factory=list)     # 文中所有引用
    references: list[str] = field(default_factory=list) # 引用外部链接
    entities: dict = field(default_factory=dict)        # 命名实体
    # 元数据
    meta: dict = field(default_factory=dict)
    fetch_duration_ms: float = 0.0
    fetch_error: str = ""


@dataclass
class DeepAnalysisResult:
    """深度采集分析完整结果"""
    seed_url: str = ""
    seed_page: PageContent | None = None
    referenced_pages: list[PageContent] = field(default_factory=list)
    total_content_chars: int = 0
    total_pages_analyzed: int = 0
    # 交叉验证
    cross_reference: dict = field(default_factory=dict)
    consistency_score: float = 50.0    # 多源一致性 0-100
    supporting_sources: int = 0
    contradicting_sources: int = 0
    # 元数据
    duration_ms: float = 0.0
    depth_reached: int = 1
    warnings: list[str] = field(default_factory=list)


# =============================================================================
# L1: 单页全文提取
# =============================================================================

class FullTextExtractor:
    """
    深度文本提取器 — 远比 GeneralCrawler 更彻底

    不仅提取正文，还提取:
    - 所有事实宣称句
    - 所有统计数据及其上下文
    - 所有直接/间接引用
    - 文章中引用的外部链接
    - 结构化数据 (Schema.org / JSON-LD)
    """

    @staticmethod
    def extract(html: str, base_url: str = "") -> PageContent:
        """从HTML中深度提取所有文本和结构化信息"""
        soup = BeautifulSoup(html, "lxml")

        # 基础清洗
        for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                          "noscript", "iframe", "object", "embed", "form"]):
            tag.decompose()

        # 标题
        title = FullTextExtractor._extract_title(soup)

        # 全文正文
        full_text = FullTextExtractor._extract_full_text(soup)

        # 提取事实宣称
        claims = FullTextExtractor._extract_claims(full_text)

        # 提取统计数据
        statistics = FullTextExtractor._extract_statistics(full_text)

        # 提取引用
        quotes = FullTextExtractor._extract_quotes(html)

        # 提取引用链接
        references = FullTextExtractor._extract_reference_links(soup, base_url)

        # 作者
        author = FullTextExtractor._extract_author(soup)

        # 发布日期
        published_date = FullTextExtractor._extract_date(soup)

        # 实体
        entities = FullTextExtractor._extract_entities(full_text)

        # 元数据
        meta = FullTextExtractor._extract_meta(soup)

        # 指纹
        content_hash = hashlib.sha256(full_text[:5000].encode()).hexdigest()[:24]

        return PageContent(
            title=title,
            full_text=full_text,
            text_length=len(full_text),
            author=author,
            published_date=published_date,
            content_hash=content_hash,
            claims=claims,
            statistics=statistics,
            quotes=quotes,
            references=references,
            entities=entities,
            meta=meta,
        )

    # ---- 标题提取 ----
    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> str:
        for sel in ["meta[property='og:title']", "meta[name='twitter:title']",
                     "title", "h1"]:
            el = soup.select_one(sel)
            if el:
                val = el.get("content") or el.get_text(strip=True)
                if val:
                    return val.strip()[:500]
        return ""

    # ---- 全文提取 ----
    @staticmethod
    def _extract_full_text(soup: BeautifulSoup) -> str:
        """多策略提取全部正文，按优先级合并"""
        texts = []
        seen = set()

        # 策略1: 语义标签
        for selector in ["article", '[role="main"]', "main",
                         "#content", "#article", ".post-content",
                         ".article-content", ".entry-content",
                         "#main-content", ".post-body", ".article-body"]:
            el = soup.select_one(selector)
            if el:
                for junk in el(["script", "style", "nav", "footer", "aside"]):
                    junk.decompose()
                txt = el.get_text(separator="\n", strip=True)
                if len(txt) > 200:
                    h = hashlib.md5(txt[:200].encode()).hexdigest()
                    if h not in seen:
                        seen.add(h)
                        texts.append(txt)
                        if sum(len(t) for t in texts) > 30000:
                            break

        # 策略2: 段落聚合
        if sum(len(t) for t in texts) < 500:
            paragraphs = []
            for p in soup.find_all(["p", "li", "td", "th", "blockquote"]):
                txt = p.get_text(strip=True)
                if len(txt) > 20:
                    paragraphs.append(txt)
            if paragraphs:
                texts.append("\n".join(paragraphs))

        # 策略3: body 回退
        if not texts or sum(len(t) for t in texts) < 100:
            body = soup.find("body")
            if body:
                for junk in body(["script", "style", "nav", "footer", "header"]):
                    junk.decompose()
                texts.append(body.get_text(separator="\n", strip=True))

        return "\n\n---\n\n".join(texts)[:DEEP_CONFIG["max_text_per_page"]]

    # ---- 事实宣称提取 ----
    @staticmethod
    def _extract_claims(text: str) -> list[str]:
        claims = []
        patterns = [
            # 数字宣称: "研究表明78%的人..."
            r'[^。！？\n]{3,}\d+(?:\.\d+)?%[^。！？\n]{3,}',
            # 因果宣称: "A导致B" "A引起B" "A造成B"
            r'[^。！？\n]{2,}(?:导致|引起|造成|引发|使得|使)[^。！？\n]{3,}',
            # 来源宣称: "根据X..." "据X报道..."
            r'(?:根据|据|按照|遵照)[^，。！？\n]{5,}',
            # 比较宣称: "比...更..." "A高于B"
            r'[^。！？\n]{3,}(?:比|高于|低于|相当于|等同于)[^。！？\n]{3,}',
        ]
        for pat in patterns:
            for m in re.finditer(pat, text):
                claim = m.group().strip()
                if 10 <= len(claim) <= 300:
                    claims.append(claim)

        # 去重
        seen = set()
        unique = []
        for c in claims:
            h = c[:50]
            if h not in seen:
                seen.add(h)
                unique.append(c)
        return unique[:30]

    # ---- 统计数据提取 ----
    @staticmethod
    def _extract_statistics(text: str) -> list[str]:
        stats = []
        # 百分比 + 数字 + 单位
        pat = r'[^。！？\n]{0,30}(?:\d+(?:\.\d+)?\s*(?:%|亿|万|千|百|倍|人|元|美元|吨|克|毫克|千米|公里|公顷|亩|度|个|次|项|篇|条|家|所|座))[^。！？\n]{0,50}'
        for m in re.finditer(pat, text):
            s = m.group().strip()
            if 10 <= len(s) <= 200:
                # 排除纯日期/时间
                if not re.match(r'^\d{4}[-/年]', s):
                    stats.append(s)
        return stats[:20]

    # ---- 引用提取 ----
    @staticmethod
    def _extract_quotes(html: str) -> list[str]:
        quotes = []
        # HTML引号
        for m in re.finditer(r'<q[^>]*>(.*?)</q>', html, re.DOTALL):
            quotes.append(re.sub(r'<[^>]+>', '', m.group(1)).strip())
        for m in re.finditer(r'<blockquote[^>]*>(.*?)</blockquote>', html, re.DOTALL):
            quotes.append(re.sub(r'<[^>]+>', '', m.group(1)).strip()[:500])
        # 文本引号
        for m in re.finditer(r'[""]([^""]{15,300})[""]', html):
            quotes.append(m.group(1).strip())
        return quotes[:20]

    # ---- 引用链接 ----
    @staticmethod
    def _extract_reference_links(soup: BeautifulSoup, base_url: str) -> list[str]:
        refs = set()
        base_domain = urlparse(base_url).netloc
        content_area = (
            soup.select_one("article")
            or soup.select_one("main")
            or soup.select_one('[role="main"]')
            or soup.find("body")
        )
        if content_area:
            for a in content_area.find_all("a", href=True):
                href = urljoin(base_url, a["href"])
                parsed = urlparse(href)
                if parsed.scheme in ("http", "https"):
                    # 外链优先
                    if parsed.netloc != base_domain:
                        refs.add(href)
                    elif re.search(r'/(?:article|post|news|story|p|blog|read|detail)/', parsed.path):
                        refs.add(href)
        return list(refs)[:30]

    # ---- 其他 ----
    @staticmethod
    def _extract_author(soup: BeautifulSoup) -> str:
        for sel in ["meta[name='author']", "meta[property='article:author']",
                     "meta[property='og:author']", "a[rel='author']",
                     "[class*='author']", "[class*='byline']"]:
            if sel.startswith("meta"):
                el = soup.select_one(sel)
                if el and el.get("content"):
                    return el["content"].strip()[:255]
            else:
                el = soup.select_one(sel)
                if el:
                    return el.get_text(strip=True)[:255]
        return ""

    @staticmethod
    def _extract_date(soup: BeautifulSoup) -> str:
        for sel in ["meta[property='article:published_time']",
                     "meta[name='pubdate']", "meta[name='publish_date']",
                     "time[datetime]"]:
            el = soup.select_one(sel)
            if el:
                val = el.get("content") or el.get("datetime")
                if val:
                    return val.strip()[:50]
        return ""

    @staticmethod
    def _extract_entities(text: str) -> dict:
        entities = {"PERSON": [], "ORG": [], "LOC": [], "EVENT": []}
        if len(text) < 100:
            return entities
        try:
            import jieba.posseg as pseg
            words = pseg.cut(text[:5000])
            for word, flag in words:
                if flag == "nr" and word not in entities["PERSON"]:
                    entities["PERSON"].append(word)
                elif flag == "ns" and word not in entities["LOC"]:
                    entities["LOC"].append(word)
                elif flag == "nt" and word not in entities["ORG"]:
                    entities["ORG"].append(word)
        except Exception:
            pass
        return entities

    @staticmethod
    def _extract_meta(soup: BeautifulSoup) -> dict:
        meta = {}
        for tag in soup.find_all("meta"):
            prop = tag.get("property") or tag.get("name", "")
            content = tag.get("content", "")
            if prop and content:
                meta[prop] = content
        # JSON-LD structured data
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict):
                    meta["jsonld"] = data
                    break
            except Exception:
                pass
        return meta


# =============================================================================
# L2: 多页深入爬取 + L3: 交叉验证
# =============================================================================

class DeepContentOrchestrator:
    """
    深度内容采集编排器

    用法:
        orch = DeepContentOrchestrator()
        result = await orch.analyze("https://example.com/article")
        # result.seed_page 有完整的全文/宣称/统计/引用
        # result.referenced_pages 有逐篇深入爬取的引用源全文
        # result.cross_reference 有多源交叉验证结果
    """

    def __init__(self, max_l2_pages: int | None = None):
        self.max_l2 = max_l2_pages or DEEP_CONFIG["max_l2_pages"]
        self.extractor = FullTextExtractor()
        self._client: httpx.AsyncClient | None = None
        self._content_hashes: set[str] = set()

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=DEEP_CONFIG["request_timeout"],
                follow_redirects=True,
                max_redirects=3,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,*/*",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    async def analyze(self, seed_url: str, title_hint: str = "",
                       deep: bool = True) -> DeepAnalysisResult:
        """执行深度分析"""
        start = time.monotonic()
        result = DeepAnalysisResult(seed_url=seed_url)

        # === L1: 爬取种子页面全文 ===
        logger.info(f"[Deep] L1 爬取种子页面: {seed_url[:60]}...")
        seed_page = await self._crawl_page(seed_url, title_hint)
        if not seed_page or not seed_page.full_text:
            result.warnings.append("种子页面无法获取全文内容，采集深度受限")
            if seed_page:
                result.seed_page = seed_page
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        result.seed_page = seed_page
        result.seed_page.url = seed_url
        result.total_content_chars = seed_page.text_length
        result.total_pages_analyzed = 1
        result.depth_reached = 1
        logger.info(f"[Deep] L1 完成: {seed_page.text_length} chars, {len(seed_page.references)} refs, {len(seed_page.claims)} claims")

        # === L2: 深入爬取引用链接 ===
        if deep and seed_page.references:
            logger.info(f"[Deep] L2 开始深入爬取 {min(len(seed_page.references), self.max_l2)} 个引用源...")
            result.depth_reached = 2
            ref_pages = await self._crawl_references(seed_page.references)

            # 去重
            for rp in ref_pages:
                if rp.content_hash not in self._content_hashes:
                    self._content_hashes.add(rp.content_hash)
                    result.referenced_pages.append(rp)
                    result.total_content_chars += rp.text_length
                    result.total_pages_analyzed += 1

            logger.info(f"[Deep] L2 完成: 深入爬取 {len(result.referenced_pages)} 篇引用源, 总内容 {result.total_content_chars} chars")

        # === L3: 交叉验证 ===
        if result.referenced_pages:
            logger.info("[Deep] L3 交叉验证开始...")
            result.depth_reached = 3
            cross_ref = self._cross_reference(seed_page, result.referenced_pages)
            result.cross_reference = cross_ref
            result.consistency_score = cross_ref.get("consistency_score", 50.0)
            result.supporting_sources = cross_ref.get("supporting", 0)
            result.contradicting_sources = cross_ref.get("contradicting", 0)

        result.duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            f"[Deep] 分析完成: {result.total_pages_analyzed} pages, "
            f"{result.total_content_chars} chars, {result.consistency_score:.0f}% consistency, "
            f"{result.duration_ms:.0f}ms"
        )
        return result

    # ------------------------------------------------------------------
    # L1: 单页爬取
    # ------------------------------------------------------------------

    async def _crawl_page(self, url: str, title_hint: str = "") -> PageContent | None:
        """爬取单个页面的完整内容"""
        try:
            client = await self._get_client()
            resp = await client.get(url)
            if resp.status_code >= 400:
                return PageContent(url=url, fetch_error=f"HTTP {resp.status_code}")

            html = resp.text[:DEEP_CONFIG["max_l1_content_chars"]]
            page = self.extractor.extract(html, base_url=url)
            page.url = url
            page.final_url = str(resp.url)
            page.platform = self._detect_platform(url)
            if title_hint and not page.title:
                page.title = title_hint
            return page

        except httpx.TimeoutException:
            return PageContent(url=url, fetch_error="请求超时")
        except Exception as e:
            return PageContent(url=url, fetch_error=str(e)[:200])

    # ------------------------------------------------------------------
    # L2: 多页深入
    # ------------------------------------------------------------------

    async def _crawl_references(self, ref_urls: list[str]) -> list[PageContent]:
        """并行爬取多个引用源"""
        urls = ref_urls[:self.max_l2]
        tasks = [self._crawl_page(u) for u in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        pages = []
        for r in results:
            if isinstance(r, PageContent) and r.full_text:
                if len(r.full_text) >= DEEP_CONFIG["min_content_length"]:
                    pages.append(r)

        return pages

    # ------------------------------------------------------------------
    # L3: 交叉验证
    # ------------------------------------------------------------------

    def _cross_reference(self, seed: PageContent,
                          refs: list[PageContent]) -> dict:
        """
        多源交叉验证——对比种子页面和各引用源的事实宣称一致性。

        检测:
        - 种子中的宣称被多少来源支持/反驳/未提及
        - 各来源之间的一致性评分
        - 矛盾点标注
        """
        seed_claims = seed.claims
        if not seed_claims:
            return {"consistency_score": 50.0, "claim_count": 0,
                    "supporting": 0, "contradicting": 0,
                    "details": [], "summary": "种子页面未提取到足够的事实宣称"}

        all_ref_text = " ".join(r.full_text[:5000] for r in refs)
        all_ref_claims = [c for r in refs for c in r.claims]

        supporting = 0
        contradicting = 0
        unmentioned = 0
        details = []

        for claim in seed_claims[:15]:
            # 简化匹配: 关键词重叠
            claim_keywords = set(re.findall(r'[\w一-鿿]{2,}', claim.lower()))
            if len(claim_keywords) < 3:
                continue

            best_overlap = 0
            best_match = ""
            for ref_claim in all_ref_claims:
                ref_keywords = set(re.findall(r'[\w一-鿿]{2,}', ref_claim.lower()))
                overlap = len(claim_keywords & ref_keywords)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_match = ref_claim

            # 判断支持/矛盾
            match_ratio = best_overlap / max(1, len(claim_keywords))
            if best_overlap >= 4 and match_ratio > 0.4:
                supporting += 1
                details.append({"claim": claim[:80], "verdict": "supported",
                                "matched_in": best_match[:80]})
            elif best_overlap >= 2:
                # 检查是否含有否定词
                neg_words = ["不", "没有", "并非", "假", "伪", "错误", "谣言",
                             "not", "false", "fake", "wrong", "incorrect"]
                if any(w in best_match.lower() for w in neg_words):
                    contradicting += 1
                    details.append({"claim": claim[:80], "verdict": "contradicted",
                                    "counter": best_match[:80]})
                else:
                    unmentioned += 1
            else:
                unmentioned += 1

        # 一致性评分
        total = supporting + contradicting + unmentioned
        if total == 0:
            consistency = 50.0
        else:
            consistency = (supporting / total) * 100

        return {
            "claim_count": len(seed_claims),
            "supporting": supporting,
            "contradicting": contradicting,
            "unmentioned": unmentioned,
            "consistency_score": round(consistency, 1),
            "details": details[:20],
            "summary": self._summarize(supporting, contradicting, unmentioned),
        }

    @staticmethod
    def _summarize(supporting: int, contradicting: int, unmentioned: int) -> str:
        parts = []
        if supporting > 0:
            parts.append(f"{supporting} 条宣称在多源中得到支持")
        if contradicting > 0:
            parts.append(f"{contradicting} 条宣称存在矛盾信息")
        if unmentioned > 0:
            parts.append(f"{unmentioned} 条宣称未被其他来源提及（可能为独家/原创信息）")
        return "；".join(parts) if parts else "无法进行有效的多源对比"

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_platform(url: str) -> str:
        patterns = {
            "weibo": [r"weibo\.com", r"t\.cn"],
            "zhihu": [r"zhihu\.com"],
            "wechat": [r"mp\.weixin\.qq\.com"],
            "bilibili": [r"bilibili\.com", r"b23\.tv"],
            "douyin": [r"douyin\.com", r"iesdouyin\.com"],
            "kuaishou": [r"kuaishou\.com"],
            "twitter": [r"twitter\.com", r"x\.com"],
            "reddit": [r"reddit\.com"],
            "youtube": [r"youtube\.com", r"youtu\.be"],
        }
        for platform, ps in patterns.items():
            for p in ps:
                if re.search(p, url, re.IGNORECASE):
                    return platform
        return "general"


# =============================================================================
# 全局单例
# =============================================================================

_deep_orchestrator: DeepContentOrchestrator | None = None


def get_deep_orchestrator() -> DeepContentOrchestrator:
    global _deep_orchestrator
    if _deep_orchestrator is None:
        _deep_orchestrator = DeepContentOrchestrator()
    return _deep_orchestrator
