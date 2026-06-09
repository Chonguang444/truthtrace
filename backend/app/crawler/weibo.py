"""
微博爬虫 — 爬取微博搜索、时间线、单条微博
"""

import re
import json
from datetime import datetime
from urllib.parse import quote

from bs4 import BeautifulSoup
from loguru import logger

from app.crawler.base import BaseCrawler, CrawlResult


class WeiboCrawler(BaseCrawler):
    """新浪微博爬虫"""

    BASE_URL = "https://weibo.com"
    SEARCH_URL = "https://s.weibo.com/weibo"
    API_URL = "https://m.weibo.cn/api/container/getIndex"

    async def fetch(self, url: str) -> CrawlResult | None:
        """
        爬取单条微博
        支持 weibo.com 和 m.weibo.cn 链接
        """
        try:
            response = await self.client.get(url)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"微博爬取失败 {url}: {e}")
            return None

        html = response.text
        soup = BeautifulSoup(html, "lxml")

        # 尝试从页面 script 标签提取 JSON 数据
        content = ""
        author = ""
        published_at = ""
        engagement = {"reposts": 0, "comments": 0, "likes": 0}
        references = []

        # 从 m.weibo.cn 页面提取
        if "m.weibo.cn" in url:
            try:
                script_text = None
                for script in soup.find_all("script"):
                    if script.string and "var $render_data" in script.string:
                        script_text = script.string
                        break

                if script_text:
                    json_match = re.search(
                        r"var \$render_data\s*=\s*\[(.*?)\]\[0\]",
                        script_text, re.DOTALL
                    )
                    if json_match:
                        data = json.loads(json_match.group(1))
                        status = data.get("status", {})
                        content = self._clean_html(
                            status.get("text", "")
                        )
                        user = status.get("user", {})
                        author = user.get("screen_name", "")
                        published_at = status.get("created_at", "")

                        # 互动数据
                        engagement = {
                            "reposts": status.get("reposts_count", 0),
                            "comments": status.get("comments_count", 0),
                            "likes": status.get("attitudes_count", 0),
                        }

                        # 引用链接
                        for ref in re.findall(r'href="(https?://[^"]+)"', content):
                            references.append(ref)

                        # 转发链
                        retweeted = status.get("retweeted_status")
                        if retweeted:
                            ref_url = f"https://m.weibo.cn/detail/{retweeted.get('id')}"
                            references.append(ref_url)
            except Exception as e:
                logger.warning(f"解析 m.weibo.cn JSON 失败: {e}")

        # 从 PC 页面提取（兜底）
        if not content:
            content_elem = soup.select_one(".WB_text, .detail_wbtext_4CRf9")
            if content_elem:
                content = content_elem.get_text(strip=True)

            author_elem = soup.select_one(".W_fb, .head_name_24eEB")
            if author_elem:
                author = author_elem.get_text(strip=True)

        return CrawlResult(
            url=url,
            final_url=str(response.url),
            title=content[:100] if content else "",
            content=content,
            author=author,
            platform="weibo",
            published_at=published_at,
            content_hash=self._compute_hash(content),
            references=references,
            engagement=engagement,
            raw_html=html,
        )

    async def search(self, keyword: str, limit: int = 20) -> list[CrawlResult]:
        """
        搜索微博关键词

        使用 m.weibo.cn 搜索 API
        """
        results = []
        try:
            encoded_keyword = quote(keyword)
            search_url = f"{self.SEARCH_URL}?q={encoded_keyword}&typeall=1&suball=1&timescope=custom:{(datetime.now().year-1)}-01-01:{datetime.now().strftime('%Y-%m-%d')}&Refer=g"

            response = await self.client.get(search_url)
            soup = BeautifulSoup(response.text, "lxml")

            # 搜索结果卡片
            for card in soup.select(".card-wrap")[:limit]:
                link = card.select_one("a[href*='weibo.com']")
                if link:
                    href = link.get("href", "")
                    if href:
                        full_url = f"https:{href}" if href.startswith("//") else href
                        result = await self.fetch(full_url)
                        if result and result.content:
                            results.append(result)
        except Exception as e:
            logger.error(f"微博搜索失败 '{keyword}': {e}")

        return results

    def _clean_html(self, text: str) -> str:
        """清理 HTML 标签"""
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
