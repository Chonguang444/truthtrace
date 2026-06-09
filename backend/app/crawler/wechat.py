"""
微信公众平台爬虫 — 爬取微信公众号文章

微信公众号是中文互联网核心信息传播渠道，
缺少此爬虫意味着溯源链路可能遗漏关键节点。
"""

import re
import json
from datetime import datetime
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup
from loguru import logger

from app.crawler.base import BaseCrawler, CrawlResult


class WechatCrawler(BaseCrawler):
    """
    微信公众平台爬虫

    支持：
    - mp.weixin.qq.com 文章链接
    - 微信搜索 (搜狗微信搜索)
    - 元数据提取 (发布时间、公众号名称、阅读数等)
    """

    BASE_URL = "https://mp.weixin.qq.com"
    SOGOU_SEARCH = "https://weixin.sogou.com/weixin"

    # 微信文章 URL 模式
    ARTICLE_PATTERNS = [
        r'mp\.weixin\.qq\.com/s\?',
        r'mp\.weixin\.qq\.com/s/',
        r'mp\.weixin\.qq\.com/mp/',
    ]

    async def fetch(self, url: str) -> CrawlResult | None:
        """
        爬取微信公众号文章

        提取：标题、正文、公众号名称、发布时间、封面图、引用链接
        """
        try:
            response = await self.client.get(url)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"微信爬取失败 {url}: {e}")
            return None

        html = response.text
        soup = BeautifulSoup(html, "lxml")

        # 提取标题
        title = self._extract_title(soup)

        # 提取公众号名称
        author = self._extract_author(soup)
        author_id = self._extract_author_id(soup, url)

        # 提取正文
        content = self._extract_content(soup)

        # 提取发布时间
        published_at = self._extract_publish_time(soup)

        # 提取封面图
        images = self._extract_images(soup, url)

        # 提取引用链接（文内链接、阅读原文）
        references = self._extract_references(soup, url)

        # 提取元数据（阅读数、点赞数等 if available)
        meta = self._extract_meta(soup)
        engagement = self._extract_engagement(soup)

        return CrawlResult(
            url=url,
            final_url=str(response.url),
            title=title,
            content=content,
            author=author,
            author_id=author_id,
            platform="wechat",
            published_at=published_at,
            content_hash=self._compute_hash(content),
            images=images,
            references=references,
            raw_html=html,
            meta=meta,
            engagement=engagement,
        )

    async def search(self, keyword: str, limit: int = 20) -> list[CrawlResult]:
        """
        微信搜索（通过搜狗微信搜索）

        Args:
            keyword: 搜索关键词
            limit: 最大结果数

        Returns:
            CrawlResult 列表
        """
        results = []
        try:
            from urllib.parse import quote

            search_url = f"{self.SOGOU_SEARCH}?type=2&query={quote(keyword)}"

            async with self.client as client:
                response = await client.get(
                    search_url,
                    headers={
                        "User-Agent": self.user_agents[0],
                        "Accept": "text/html,application/xhtml+xml,*/*",
                        "Referer": "https://weixin.sogou.com/",
                    },
                )
                soup = BeautifulSoup(response.text, "lxml")

                # 搜索结果条目
                for item in soup.select(".news-box .news-list li")[:limit]:
                    link = item.select_one("a[href*='mp.weixin.qq.com']")
                    if not link:
                        continue

                    href = link.get("href", "")
                    if not href:
                        continue

                    # 爬取结果文章
                    result = await self.fetch(href)
                    if result and result.content:
                        results.append(result)

        except Exception as e:
            logger.error(f"微信搜索失败 '{keyword}': {e}")

        return results

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取文章标题"""
        strategies = [
            lambda: soup.select_one("#activity-name"),
            lambda: soup.select_one(".rich_media_title"),
            lambda: soup.find("meta", property="og:title"),
            lambda: soup.find("title"),
        ]
        for strategy in strategies:
            elem = strategy()
            if elem:
                text = elem.get("content") or elem.get_text(strip=True)
                if text and len(text) > 1:
                    # 去掉尾部 "| 微信公众平台" 等后缀
                    text = re.sub(r'\s*[|_\-—]\s*.*$', '', text.strip())
                    return text[:500]
        return ""

    def _extract_author(self, soup: BeautifulSoup) -> str:
        """提取公众号名称"""
        strategies = [
            lambda: soup.select_one("#js_name"),
            lambda: soup.select_one(".rich_media_meta_nickname"),
            lambda: soup.select_one("#js_author_name"),
            lambda: soup.select_one(".profile_nickname"),
            lambda: soup.find("meta", attrs={"name": "author"}),
        ]
        for strategy in strategies:
            elem = strategy()
            if elem:
                text = elem.get("content") or elem.get_text(strip=True)
                if text and len(text) > 1:
                    return text.strip()[:255]
        return ""

    def _extract_author_id(self, soup: BeautifulSoup, url: str) -> str:
        """提取公众号 ID (__biz 参数)"""
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            return params.get("__biz", [""])[0]
        except Exception:
            pass

        # 从页面 JS 数据提取
        for script in soup.find_all("script"):
            if script.string and "__biz" in (script.string or ""):
                match = re.search(r'__biz\s*=\s*"([^"]+)"', script.string)
                if match:
                    return match.group(1)
        return ""

    def _extract_content(self, soup: BeautifulSoup) -> str:
        """提取文章正文"""
        content_selectors = [
            "#js_content",
            ".rich_media_content",
            ".rich_media_area_primary",
        ]

        for selector in content_selectors:
            elem = soup.select_one(selector)
            if elem and len(elem.get_text(strip=True)) > 50:
                # 移除脚本和样式
                for tag in elem(["script", "style"]):
                    tag.decompose()
                # 替换 <br> 为换行
                for br in elem.find_all("br"):
                    br.replace_with("\n")
                content = elem.get_text(separator="\n", strip=True)
                # 过滤掉明显的噪音
                content = re.sub(r'\n{3,}', '\n\n', content)
                return content[:10000]

        # 回退
        body = soup.find("body")
        if body:
            for tag in body(["script", "style"]):
                tag.decompose()
            return body.get_text(separator="\n", strip=True)[:5000]

        return ""

    def _extract_publish_time(self, soup: BeautifulSoup) -> str:
        """提取发布时间"""
        # 方法1: 页面中的 JS 数据
        for script in soup.find_all("script"):
            if script.string and "publish_time" in (script.string or ""):
                match = re.search(r'"publish_time"\s*:\s*"(\d{4}-\d{2}-\d{2})"', script.string)
                if match:
                    return match.group(1) + "T00:00:00+08:00"

        # 方法2: meta 标签
        meta_time = soup.find("meta", property="article:published_time")
        if meta_time:
            return meta_time.get("content", "")

        # 方法3: 页面中的时间文本
        time_elems = soup.select(".rich_media_meta_text, #publish_time, .weui-desktop-mass")
        for elem in time_elems:
            text = elem.get_text(strip=True)
            date_match = re.search(r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})', text)
            if date_match:
                dt_str = date_match.group(1).replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
                try:
                    dt = datetime.strptime(dt_str, "%Y-%m-%d")
                    return dt.isoformat() + "T00:00:00+08:00"
                except ValueError:
                    return dt_str
        return ""

    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """提取文章图片"""
        images = []
        from urllib.parse import urljoin

        # 封面图
        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            images.append(og_img["content"])

        # 正文图片
        for img in soup.select("#js_content img, .rich_media_content img"):
            src = img.get("data-src") or img.get("src")
            if src:
                full_url = urljoin(base_url, src)
                if full_url not in images and "mmbiz.qpic.cn" in full_url:
                    images.append(full_url)

        return images[:20]

    def _extract_references(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        """提取引用链接（文内链接 + 阅读原文）"""
        refs = set()
        from urllib.parse import urljoin

        content_area = (
            soup.select_one("#js_content")
            or soup.select_one(".rich_media_content")
        )

        if content_area:
            for a in content_area.find_all("a", href=True):
                href = urljoin(base_url, a["href"])
                if href.startswith("http") and "mp.weixin.qq.com" not in href:
                    refs.add(href)

            # 阅读原文链接
            source_link = soup.select_one("#js_source_link, .original_link")
            if source_link:
                href = source_link.get("href", "")
                if href and href.startswith("http"):
                    refs.add(href)

        return list(refs)[:50]

    def _extract_meta(self, soup: BeautifulSoup) -> dict:
        """提取元数据"""
        meta = {}
        for tag in soup.find_all("meta"):
            prop = tag.get("property") or tag.get("name", "")
            content = tag.get("content", "")
            if prop and content:
                meta[prop] = content

        # 提取 var 变量中的关键数据
        var_patterns = {
            "msg_source_url": r'var\s+msg_source_url\s*=\s*"([^"]*)"',
            "msg_cdn_url": r'var\s+msg_cdn_url\s*=\s*"([^"]*)"',
        }
        for script in soup.find_all("script"):
            if script.string:
                for key, pattern in var_patterns.items():
                    match = re.search(pattern, script.string)
                    if match:
                        meta[key] = match.group(1)

        return meta

    def _extract_engagement(self, soup: BeautifulSoup) -> dict:
        """尝试提取互动数据（阅读数等）"""
        engagement = {
            "views": 0,
            "likes": 0,
            "shares": 0,
        }

        for script in soup.find_all("script"):
            if script.string:
                for pattern, key in [
                    (r'"read_num"\s*:\s*(\d+)', "views"),
                    (r'"like_num"\s*:\s*(\d+)', "likes"),
                    (r'"share_num"\s*:\s*(\d+)', "shares"),
                ]:
                    match = re.search(pattern, script.string)
                    if match:
                        engagement[key] = int(match.group(1))

        return engagement if any(v > 0 for v in engagement.values()) else {}

    @staticmethod
    def is_wechat_url(url: str) -> bool:
        """判断 URL 是否为微信文章"""
        domain = urlparse(url).netloc.lower()
        return "mp.weixin.qq.com" in domain

    @classmethod
    def is_wechat_article(cls, url: str) -> bool:
        """判断 URL 是否为微信文章"""
        return cls.is_wechat_url(url)
