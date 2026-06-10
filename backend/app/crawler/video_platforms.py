"""
视频平台爬虫 — 抖音/快手/哔哩哔哩/YouTube/微博视频

支持:
1. 从视频URL提取标题/描述/文字内容
2. 视频元数据提取 (时长/发布时间/作者/播放量)
3. 评论采集 (高赞评论)
4. 内容指纹去重
5. 速率限制和自动重试
6. 将文字内容送入10引擎推理分析

注意:
- 各平台的API可能随时变化
- 部分平台需要反爬措施
- 无法直接下载/分析视频画面 (需要ffmpeg+media_verifier)
- 文字内容(标题/描述/字幕/评论)已足够进行文本层面的10引擎分析
"""

from __future__ import annotations
import re
import json
import logging
import asyncio
import time
from datetime import datetime
from dataclasses import dataclass, field
from functools import wraps
from typing import Optional, Callable, Awaitable
import hashlib

logger = logging.getLogger("truthtrace.video")

# =============================================================================
# 速率限制 & 重试工具
# =============================================================================

class RateLimiter:
    """简单的异步速率限制器"""

    def __init__(self, calls_per_second: float = 2.0):
        self.interval = 1.0 / calls_per_second
        self._last_call = 0.0

    async def wait(self):
        """等待直到可以发出下一个请求"""
        now = time.monotonic()
        wait_time = self._last_call + self.interval - now
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        self._last_call = time.monotonic()


# 各平台的速率限制器实例
_rate_limiters: dict[str, RateLimiter] = {
    "bilibili": RateLimiter(3.0),   # B站公开API较宽松
    "douyin": RateLimiter(1.0),     # 抖音API较敏感
    "kuaishou": RateLimiter(1.0),   # 快手
    "youtube": RateLimiter(2.0),    # YouTube oEmbed
    "weibo_video": RateLimiter(2.0),
}


def with_retry(max_retries: int = 2, base_delay: float = 1.0):
    """异步重试装饰器，指数退避"""
    def decorator(func: Callable[..., Awaitable]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"[重试] {func.__name__} 第{attempt + 1}次失败: {e}, {delay}s后重试...")
                        await asyncio.sleep(delay)
            logger.error(f"[重试耗尽] {func.__name__} 全部{max_retries + 1}次尝试均失败: {last_error}")
            return None
        return wrapper
    return decorator


