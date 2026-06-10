"""
实时监控 API — 热点趋势、叙事告警、手动触发监控

所有 GET 端点均为纯缓存读取（<10ms），不做实时爬取。
实时爬取仅由 POST /monitor/crawl 或 Celery Beat 定时任务触发。
"""

from fastapi import APIRouter, Query, HTTPException

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
async def trigger_monitor_crawl():
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
async def dismiss_alert(alert_id: str):
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
