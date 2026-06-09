"""
URL 解析器 — 跟踪短链接跳转链，还原原始 URL
"""

import re
from urllib.parse import urlparse

import httpx
from loguru import logger


class URLResolver:
    """
    URL 跳转链解析器

    支持：
    - HTTP 30x 重定向跟踪
    - 常见短链接服务：t.cn, bit.ly, ow.ly, tinyurl.com, short.com 等
    - HTML meta refresh 跳转
    - JavaScript window.location 跳转（基础）
    """

    # 已知短链接域名
    SHORTLINK_DOMAINS = {
        "t.cn", "bit.ly", "ow.ly", "tinyurl.com", "is.gd",
        "buff.ly", "short.com", "goo.gl", "dwz.cn", "suo.im",
        "dlvr.it", "ift.tt", "zpr.io", "shrtco.de", "cutt.ly",
        "shorturl.at", "tiny.cc", "lc.chat",
    }

    def __init__(self, timeout: int = 15, max_redirects: int = 20):
        self.timeout = timeout
        self.max_redirects = max_redirects

    async def resolve(self, url: str) -> list[tuple[str, int]]:
        """
        解析 URL 跳转链

        Args:
            url: 要解析的 URL

        Returns:
            跳转链列表: [(url, http_status), ...]
            链尾为最终目标 URL
        """
        chain: list[tuple[str, int]] = []
        current_url = url
        visited = set()

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=False,  # 手动跟踪以记录每一跳
        ) as client:
            for _ in range(self.max_redirects):
                if current_url in visited:
                    logger.warning(f"检测到跳转循环: {current_url}")
                    break
                visited.add(current_url)

                try:
                    response = await client.get(
                        current_url,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "Accept": "text/html,application/xhtml+xml,*/*",
                        },
                    )

                    status = response.status_code
                    chain.append((current_url, status))

                    # HTTP 重定向
                    if status in (301, 302, 303, 307, 308):
                        next_url = response.headers.get("Location", "")
                        if next_url:
                            # 处理相对路径
                            if not next_url.startswith("http"):
                                from urllib.parse import urljoin
                                next_url = urljoin(current_url, next_url)
                            current_url = next_url
                            continue

                    # 检查 HTML meta refresh
                    if status == 200:
                        meta_url = self._extract_meta_refresh(response.text)
                        if meta_url:
                            from urllib.parse import urljoin
                            current_url = urljoin(current_url, meta_url)
                            continue

                        # 检查 JavaScript 跳转
                        js_url = self._extract_js_redirect(response.text)
                        if js_url:
                            from urllib.parse import urljoin
                            current_url = urljoin(current_url, js_url)
                            continue

                    # 无更多跳转 — 到达最终目标
                    break

                except Exception as e:
                    logger.error(f"URL 解析错误 {current_url}: {e}")
                    chain.append((current_url, 0))
                    break

        return chain

    def is_shortlink(self, url: str) -> bool:
        """判断是否为已知短链接"""
        try:
            domain = urlparse(url).netloc.lower()
            domain = re.sub(r'^www\.', '', domain)
            return domain in self.SHORTLINK_DOMAINS
        except Exception:
            return False

    def get_final_url(self, chain: list[tuple[str, int]]) -> str:
        """从跳转链中获取最终 URL"""
        if chain:
            return chain[-1][0]
        return ""

    def _extract_meta_refresh(self, html: str) -> str | None:
        """提取 HTML meta refresh 跳转 URL"""
        match = re.search(
            r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]+content=["\']?\d+;\s*url=([^"\'>\s]+)',
            html, re.IGNORECASE
        )
        if match:
            return match.group(1)
        return None

    def _extract_js_redirect(self, html: str) -> str | None:
        """提取 JavaScript 跳转 URL（基本模式）"""
        patterns = [
            r'window\.location\s*=\s*["\']([^"\']+)["\']',
            r'window\.location\.href\s*=\s*["\']([^"\']+)["\']',
            r'location\.replace\s*\(\s*["\']([^"\']+)["\']\s*\)',
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                return match.group(1)
        return None
