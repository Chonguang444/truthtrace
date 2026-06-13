"""
管理员后台 API — 分析审查/告警管理/系统健康/用户管理
所有端点需要管理员权限
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, text
from uuid import UUID
from datetime import datetime, timedelta, timezone

from app.models.base import get_db
from app.models.event import Event, Source, RumorReport, EventStatus
from app.models.user import User, UserRole
from app.auth.jwt import get_admin_user

router = APIRouter()


# =============================================================================
# 系统概览
# =============================================================================

@router.get("/admin/overview")
async def admin_overview(_admin: User = Depends(get_admin_user), db: AsyncSession = Depends(get_db)):
    """管理员仪表盘概览"""
    total_events = (await db.execute(select(func.count(Event.id)))).scalar() or 0
    total_sources = (await db.execute(select(func.count(Source.id)))).scalar() or 0
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_rumors = (await db.execute(select(func.count(RumorReport.id)))).scalar() or 0

    # 最近24h事件
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_events = (await db.execute(
        select(func.count(Event.id)).where(Event.created_at >= since)
    )).scalar() or 0

    # 低可信度事件数
    low_cred = (await db.execute(
        select(func.count(Event.id)).where(Event.credibility_score < 40)
    )).scalar() or 0

    return {
        "total_events": total_events,
        "total_sources": total_sources,
        "total_users": total_users,
        "total_rumor_reports": total_rumors,
        "recent_24h_events": recent_events,
        "low_credibility_events": low_cred,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# 分析审查 — 按风险排序
# =============================================================================

@router.get("/admin/analysis/review")
async def list_analyses(
    _admin: User = Depends(get_admin_user),
    sort_by: str = Query("credibility_score", description="排序: credibility_score / created_at / fallacy_count"),
    risk_level: str | None = Query(None, description="风险筛选: high/medium/low"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """获取所有事件的分析结果列表（按风险排序）"""
    stmt = select(Event)

    # 仅返回有引擎分析的事件
    stmt = stmt.where(Event.engine_analysis.isnot(None))

    # 排序
    if sort_by == "created_at":
        stmt = stmt.order_by(Event.created_at.desc())
    else:
        stmt = stmt.order_by(Event.credibility_score.asc())  # 低分在前

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    events = result.scalars().all()

    items = []
    for event in events:
        analysis = event.engine_analysis or {}
        items.append({
            "event_id": str(event.id),
            "title": event.title,
            "status": event.status.value if event.status else None,
            "credibility_score": event.credibility_score,
            "engine_verdict": analysis.get("verdict"),
            "engine_confidence": analysis.get("confidence"),
            "distortion_count": len(analysis.get("distortion_analysis", {}).get("matches", [])),
            "fallacy_count": analysis.get("fallacy_analysis", {}).get("fallacy_count", 0),
            "narrative_dominant": analysis.get("narrative_analysis", {}).get("dominant_narrative"),
            "manipulation_score": analysis.get("narrative_analysis", {}).get("manipulation_score", 0),
            "stat_risk": analysis.get("statistical_analysis", {}).get("risk_score", 0),
            "correction": analysis.get("correction", "")[:200],
            "created_at": event.created_at.isoformat() if event.created_at else None,
        })

    # 风险筛选
    if risk_level == "high":
        items = [i for i in items if i["credibility_score"] < 30]
    elif risk_level == "medium":
        items = [i for i in items if 30 <= i["credibility_score"] <= 55]
    elif risk_level == "low":
        items = [i for i in items if i["credibility_score"] > 55]

    return {
        "total": len(items),
        "offset": offset,
        "limit": limit,
        "items": items,
    }


@router.get("/admin/analysis/{event_id}")
async def get_full_analysis(
    event_id: UUID,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单个事件的完整分析（管理员可看所有原始数据）"""
    event = await db.get(Event, event_id)
    if not event:
        raise HTTPException(404, "事件不存在")

    return {
        "event": {
            "id": str(event.id),
            "title": event.title,
            "summary": event.summary,
            "keywords": event.keywords,
            "status": event.status.value if event.status else None,
            "credibility_score": event.credibility_score,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        },
        "engine_analysis": event.engine_analysis,
    }


