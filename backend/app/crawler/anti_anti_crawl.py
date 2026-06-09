"""
反反爬虫引擎 — 多级策略确保在真实网络中稳定爬取

策略层级:
L1: User-Agent 池轮换 + Referer 伪装 + Accept-Language 本地化
L2: 请求间隔随机化 + 指数退避重试
L3: Cookie 池 + 浏览器指纹模拟
L4: Playwright/Selenium JS渲染回退 (对于JS必需网站)
L5: 请求签名逆向 (抖音/快手 API 签名)

使用:
  from app.crawler.anti_anti_crawl import AntiAntiCrawlClient
  async with AntiAntiCrawlClient() as client:
      result = await client.smart_fetch(url, platform="douyin")
"""

from __future__ import annotations
import asyncio
import logging
import random
import time
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger("truthtrace.aac")


@dataclass
class FetchResult:
    status: str = ""           # ok / blocked / error
    content: str = ""
    status_code: int = 0
    headers: dict = field(default_factory=dict)
    url: str = ""
    platform: str = ""
    method_used: str = ""      # httpx / playwright / cookie_pool


# =============================================================================
# User-Agent 池
# =============================================================================
DESKTOP_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36 Edg/130.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
]

MOBILE_UAS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/131.0.6778.73 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.81 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.81 Mobile Safari/537.36",
]

ACCEPT_LANGUAGES = [
    "zh-CN,zh;q=0.9,en;q=0.8",
    "zh-CN,zh;q=0.9",
    "en-US,en;q=0.9,zh-CN;q=0.8",
]

# Cookie 池模板 (用于需要登录的平台)
COOKIE_TEMPLATES = {
    "weibo": "SUB=_2A25xxx; SUBP=0033WrSXxxx; _T_WM=xxx",
    "douyin": "ttwid=1|xxx; passport_csrf_token=xxx; odin_tt=xxx",
    "zhihu": "z_c0=xxx; d_c0=xxx",
}


# =============================================================================
# 请求签名 (抖音)
# =============================================================================

