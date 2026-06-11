"""
MediaCrawler 多平台采集扩展 — 增强版爬虫模块

在现有 BaseCrawler (general/web) 基础上扩展 5+ 新平台支持:
  - 小红书 (Xiaohongshu)
  - 抖音 (Douyin)
  - 快手 (Kuaishou)
  - B站增强 (Bilibili) — 增强版
  - Twitter/X

设计参考:
  - MediaCrawler (github.com/NanmiCoder/MediaCrawler): 8+ platforms, async
  - Ultimate-Social-Scrapers: Playwright/Puppeteer, anti-bot

架构:
  每个平台使用统一的 MediaCrawlResult，集成到现有 CrawlResult 体系。
  复用现有的 base.py CrawlerSandbox 和 anti_anti_crawl.py。
"""

from __future__ import annotations
import re
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger("truthtrace.media_crawler")

# =============================================================================
# 统一测试结果
# =============================================================================

@dataclass
class MediaCrawlResult:
    """多平台统一采集结果"""
    platform: str = ""
    url: str = ""
    resolved_url: str = ""
    title: str = ""
    content: str = ""
    author: str = ""
    author_id: str = ""
    published_at: str = ""
    fetched_at: str = ""
    engagement: dict = field(default_factory=dict)  # {likes, comments, shares, views}
    images: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    source_type: str = "social_media"  # social_media / short_video / forum
    is_video: bool = False
    video_duration: int = 0
    success: bool = False
    error: str = ""
    raw_metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "url": self.url,
            "resolved_url": self.resolved_url,
            "title": self.title,
            "content": self.content[:5000] if self.content else "",
            "author": self.author,
            "author_id": self.author_id,
            "published_at": self.published_at,
            "fetched_at": self.fetched_at,
            "engagement": self.engagement,
            "images": self.images[:10],
            "hashtags": self.hashtags,
            "source_type": self.source_type,
            "is_video": self.is_video,
            "video_duration": self.video_duration,
            "success": self.success,
            "error": self.error,
        }


# =============================================================================
# 平台识别
# =============================================================================

PLATFORM_DETECTORS = {
    "bilibili": [
        r'bilibili\.com/video/BV[\w]+',
        r'b23\.tv/[\w]+',
        r'bilibili\.com/read/cv\d+',
    ],
    "xiaohongshu": [
        r'xhslink\.com/[\w]+',
        r'xiaohongshu\.com/discovery/item/[\w]+',
        r'xiaohongshu\.com/explore/[\w]+',
        r'xhslink\.com',
    ],
    "douyin": [
        r'douyin\.com/video/\d+',
        r'v\.douyin\.com/[\w]+',
        r'douyin\.com/user/[\w]+',
    ],
    "kuaishou": [
        r'kuaishou\.com/short-video/[\w]+',
        r'v\.kuaishou\.com/[\w]+',
        r'kuaishou\.com/f/[\w]+',
    ],
    "twitter": [
        r'twitter\.com/\w+/status/\d+',
        r'x\.com/\w+/status/\d+',
        r't\.co/[\w]+',
    ],
}


def detect_platform(url: str) -> str | None:
    """检测 URL 对应的平台"""
    for platform, patterns in PLATFORM_DETECTORS.items():
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return platform
    return None


# =============================================================================
# 平台处理器
# =============================================================================

