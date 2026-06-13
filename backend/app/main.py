"""
TruthTrace — 平浪散暴平台 API
FastAPI 应用入口，集成速率限制、CORS、结构化日志
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models.base import engine, Base
from app.api import search, events, trace, rumors, stats, auth, ws, export, monitor, admin, feedback, reporting, video, system
from app.api import literacy, situational, community, debunk_studio, vertical_medical, developer, quick_check, analytics, detectzoo
from app.api import new_engines  # P0-P2 新引擎 API
from app.middleware.rate_limit import setup_rate_limit, get_limiter
from app.security import SecurityHeadersMiddleware

settings = get_settings()

# --- 结构化日志 ---
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("truthtrace")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期 — Render免费层快速启动：先响应health check，后台慢初始化"""
    import asyncio as _asyncio
    from sqlalchemy import text as sa_text

    setup_complete = False

    async def _slow_startup():
        """后台慢初始化 — 不影响 Render health check"""
        nonlocal setup_complete
        await _asyncio.sleep(1)  # 等uvicorn完全就绪

        # --- 数据库迁移 ---
        try:
            from alembic.config import Config
            from alembic import command as alembic_command
            import os as _os
            alembic_cfg = Config(_os.path.join(_os.path.dirname(__file__), "..", "alembic.ini"))
            sync_url = settings.database_url.replace("+asyncpg", "").replace("+aiosqlite", "")
            alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
            async with engine.begin() as conn:
                def _run(sync_conn):
                    alembic_cfg.attributes['connection'] = sync_conn
                    alembic_command.upgrade(alembic_cfg, "head")
                await conn.run_sync(_run)
            logger.info("Database migration complete")
        except Exception as e:
            logger.warning(f"Migration skipped: {e}")
            try:
                async with engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
            except Exception:
                pass

        # --- 全文搜索索引 ---
        try:
            async with engine.begin() as conn:
                await conn.execute(sa_text(
                    "CREATE INDEX IF NOT EXISTS ix_events_search_tsv ON events "
                    "USING gin (to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(summary,'')))"
                ))
        except Exception:
            pass

        # --- 自动种子数据 (空DB时) ---
        try:
            from app.models.base import async_session_factory
            from app.models.event import Event, RumorReport, EventStatus
            from sqlalchemy import select as sa_select, func as sa_func
            import uuid as _uuid
            _now = __import__('datetime').datetime.now(__import__('datetime').timezone.utc)
            async with async_session_factory() as _sess:
                cnt = (await _sess.execute(sa_select(sa_func.count(Event.id)))).scalar() or 0
                if cnt == 0:
                    evs = [
                        Event(id=_uuid.uuid4(), title="WHO: 阿斯巴甜列为2B类致癌物",
                              summary="世界卫生组织将阿斯巴甜列为2B类可能致癌物质，强调日常摄入量安全",
                              keywords=["阿斯巴甜","WHO","致癌"], credibility_score=65, status=EventStatus.ACTIVE,
                              first_seen_at=_now, last_updated_at=_now),
                        Event(id=_uuid.uuid4(), title="5G基站辐射危害已被证伪",
                              summary="国家卫健委、工信部联合辟谣：5G基站辐射值远低于国际标准",
                              keywords=["5G","辐射","辟谣"], credibility_score=80, status=EventStatus.ACTIVE,
                              first_seen_at=_now, last_updated_at=_now),
                        Event(id=_uuid.uuid4(), title="自来水加氯过量致癌传闻",
                              summary="社交媒体流传自来水加氯消毒产生致癌物，水务部门回应氯含量符合国标",
                              keywords=["自来水","氯","致癌"], credibility_score=25, status=EventStatus.EMERGING,
                              first_seen_at=_now, last_updated_at=_now),
                        Event(id=_uuid.uuid4(), title="新冠疫苗含芯片追踪技术",
                              summary="海外社交媒体谣传疫苗含微芯片，世界卫生组织及多国疾控中心辟谣",
                              keywords=["疫苗","芯片","新冠","谣言"], credibility_score=5, status=EventStatus.ACTIVE,
                              first_seen_at=_now, last_updated_at=_now),
                    ]
                    [_sess.add(ev) for ev in evs]
                    await _sess.flush()
                    rr = RumorReport(id=_uuid.uuid4(), event_id=evs[-1].id,
                                     rumor_claim="新冠疫苗含微芯片追踪技术",
                                     fact_check_result="WHO、美国CDC、中国疾控中心均声明：疫苗不含任何微芯片。这是典型的技术误导型谣言。",
                                     verdict="false",
                                     verified_sources=[{"url":"https://www.who.int/covid-19/vaccines","title":"WHO疫苗建议"}])
                    _sess.add(rr)
                    await _sess.commit()
                    logger.info(f"Auto-seeded {len(evs)} demo events + 1 rumor report")
        except Exception as _e:
            logger.debug(f"Auto-seed skipped: {_e}")

        setup_complete = True
        logger.info(f"{settings.app_name} v{settings.app_version} fully initialized")

        # --- 自动采集器 ---
        try:
            from app.monitor.auto_collector import start_collector
            await start_collector()
        except Exception as e:
            logger.debug(f"AutoCollector: {e}")

        # --- 监控调度 (仅非debug模式) ---
        if not settings.debug:
            try:
                from app.monitor.hotspot_monitor import monitor_scheduler
                await monitor_scheduler.start(interval_minutes=15)
            except Exception as e:
                logger.debug(f"Monitor: {e}")

    # 立即返回 — 不阻塞 Render health check
    _asyncio.create_task(_slow_startup())
    logger.info(f"{settings.app_name} v{settings.app_version} starting (background init...)")

    yield

    # --- 清理 ---
    try:
        from app.monitor.hotspot_monitor import monitor_scheduler
        await monitor_scheduler.stop()
    except Exception:
        pass
    try:
        from app.monitor.auto_collector import stop_collector
        await stop_collector()
    except Exception:
        pass
    await engine.dispose()
    logger.info(f"{settings.app_name} shut down")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="TruthTrace 平浪散暴 API — 提交 URL 自动溯源、构建传播链、评估可信度、生成辟谣报告",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# --- CORS 配置 ---
