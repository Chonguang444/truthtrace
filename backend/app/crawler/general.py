"""
通用网页爬虫 — 适用于任意网页的爬取和分析
"""

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from loguru import logger

from app.crawler.base import BaseCrawler, CrawlResult


class GeneralCrawler(BaseCrawler):
    """通用网页爬虫，支持静态和动态页面"""

    async def fetch(self, url: str) -> CrawlResult | None:
        """
        爬取指定 URL 的网页内容

        使用 BeautifulSoup 提取：
        - 标题 (og:title, <title>, <h1>)
        - 正文 (article, main, #content 等语义标签)
        - 作者 (meta author, og:author, schema.org)
        - 发布时间 (meta published, og:published_time, schema.org)
        - 引用的外链
        - Open Graph 图片
        """
        try:
            response = await self.client.get(url)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"爬取失败 {url}: {e}")
            return None

        html = response.text
        soup = BeautifulSoup(html, "lxml")

        # 提取标题
        title = self._extract_title(soup)

        # 提取正文
        content = self._extract_content(soup)

        # 提取作者
        author = self._extract_author(soup)

        # 提取发布时间
        published_at = self._extract_published_time(soup)

        # 提取图片
        images = self._extract_images(soup, url)

        # 提取引用链接
        references = self._extract_references(soup, url)

        # 提取 Open Graph / meta 数据
        meta = self._extract_meta(soup)

        return CrawlResult(
            url=url,
            final_url=str(response.url),
            title=title,
            content=content,
            author=author,
            platform="general",
            published_at=published_at,
            content_hash=self._compute_hash(content),
            images=images,
            references=references,
            raw_html=html,
            meta=meta,
        )

    async def search(self, keyword: str, limit: int = 20) -> list[CrawlResult]:
        """
        通过搜索引擎搜索关键词

        使用 DuckDuckGo 或 Bing 作为后端。
        """
        results = []
        try:
            # 使用 DuckDuckGo HTML 搜索（无需 API key）
            search_url = f"https://html.duckduckgo.com/html/?q={keyword}"
            response = await self.client.get(search_url)
            soup = BeautifulSoup(response.text, "lxml")

            for link in soup.select(".result__a")[:limit]:
                href = link.get("href", "")
                if href and href.startswith("http"):
                    # 爬取每个搜索结果
                    result = await self.fetch(href)
                    if result:
                        results.append(result)

            return results
        except Exception as e:
            logger.error(f"搜索失败 '{keyword}': {e}")
            return results

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """多策略提取标题"""
        strategies = [
            lambda: soup.find("meta", property="og:title"),
            lambda: soup.find("meta", attrs={"name": "twitter:title"}),
            lambda: soup.find("title"),
            lambda: soup.find("h1"),
        ]
        for strategy in strategies:
            elem = strategy()
            if elem:
                content = elem.get("content") or elem.get_text()
                if content:
                    return content.strip()[:500]
        return ""

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """多策略提取正文"""
        # 按优先级尝试语义标签
        content_selectors = [
            "article",
            '[role="main"]',
            "main",
            "#content",
            "#article",
            ".post-content",
            ".article-content",
            ".entry-content",
            "#main-content",
        ]

        for selector in content_selectors:
            elem = soup.select_one(selector)
            if elem and len(elem.get_text(strip=True)) > 50:
                # 清除脚本和样式
                for tag in elem(["script", "style", "nav", "footer", "aside"]):
                    tag.decompose()
                return elem.get_text(separator="\n", strip=True)

        # 回退：取 body 文本
        body = soup.find("body")
        if body:
            for tag in body(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            return body.get_text(separator="\n", strip=True)[:10000]

        return ""

    def _extract_author(self, soup: BeautifulSoup) -> str:
        """多策略提取作者"""
        strategies = [
            lambda: soup.find("meta", attrs={"name": "author"}),
            lambda: soup.find("meta", property="article:author"),
            lambda: soup.find("meta", property="og:author"),
            lambda: soup.find("a", rel="author"),
            lambda: soup.find(attrs={"class": re.compile(r"author|byline", re.I)}),
        ]
        for strategy in strategies:
            elem = strategy()
            if elem:
                content = elem.get("content") or elem.get_text()
                if content:
                    return content.strip()[:255]
        return ""

    def _extract_published_time(self, soup: BeautifulSoup) -> str:
        """多策略提取发布时间"""
        time_selectors = [
            ('meta', {'property': 'article:published_time'}),
            ('meta', {'property': 'og:published_time'}),
            ('meta', {'name': 'pubdate'}),
            ('meta', {'name': 'publish_date'}),
            ('time', {'datetime': True}),
            ('time', {'pubdate': True}),
        ]

        for tag, attrs in time_selectors:
            elem = soup.find(tag, attrs)
            if elem:
                dt_str = elem.get("content") or elem.get("datetime")
                if dt_str:
                    try:
                        # 尝试解析 ISO 8601
                        return datetime.fromisoformat(
                            dt_str.replace("Z", "+00:00")
                        ).isoformat()
                    except (ValueError, TypeError):
                        return dt_str
        return ""

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """提取页面中的图片 URL"""
        images = []

        # Open Graph 图片
        og_img = soup.find("meta", property="og:image")
        if og_img:
            img_url = og_img.get("content", "")
            if img_url:
                images.append(urljoin(base_url, img_url))

        # 文章中的大图
        for img in soup.select("article img, .content img, .post img")[:10]:
            src = img.get("src") or img.get("data-src")
            if src:
                full_url = urljoin(base_url, src)
                if full_url not in images:
                    images.append(full_url)

        return images[:20]

    def _extract_references(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """提取内容中的引用链接"""
        refs = set()
        base_domain = urlparse(base_url).netloc

        # 查找正文区的外链
        content_area = (
            soup.select_one("article")
            or soup.select_one("main")
            or soup.select_one(".content")
        )

        if content_area:
            for a in content_area.find_all("a", href=True):
                href = urljoin(base_url, a["href"])
                parsed = urlparse(href)
                # 只保留不同域名或相同域名的文章链接
                if parsed.scheme in ("http", "https") and parsed.netloc != base_domain:
                    refs.add(href)

        return list(refs)[:50]

    def _extract_meta(self, soup: BeautifulSoup) -> dict:
        """提取 Open Graph 和 Twitter Card 元数据"""
        meta = {}

        for tag in soup.find_all("meta"):
            prop = tag.get("property") or tag.get("name", "")
            content = tag.get("content", "")
            if prop and content:
                meta[prop] = content

        return meta
