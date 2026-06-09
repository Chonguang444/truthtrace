"""
数据统计报表 API — 叙事趋势/辟谣效果/仪表盘图表/定时报表
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from datetime import datetime, timedelta
from collections import Counter

from app.models.base import get_db
from app.models.event import Event, Source, RumorReport, Platform

router = APIRouter()


@router.get("/reporting/narrative-trends")
async def narrative_trends(
    days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    """叙事框架趋势 — 过去N天内各叙事的出现频率"""
    since = datetime.utcnow() - timedelta(days=days)
    stmt = select(Event).where(
        Event.engine_analysis.isnot(None),
        Event.created_at >= since,
    ).order_by(Event.created_at.desc()).limit(500)
    result = await db.execute(stmt)
    events = result.scalars().all()

    # 按天 + 按叙事类型聚合
    daily_narratives: dict[str, Counter] = {}  # "2026-01-15" → Counter{narrative: count}
    total_narratives = Counter()

    for ev in events:
        day = ev.created_at.strftime("%Y-%m-%d") if ev.created_at else "unknown"
        analysis = ev.engine_analysis or {}
        dominant = analysis.get("narrative_analysis", {}).get("dominant_narrative")
        if dominant:
            if day not in daily_narratives:
                daily_narratives[day] = Counter()
            daily_narratives[day][dominant] += 1
            total_narratives[dominant] += 1

    return {
        "period_days": days,
        "total_events_analyzed": len(events),
        "top_narratives": [
            {"type": k, "count": v}
            for k, v in total_narratives.most_common(12)
        ],
        "daily_trends": [
            {"date": day, "narratives": dict(counter)}
            for day, counter in sorted(daily_narratives.items())
        ],
    }


@router.get("/reporting/verdict-distribution")
async def verdict_distribution(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """判定分布 — 过去N天的引擎判定统计"""
    since = datetime.utcnow() - timedelta(days=days)
    stmt = select(Event).where(
        Event.engine_analysis.isnot(None),
        Event.created_at >= since,
    )
    result = await db.execute(stmt)
    events = result.scalars().all()

    verdicts = Counter()
    daily: dict[str, Counter] = {}
    for ev in events:
        analysis = ev.engine_analysis or {}
        v = analysis.get("verdict", "unknown")
        verdicts[v] += 1
        day = ev.created_at.strftime("%Y-%m-%d") if ev.created_at else "unknown"
        if day not in daily:
            daily[day] = Counter()
        daily[day][v] += 1

    total = len(events)
    return {
        "period_days": days,
        "total": total,
        "distribution": [
            {"verdict": k, "count": v, "percentage": round(v / max(1, total) * 100, 1)}
            for k, v in verdicts.most_common()
        ],
        "daily_trends": [
            {"date": d, "verdicts": dict(c)}
            for d, c in sorted(daily.items())
        ],
    }


@router.get("/reporting/platform-stats")
async def platform_stats(db: AsyncSession = Depends(get_db)):
    """来源平台统计 + 各平台的可信度均值"""
    result = await db.execute(
        select(Source.platform, func.count(Source.id), func.avg(Source.authority_score))
        .group_by(Source.platform)
    )
    rows = result.all()

    total = sum(c for _, c, _ in rows)
    return {
        "total_sources": total,
        "platforms": [
            {
                "platform": p.value if hasattr(p, "value") else str(p),
                "count": c,
                "percentage": round(c / max(1, total) * 100, 1),
                "avg_authority_score": round(avg or 0, 1),
            }
            for p, c, avg in sorted(rows, key=lambda x: -x[1])
        ],
    }


@router.get("/reporting/credibility-timeline")
async def credibility_timeline(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """可信度评分时间线 — 过去N天的每日平均可信度"""
    since = datetime.utcnow() - timedelta(days=days)
    stmt = select(Event).where(Event.created_at >= since).order_by(Event.created_at.asc())
    result = await db.execute(stmt)
    events = result.scalars().all()

    daily_scores: dict[str, list[float]] = {}
    for ev in events:
        day = ev.created_at.strftime("%Y-%m-%d") if ev.created_at else "unknown"
        if day not in daily_scores:
            daily_scores[day] = []
        daily_scores[day].append(float(ev.credibility_score))

    return {
        "period_days": days,
        "timeline": [
            {
                "date": day,
                "avg_score": round(sum(scores) / len(scores), 1),
                "min_score": round(min(scores), 1),
                "max_score": round(max(scores), 1),
                "count": len(scores),
            }
            for day, scores in sorted(daily_scores.items())
        ],
    }


@router.get("/reporting/debunk-effectiveness")
async def debunk_effectiveness(db: AsyncSession = Depends(get_db)):
    """辟谣效果 — 已辟谣 vs 未辟谣事件的可信度分布"""
    # 有辟谣报告的事件
    stmt_rumored = select(Event).where(
        Event.rumor_report.has(),
        Event.engine_analysis.isnot(None),
    )
    result = await db.execute(stmt_rumored)
    rumored = result.scalars().all()

    # 无辟谣报告但有分析的事件
    stmt_no_rumor = select(Event).where(
        ~Event.rumor_report.has(),
        Event.engine_analysis.isnot(None),
    )
    result = await db.execute(stmt_no_rumor)
    no_rumor = result.scalars().all()

    return {
        "with_rumor_report": {
            "count": len(rumored),
            "avg_credibility": round(
                sum(e.credibility_score for e in rumored) / max(1, len(rumored)), 1
            ),
        },
        "without_rumor_report": {
            "count": len(no_rumor),
            "avg_credibility": round(
                sum(e.credibility_score for e in no_rumor) / max(1, len(no_rumor)), 1
            ),
        },
        "note": "辟谣报告的发布是识别谣言后的后续动作——有辟谣报告的事件可信度低是预期的、正确的。此指标追踪的是辟谣覆盖率。",
    }
