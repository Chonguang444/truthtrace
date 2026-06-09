"""
Celery 应用配置 + Beat 定时任务调度
"""

from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "truthtrace",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # =========================================================================
    # Beat 定时调度
    # =========================================================================
    beat_schedule={
        # 每15分钟爬取热点并分析
        "monitor-crawl-hotspots": {
            "task": "app.tasks.scheduled_tasks.crawl_and_analyze_hotspots",
            "schedule": crontab(minute="*/15"),
            "options": {"expires": 840},  # 14分钟后过期
        },
        # 每小时生成叙事趋势报告
        "report-narrative-summary": {
            "task": "app.tasks.scheduled_tasks.generate_narrative_report",
            "schedule": crontab(minute="0", hour="*/1"),
            "options": {"expires": 3540},
        },
        # 每天凌晨清理旧通知
        "clean-old-notifications": {
            "task": "app.tasks.scheduled_tasks.cleanup_old_notifications",
            "schedule": crontab(minute="30", hour="3"),
            "options": {"expires": 600},
        },
        # 每周一生成周报
        "weekly-report": {
            "task": "app.tasks.scheduled_tasks.generate_weekly_report",
            "schedule": crontab(minute="0", hour="8", day_of_week="1"),
            "options": {"expires": 3600},
        },
    },
)
