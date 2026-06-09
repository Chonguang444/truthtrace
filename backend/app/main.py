"""
TruthTrace — 网络事件追溯平台 API
FastAPI 应用入口，集成速率限制、CORS、结构化日志
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models.base import engine, Base
from app.api import search, events, trace, rumors, stats, auth, ws, export, monitor, admin, feedback, reporting, video, system
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
    """应用生命周期：启动时创建数据库表和索引"""
    from sqlalchemy import text as sa_text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 创建 GIN 全文搜索索引 (ORM 不支持复合函数表达式索引)
        try:
            await conn.execute(sa_text(
                "CREATE INDEX IF NOT EXISTS ix_events_search_tsv ON events "
                "USING gin (to_tsvector('simple', coalesce(title, '')) "
                "|| to_tsvector('simple', coalesce(summary, '')))"
            ))
            await conn.execute(sa_text(
                "CREATE INDEX IF NOT EXISTS ix_events_keywords_gin ON events "
                "USING gin (keywords)"
            ))
        except Exception as e:
            logger.warning(f"GIN index creation skipped: {e}")
    logger.info(f"{settings.app_name} v{settings.app_version} started")
    # 启动自动采集器(部署后立即开始爬取)
    try:
        from app.monitor.auto_collector import start_collector, stop_collector
        await start_collector()
    except Exception as e:
        logger.warning(f"AutoCollector 启动跳过: {e}")
    yield
    try:
        await stop_collector()
    except Exception:
        pass
    await engine.dispose()
    logger.info(f"{settings.app_name} shut down")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="全网事件追溯 & 辟谣平台 API — 提交 URL 自动溯源、构建传播链、评估可信度、生成辟谣报告",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# --- CORS 配置 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 安全头中间件 ---
app.add_middleware(SecurityHeadersMiddleware)

# --- 速率限制 ---
limiter = setup_rate_limit(app)


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
            "search_trending": "/api/search/trending",
            "trace": "POST /api/trace",
            "trace_batch": "POST /api/trace/batch",
            "tasks": "/api/tasks/{task_id}",
            "events": "/api/events/{event_id}",
            "rumors": "/api/rumors",
            "stats": "/api/stats",
            "health": "/api/health",
        },
        "docs": "/api/docs",
    }
