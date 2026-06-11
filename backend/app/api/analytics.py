"""
辟谣效果追踪 & A/B 测试基础

追踪辟谣内容的传播效果，为优化辟谣策略提供数据支撑：
- 哪种语气(tone)的辟谣更容易被分享？
- 哪种格式(一句话/完整/三明治)更有效？
- 不同平台的辟谣效果差异？
"""

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, field_validator
from datetime import datetime, timezone
from collections import defaultdict

router = APIRouter()


# =============================================================================
# 请求模型
# =============================================================================

class DebunkViewEvent(BaseModel):
    event_id: str = ""
    tone: str = ""           # neutral / authoritative / empathetic / educational / concise
    format: str = ""         # short / full / sandwich
    url: str = ""            # page URL where viewed
    engine_version: str = ""

    @field_validator("tone")
    @classmethod
    def valid_tone(cls, v: str) -> str:
        return v if v in ("neutral", "authoritative", "empathetic", "educational", "concise") else ""


class DebunkCopyEvent(BaseModel):
    event_id: str = ""
    tone: str = ""
    format: str = ""
    section: str = ""        # short / wedge / narrative / bridge / sandwich / full


class DebunkShareEvent(BaseModel):
    event_id: str = ""
    tone: str = ""
    platform: str = ""       # weibo / twitter / wechat / copy


# =============================================================================
# 内存存储 (生产环境用 SQLite/PostgreSQL)
# =============================================================================

_views: list[dict] = []       # 最近 10000 条查看事件
_copies: list[dict] = []      # 复制事件
_shares: list[dict] = []      # 分享事件

MAX_EVENTS = 10000


def _record_event(store: list, event: dict):
    store.append(event)
    if len(store) > MAX_EVENTS:
        store[:] = store[-MAX_EVENTS//2:]


# =============================================================================
# 端点
# =============================================================================

@router.post("/analytics/debunk-view")
async def track_debunk_view(req: DebunkViewEvent, request: Request):
    """记录辟谣卡片被查看"""
    _record_event(_views, {
        **req.model_dump(),
        "client_ip": (request.client.host or "unknown")[:20],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"status": "recorded"}


@router.post("/analytics/debunk-copy")
async def track_debunk_copy(req: DebunkCopyEvent, request: Request):
    """记录辟谣文本被复制"""
    _record_event(_copies, {
        **req.model_dump(),
        "client_ip": (request.client.host or "unknown")[:20],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"status": "recorded"}


@router.post("/analytics/debunk-share")
async def track_debunk_share(req: DebunkShareEvent, request: Request):
    """记录辟谣内容被分享到平台"""
    _record_event(_shares, {
        **req.model_dump(),
        "client_ip": (request.client.host or "unknown")[:20],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"status": "recorded"}


@router.get("/analytics/debunk-stats")
async def get_debunk_stats(event_id: str = ""):
    """
    获取辟谣效果统计。

    返回:
    - 各语气(tone)的查看/复制/分享次数
    - 各格式(format)的使用统计
    - 各平台的分享分布
    """
    # 过滤
    views = [e for e in _views if not event_id or e["event_id"] == event_id]
    copies = [e for e in _copies if not event_id or e["event_id"] == event_id]
    shares = [e for e in _shares if not event_id or e["event_id"] == event_id]

    # 按语气统计
    tone_stats: dict[str, dict] = defaultdict(lambda: {"views": 0, "copies": 0, "shares": 0})
    for e in views:
        if e["tone"]:
            tone_stats[e["tone"]]["views"] += 1
    for e in copies:
        if e["tone"]:
            tone_stats[e["tone"]]["copies"] += 1
    for e in shares:
        if e["tone"]:
            tone_stats[e["tone"]]["shares"] += 1

    # 按格式统计
    format_stats: dict[str, int] = defaultdict(int)
    for e in views:
        if e["format"]:
            format_stats[e["format"]] += 1
    for e in copies:
        if e["format"]:
            format_stats[e["format"]] += 1
    for e in shares:
        if e.get("format"):
            format_stats[e["format"]] += 1

    # 分享平台分布
    platform_stats: dict[str, int] = defaultdict(int)
    for e in shares:
        if e["platform"]:
            platform_stats[e["platform"]] += 1

    # 计算转化率
    tone_conversion = {}
    for tone, stats in tone_stats.items():
        if stats["views"] > 0:
            tone_conversion[tone] = {
                "views": stats["views"],
                "copies": stats["copies"],
                "shares": stats["shares"],
                "copy_rate": round(stats["copies"] / stats["views"], 3),
                "share_rate": round(stats["shares"] / stats["views"], 3),
            }

    return {
        "total": {
            "views": len(views),
            "copies": len(copies),
            "shares": len(shares),
        },
        "by_tone": tone_conversion,
        "by_format": dict(format_stats),
        "by_platform": dict(platform_stats),
        "recent_events": {
            "views": len([e for e in _views if event_id]),
            "copies": len([e for e in _copies if event_id]),
            "shares": len([e for e in _shares if event_id]),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/analytics/debunk-ab-test")
async def get_ab_test_results(event_id: str = ""):
    """
    A/B 测试结果：对比不同语气策略的效果。

    返回每种语气的相对效果评分(0-100):
    - 基于 (分享率 × 0.5 + 复制率 × 0.3 + 查看数 × 0.2) 加权
    """
    views = [e for e in _views if not event_id or e["event_id"] == event_id]
    copies = [e for e in _copies if not event_id or e["event_id"] == event_id]
    shares = [e for e in _shares if not event_id or e["event_id"] == event_id]

    tone_scores: dict[str, dict] = defaultdict(lambda: {"views": 0, "copies": 0, "shares": 0})
    for e in views:
        if e["tone"]:
            tone_scores[e["tone"]]["views"] += 1
    for e in copies:
        if e["tone"]:
            tone_scores[e["tone"]]["copies"] += 1
    for e in shares:
        if e["tone"]:
            tone_scores[e["tone"]]["shares"] += 1

    max_views = max((s["views"] for s in tone_scores.values()), default=1)

    results = {}
    for tone, stats in tone_scores.items():
        v = stats["views"]
        c = stats["copies"]
        s = stats["shares"]
        share_rate = s / max(v, 1)
        copy_rate = c / max(v, 1)
        view_norm = v / max_views

        effectiveness = (share_rate * 50 + copy_rate * 30 + view_norm * 20)
        results[tone] = {
            "views": v,
            "copies": c,
            "shares": s,
            "share_rate": round(share_rate, 3),
            "copy_rate": round(copy_rate, 3),
            "effectiveness_score": round(min(100, effectiveness), 1),
        }

    # 排序
    sorted_results = dict(sorted(results.items(), key=lambda x: x[1]["effectiveness_score"], reverse=True))

    return {
        "ab_test_results": sorted_results,
        "sample_size": len(views),
        "recommendation": (
            f"最佳辟谣语气: {next(iter(sorted_results))}"
            if sorted_results else "数据不足，无法推荐"
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
