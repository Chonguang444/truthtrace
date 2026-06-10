"""
Celery Beat 定时任务 — 监控爬取/报表生成/清理
"""

from celery import shared_task
import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger("truthtrace.scheduled")


@shared_task(name="app.tasks.scheduled_tasks.crawl_and_analyze_hotspots")
def crawl_and_analyze_hotspots():
    """每15分钟：爬取热点并运行引擎分析"""
    from app.monitor.hotspot_monitor import monitor_scheduler
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        items = loop.run_until_complete(monitor_scheduler.run_once())
        analyzed = sum(1 for i in items if i.engine_analysis)
        alerts = len(monitor_scheduler.alert_manager.get_active_alerts())
        logger.info(f"[cron] 热点监控: 爬取{len(items)}条, 分析{analyzed}条, 活跃告警{alerts}条")
        return {"crawled": len(items), "analyzed": analyzed, "alerts": alerts}
    except Exception as e:
        logger.error(f"[cron] 热点监控失败: {e}")
        return {"error": str(e)}
    finally:
        loop.close()


@shared_task(name="app.tasks.scheduled_tasks.generate_narrative_report")
def generate_narrative_report():
    """每小时：生成当前叙事分布摘要"""
    from collections import Counter
    from app.models.event import Event
    from app.models.base import async_session_factory
    from sqlalchemy import select

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        async def _run():
            async with async_session_factory() as session:
                stmt = select(Event).where(Event.engine_analysis.isnot(None)).limit(200)
                result = await session.execute(stmt)
                events = result.scalars().all()

                narratives = Counter()
                verdicts = Counter()
                for ev in events:
                    analysis = ev.engine_analysis or {}
                    na = analysis.get("narrative_analysis", {})
                    dominant = na.get("dominant_narrative")
                    if dominant:
                        narratives[dominant] += 1
                    verdict = analysis.get("verdict")
                    if verdict:
                        verdicts[verdict] += 1

                return {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "events_analyzed": len(events),
                    "narratives": dict(narratives.most_common(10)),
                    "verdicts": dict(verdicts),
                }

        report = loop.run_until_complete(_run())
        logger.info(f"[cron] 叙事报告已生成: {report['events_analyzed']}个事件")
        return report
    except Exception as e:
        logger.error(f"[cron] 报表生成失败: {e}")
        return {"error": str(e)}
    finally:
        loop.close()


@shared_task(name="app.tasks.scheduled_tasks.cleanup_old_notifications")
def cleanup_old_notifications():
    """每天凌晨3:30：清理30天前的通知"""
    from app.notifications.notification_service import _notification_store
    cutoff = datetime.now(timezone.utc)
    cleaned = 0
    for user_id in list(_notification_store.keys()):
        before = len(_notification_store[user_id])
        _notification_store[user_id] = [
            n for n in _notification_store[user_id]
            if (cutoff - n.created_at).days < 30
        ]
        cleaned += before - len(_notification_store[user_id])
    logger.info(f"[cron] 清理完成: 移除{cleaned}条旧通知")
    return {"cleaned": cleaned}


@shared_task(name="app.tasks.scheduled_tasks.generate_weekly_report")
def generate_weekly_report():
    """每周一8:00：生成周报"""
    from datetime import timedelta
    from app.models.event import Event
    from app.models.base import async_session_factory
    from sqlalchemy import select

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        async def _run():
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            async with async_session_factory() as session:
                stmt = select(Event).where(Event.created_at >= week_ago)
                result = await session.execute(stmt)
                events = result.scalars().all()

                total = len(events)
                analyzed = sum(1 for e in events if e.engine_analysis)
                low_cred = sum(1 for e in events if e.credibility_score < 40)
                high_cred = sum(1 for e in events if e.credibility_score >= 70)

                return {
                    "period": f"{week_ago.strftime('%Y-%m-%d')} ~ {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
                    "total_new_events": total,
                    "analyzed_events": analyzed,
                    "low_credibility_events": low_cred,
                    "high_credibility_events": high_cred,
                    "rumor_rate": round(low_cred / max(1, total) * 100, 1),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }

        report = loop.run_until_complete(_run())
        logger.info(f"[cron] 周报已生成: {report}")
        return report
    except Exception as e:
        logger.error(f"[cron] 周报生成失败: {e}")
        return {"error": str(e)}
    finally:
        loop.close()