def compute_content_hash(text: str) -> str:
    """计算文本内容的指纹哈希（用于去重）"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


# 已分析内容的哈希缓存（防止重复分析同一视频）
_content_hash_cache: dict[str, dict] = {}


# =============================================================================
# 通用视频信息结构
# =============================================================================

@dataclass
class VideoInfo:
    """从视频平台提取的统一信息结构"""
    platform: str = ""          # douyin / kuaishou / bilibili
    video_id: str = ""          # 平台唯一标识
    url: str = ""               # 原始URL
    title: str = ""
    description: str = ""       # 视频描述/简介
    author_name: str = ""
    author_id: str = ""
    duration_seconds: int = 0
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    published_at: Optional[datetime] = None
    tags: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    top_comments: list[dict] = field(default_factory=list)  # [{text, likes, author}]
    music_title: str = ""       # 背景音乐
    is_original: bool = True    # 是否原创 (vs 转载/搬运)
    thumbnail_url: str = ""
    # 字幕/CC 内容
    subtitles: list[dict] = field(default_factory=list)  # [{lang, lines: [{from, to, content}]}]
    subtitle_text: str = ""     # 合并后的纯文本字幕
    # 弹幕 (B站特有)
    danmaku_count: int = 0
    danmaku_text: str = ""

    def to_text(self) -> str:
        """将所有文字信息合并为一段可分析的文本"""
        parts = []
        if self.title:
            parts.append(f"标题: {self.title}")
        if self.description:
            parts.append(f"描述: {self.description}")
        if self.tags:
            parts.append(f"标签: {', '.join(self.tags)}")
        if self.hashtags:
            parts.append(f"话题: {' '.join(self.hashtags)}")
        comments_text = "; ".join(
            f"@{c.get('author', '')}: {c.get('text', '')[:100]}"
            for c in self.top_comments[:10]
        )
        if comments_text:
            parts.append(f"热门评论: {comments_text}")
        if self.subtitle_text:
            parts.append(f"字幕内容: {self.subtitle_text[:3000]}")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "video_id": self.video_id,
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "author_name": self.author_name,
            "author_id": self.author_id,
            "duration_seconds": self.duration_seconds,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "share_count": self.share_count,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "tags": self.tags,
            "hashtags": self.hashtags,
            "top_comments": self.top_comments,
            "music_title": self.music_title,
            "is_original": self.is_original,
            "thumbnail_url": self.thumbnail_url,
            "subtitles": self.subtitles,
            "subtitle_text": self.subtitle_text,
            "danmaku_count": self.danmaku_count,
            "text_content": self.to_text(),
        }


# =============================================================================
# URL 识别
# =============================================================================

def identify_video_platform(url: str) -> str | None:
    """识别视频URL的平台"""
    patterns = {
        "douyin": [r"douyin\.com", r"iesdouyin\.com", r"v\.douyin\.com"],
        "kuaishou": [r"kuaishou\.com", r"v\.kuaishou\.com", r"chengzijianzhan\.com"],
        "bilibili": [r"bilibili\.com", r"b23\.tv", r"bilivideo\.com"],
        "weibo_video": [r"weibo\.com/tv", r"video\.weibo\.com"],
        "youtube": [r"youtube\.com", r"youtu\.be"],
    }
    for platform, ps in patterns.items():
        for p in ps:
            if re.search(p, url, re.IGNORECASE):
                return platform
    return None


# =============================================================================
# 哔哩哔哩爬虫 (有公开API，最稳定)
# =============================================================================

class BilibiliCrawler:
    """
    B站视频信息爬虫 — 完整采集：元数据+字幕+评论+弹幕统计

    新增 wbi 签名支持，可采集需要登录权限的字幕数据。
    """

    BASE_URL = "https://api.bilibili.com/x/web-interface/view?bvid="
    COMMENTS_URL = "https://api.bilibili.com/x/v2/reply?type=1&oid={oid}&sort=2&pn=1&ps=10"
    WBI_INFO_URL = "https://api.bilibili.com/x/web-interface/nav"
    PLAYER_URL = "https://api.bilibili.com/x/player/v2"

    # wbi 密钥缓存
    _mixin_key: str = ""
    _wbi_img_url: str = ""
    _wbi_sub_url: str = ""
    _wbi_ts: float = 0.0

    @staticmethod
    def extract_bvid(url: str) -> str | None:
        for pattern in [r'/video/(BV[A-Za-z0-9]{10})', r'bvid=(BV[A-Za-z0-9]{10})',
                        r'bilibili\.com/(?:video/)?(av\d+)', r'b23\.tv/([A-Za-z0-9]+)']:
            m = re.search(pattern, url)
            if m:
                return m.group(1)
        return None

    @classmethod
    def _wbi_sign(cls, params: dict) -> dict:
        """对参数进行 wbi 签名 (简化版 mixin key + MD5)"""
        import hashlib, time

        if not cls._mixin_key or (time.time() - cls._wbi_ts) > 3600:
            # Key expired
            cls._mixin_key = "7cd084941338484aae1ad9425b84077c"  # B站公开的固定 mixin key
            cls._wbi_ts = time.time()

        # 添加 wts 时间戳
        params["wts"] = int(time.time())

        # 按键排序 + MD5(mixin_key)
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        query = "&".join(f"{k}={v}" for k, v in sorted_params)
        sign = hashlib.md5((query + cls._mixin_key[:32]).encode()).hexdigest()
        params["w_rid"] = sign
        return params

    @classmethod
    async def _fetch_wbi_keys(cls, client) -> bool:
        """从导航栏 API 获取 wbi 密钥"""
        try:
            resp = await client.get(
                cls.WBI_INFO_URL,
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"}
            )
            if resp.status_code == 200:
                data = resp.json()
                wbi_img = data.get("data", {}).get("wbi_img", {})
                if wbi_img:
                    img_url = wbi_img.get("img_url", "")
                    sub_url = wbi_img.get("sub_url", "")
                    if img_url:
                        # Extract key from URL path
                        from urllib.parse import urlparse
                        img_path = urlparse(img_url).path.split("/")[-1].replace(".png", "")
                        sub_path = urlparse(sub_url).path.split("/")[-1].replace(".png", "")
                        cls._mixin_key = (img_path + sub_path)[:32]
                        cls._wbi_ts = time.time()
                        return True
        except Exception:
            pass
        # Fallback to fixed mixin key
        cls._mixin_key = "7cd084941338484aae1ad9425b84077c"
        cls._wbi_ts = time.time()
        return True

    @with_retry(max_retries=2, base_delay=1.0)
    async def fetch(self, url: str) -> VideoInfo | None:
        """获取B站视频信息——完整版：元数据+字幕+评论"""
        bvid = self.extract_bvid(url)
        if not bvid:
            return None

        limiter = _rate_limiters["bilibili"]
        await limiter.wait()

        try:
            import httpx
            async with httpx.AsyncClient(timeout=20) as client:
                # 获取 wbi 密钥
                await self._fetch_wbi_keys(client)

                # Step 1: 获取视频基础信息
                params = {"bvid": bvid}
                params = self._wbi_sign(params)
                param_str = "&".join(f"{k}={v}" for k, v in params.items())

                resp = await client.get(
                    f"https://api.bilibili.com/x/web-interface/view?{param_str}",
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Referer": f"https://www.bilibili.com/video/{bvid}",
                        "Accept": "application/json",
                    }
                )
                if resp.status_code != 200:
                    return None

                data = resp.json()
                if data.get("code") != 0:
                    return None

                v = data.get("data", {})
                owner = v.get("owner", {})
                stat = v.get("stat", {})

                info = VideoInfo(
                    platform="bilibili",
                    video_id=bvid,
                    url=f"https://www.bilibili.com/video/{bvid}",
                    title=v.get("title", ""),
                    description=v.get("desc", ""),
                    author_name=owner.get("name", ""),
                    author_id=str(owner.get("mid", "")),
                    duration_seconds=int(v.get("duration", 0)),
                    view_count=int(stat.get("view", 0)),
                    like_count=int(stat.get("like", 0)),
                    comment_count=int(stat.get("reply", 0)),
                    share_count=int(stat.get("share", 0)),
                    published_at=datetime.fromtimestamp(int(v.get("pubdate", 0))) if v.get("pubdate") else None,
                    tags=[t.get("tag_name", "") for t in v.get("tags", [])[:10]] if v.get("tags") else [],
                    thumbnail_url=v.get("pic", ""),
                    is_original=v.get("copyright", 1) == 1,
                    danmaku_count=int(stat.get("danmaku", 0)),
                )

                # Step 2: 获取字幕/CC (使用 player v2 API + wbi)
                pages = v.get("pages", [])
                if pages:
                    cid = pages[0].get("cid", 0)
                    if cid:
                        try:
                            sub_params = self._wbi_sign({"bvid": bvid, "cid": cid})
                            sub_param_str = "&".join(f"{k}={v}" for k, v in sub_params.items())
                            sub_resp = await client.get(
                                f"{self.PLAYER_URL}?{sub_param_str}",
                                headers={
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                    "Referer": f"https://www.bilibili.com/video/{bvid}",
                                }
                            )
                            if sub_resp.status_code == 200:
                                sub_data = sub_resp.json()
                                subtitle_info = sub_data.get("data", {}).get("subtitle", {})
                                subs = subtitle_info.get("subtitles", [])

                                if subs:
                                    for sub in subs:
                                        sub_url = sub.get("subtitle_url", "")
                                        if sub_url:
                                            full_sub_url = "https:" + sub_url if sub_url.startswith("//") else sub_url
                                            try:
                                                sub_content = await client.get(full_sub_url, headers={
                                                    "User-Agent": "Mozilla/5.0",
                                                    "Referer": "https://www.bilibili.com/"
                                                })
                                                sub_json = sub_content.json()
                                                lines = sub_json.get("body", [])
                                                sub_lines = [
                                                    {"from": l.get("from", 0), "to": l.get("to", 0),
                                                     "content": l.get("content", "")}
                                                    for l in lines if l.get("content")
                                                ]
                                                info.subtitles.append({
                                                    "lang": sub.get("lan_doc", sub.get("lan", "unknown")),
                                                    "line_count": len(sub_lines),
                                                    "lines": sub_lines[:100],  # cap at 100
                                                })
                                                logger.info(f"[B站字幕] {bvid}: {len(sub_lines)} 行字幕")
                                            except Exception as se:
                                                logger.debug(f"[B站字幕] 获取失败: {se}")
                        except Exception:
                            pass  # 字幕非必须

                # 合并字幕文本
                all_sub_texts = []
                for s in info.subtitles:
                    for line in s.get("lines", []):
                        all_sub_texts.append(line.get("content", ""))
                info.subtitle_text = "\n".join(all_sub_texts[:200])  # cap at 200 lines

                # Step 3: 获取高赞评论
                try:
                    oid = v.get("aid") or v.get("id", 0)
                    comments_resp = await client.get(
                        self.COMMENTS_URL.format(oid=oid),
                        headers={
                            "User-Agent": "Mozilla/5.0",
                            "Referer": f"https://www.bilibili.com/video/{bvid}",
                        }
                    )
                    if comments_resp.status_code == 200:
                        c_data = comments_resp.json()
                        replies = c_data.get("data", {}).get("replies", [])
                        info.top_comments = [
                            {"text": r.get("content", {}).get("message", ""),
                             "likes": r.get("like", 0),
                             "author": r.get("member", {}).get("uname", ""),
                             "reply_count": r.get("rcount", 0)}
                            for r in replies[:10]
                        ]
                except Exception:
                    pass

                logger.info(
                    f"[B站] {info.title[:30]}... "
                    f"({info.view_count}播/{info.danmaku_count}弹幕/"
                    f"{len(info.subtitles)}字幕/{len(info.top_comments)}评)"
                )
                return info

        except Exception as e:
            logger.warning(f"[B站] 爬取失败: {e}")
            return None


# =============================================================================
# YouTube 爬虫 (使用 oEmbed API，无需 API Key)
# =============================================================================

class YouTubeCrawler:
    """YouTube 视频信息爬虫 — 使用 oEmbed 端点 (公开)"""

    OEMBED_URL = "https://www.youtube.com/oembed"
    INFO_URL = "https://www.youtube.com/watch"

    @staticmethod
    def extract_video_id(url: str) -> str | None:
        """从 YouTube URL 提取 video ID"""
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([A-Za-z0-9_-]{11})',
            r'youtube\.com/shorts/([A-Za-z0-9_-]{11})',
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                return m.group(1)
        return None

    @with_retry(max_retries=2, base_delay=1.5)
    async def fetch(self, url: str) -> VideoInfo | None:
        """获取YouTube视频信息"""
        video_id = self.extract_video_id(url)
        if not video_id:
            return None

        limiter = _rate_limiters["youtube"]
        await limiter.wait()

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                # 使用 oEmbed API 获取基础信息
                resp = await client.get(
                    self.OEMBED_URL,
                    params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
                    headers={"User-Agent": "Mozilla/5.0"}
                )

                if resp.status_code != 200:
                    # 回退: 从页面meta标签提取
                    return await self._parse_from_page(client, video_id, url)

                data = resp.json()
                title = data.get("title", "")
                author = data.get("author_name", "")
                author_url = data.get("author_url", "")

                # 从页面提取更多元数据
                page_info = await self._scrape_watch_page(client, video_id)
                if page_info:
                    title = page_info.get("title", title)
                    desc = page_info.get("description", "")
                    views = page_info.get("views", 0)
                    likes = page_info.get("likes", 0)
                    published = page_info.get("published_at")
                    tags = page_info.get("tags", [])
                else:
                    desc = ""
                    views = 0
                    likes = 0
                    published = None
                    tags = []

                info = VideoInfo(
                    platform="youtube",
                    video_id=video_id,
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    title=title,
                    description=desc[:1000] if desc else "",
                    author_name=author,
                    author_id=author_url.split("/")[-1] if "/" in author_url else author,
                    view_count=views,
                    like_count=likes,
                    published_at=published,
                    tags=tags,
                    thumbnail_url=f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                )

                logger.info(f"[YouTube] 获取视频: {info.title[:40]}... ({info.view_count}观看)")
                return info

        except Exception as e:
            logger.warning(f"[YouTube] oEmbed 失败: {e}")
            return None

    async def _parse_from_page(self, client, video_id: str, url: str) -> VideoInfo | None:
        """从 YouTube watch 页面 meta 标签提取信息"""
        try:
            resp = await client.get(
                f"https://www.youtube.com/watch?v={video_id}",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                         "Accept-Language": "zh-CN,zh;q=0.9"}
            )
            html = resp.text

            title = ""
            m = re.search(r'<meta\s+name="title"\s+content="([^"]+)"', html)
            if m: title = m.group(1)

            desc = ""
            m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
            if m: desc = m.group(1)

            author = ""
            m = re.search(r'"channelId":"([^"]+)"', html)
            channel_id = m.group(1) if m else ""
            m = re.search(r'"ownerChannelName":"([^"]+)"', html)
            if m: author = m.group(1)

            return VideoInfo(
                platform="youtube",
                video_id=video_id,
                url=f"https://www.youtube.com/watch?v={video_id}",
                title=title or "YouTube视频",
                description=desc or "",
                author_name=author,
                author_id=channel_id,
                thumbnail_url=f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
            )
        except Exception:
            return None

    async def _scrape_watch_page(self, client, video_id: str) -> dict | None:
        """爬取YouTube watch页面获取结构化数据 (ytInitialData)"""
        try:
            resp = await client.get(
                f"https://www.youtube.com/watch?v={video_id}",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                         "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"}
            )
            html = resp.text

            # 提取 ytInitialPlayerResponse 或 ytInitialData
            m = re.search(r'var\s+ytInitialPlayerResponse\s*=\s*({.+?});\s*var\s+', html, re.DOTALL)
            if not m:
                m = re.search(r'var\s+ytInitialPlayerResponse\s*=\s*({.+?});</script>', html, re.DOTALL)

            if not m:
                return None

            data = json.loads(m.group(1))

            video_details = data.get("videoDetails", {})
            microformat = data.get("microformat", {}).get("playerMicroformatRenderer", {})

            result = {
                "title": video_details.get("title", ""),
                "description": video_details.get("shortDescription", "") if video_details.get("shortDescription") else "",
                "views": int(video_details.get("viewCount", 0)),
                "likes": 0,
                "tags": video_details.get("keywords", []),
            }

            # 解析发布日期
            publish_str = microformat.get("publishDate", "")
            if publish_str:
                try:
                    result["published_at"] = datetime.fromisoformat(publish_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            return result

        except (json.JSONDecodeError, AttributeError) as e:
            logger.debug(f"[YouTube] 页面解析失败: {e}")
            return None
        except Exception as e:
            logger.warning(f"[YouTube] 页面爬取失败: {e}")
            return None


# =============================================================================
# 抖音爬虫 (使用公开的分享页解析)
# =============================================================================

class DouyinCrawler:
    """抖音视频信息爬虫 — 从分享链接解析"""

    @staticmethod
    def extract_video_id(url: str) -> str | None:
        """从抖音分享链接提取 video_id"""
        # 短链接: https://v.douyin.com/xxxx/
        m = re.search(r'(?:video|note)/(\d+)', url)
        if m:
            return m.group(1)
        return None

    @with_retry(max_retries=2, base_delay=1.5)
    async def fetch(self, url: str) -> VideoInfo | None:
        """获取抖音视频信息"""
        limiter = _rate_limiters["douyin"]
        await limiter.wait()

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                # 抖音短链接先跟随重定向获取长链接
                resp = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
                    }
                )

                # 从页面中提取 video_id 和 JSON 数据
                html = resp.text

                # 尝试从页面加载的数据中提取视频信息
                video_id = self.extract_video_id(str(resp.url))
                if not video_id:
                    # 从HTML提取
                    m = re.search(r'"aweme_id"\s*:\s*"(\d+)"', html)
                    if not m:
                        m = re.search(r'"video_id"\s*:\s*"(\d+)"', html)
                    if m:
                        video_id = m.group(1)

                if not video_id:
                    # 从 HTML meta 标签提取
                    m = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]+)"', html)
                    title = m.group(1)[:100] if m else "未获取到标题"
                    # 无法获取完整信息的回退
                    return VideoInfo(
                        platform="douyin",
                        video_id=hashlib.md5(url.encode()).hexdigest()[:12],
                        url=url,
                        title=title,
                        description=title,
                    )

                # 尝试调用 douyin API (可能被反爬)
                api_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}"
                api_resp = await client.get(
                    api_url,
                    headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)", "Referer": "https://www.douyin.com/"}
                )

                if api_resp.status_code == 200:
                    data = api_resp.json()
                    items = data.get("item_list", [])
                    if items:
                        item = items[0]
                        author = item.get("author", {})
                        stats = item.get("statistics", {})
                        music = item.get("music", {})

                        info = VideoInfo(
                            platform="douyin",
                            video_id=video_id,
                            url=url,
                            title=item.get("desc", "") or item.get("share_info", {}).get("share_title", ""),
                            description=item.get("desc", ""),
                            author_name=author.get("nickname", ""),
                            author_id=author.get("unique_id", ""),
                            duration_seconds=int(item.get("duration", 0)) // 1000,
                            view_count=int(stats.get("play_count", 0)),
                            like_count=int(stats.get("digg_count", 0)),
                            comment_count=int(stats.get("comment_count", 0)),
                            share_count=int(stats.get("share_count", 0)),
                            published_at=datetime.fromtimestamp(item.get("create_time", 0)) if item.get("create_time") else None,
                            tags=[],
                            hashtags=re.findall(r'#(\w+)', item.get("desc", "")),
                            music_title=music.get("title", ""),
                            thumbnail_url=item.get("video", {}).get("cover", {}).get("url_list", [""])[0],
                        )
                        logger.info(f"[抖音] 获取视频: {info.title[:30]}... ({info.view_count}播放)")
                        return info

        except Exception as e:
            logger.warning(f"[抖音] 爬取失败: {e}")

        # 回退: 至少从URL提取基本信息
        return VideoInfo(
            platform="douyin",
            video_id=hashlib.md5(url.encode()).hexdigest()[:12],
            url=url,
            title="抖音视频 (需进一步解析)",
            description="该链接指向抖音上的一个视频。详细信息需要平台的进一步访问。",
        )


# =============================================================================
# 快手爬虫
# =============================================================================

class KuaishouCrawler:
    """快手视频信息爬虫"""

    @with_retry(max_retries=2, base_delay=1.5)
    async def fetch(self, url: str) -> VideoInfo | None:
        """获取快手视频信息"""
        limiter = _rate_limiters["kuaishou"]
        await limiter.wait()

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(
                    url,
                    headers={"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"}
                )
                html = resp.text

                # 从 meta 标签提取
                title = ""
                m = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', html)
                if m:
                    title = m.group(1)

                desc = ""
                m = re.search(r'<meta[^>]*property="og:description"[^>]*content="([^"]+)"', html)
                if m:
                    desc = m.group(1)

                author = ""
                m = re.search(r'"userName"\s*:\s*"([^"]+)"', html)
                if m:
                    author = m.group(1)

                return VideoInfo(
                    platform="kuaishou",
                    video_id=hashlib.md5(url.encode()).hexdigest()[:12],
                    url=url,
                    title=title or "快手视频",
                    description=desc or title or "",
                    author_name=author or "",
                )

        except Exception as e:
            logger.warning(f"[快手] 爬取失败: {e}")

        return VideoInfo(
            platform="kuaishou",
            video_id=hashlib.md5(url.encode()).hexdigest()[:12],
            url=url,
            title="快手视频 (需进一步解析)",
            description="该链接指向快手上的一个视频。详细信息需要平台的进一步访问。",
        )


# =============================================================================
# 微博视频爬虫
# =============================================================================

class WeiboVideoCrawler:
    """微博视频信息爬虫 — 解析微博视频页面"""

    @staticmethod
    def extract_video_id(url: str) -> str | None:
        """从微博视频URL提取标识"""
        # https://weibo.com/tv/show/1034:xxxxx
        # https://video.weibo.com/show?fid=1034:xxxxx
        patterns = [
            r'(?:show/|fid=)(1034:\d+)',
            r'(?:tv/show|video/)(\d+:\w+)',
            r'weibo\.com/(\d+)/(\w+)',  # 直接微博URL
        ]
        for p in patterns:
            m = re.search(p, url)
            if m:
                return m.group(1)
        return hashlib.md5(url.encode()).hexdigest()[:12]

    @with_retry(max_retries=2, base_delay=1.0)
    async def fetch(self, url: str) -> VideoInfo | None:
        """获取微博视频信息"""
        limiter = _rate_limiters["weibo_video"]
        await limiter.wait()

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
                        "Referer": "https://weibo.com/",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    }
                )
                html = resp.text

                # 从页面 meta 标签提取
                title = ""
                m = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
                if not m:
                    m = re.search(r'<title>([^<]+)</title>', html)
                if m:
                    title = m.group(1).strip()

                desc = ""
                m = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html)
                if not m:
                    m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html)
                if m:
                    desc = m.group(1).strip()

                author = ""
                m = re.search(r'"screen_name"\s*:\s*"([^"]+)"', html)
                if not m:
                    m = re.search(r'"nickname"\s*:\s*"([^"]+)"', html)
                if not m:
                    m = re.search(r'<span\s+class="name"[^>]*>([^<]+)</span>', html)
                if m:
                    author = m.group(1)

                author_id = ""
                m = re.search(r'"uid"\s*:\s*"(\d+)"', html) or re.search(r'"idstr"\s*:\s*"(\d+)"', html)
                if m:
                    author_id = m.group(1)

                # 播放量
                views = 0
                m = re.search(r'(?:play_count|"play"\s*:\s*)"?(\d+)"?', html)
                if m:
                    views = int(m.group(1))

                # 发布时间
                published = None
                m = re.search(r'"created_at"\s*:\s*"([^"]+)"', html)
                if m:
                    try:
                        from datetime import timezone, timedelta
                        # 微博时间格式: "Wed Jun 10 15:30:00 +0800 2026"
                        published = datetime.strptime(m.group(1), "%a %b %d %H:%M:%S %z %Y")
                    except (ValueError, TypeError):
                        pass

                # 视频时长
                duration = 0
                m = re.search(r'"duration"\s*:\s*(\d+)', html)
                if m:
                    duration = int(m.group(1))

                video_id = self.extract_video_id(url)

                info = VideoInfo(
                    platform="weibo_video",
                    video_id=video_id,
                    url=url,
                    title=title or "微博视频",
                    description=desc or title or "",
                    author_name=author or "",
                    author_id=author_id or "",
                    duration_seconds=duration,
                    view_count=views,
                    published_at=published,
                    is_original=True,  # 无法确定
                )

                logger.info(f"[微博视频] 获取: {info.title[:40]}... (作者: {info.author_name})")
                return info

        except Exception as e:
            logger.warning(f"[微博视频] 爬取失败: {e}")

        return VideoInfo(
            platform="weibo_video",
            video_id=hashlib.md5(url.encode()).hexdigest()[:12],
            url=url,
            title="微博视频 (需进一步解析)",
            description="该链接指向微博上的一个视频。详细信息需要平台的进一步访问。",
        )


# =============================================================================
# 统一视频分析入口
# =============================================================================

async def analyze_video_url(url: str, use_cache: bool = True) -> dict | None:
    """
    统一视频分析: 识别平台 → 去重检查 → 爬取 → 文本 → 10引擎分析

    Args:
        url: 视频URL
        use_cache: 是否使用缓存（已分析过的相同内容跳过引擎分析）

    Returns: 包含 video_info + engine_analysis 的完整结果
    """
    platform = identify_video_platform(url)
    if not platform:
        return {
            "error": "不支持的视频平台",
            "url": url,
            "supported_platforms": ["bilibili", "douyin", "kuaishou", "weibo_video", "youtube"],
        }

    # 选择爬虫
    crawlers = {
        "bilibili": BilibiliCrawler(),
        "douyin": DouyinCrawler(),
        "kuaishou": KuaishouCrawler(),
        "youtube": YouTubeCrawler(),
        "weibo_video": WeiboVideoCrawler(),
    }
    crawler = crawlers.get(platform)
    if not crawler:
        return {"error": f"平台 {platform} 的爬虫尚未实现", "url": url}

    # Step 1: 爬取视频元数据
    video_info = await crawler.fetch(url)
    if not video_info:
        return {"error": "无法获取视频信息", "platform": platform, "url": url}

    # Step 1.5: 内容去重检查
    text_content = video_info.to_text()
    content_hash = compute_content_hash(text_content)

    if use_cache and content_hash in _content_hash_cache:
        logger.info(f"[缓存命中] {platform}/{video_info.video_id} 内容已分析过，使用缓存结果")
        cached = _content_hash_cache[content_hash].copy()
        cached["video_info"] = video_info.to_dict()
        cached["cached"] = True
        cached["cache_hit"] = True
        return cached

    # Step 2: 将文字内容送入引擎分析
    try:
        from app.engine.reasoning import run_reasoning_pipeline
        engine_result = await run_reasoning_pipeline(
            url=url,
            title=video_info.title,
            text=text_content,
            author=video_info.author_name,
            platform=platform,
        )

        result = {
            "video_info": video_info.to_dict(),
            "engine_analysis": engine_result.to_dict() if engine_result else None,
            "platform": platform,
            "content_hash": content_hash,
            "cached": False,
        }

        # 缓存分析结果
        if len(_content_hash_cache) > 500:
            # 简单的 LRU: 删除最旧的50个条目
            keys = list(_content_hash_cache.keys())[:50]
            for k in keys:
                del _content_hash_cache[k]
        _content_hash_cache[content_hash] = result

        return result

    except Exception as e:
        logger.error(f"视频分析引擎失败: {e}")
        return {
            "video_info": video_info.to_dict(),
            "engine_analysis": None,
            "platform": platform,
            "engine_error": str(e),
            "content_hash": content_hash,
            "cached": False,
        }


def clear_cache():
    """清空内容哈希缓存（用于调试或内存管理）"""
    _content_hash_cache.clear()
    logger.info(f"[缓存] 已清空内容哈希缓存")


def cache_stats() -> dict:
    """返回缓存统计信息"""
    return {
        "cached_entries": len(_content_hash_cache),
        "max_entries": 500,
    }


# =============================================================================
# API 端点 (注册到 video 路由)
# =============================================================================

async def create_video_trace_api(url: str):
    """供 API 端点调用的入口"""
    return await analyze_video_url(url)
