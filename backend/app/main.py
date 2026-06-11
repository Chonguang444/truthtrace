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
    """应用生命周期：自动迁移数据库（Alembic）"""
    from sqlalchemy import text as sa_text, inspect

    # --- 数据库迁移 ---
    # 生产环境推荐: DATABASE_URL="..." alembic upgrade head && uvicorn ...
    # 开发环境: 自动使用 Alembic 运行迁移
    try:
        from alembic.config import Config
        from alembic import command as alembic_command
        import os as _os

        alembic_cfg = Config(_os.path.join(_os.path.dirname(__file__), "..", "alembic.ini"))
        # Override DB URL for sync migration
        sync_url = settings.database_url.replace("+asyncpg", "").replace("+aiosqlite", "")
        alembic_cfg.set_main_option("sqlalchemy.url", sync_url)

        async with engine.begin() as conn:
            def _run_migrations(sync_conn):
                # Point alembic to the existing connection
                alembic_cfg.attributes['connection'] = sync_conn
                alembic_command.upgrade(alembic_cfg, "head")
            await conn.run_sync(_run_migrations)
        logger.info("Database migration complete")
    except Exception as e:
        # Fallback: use create_all for development convenience
        logger.warning(f"Alembic migration skipped (falling back to create_all): {e}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # --- 全文搜索索引 (PostgreSQL only, auto-skipped by SQLite) ---
    try:
        async with engine.begin() as conn:
            await conn.execute(sa_text(
                "CREATE INDEX IF NOT EXISTS ix_events_search_tsv ON events "
                "USING gin (to_tsvector('simple', coalesce(title, '')) "
                "|| to_tsvector('simple', coalesce(summary, '')))"
            ))
            await conn.execute(sa_text(
                "CREATE INDEX IF NOT EXISTS ix_events_keywords_gin ON events "
                "USING gin (keywords)"
            ))
    except Exception:
        logger.debug("GIN indexes skipped (not PostgreSQL or already exist)")

    logger.info(f"{settings.app_name} v{settings.app_version} started")
    # 启动自动采集器(部署后立即开始爬取)
    try:
        from app.monitor.auto_collector import start_collector, stop_collector
        await start_collector()
    except Exception as e:
        logger.warning(f"AutoCollector 启动跳过: {e}")
    # 启动监控定时调度 (每15分钟爬取热搜+分析+告警)
    try:
        from app.monitor.hotspot_monitor import monitor_scheduler
        if settings.debug:
            # 开发环境: 不自动启动(避免频繁调用)
            logger.info("开发模式: 监控调度器不自动启动 (可通过 POST /api/monitor/crawl 手动触发)")
        else:
            await monitor_scheduler.start(interval_minutes=15)
    except Exception as e:
        logger.warning(f"监控调度器启动跳过: {e}")
    yield
    try:
        await monitor_scheduler.stop()
    except Exception:
        pass
    try:
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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
