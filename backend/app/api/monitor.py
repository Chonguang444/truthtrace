"""
实时监控 API — 热点趋势、叙事告警、手动触发监控

所有 GET 端点均为纯缓存读取（<10ms），不做实时爬取。
实时爬取仅由 POST /monitor/crawl 或 Celery Beat 定时任务触发。
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from app.auth.jwt import get_admin_user

router = APIRouter()

# 延迟导入避免模块初始化时的 I/O 开销
_scheduler = None


def _get_scheduler():
    global _scheduler
    if _scheduler is None:
        from app.monitor.hotspot_monitor import monitor_scheduler
        _scheduler = monitor_scheduler
    return _scheduler


@router.get("/monitor/hot")
async def get_hot_items(
    platform: str | None = Query(None),
    limit: int = Query(30, ge=1, le=100),
):
    """获取缓存的热点条目（<10ms，不触发实时爬取）"""
    sched = _get_scheduler()
    items = getattr(sched, '_cached_items', None) or []

    if platform:
        items = [i for i in items if i.platform == platform]

    return {
        "total": len(items),
        "platforms": list(set(i.platform for i in items)),
        "updated_at": sched.state.last_crawl_at.isoformat() if sched.state.last_crawl_at else None,
        "items": [i.to_dict() for i in items[:limit]],
        "cached": True,
    }


@router.post("/monitor/crawl")
async def trigger_monitor_crawl(current_user = Depends(get_admin_user)):
    """手动触发监控爬取（慢，需等待）"""
    sched = _get_scheduler()
    items = await sched.run_once()
    return {
        "status": "completed",
        "total_crawled": len(items),
        "total_analyzed": sched.state.total_analyzed,
        "alerts_count": len(sched.alert_manager.get_active_alerts()),
    }


@router.get("/monitor/alerts")
async def get_narrative_alerts():
    sched = _get_scheduler()
    alerts = sched.alert_manager.get_active_alerts()
    return {"alerts_count": len(alerts), "alerts": [a.to_dict() for a in alerts]}


@router.post("/monitor/alerts/{alert_id}/dismiss")
async def dismiss_alert(alert_id: str, current_user = Depends(get_admin_user)):
    sched = _get_scheduler()
    sched.alert_manager.dismiss_alert(alert_id)
    return {"status": "dismissed"}


@router.get("/monitor/status")
async def get_monitor_status():
    sched = _get_scheduler()
    state = sched.get_state()
    return {
        "is_running": state.is_running,
        "last_crawl_at": state.last_crawl_at.isoformat() if state.last_crawl_at else None,
        "total_crawled": state.total_crawled,
        "total_analyzed": state.total_analyzed,
        "active_alerts": state.alerts_count,
    }


@router.get("/monitor/narratives/summary")
async def get_narrative_summary():
    sched = _get_scheduler()
    items = getattr(sched, '_cached_items', None) or []
    if not items:
        return {"summary": [], "message": "暂无数据，请先触发监控爬取"}

    narratives: dict[str, int] = {}
    for item in items:
        if item.engine_analysis:
            na = item.engine_analysis.get("narrative_analysis", {})
            dominant = na.get("dominant_narrative")
            if dominant:
                narratives[dominant] = narratives.get(dominant, 0) + 1

    return {
        "total_items": len(items),
        "analyzed_items": sum(1 for i in items if i.engine_analysis),
        "narratives": [
            {"type": k, "count": v} for k, v in sorted(narratives.items(), key=lambda x: -x[1])
        ],
    }


@router.get("/monitor/trends")
async def get_monitor_trends(days: int = 7):
    """获取监控历史趋势数据 — 热点数量/平台活跃度/叙事变迁/平均可信度随时间变化"""
    from app.monitor.hotspot_monitor import monitor_scheduler
    from collections import defaultdict
    from datetime import datetime, timedelta, timezone

    # Load persisted items from SQLite
    persisted = monitor_scheduler._store.load_items(limit=500)
    cached = [item.to_dict() for item in monitor_scheduler._cached_items]

    all_items = persisted + [
        i for i in cached
        if not any(p.get("id") == i.get("id") for p in persisted)
    ]

    # Filter by date range
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days))
    filtered = []
    for item in all_items:
        crawled_at = item.get("crawled_at") or item.get("created_at") or ""
        if crawled_at:
            try:
                dt = datetime.fromisoformat(crawled_at) if isinstance(crawled_at, str) else crawled_at
                if dt.replace(tzinfo=None) >= cutoff.replace(tzinfo=None):
                    filtered.append(item)
            except (ValueError, TypeError):
                filtered.append(item)  # Keep if date parsing fails
        else:
            filtered.append(item)

    if not filtered:
        # Fallback to in-memory if no persisted data
        return {
            "trends": [], "platform_activity": {}, "narrative_timeline": [],
            "credibility_trend": [], "total_items": 0,
            "note": "暂无历史数据，请先触发监控爬取。持久化数据将在此展示。",
        }

    # 1. Hotspot count by day
    by_day: dict[str, int] = defaultdict(int)
    # 2. Platform activity by day
    platform_by_day: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    # 3. Narrative timeline
    narrative_by_day: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    # 4. Credibility trend
    credibility_by_day: dict[str, list[float]] = defaultdict(list)

    for item in filtered:
        crawled_at = item.get("crawled_at") or ""
        day = crawled_at[:10] if crawled_at else "unknown"

        by_day[day] += 1
        platform = item.get("platform", "unknown")
        platform_by_day[day][platform] += 1

        # Narrative
        engine = item.get("engine_analysis")
        if isinstance(engine, str):
            try:
                import json
                engine = json.loads(engine)
            except Exception:
                engine = None
        if isinstance(engine, dict):
            na = engine.get("narrative_analysis", {})
            dominant = na.get("dominant_narrative")
            if dominant:
                narrative_by_day[day][dominant] += 1
            credibility = engine.get("credibility_score")
            if credibility is not None:
                credibility_by_day[day].append(float(credibility))

    return {
        "trends": [
            {"date": d, "count": c}
            for d, c in sorted(by_day.items())
        ],
        "platform_activity": {
            d: dict(counts) for d, counts in sorted(platform_by_day.items())
        },
        "narrative_timeline": {
            d: dict(counts) for d, counts in sorted(narrative_by_day.items())
        },
        "credibility_trend": [
            {
                "date": d,
                "avg_credibility": round(sum(scores) / len(scores), 1),
                "sample_count": len(scores),
                "min": round(min(scores), 1),
                "max": round(max(scores), 1),
            }
            for d, scores in sorted(credibility_by_day.items())
            if scores
        ],
        "total_items": len(filtered),
        "date_range_days": days,
    }
