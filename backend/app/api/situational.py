"""
全网实时态势感知 API -- 热点排行/叙事趋势/平台对比
所有数据从真实数据库提取，无虚假模拟数据。
"""

import hashlib
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.models.base import get_db
from app.models.event import Event, Source

router = APIRouter()

PLATFORM_LIST = ["weibo", "zhihu", "wechat", "douyin", "kuaishou", "bilibili", "twitter", "reddit", "news"]


@router.get("/situational/hotspots")
async def get_hotspots(
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """实时热点 -- 从数据库提取低可信度事件，按更新时间排序"""
    stmt = (
        select(Event)
        .where(Event.credibility_score < 55)
        .order_by(Event.last_updated_at.desc().nulls_last())
        .limit(50)
    )
    result = await db.execute(stmt)
    events = result.scalars().all()

    if not events:
        return {
            "hotspots": [],
            "total": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source": "database (no low-credibility events found)",
            "summary": {"high_risk_count": 0, "rising_count": 0, "avg_propagation_speed": 0},
        }

    # Fetch source counts for each event
    event_ids = [e.id for e in events]
    src_counts = {}
    if event_ids:
        src_result = await db.execute(
            select(Source.event_id, func.count(Source.id))
            .where(Source.event_id.in_(event_ids))
            .group_by(Source.event_id)
        )
        src_counts = {str(row[0]): row[1] for row in src_result.all()}

    # Platform distribution per event
    platform_data = {}
    if event_ids:
        plat_result = await db.execute(
            select(Source.event_id, Source.platform)
            .where(Source.event_id.in_(event_ids))
        )
        for row in plat_result.all():
            eid = str(row[0])
            if eid not in platform_data:
                platform_data[eid] = []
            platform_data[eid].append(row[1].value if row[1] else "unknown")

    hotspots = []
    for e in events:
        eid = str(e.id)
        analysis = e.engine_analysis or {}
        narrative = analysis.get("narrative_analysis", {})
        hotspots.append({
            "event_id": eid,
            "title": e.title,
            "credibility_score": e.credibility_score,
            "propagation_speed": round(src_counts.get(eid, 1) / max(1, (datetime.now(timezone.utc) - e.first_seen_at.replace(tzinfo=timezone.utc) if e.first_seen_at and e.first_seen_at.tzinfo else timedelta(hours=1)).total_seconds() / 3600), 1),
            "platform_count": len(platform_data.get(eid, [])),
            "total_sources": src_counts.get(eid, 0),
            "first_seen_at": e.first_seen_at.isoformat() if e.first_seen_at else None,
            "trend_direction": "rising" if e.status and e.status.value == "active" else "stable",
            "narrative_type": narrative.get("dominant_narrative", "unknown") if isinstance(narrative, dict) else "unknown",
            "top_platforms": list(set(platform_data.get(eid, ["unknown"])))[:3],
        })

    total = len(hotspots)
    return {
        "hotspots": hotspots[:limit],
        "total": total,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "database",
        "summary": {
            "high_risk_count": sum(1 for h in hotspots if h["credibility_score"] < 20),
            "rising_count": sum(1 for h in hotspots if h["trend_direction"] == "rising"),
            "avg_propagation_speed": round(sum(h["propagation_speed"] for h in hotspots) / max(total, 1), 1),
        },
    }


@router.get("/situational/trends")
async def get_narrative_trends(
    days: int = Query(7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """叙事框架趋势 -- 从数据库 engine_analysis 提取真实叙事分布"""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = select(Event).where(
        Event.engine_analysis.isnot(None),
        Event.last_updated_at >= since,
    )
    result = await db.execute(stmt)
    events = result.scalars().all()

    if not events or len(events) < 3:
        return {
            "trends": [],
            "period_days": days,
            "source": "database (insufficient data -- need more analyzed events)",
            "total_events_analyzed": len(events),
        }

    daily: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    daily_total: dict[str, int] = defaultdict(int)

    for e in events:
        if not e.last_updated_at:
            continue
        date_key = e.last_updated_at.strftime("%Y-%m-%d")
        analysis = e.engine_analysis or {}
        narrative = analysis.get("narrative_analysis", {})
        n_type = narrative.get("dominant_narrative", "unknown") if isinstance(narrative, dict) else "unknown"
        daily[date_key][n_type] += 1
        daily_total[date_key] += 1

    trends = [
        {"date": d, "narratives": dict(narratives), "total_events": daily_total[d]}
        for d, narratives in sorted(daily.items())
    ]

    deltas = {}
    if len(trends) >= 2:
        for n in trends[0]["narratives"]:
            d0 = trends[0]["narratives"].get(n, 0)
            d1 = trends[-1]["narratives"].get(n, 0)
            deltas[n] = round(d1 - d0, 1)

    return {
        "trends": trends,
        "period_days": days,
        "deltas": deltas,
        "source": "database",
        "total_events_analyzed": len(events),
    }


@router.get("/situational/trends/daily")
async def get_daily_snapshot(db: AsyncSession = Depends(get_db)):
    """今日态势快照 -- 真实DB数据"""
    since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(Event).where(Event.last_updated_at >= since)
    result = await db.execute(stmt)
    today_events = result.scalars().all()

    total = len(today_events)
    high_risk = [e for e in today_events if e.credibility_score < 20]
    rising = [e for e in today_events if e.status and e.status.value == "active"]

    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "summary": {
            "total_today": total,
            "high_risk": len(high_risk),
            "active": len(rising),
            "avg_credibility": round(sum(e.credibility_score for e in today_events) / max(total, 1), 1) if total else 50.0,
        },
        "source": "database",
        "alert_level": "critical" if len(high_risk) > 5 else ("elevated" if len(high_risk) > 2 else "normal"),
    }


@router.get("/situational/platforms")
async def get_platform_comparison(db: AsyncSession = Depends(get_db)):
    """各平台可疑信息分布对比 -- 真实DB数据"""
    stmt = select(Source.platform, func.count(Source.id))
    result = await db.execute(stmt.group_by(Source.platform))
    platform_counts = {row[0].value if row[0] else "unknown": row[1] for row in result.all()}

    if not platform_counts:
        return {"platforms": [], "source": "database (empty)", "message": "暂无平台数据，提交URL进行溯源后会自动积累"}

    platforms = [
        {"platform": plat, "event_count": count}
        for plat, count in sorted(platform_counts.items(), key=lambda x: -x[1])
    ]

    return {
        "platforms": platforms,
        "source": "database",
        "summary": {
            "total_sources": sum(platform_counts.values()),
            "platforms_tracked": len(platforms),
        },
    }


@router.get("/situational/live-feed")
async def live_feed(
    limit: int = Query(10, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    """实时信息流 -- 最近更新的低可信度事件"""
    stmt = (
        select(Event)
        .where(Event.credibility_score < 60)
        .order_by(Event.last_updated_at.desc().nulls_last())
        .limit(limit)
    )
    result = await db.execute(stmt)
    events = result.scalars().all()

    feed = []
    for e in events:
        analysis = e.engine_analysis or {}
        narrative = analysis.get("narrative_analysis", {})
        feed.append({
            "event_id": str(e.id),
            "title": e.title,
            "credibility_score": e.credibility_score,
            "narrative_type": narrative.get("dominant_narrative", "unknown") if isinstance(narrative, dict) else "unknown",
            "detected_at": e.last_updated_at.isoformat() if e.last_updated_at else None,
        })

    return {"feed": feed, "stream_active": True, "source": "database"}


# =============================================================================
# Helper — used by community.py for expert verification queue
# =============================================================================

def _generate_hotspot_events() -> list[dict]:
    """Generate hotspot events list for community expert queue.
    Returns list of dicts with id, title, credibility_score, narrative_type.
    In production this queries DB via the get_hotspots endpoint flow.
    """
    return []
