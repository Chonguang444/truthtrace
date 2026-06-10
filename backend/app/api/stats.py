"""
仪表盘统计 API — 综合统计、事件趋势、辟谣概览、实时热点
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, desc, case
from datetime import datetime, timedelta, timezone

from app.models.base import get_db
from app.models.event import Event, Source, RumorReport, EventStatus, Platform

router = APIRouter()


# ---------------------------------------------------------------------------
# Dashboard 综合摘要 — 首页用
# ---------------------------------------------------------------------------

@router.get("/stats/dashboard")
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
):
    """
    仪表盘综合摘要 — 首页数据面板

    返回：
    - 全局统计 (事件/来源/辟谣总数、平均可信度)
    - 今日新增事件
    - 最近7天趋势
    - 最新热点事件 (top 5)
    - 辟谣判定分布
    - 平台分布 top 5
    - 可信度分布 (高/中/低)
    """
    now = datetime.now(timezone.utc)
    today = now.date()
    seven_days_ago = now - timedelta(days=7)

    # --- 全局统计 ---
    total_events = (await db.execute(select(func.count(Event.id)))).scalar() or 0
    total_sources = (await db.execute(select(func.count(Source.id)))).scalar() or 0
    total_rumors = (await db.execute(select(func.count(RumorReport.id)))).scalar() or 0
    avg_cred = (await db.execute(select(func.avg(Event.credibility_score)))).scalar() or 50.0

    # --- 今日新增 ---
    today_start = datetime(today.year, today.month, today.day)
    today_events = (
        await db.execute(
            select(func.count(Event.id)).where(Event.created_at >= today_start)
        )
    ).scalar() or 0

    today_traces = (
        await db.execute(
            select(func.count(Source.id)).where(Source.fetched_at >= today_start)
        )
    ).scalar() or 0

    # --- 最近7天趋势 ---
    trend_result = await db.execute(
        select(
            func.date(Event.created_at).label("day"),
            func.count(Event.id).label("cnt"),
        )
        .where(Event.created_at >= seven_days_ago)
        .group_by(text("day"))
        .order_by(text("day"))
    )
    trend = [
        {"date": str(row.day), "count": row.cnt}
        for row in trend_result.all()
    ]

    # --- 最新热点事件 (基于来源数量 + 可信度) ---
    hot_result = await db.execute(
        select(Event)
        .where(Event.last_updated_at >= seven_days_ago)
        .order_by(Event.credibility_score.desc(), Event.last_updated_at.desc().nulls_last())
        .limit(5)
    )
    hot_events = hot_result.scalars().all()

    # 获取每个热点事件的来源数量
    hot_with_counts = []
    for ev in hot_events:
        cnt = (
            await db.execute(
                select(func.count(Source.id)).where(Source.event_id == ev.id)
            )
        ).scalar() or 0
        hot_with_counts.append({
            "id": str(ev.id),
            "title": ev.title,
            "status": ev.status.value if ev.status else None,
            "credibility_score": ev.credibility_score,
            "source_count": cnt,
            "last_updated_at": ev.last_updated_at.isoformat() if ev.last_updated_at else None,
        })

    # --- 辟谣判定分布 ---
    verdict_result = await db.execute(
        select(RumorReport.verdict, func.count(RumorReport.id))
        .group_by(RumorReport.verdict)
    )
    verdicts = [
        {"verdict": v, "count": c}
        for v, c in verdict_result.all()
    ]

    # --- 平台分布 top 5 ---
    platform_result = await db.execute(
        select(Source.platform, func.count(Source.id).label("cnt"))
        .group_by(Source.platform)
        .order_by(desc(text("cnt")))
        .limit(5)
    )
    platforms = []
    total_pf = 0
    for pf, cnt in platform_result.all():
        platforms.append({
            "platform": pf.value if hasattr(pf, "value") else str(pf),
            "count": cnt,
        })
        total_pf += cnt
    for p in platforms:
        p["percentage"] = round(p["count"] / total_pf * 100, 1) if total_pf > 0 else 0

    # --- 可信度分布 ---
    cred_high = (
        await db.execute(select(func.count(Event.id)).where(Event.credibility_score >= 70))
    ).scalar() or 0
    cred_medium = (
        await db.execute(
            select(func.count(Event.id)).where(
                Event.credibility_score >= 40, Event.credibility_score < 70
            )
        )
    ).scalar() or 0
    cred_low = (
        await db.execute(select(func.count(Event.id)).where(Event.credibility_score < 40))
    ).scalar() or 0

    # --- 事件状态分布 ---
    status_result = await db.execute(
        select(Event.status, func.count(Event.id)).group_by(Event.status)
    )
    status_dist = [
        {"status": st.value if hasattr(st, "value") else str(st), "count": cnt}
        for st, cnt in status_result.all()
    ]

    return {
        "overview": {
            "total_events": total_events,
            "total_sources": total_sources,
            "total_rumor_reports": total_rumors,
            "avg_credibility": round(avg_cred, 1),
        },
        "today": {
            "new_events": today_events,
            "new_traces": today_traces,
        },
        "trend_7d": trend,
        "hot_events": hot_with_counts,
        "verdicts": verdicts,
        "platforms": platforms,
        "credibility_distribution": {
            "high": cred_high,
            "medium": cred_medium,
            "low": cred_low,
        },
        "status_distribution": status_dist,
        "updated_at": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# 基础统计端点
# ---------------------------------------------------------------------------

@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
):
    """仪表盘总览统计（精简版，向后兼容）"""
    total_events = (await db.execute(select(func.count(Event.id)))).scalar() or 0
    total_sources = (await db.execute(select(func.count(Source.id)))).scalar() or 0
    total_rumors = (await db.execute(select(func.count(RumorReport.id)))).scalar() or 0
    avg_cred = (await db.execute(select(func.avg(Event.credibility_score)))).scalar() or 50.0
    today = func.date(datetime.now(timezone.utc))
    today_events = (
        await db.execute(select(func.count(Event.id)).where(func.date(Event.created_at) == today))
    ).scalar() or 0

    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent = await db.execute(
        select(Event.created_at, Event.status).where(Event.created_at >= seven_days_ago)
    )
    daily: dict[str, int] = {}
    for created_at, _ in recent.all():
        day = created_at.strftime("%m-%d") if created_at else "unknown"
        daily[day] = daily.get(day, 0) + 1

    return {
        "total_events": total_events,
        "total_sources": total_sources,
        "total_rumor_reports": total_rumors,
        "avg_credibility": round(avg_cred, 1),
        "today_events": today_events,
        "recent_7d_trend": [
            {"date": k, "count": v} for k, v in sorted(daily.items())
        ],
    }


@router.get("/stats/platforms")
async def get_platform_distribution(
    db: AsyncSession = Depends(get_db),
):
    """平台来源分布统计"""
    result = await db.execute(
        select(Source.platform, func.count(Source.id))
        .group_by(Source.platform)
        .order_by(func.count(Source.id).desc())
    )
    rows = result.all()
    total = sum(c for _, c in rows)
    return {
        "total_sources": total,
        "platforms": [
            {
                "platform": p.value if hasattr(p, "value") else str(p),
                "count": c,
                "percentage": round(c / total * 100, 1) if total > 0 else 0,
            }
            for p, c in rows
        ],
    }


@router.get("/stats/rumors")
async def get_rumor_stats(
    db: AsyncSession = Depends(get_db),
):
    """辟谣统计"""
    verdict_result = await db.execute(
        select(RumorReport.verdict, func.count(RumorReport.id))
        .group_by(RumorReport.verdict)
    )
    verdicts = verdict_result.all()
    total = sum(c for _, c in verdicts)
    return {
        "total_rumors": total,
        "verdicts": [
            {"verdict": v, "count": c, "percentage": round(c / total * 100, 1) if total > 0 else 0}
            for v, c in verdicts
        ],
    }


@router.get("/stats/credibility")
async def get_credibility_distribution(
    db: AsyncSession = Depends(get_db),
):
    """可信度评分分布"""
    high = (await db.execute(
        select(func.count(Event.id)).where(Event.credibility_score >= 70)
    )).scalar() or 0
    medium = (await db.execute(
        select(func.count(Event.id)).where(
            Event.credibility_score >= 40, Event.credibility_score < 70
        )
    )).scalar() or 0
    low = (await db.execute(
        select(func.count(Event.id)).where(Event.credibility_score < 40)
    )).scalar() or 0
    return {
        "high_credibility": high,
        "medium_credibility": medium,
        "low_credibility": low,
    }


@router.get("/stats/trending")
async def get_trending_events(
    hours: int = Query(24, ge=1, le=168, description="最近 N 小时"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    热门/趋势事件

    基于最近 N 小时内的活跃度（来源数×0.6 + 可信度×0.4）综合排序。
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    subq = (
        select(
            Event.id,
            func.count(Source.id).label("source_count"),
        )
        .outerjoin(Source, Source.event_id == Event.id)
        .where(Event.last_updated_at >= since)
        .group_by(Event.id)
        .subquery()
    )

    stmt = (
        select(
            Event,
            subq.c.source_count,
            (subq.c.source_count * 0.6 + Event.credibility_score * 0.4).label("hotness"),
        )
        .join(subq, Event.id == subq.c.id)
        .order_by(desc(text("hotness")))
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return {
        "hours": hours,
        "events": [
            {
                "id": str(row[0].id),
                "title": row[0].title,
                "summary": row[0].summary,
                "status": row[0].status.value if row[0].status else None,
                "credibility_score": row[0].credibility_score,
                "source_count": row[1],
                "hotness_score": round(row[2], 1),
                "last_updated_at": row[0].last_updated_at.isoformat() if row[0].last_updated_at else None,
            }
            for row in rows
        ],
    }
