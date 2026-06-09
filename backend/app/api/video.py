"""
视频平台分析 API — 抖音/快手/B站视频溯源分析
"""

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from app.crawler.video_platforms import analyze_video_url, identify_video_platform

router = APIRouter()


class VideoTraceRequest(BaseModel):
    url: str
    deep_trace: bool = False


@router.post("/video/analyze")
async def analyze_video(req: VideoTraceRequest):
    """提交视频链接进行溯源分析"""
    platform = identify_video_platform(req.url)
    if not platform:
        raise HTTPException(400, f"不支持的视频平台。支持的: bilibili, douyin, kuaishou, weibo_video, youtube")
    result = await analyze_video_url(req.url)
    return result


@router.get("/video/detect")
async def detect_platform(url: str = Query(..., description="视频 URL")):
    """检测视频URL的平台类型"""
    platform = identify_video_platform(url)
    return {
        "url": url,
        "platform": platform,
        "supported": platform is not None,
    }