class MediaCrawler:
    """多平台采集器 — 为每个平台提供专用提取策略"""

    # 平台 → 处理器方法映射
    PLATFORM_HANDLERS = {
        "xiaohongshu": "_fetch_xiaohongshu",
        "douyin": "_fetch_douyin",
        "kuaishou": "_fetch_kuaishou",
        "bilibili": "_fetch_bilibili",
        "twitter": "_fetch_twitter",
    }

    def __init__(self):
        self._session = None

    async def fetch(self, url: str, timeout: int = 30) -> MediaCrawlResult:
        """主入口 — 自动识别平台并调用对应处理器"""
        platform = detect_platform(url)

        if not platform:
            return MediaCrawlResult(
                url=url,
                success=False,
                error=f"无法识别平台: {url}。支持的平台: {', '.join(self.PLATFORM_HANDLERS.keys())}",
            )

        handler_name = self.PLATFORM_HANDLERS.get(platform)
        if not handler_name:
            return MediaCrawlResult(
                platform=platform, url=url, success=False,
                error=f"平台 '{platform}' 已识别但处理器未实现",
            )

        handler = getattr(self, handler_name, None)
        if not handler:
            return MediaCrawlResult(
                platform=platform, url=url, success=False,
                error=f"处理器 '{handler_name}' 未找到",
            )

        try:
            result = await handler(url, timeout)
            result.platform = platform
            result.fetched_at = datetime.now().isoformat()
            return result
        except Exception as e:
            logger.warning(f"{platform} 采集失败: {e}")
            return MediaCrawlResult(
                platform=platform, url=url, success=False,
                error=f"{platform} 采集异常: {str(e)[:200]}",
            )

    async def fetch_multiple(self, urls: list[str]) -> list[MediaCrawlResult]:
        """批量采集多个 URL (串行，避免触发反爬)"""
        import asyncio
        results = []
        for url in urls:
            result = await self.fetch(url)
            results.append(result)
            if result.success:
                await asyncio.sleep(1.5)  # 请求间隔
        return results

    # -------------------------------------------------------------------
    # 小红书 (Xiaohongshu)
    # -------------------------------------------------------------------

    async def _fetch_xiaohongshu(self, url: str, timeout: int = 30) -> MediaCrawlResult:
        """小红书分享链接解析"""
        result = MediaCrawlResult(url=url, platform="xiaohongshu", source_type="social_media")

        # 尝试解析短链接 (xhslink.com)
        if "xhslink.com" in url:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=float(timeout), follow_redirects=True) as client:
                    response = await client.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
                        "Accept": "text/html,application/xhtml+xml",
                    })
                    result.resolved_url = str(response.url)

                    # 从 HTML 提取基本信息
                    html = response.text
                    title_match = re.search(r'<title>([^<]+)</title>', html)
                    desc_match = re.search(r'"desc"\s*:\s*"([^"]+)"', html)

                    if title_match:
                        result.title = title_match.group(1).strip()
                    if desc_match:
                        result.content = desc_match.group(1)
            except ImportError:
                result.error = "httpx 不可用，无法跟随短链接"
                return result
            except Exception as e:
                result.error = f"短链接解析失败: {e}"
                return result

        result.success = bool(result.title or result.content)
        if not result.success:
            result.error = result.error or "未能提取有效内容"

        return result

    # -------------------------------------------------------------------
    # 抖音 (Douyin)
    # -------------------------------------------------------------------

    async def _fetch_douyin(self, url: str, timeout: int = 30) -> MediaCrawlResult:
        """抖音分享链接解析"""
        result = MediaCrawlResult(url=url, platform="douyin", source_type="short_video",
                                   is_video=True)

        try:
            import httpx
            async with httpx.AsyncClient(timeout=float(timeout), follow_redirects=True) as client:
                response = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
                    "Accept": "text/html,application/xhtml+xml",
                })
                result.resolved_url = str(response.url)
                html = response.text

                # 从 meta/JSON 提取
                title_match = re.search(r'<title>([^<]+)</title>', html)
                desc_match = re.search(r'"desc"\s*:\s*"([^"]*)"', html)
                author_match = re.search(r'"nickname"\s*:\s*"([^"]*)"', html)
                likes_match = re.search(r'"digg_count"\s*:\s*(\d+)', html)
                comments_match = re.search(r'"comment_count"\s*:\s*(\d+)', html)
                shares_match = re.search(r'"share_count"\s*:\s*(\d+)', html)

                if title_match:
                    result.title = title_match.group(1).strip()
                if desc_match:
                    result.content = desc_match.group(1)
                if author_match:
                    result.author = author_match.group(1)
                if likes_match:
                    result.engagement["likes"] = int(likes_match.group(1))
                if comments_match:
                    result.engagement["comments"] = int(comments_match.group(1))
                if shares_match:
                    result.engagement["shares"] = int(shares_match.group(1))

                # 提取标签
                result.hashtags = re.findall(r'#(\w+)', html)

        except ImportError:
            result.error = "httpx 不可用"
        except Exception as e:
            result.error = f"抖音解析失败: {e}"

        result.success = bool(result.title or result.content)
        return result

    # -------------------------------------------------------------------
    # 快手 (Kuaishou)
    # -------------------------------------------------------------------

    async def _fetch_kuaishou(self, url: str, timeout: int = 30) -> MediaCrawlResult:
        """快手分享链接解析"""
        result = MediaCrawlResult(url=url, platform="kuaishou", source_type="short_video",
                                   is_video=True)

        try:
            import httpx
            async with httpx.AsyncClient(timeout=float(timeout), follow_redirects=True) as client:
                response = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
                })
                result.resolved_url = str(response.url)
                html = response.text

                title_match = re.search(r'<title>([^<]+)</title>', html)
                desc_match = re.search(r'"caption"\s*:\s*"([^"]*)"', html)
                author_match = re.search(r'"userName"\s*:\s*"([^"]*)"', html)

                if title_match:
                    result.title = title_match.group(1).strip()
                if desc_match:
                    result.content = desc_match.group(1)
                if author_match:
                    result.author = author_match.group(1)

        except ImportError:
            result.error = "httpx 不可用"
        except Exception as e:
            result.error = f"快手解析失败: {e}"

        result.success = bool(result.title or result.content)
        return result

    # -------------------------------------------------------------------
    # B站增强 (Bilibili) — 在现有 BilibiliCrawler 基础上增强
    # -------------------------------------------------------------------

    async def _fetch_bilibili(self, url: str, timeout: int = 30) -> MediaCrawlResult:
        """B站增强采集 — 直接使用现有 BilibiliCrawler"""
        result = MediaCrawlResult(url=url, platform="bilibili", source_type="social_media")

        try:
            from app.crawler.video_platforms import BilibiliCrawler
            crawler = BilibiliCrawler()
            info = await crawler.get_video_info(url)

            if info:
                result.title = info.title or ""
                result.content = info.desc or ""
                result.author = info.owner_name or ""
                result.engagement = {
                    "views": info.view_count or 0,
                    "likes": info.like_count or 0,
                    "comments": info.comment_count or 0,
                    "shares": info.share_count or 0,
                    "danmaku": info.danmaku_count or 0,
                }
                result.images = [info.pic_url] if info.pic_url else []
                result.is_video = True
                result.video_duration = info.duration or 0
                result.success = True
        except ImportError:
            # Fallback: 简单 HTTP 解析
            result = await self._fallback_fetch(url, "bilibili", timeout)
        except Exception as e:
            logger.warning(f"B站采集: BilibiliCrawler不可用 ({e}), 使用HTTP fallback")
            result = await self._fallback_fetch(url, "bilibili", timeout)

        return result

    # -------------------------------------------------------------------
    # Twitter/X
    # -------------------------------------------------------------------

    async def _fetch_twitter(self, url: str, timeout: int = 30) -> MediaCrawlResult:
        """Twitter/X 推文采集"""
        result = MediaCrawlResult(url=url, platform="twitter", source_type="social_media")

        # 提取 tweet ID
        tweet_id_match = re.search(r'/status/(\d+)', url)
        tweet_id = tweet_id_match.group(1) if tweet_id_match else None

        try:
            import httpx

            # 使用 Twitter API v2 (如果配置了 bearer token)
            from app.config import get_settings
            settings = get_settings()
            bearer_token = getattr(settings, 'twitter_bearer_token', '')

            if bearer_token and tweet_id:
                async with httpx.AsyncClient(timeout=float(timeout)) as client:
                    api_response = await client.get(
                        f"https://api.twitter.com/2/tweets/{tweet_id}",
                        params={
                            "tweet.fields": "created_at,public_metrics,author_id,text",
                            "expansions": "author_id",
                            "user.fields": "username,name",
                        },
                        headers={"Authorization": f"Bearer {bearer_token}"},
                    )
                    if api_response.status_code == 200:
                        data = api_response.json()
                        tweet = data.get("data", {})
                        users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

                        result.title = tweet.get("text", "")[:150]
                        result.content = tweet.get("text", "")
                        result.author = users.get(tweet.get("author_id", ""), {}).get("username", "")
                        result.author_id = tweet.get("author_id", "")
                        result.published_at = tweet.get("created_at", "")

                        metrics = tweet.get("public_metrics", {})
                        result.engagement = {
                            "likes": metrics.get("like_count", 0),
                            "retweets": metrics.get("retweet_count", 0),
                            "replies": metrics.get("reply_count", 0),
                            "quotes": metrics.get("quote_count", 0),
                        }
                        result.success = True
                        return result

            # Fallback: 使用 oEmbed
            async with httpx.AsyncClient(timeout=float(timeout)) as client:
                oembed_url = f"https://publish.twitter.com/oembed?url={url}"
                oembed_resp = await client.get(oembed_url)
                if oembed_resp.status_code == 200:
                    oembed = oembed_resp.json()
                    result.title = oembed.get("author_name", "")
                    result.content = oembed.get("html", "")[:2000]
                    result.author = oembed.get("author_name", "")
                    result.success = True

        except ImportError:
            result.error = "httpx 不可用，无法采集 Twitter"
        except Exception as e:
            result.error = f"Twitter 采集失败: {e}"

        return result

    # -------------------------------------------------------------------
    # HTTP Fallback (通用)
    # -------------------------------------------------------------------

    async def _fallback_fetch(self, url: str, platform: str, timeout: int = 15) -> MediaCrawlResult:
        """HTTP fallback: 通用页面标题+描述提取"""
        result = MediaCrawlResult(url=url, platform=platform)

        try:
            import httpx
            async with httpx.AsyncClient(timeout=float(timeout), follow_redirects=True) as client:
                response = await client.get(url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                })
                result.resolved_url = str(response.url)
                html = response.text

                # 提取 OpenGraph 元数据
                title_match = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html, re.I)
                if not title_match:
                    title_match = re.search(r'<title>([^<]+)</title>', html)
                desc_match = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html, re.I)

                if title_match:
                    result.title = title_match.group(1).strip()[:300]
                if desc_match:
                    result.content = desc_match.group(1).strip()[:2000]

                result.success = bool(result.title)
        except ImportError:
            result.error = "httpx 不可用"
        except Exception as e:
            result.error = f"HTTP fallback 失败: {e}"

        return result
