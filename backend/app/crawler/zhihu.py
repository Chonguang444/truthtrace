"""
知乎爬虫 — 爬取知乎问题、回答、文章
"""

import re
import json
from datetime import datetime

from bs4 import BeautifulSoup
from loguru import logger

from app.crawler.base import BaseCrawler, CrawlResult


class ZhihuCrawler(BaseCrawler):
    """知乎爬虫"""

    BASE_URL = "https://www.zhihu.com"
    SEARCH_URL = "https://www.zhihu.com/search"

    async def fetch(self, url: str) -> CrawlResult | None:
        """
        爬取知乎页面（问题/回答/文章）

        支持:
        - 问题页面: zhihu.com/question/{id}
        - 回答页面: zhihu.com/question/{qid}/answer/{aid}
        - 文章页面: zhuanlan.zhihu.com/p/{id}
        """
        try:
            response = await self.client.get(url)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"知乎爬取失败 {url}: {e}")
            return None

        html = response.text
        soup = BeautifulSoup(html, "lxml")

        content = ""
        author = ""
        published_at = ""
        title = ""
        engagement = {"upvotes": 0, "comments": 0}
        references = []

        # 尝试从初始状态 JSON 提取数据（知乎 SSR 渲染）
        data = self._extract_initial_data(html)
        if data:
            try:
                # 问题数据
                question = self._find_in_data(data, "question")
                if question:
                    title = question.get("title", "")
                    content = question.get("detail", "")

                # 回答数据
                answers = self._find_in_data(data, "answers")
                if answers:
                    for answer in answers[:5]:
                        answer_content = answer.get("content", "")
                        content += "\n\n" + self._clean_html(answer_content)
                        if not author:
                            author_info = answer.get("author", {})
                            author = author_info.get("name", "")

            except Exception as e:
                logger.warning(f"解析知乎初始数据失败: {e}")

        # 从 HTML 兜底提取
        if not content:
            content_elem = (
                soup.select_one(".RichContent-inner")
                or soup.select_one(".Post-RichText")
                or soup.select_one(".QuestionRichText")
            )
            if content_elem:
                content = content_elem.get_text(separator="\n", strip=True)

        if not title:
            title_elem = (
                soup.select_one("h1.QuestionHeader-title")
                or soup.select_one(".Post-Title")
                or soup.find("title")
            )
            if title_elem:
                title = title_elem.get_text(strip=True)

        if not author:
            author_elem = soup.select_one(".AuthorInfo-name")
            if author_elem:
                author = author_elem.get_text(strip=True)

        # 提取引用链接
        content_soup = BeautifulSoup(content, "html.parser") if "<" in content else None
        if content_soup:
            for a in content_soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("http"):
                    references.append(href)

        return CrawlResult(
            url=url,
            final_url=str(response.url),
            title=title,
            content=content[:10000],
            author=author,
            platform="zhihu",
            published_at=published_at,
            content_hash=self._compute_hash(content),
            references=references,
            engagement=engagement,
            raw_html=html,
        )

    async def search(self, keyword: str, limit: int = 20) -> list[CrawlResult]:
        """
        搜索知乎

        使用知乎搜索 API 或 HTML 搜索页面
        """
        results = []
        try:
            search_url = f"{self.SEARCH_URL}?type=content&q={keyword}"
            response = await self.client.get(search_url)
            soup = BeautifulSoup(response.text, "lxml")

            for item in soup.select(".List-item")[:limit]:
                link = item.select_one("a[href]")
                if link:
                    href = link.get("href", "")
                    if not href.startswith("http"):
                        href = self.BASE_URL + href

                    result = await self.fetch(href)
                    if result and result.content:
                        results.append(result)

        except Exception as e:
            logger.error(f"知乎搜索失败 '{keyword}': {e}")

        return results

    def _extract_initial_data(self, html: str) -> dict | None:
        """从 SSR 页面提取初始数据 JSON"""
        match = re.search(
            r'<script id="js-initialData"[^>]*>(.*?)</script>',
            html, re.DOTALL
        )
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return None

    def _find_in_data(self, data: dict, key: str) -> any:
        """递归查找数据结构中的键"""
        if isinstance(data, dict):
            if key in data:
                return data[key]
            for v in data.values():
                result = self._find_in_data(v, key)
                if result is not None:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = self._find_in_data(item, key)
                if result is not None:
                    return result
        return None

    def _clean_html(self, text: str) -> str:
        """清理 HTML 标签"""
        if not text:
            return ""
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
