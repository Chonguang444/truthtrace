"""
API 速率限制中间件
使用 slowapi (基于 limits 库) + Redis/内存后端
"""

import logging
from typing import Callable

from fastapi import FastAPI, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware

logger = logging.getLogger("truthtrace.ratelimit")

# 默认使用内存存储；有 Redis 时自动切换
_redis_url: str | None = None


def _get_redis_url() -> str | None:
    """尝试读取 Redis 配置"""
    global _redis_url
    if _redis_url is None:
        try:
            from app.config import get_settings
            settings = get_settings()
            _redis_url = settings.redis_url
        except Exception:
            _redis_url = False  # 标记不可用
    return _redis_url if _redis_url and _redis_url is not False else None


def create_limiter() -> Limiter:
    """
    创建速率限制器

    Redis URL 示例:
        redis://localhost:6379/0
        redis://:password@localhost:6379/0

    无 Redis 时使用内存存储 (多进程环境下不共享)。
    """
    redis_url = _get_redis_url()
    if redis_url:
        import redis as _redis
        try:
            # 测试连接
            r = _redis.from_url(redis_url, socket_connect_timeout=1)
            r.ping()
            r.close()
            logger.info(f"Rate limiter using Redis: {redis_url}")
            return Limiter(
                key_func=get_remote_address,
                storage_uri=redis_url,
                default_limits=["200/minute", "2000/hour"],
            )
        except Exception as e:
            logger.warning(f"Redis not available for rate limiting ({e}), using in-memory storage")

    logger.info("Rate limiter using in-memory storage")
    return Limiter(
        key_func=get_remote_address,
        default_limits=["200/minute", "2000/hour"],
    )


def setup_rate_limit(app: FastAPI) -> Limiter:
    """
    为 FastAPI 应用配置速率限制

    用法:
        from app.middleware.rate_limit import setup_rate_limit
        limiter = setup_rate_limit(app)

        @app.get("/api/sensitive")
        @limiter.limit("5/minute")
        async def sensitive_endpoint(): ...
    """
    limiter = create_limiter()

    # 注册限流异常处理器
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # 添加 SlowAPI 中间件 (必须在其他中间件之前)
    app.add_middleware(SlowAPIMiddleware)

    return limiter


def get_limiter(app: FastAPI) -> Limiter | None:
    """获取已注册的 limiter 实例"""
    return getattr(app.state, "limiter", None)


# =============================================================================
# 内存级限流回退 (用于敏感端点如 /auth/login 的额外保护)
# =============================================================================

import time as _time
from collections import defaultdict

_login_attempts: dict[str, list[float]] = defaultdict(list)
_LOGIN_MAX_ATTEMPTS = 5
_LOGIN_WINDOW = 60  # 60 秒窗口


def check_login_rate_limit(client_ip: str) -> bool:
    """
    检查登录尝试频率。返回 True 表示允许，False 表示超限。

    每 IP 每 60 秒最多 5 次尝试。
    """
    now = _time.time()
    # 清理过期记录
    _login_attempts[client_ip] = [
        t for t in _login_attempts[client_ip]
        if now - t < _LOGIN_WINDOW
    ]
    if len(_login_attempts[client_ip]) >= _LOGIN_MAX_ATTEMPTS:
        return False
    _login_attempts[client_ip].append(now)
    # 清理旧 IP 记录防止内存泄漏
    if len(_login_attempts) > 10000:
        expired_ips = [
            ip for ip, attempts in _login_attempts.items()
            if not attempts or now - max(attempts) > _LOGIN_WINDOW * 2
        ]
        for ip in expired_ips:
            del _login_attempts[ip]
    return True