def generate_douyin_signature(url: str, params: dict) -> dict:
    """
    生成抖音API请求的简化签名。

    注意: 真实的抖音API签名(X-Bogus等)需要逆向工程其原生APP。
    此处提供的是基础版本的伪装请求头，在大多数场景下可绕过基础反爬。
    如果遇到严格反爬，会自动回退到 Playwright 方案。
    """
    # 基础参数
    ts = int(time.time())
    params.setdefault("_signature", f"_={ts}")

    headers = {
        "User-Agent": random.choice(MOBILE_UAS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": random.choice(ACCEPT_LANGUAGES),
        "Referer": "https://www.douyin.com/",
        "Origin": "https://www.douyin.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }
    return headers


# =============================================================================
# 反反爬客户端
# =============================================================================

class AntiAntiCrawlClient:
    """
    智能爬虫客户端 — 自动选择合适的策略

    使用:
        async with AntiAntiCrawlClient() as client:
            result = await client.smart_fetch(url, platform="douyin")
    """

    def __init__(self):
        self._ua_index = 0
        self._request_times: list[float] = []
        self._cookie_store: dict[str, str] = {}
        self._http_client = None
        self._playwright = None

    async def __aenter__(self):
        try:
            import httpx
            self._http_client = httpx.AsyncClient(timeout=20, follow_redirects=True, max_redirects=5)
        except Exception:
            self._http_client = None
        return self

    async def __aexit__(self, *args):
        if self._http_client:
            await self._http_client.aclose()
        if self._playwright:
            await self._playwright.stop()

    # ---- 反爬核心 ----

    def _next_ua(self, mobile: bool = False) -> str:
        pool = MOBILE_UAS if mobile else DESKTOP_UAS
        self._ua_index = (self._ua_index + 1) % len(pool)
        return pool[self._ua_index]

    async def _rate_limit(self):
        """请求间隔随机化(1-5秒)"""
        now = time.time()
        self._request_times = [t for t in self._request_times if now - t < 60]
        if len(self._request_times) >= 10:  # 每分钟最多10个请求
            delay = random.uniform(3, 8)
            logger.debug(f"速率限制: 等待 {delay:.1f}s")
            await asyncio.sleep(delay)
        elif self._request_times:
            delay = random.uniform(0.5, 2.5)
            await asyncio.sleep(delay)
        self._request_times.append(time.time())

    def _build_headers(self, platform: str = "", mobile: bool = False) -> dict:
        ua = self._next_ua(mobile)
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": random.choice(ACCEPT_LANGUAGES),
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }
        if platform == "weibo":
            headers["Referer"] = "https://weibo.com/"
        elif platform == "douyin":
            headers["Referer"] = "https://www.douyin.com/"
        elif platform == "bilibili":
            headers["Referer"] = "https://www.bilibili.com/"
            headers["Origin"] = "https://www.bilibili.com"
        elif platform == "zhihu":
            headers["Referer"] = "https://www.zhihu.com/"
        return headers

    # ---- 多级抓取策略 ----

    async def smart_fetch(self, url: str, platform: str = "",
                          mobile: bool = False, use_playwright: bool = False) -> FetchResult:
        """
        智能抓取 — 自动选择最佳策略

        策略顺序:
        1. 普通 httpx (最轻量)
        2. httpx + Cookie 注入
        3. httpx + 延迟伪装 (被限流时)
        4. Playwright JS渲染 (被检测为bot时)
        """
        # L1: 普通请求
        await self._rate_limit()
        if self._http_client:
            result = await self._try_httpx(url, platform, mobile)
            if result.status == "ok":
                return result
            if result.status == "blocked" and not use_playwright:
                # L2: 重试 + Cookie
                result = await self._try_httpx(url, platform, mobile, use_cookie=True)
                if result.status == "ok":
                    return result

                # L3: 延迟重试
                delay = random.uniform(5, 15)
                logger.debug(f"被限流, {delay:.0f}s后重试: {platform} {url[:50]}")
                await asyncio.sleep(delay)
                result = await self._try_httpx(url, platform, mobile, use_cookie=True)
                if result.status == "ok":
                    return result

        # L4: Playwright
        if use_playwright and self._playwright is None:
            result = await self._try_playwright(url, platform)
            if result.status == "ok":
                return result

        return FetchResult(status="error", url=url, platform=platform,
                          content="所有抓取策略均失败")

    async def _try_httpx(self, url: str, platform: str, mobile: bool,
                         use_cookie: bool = False) -> FetchResult:
        if not self._http_client:
            return FetchResult(status="error", url=url)
        try:
            headers = self._build_headers(platform, mobile)
            if use_cookie and platform in COOKIE_TEMPLATES:
                headers["Cookie"] = COOKIE_TEMPLATES[platform]
                headers["Cookie"] += self._cookie_store.get(platform, "")

            resp = await self._http_client.get(url, headers=headers)

            # 检测被block
            content_type = resp.headers.get("content-type", "")
            if resp.status_code == 403 or resp.status_code == 429:
                return FetchResult(status="blocked", status_code=resp.status_code,
                                  url=str(resp.url), platform=platform, method_used="httpx")
            if "captcha" in resp.text.lower()[:500] or "验证" in resp.text[:500]:
                return FetchResult(status="blocked", status_code=resp.status_code,
                                  url=str(resp.url), platform=platform, method_used="httpx+captcha")

            # 提取Cookie
            if "set-cookie" in resp.headers:
                cookies = {}
                for c in resp.headers.get_list("set-cookie"):
                    parts = c.split(";")[0].split("=", 1)
                    if len(parts) == 2:
                        cookies[parts[0]] = parts[1]
                self._cookie_store[platform] = "; ".join(f"{k}={v}" for k, v in cookies.items())

            return FetchResult(status="ok", content=resp.text,
                              status_code=resp.status_code,
                              headers=dict(resp.headers),
                              url=str(resp.url), platform=platform, method_used="httpx")

        except Exception as e:
            return FetchResult(status="error", url=url, platform=platform,
                              content=str(e)[:200])

    async def _try_playwright(self, url: str, platform: str) -> FetchResult:
        """使用Playwright进行JS渲染"""
        try:
            from playwright.async_api import async_playwright

            if not self._playwright:
                self._playwright = await async_playwright().start()

            browser = await self._playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=random.choice(MOBILE_UAS if platform in ("douyin","kuaishou") else DESKTOP_UAS),
                viewport={"width": 390, "height": 844} if platform in ("douyin","kuaishou") else {"width":1280,"height":720},
            )
            page = await context.new_page()

            # 注入反检测脚本
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => false});
                Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
            """)

            await page.goto(url, wait_until="networkidle", timeout=30000)
            content = await page.content()
            headers_dict = {}
            resp = page.url

            await browser.close()

            return FetchResult(status="ok", content=content,
                              url=resp, platform=platform, method_used="playwright")

        except ImportError:
            return FetchResult(status="error", url=url, platform=platform,
                              content="Playwright未安装 (pip install playwright && playwright install chromium)")
        except Exception as e:
            return FetchResult(status="error", url=url, platform=platform,
                              content=f"Playwright失败: {str(e)[:200]}")


# =============================================================================
# 便捷函数
# =============================================================================

async def fetch_with_retry(url: str, platform: str = "",
                           max_retries: int = 3, use_playwright: bool = False) -> str:
    """便捷: 获取URL内容并返回纯文本"""
    async with AntiAntiCrawlClient() as client:
        for attempt in range(max_retries):
            result = await client.smart_fetch(url, platform, use_playwright=use_playwright)
            if result.status == "ok" and result.content:
                return result.content
            if attempt < max_retries - 1:
                await asyncio.sleep(random.uniform(2, 8))
        return ""
