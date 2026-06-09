"""
视频平台爬虫 — 抖音/快手/哔哩哔哩

支持:
1. 从视频URL提取标题/描述/文字内容
2. 视频元数据提取 (时长/发布时间/作者/播放量)
3. 评论采集 (高赞评论)
4. 将文字内容送入10引擎推理分析

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
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional
import hashlib

logger = logging.getLogger("truthtrace.video")


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
    """B站视频信息爬虫 — 使用公开API"""

    BASE_URL = "https://api.bilibili.com/x/web-interface/view?bvid="
    COMMENTS_URL = "https://api.bilibili.com/x/v2/reply?type=1&oid={oid}&sort=2&pn=1&ps=10"

    @staticmethod
    def extract_bvid(url: str) -> str | None:
        """从URL提取 BV号"""
        for pattern in [r'/video/(BV[A-Za-z0-9]{10})', r'bvid=(BV[A-Za-z0-9]{10})']:
            m = re.search(pattern, url)
            if m:
                return m.group(1)
        return None

    async def fetch(self, url: str) -> VideoInfo | None:
        """获取B站视频信息"""
        bvid = self.extract_bvid(url)
        if not bvid:
            return None

        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                # 获取视频基础信息
                resp = await client.get(
                    self.BASE_URL + bvid,
                    headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"}
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
                    url=url,
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
                    tags=[],  # B站用标签系统，需要额外API
                    thumbnail_url=v.get("pic", ""),
                    is_original=v.get("copyright", 1) == 1,
                )

                # 获取高赞评论
                try:
                    oid = v.get("aid") or v.get("id", 0)
                    comments_resp = await client.get(
                        self.COMMENTS_URL.format(oid=oid),
                        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"}
                    )
                    if comments_resp.status_code == 200:
                        c_data = comments_resp.json()
                        replies = c_data.get("data", {}).get("replies", [])
                        info.top_comments = [
                            {"text": r.get("content", {}).get("message", ""),
                             "likes": r.get("like", 0),
                             "author": r.get("member", {}).get("uname", "")}
                            for r in replies[:10]
                        ]
                except Exception:
                    pass  # 评论非必须

                logger.info(f"[B站] 获取视频: {info.title[:30]}... ({info.view_count}播放)")
                return info

        except Exception as e:
            logger.warning(f"[B站] 爬取失败: {e}")
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

    async def fetch(self, url: str) -> VideoInfo | None:
        """获取抖音视频信息"""
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

    async def fetch(self, url: str) -> VideoInfo | None:
        """获取快手视频信息"""
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
# 统一视频分析入口
# =============================================================================

async def analyze_video_url(url: str) -> dict | None:
    """
    统一视频分析: 识别平台 → 爬取 → 文本 → 10引擎分析

    Returns: 包含 video_info + engine_analysis 的完整结果
    """
    platform = identify_video_platform(url)
    if not platform:
        return {"error": "不支持的视频平台", "url": url, "supported_platforms": ["bilibili", "douyin", "kuaishou", "weibo_video", "youtube"]}

    # 选择爬虫
    crawlers = {
        "bilibili": BilibiliCrawler(),
        "douyin": DouyinCrawler(),
        "kuaishou": KuaishouCrawler(),
    }
    crawler = crawlers.get(platform)
    if not crawler:
        return {"error": f"平台 {platform} 的爬虫尚未实现", "url": url}

    # Step 1: 爬取视频元数据
    video_info = await crawler.fetch(url)
    if not video_info:
        return {"error": "无法获取视频信息", "platform": platform, "url": url}

    # Step 2: 将文字内容送入引擎分析
    text_content = video_info.to_text()

    try:
        from app.engine.reasoning import run_reasoning_pipeline
        engine_result = await run_reasoning_pipeline(
            url=url,
            title=video_info.title,
            text=text_content,
            author=video_info.author_name,
            platform=platform,
        )

        return {
            "video_info": video_info.to_dict(),
            "engine_analysis": engine_result.to_dict(),
            "platform": platform,
        }
    except Exception as e:
        logger.error(f"视频分析引擎失败: {e}")
        return {
            "video_info": video_info.to_dict(),
            "engine_analysis": None,
            "platform": platform,
            "engine_error": str(e),
        }


# =============================================================================
# API 端点 (注册到 video 路由)
# =============================================================================

async def create_video_trace_api(url: str):
    """供 API 端点调用的入口"""
    return await analyze_video_url(url)
