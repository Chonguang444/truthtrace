"""
实时监控 API — 热点趋势、叙事告警、手动触发监控
"""

from fastapi import APIRouter, Query, HTTPException
from app.monitor.hotspot_monitor import monitor_scheduler

router = APIRouter()


@router.get("/monitor/hot")
async def get_hot_items(
    platform: str | None = Query(None, description="筛选平台: weibo/zhihu/baidu"),
    limit: int = Query(30, ge=1, le=100),
):
    """获取最新爬取的热点条目"""
    # 如果没有缓存数据，触发一次爬取
    items = await monitor_scheduler.crawler.crawl_all() if not hasattr(monitor_scheduler, '_cached_items') else []
    if not items:
        monitor_scheduler._cached_items = []

    # 平台筛选
    if platform:
        items = [i for i in items if i.platform == platform]

    return {
        "total": len(items),
        "platforms": list(set(i.platform for i in items)),
        "updated_at": monitor_scheduler.state.last_crawl_at.isoformat() if monitor_scheduler.state.last_crawl_at else None,
        "items": [i.to_dict() for i in items[:limit]],
    }


@router.post("/monitor/crawl")
async def trigger_monitor_crawl():
    """手动触发一次监控爬取+分析"""
    items = await monitor_scheduler.run_once()
    return {
        "status": "completed",
        "total_crawled": len(items),
        "total_analyzed": monitor_scheduler.state.total_analyzed,
        "alerts_count": len(monitor_scheduler.alert_manager.get_active_alerts()),
    }


@router.get("/monitor/alerts")
async def get_narrative_alerts():
    """获取活跃的叙事框架告警"""
    alerts = monitor_scheduler.alert_manager.get_active_alerts()
    return {
        "alerts_count": len(alerts),
        "alerts": [a.to_dict() for a in alerts],
    }


@router.post("/monitor/alerts/{alert_id}/dismiss")
async def dismiss_alert(alert_id: str):
    """关闭告警"""
    monitor_scheduler.alert_manager.dismiss_alert(alert_id)
    return {"status": "dismissed"}


@router.get("/monitor/status")
async def get_monitor_status():
    """获取监控系统状态"""
    state = monitor_scheduler.get_state()
    return {
        "is_running": state.is_running,
        "last_crawl_at": state.last_crawl_at.isoformat() if state.last_crawl_at else None,
        "total_crawled": state.total_crawled,
        "total_analyzed": state.total_analyzed,
        "active_alerts": state.alerts_count,
    }


@router.get("/monitor/narratives/summary")
async def get_narrative_summary():
    """获取爬取结果的叙事框架汇总统计"""
    items = getattr(monitor_scheduler, '_cached_items', [])
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