if settings.cors_origins:
    # Parse from comma-separated env var: "https://a.com,https://b.com"
    cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
else:
    cors_origins = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]
# Always allow Vercel deploy domains (production + all preview deploys)
cors_origin_regex = r"https://truthtrace(-[a-zA-Z0-9-]*)?\.vercel\.app"
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 安全头中间件 ---
app.add_middleware(SecurityHeadersMiddleware)

# --- 速率限制 ---
limiter = setup_rate_limit(app)


# --- 全局异常处理器 (兜底所有未处理的 API 异常) ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """捕获所有未处理的异常，返回统一错误格式，避免 500 空白页"""
    logger.error(
        f"未处理异常 {request.method} {request.url.path}: {type(exc).__name__}: {exc}",
        exc_info=settings.debug,
    )
    # 如果是已知的 HTTP 异常，保留原始状态码
    from fastapi.responses import JSONResponse
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail, "path": request.url.path},
        )
    # 数据库连接错误
    err_msg = str(exc)
    if "connect" in err_msg.lower() or "connection" in err_msg.lower():
        return JSONResponse(
            status_code=503,
            content={"detail": "服务暂时不可用，请稍后重试", "path": request.url.path},
        )
    # 通用错误
    return JSONResponse(
        status_code=500,
        content={
            "detail": "服务器内部错误" if not settings.debug else f"{type(exc).__name__}: {err_msg[:200]}",
            "path": request.url.path,
        },
    )


# --- 请求日志中间件 ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录每个请求的方法、路径和状态码"""
    response = await call_next(request)
    logger.debug(f"{request.method} {request.url.path} → {response.status_code}")
    return response


# --- 注册路由 ---
app.include_router(search.router, prefix="/api", tags=["搜索"])
app.include_router(events.router, prefix="/api", tags=["事件"])
app.include_router(trace.router, prefix="/api", tags=["溯源"])
app.include_router(rumors.router, prefix="/api", tags=["辟谣"])
app.include_router(stats.router, prefix="/api", tags=["统计"])
app.include_router(auth.router, prefix="/api", tags=["用户"])
app.include_router(ws.router, prefix="/api", tags=["实时推送"])
app.include_router(export.router, prefix="/api", tags=["导出"])
app.include_router(monitor.router, prefix="/api", tags=["监控"])
app.include_router(admin.router, prefix="/api", tags=["管理"])
app.include_router(feedback.router, prefix="/api", tags=["反馈"])
app.include_router(reporting.router, prefix="/api", tags=["报表"])
app.include_router(video.router, prefix="/api", tags=["视频"])
app.include_router(system.router, prefix="/api", tags=["系统"])
app.include_router(literacy.router, prefix="/api", tags=["信息素养学院"])
app.include_router(situational.router, prefix="/api", tags=["态势感知"])
app.include_router(community.router, prefix="/api", tags=["协作众包"])
app.include_router(debunk_studio.router, prefix="/api", tags=["辟谣工坊"])
app.include_router(vertical_medical.router, prefix="/api", tags=["医疗垂直"])
app.include_router(developer.router, prefix="/api", tags=["API平台"])
app.include_router(quick_check.router, prefix="/api", tags=["快速检测"])
app.include_router(analytics.router, prefix="/api", tags=["效果追踪"])
app.include_router(detectzoo.router, prefix="/api", tags=["跨库共享"])
app.include_router(new_engines.router, prefix="/api", tags=["新引擎 P0-P2"])


# --- 核心端点 ---

@app.get("/api/health")
async def health_check():
    """健康检查端点 — 用于 Docker 健康探针和监控"""
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/api/")
async def api_root():
    """API 根路径 — 返回可用端点概览"""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "endpoints": {
            "search": "/api/search?q=关键词",
            "trace": "POST /api/trace",
            "events": "/api/events/{event_id}",
            "rumors": "/api/rumors",
            "stats": "/api/stats",
            "health": "/api/health",
        },
        "new_features": {
            "literacy_academy": "/api/literacy/challenges — 信息素养挑战赛",
            "situational_awareness": "/api/situational/hotspots — 实时态势感知",
            "community": "/api/community/bounties — 协作众包验证",
            "debunk_studio": "/api/studio/generate-article — 辟谣工坊",
            "medical_vertical": "/api/vertical/medical/verify — 医疗验证",
            "developer_api": "/api/developer/docs — API开放平台",
        },
        "docs": "/api/docs",
    }