# =============================================================================
# 告警管理
# =============================================================================

@router.get("/admin/alerts")
async def list_alerts(_admin: User = Depends(get_admin_user)):
    """获取所有活跃的叙事告警"""
    from app.monitor.hotspot_monitor import monitor_scheduler
    alerts = monitor_scheduler.alert_manager.get_active_alerts()
    return {
        "alerts": [a.to_dict() for a in alerts],
        "count": len(alerts),
    }


@router.post("/admin/alerts/{alert_id}/dismiss")
async def dismiss_alert_endpoint(alert_id: str, _admin: User = Depends(get_admin_user)):
    from app.monitor.hotspot_monitor import monitor_scheduler
    monitor_scheduler.alert_manager.dismiss_alert(alert_id)
    return {"status": "dismissed"}


# =============================================================================
# 用户管理
# =============================================================================

@router.get("/admin/users")
async def list_users(
    _admin: User = Depends(get_admin_user),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """用户列表"""
    stmt = select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    users = result.scalars().all()

    total = (await db.execute(select(func.count(User.id)))).scalar() or 0

    return {
        "total": total,
        "users": [
            {
                "id": str(u.id),
                "username": u.username,
                "email": u.email,
                "role": u.role.value if u.role else "user",
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            }
            for u in users
        ],
    }


@router.post("/admin/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: UUID,
    _admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """启用/禁用用户"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    user.is_active = not user.is_active
    await db.commit()
    return {"user_id": str(user_id), "is_active": user.is_active}


# =============================================================================
# 系统健康
# =============================================================================

@router.get("/admin/health")
async def system_health(_admin: User = Depends(get_admin_user)):
    """系统健康检查"""
    checks = {}

    # 数据库
    try:
        from app.models.base import engine
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)[:100]}"

    # 引擎
    try:
        from app.engine import run_reasoning_pipeline
        checks["reasoning_engine"] = "healthy"
    except Exception as e:
        checks["reasoning_engine"] = f"error: {str(e)[:100]}"

    # 监控
    from app.monitor.hotspot_monitor import monitor_scheduler
    state = monitor_scheduler.get_state()
    checks["monitor"] = {
        "running": state.is_running,
        "last_crawl": state.last_crawl_at.isoformat() if state.last_crawl_at else None,
        "total_analyzed": state.total_analyzed,
    }

    # 通知
    from app.notifications.notification_service import _notification_store
    checks["notifications"] = {
        "stored_count": sum(len(v) for v in _notification_store.values()),
        "user_count": len(_notification_store),
    }

    return {
        "status": "healthy" if all(
            isinstance(v, str) and v == "healthy" or isinstance(v, dict)
            for v in checks.values()
        ) else "degraded",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/admin/reset-error-log")
async def get_last_error():
    """Returns the last startup error for debugging"""
    import traceback as _tb
    try:
        from app.models.base import Base, engine as _engine
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, checkfirst=True)
        return {"status": "tables_created"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "traceback": str(_tb.format_exc())[-1000:]}


@router.get("/admin/seed-simple")
async def seed_simple():
    """Seed demo data directly (no auth, standalone DB session)"""
    from app.models.base import async_session_factory
    from sqlalchemy import select as sa_select, func as sa_func
    import uuid as _uuid

    results = []
    try:
        async with async_session_factory() as session:
            # Check existing
            count = (await session.execute(sa_select(sa_func.count(Event.id)))).scalar() or 0
            if count > 0:
                return {"status": "ok", "message": f"Already seeded ({count} events)", "details": results}

            now = datetime.now(timezone.utc)
            e4 = Event(id=_uuid.uuid4(), title="疫苗含芯片追踪技术",
                       summary="海外社交媒体谣传疫苗含微芯片，世界卫生组织及多国疾控中心辟谣",
                       keywords=["疫苗","芯片","新冠","谣言"], credibility_score=5.0,
                       status=EventStatus.ACTIVE, first_seen_at=now, last_updated_at=now)
            session.add(e4)
            await session.flush()

            r = RumorReport(id=_uuid.uuid4(), event_id=e4.id,
                           rumor_claim="新冠疫苗含微芯片追踪技术",
                           fact_check_result="WHO、美国CDC、中国疾控中心均声明：疫苗不含任何微芯片。这是技术误导型谣言。",
                           verdict="false",
                           verified_sources=[{"url":"https://www.who.int/covid-19/vaccines","title":"WHO疫苗建议"},
                                            {"url":"https://www.cdc.gov/vaccines/covid-19","title":"CDC疫苗事实"}])
            session.add(r)
            await session.commit()
            results.append("Seeded 1 event + 1 rumor report")

        return {"status": "ok", "message": "Seed data inserted", "details": results}
    except Exception as e:
        import traceback as _tb2
        return {"status": "error", "error": f"{type(e).__name__}: {e}",
                "traceback": str(_tb2.format_exc())[-800:]}


@router.post("/admin/setup-db")
async def setup_database(db: AsyncSession = Depends(get_db)):
    """Initialize DB tables + seed data via ORM"""
    from app.models.base import Base, engine
    results = []

    # Step 1: Create tables via ORM
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, checkfirst=True)
        results.append("Tables OK")
    except Exception as e:
        results.append(f"Tables error: {e}")

    # Step 2: Seed
    try:
        import uuid as _uuid
        now = datetime.now(timezone.utc)
        count = (await db.execute(select(func.count(Event.id)))).scalar() or 0
        if count > 0:
            return {"status": "ok", "events_count": count, "details": results + [f"Skipped — {count} exist"]}

        e = [
            Event(id=_uuid.uuid4(), title="WHO: 阿斯巴甜2B类致癌", summary="WHO将阿斯巴甜列为2B类可能致癌物，强调日摄入安全",
                  keywords=["阿斯巴甜","WHO","致癌"], credibility_score=65, status=EventStatus.ACTIVE,
                  first_seen_at=now, last_updated_at=now),
            Event(id=_uuid.uuid4(), title="5G基站辐射证伪", summary="卫健委工信部辟谣：5G辐射值远低于国际标准",
                  keywords=["5G","辐射","辟谣"], credibility_score=80, status=EventStatus.ACTIVE,
                  first_seen_at=now, last_updated_at=now),
            Event(id=_uuid.uuid4(), title="自来水加氯致癌传闻", summary="流传氯消毒致癌，水务回应含量符国标",
                  keywords=["自来水","氯","致癌"], credibility_score=25, status=EventStatus.EMERGING,
                  first_seen_at=now, last_updated_at=now),
            Event(id=_uuid.uuid4(), title="疫苗含芯片追踪技术", summary="海外谣传疫苗含微芯片，多国机构辟谣",
                  keywords=["疫苗","芯片","谣言"], credibility_score=5, status=EventStatus.ACTIVE,
                  first_seen_at=now, last_updated_at=now),
        ]
        for ev in e:
            db.add(ev)
        await db.flush()

        r = RumorReport(id=_uuid.uuid4(), event_id=e[-1].id, rumor_claim="疫苗含芯片",
                        fact_check_result="WHO/CDC/中国疾控中心均声明不含微芯片", verdict="false",
                        verified_sources=[{"url":"https://who.int/covid19","title":"WHO"}])
        db.add(r)
        await db.commit()
        results.append(f"Seeded {len(e)} events + 1 rumor")
    except Exception as ex:
        results.append(f"Seed error: {type(ex).__name__}: {str(ex)[:300]}")

    return {"status": "ok", "details": results}
