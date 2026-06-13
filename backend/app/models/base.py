"""
数据库基类和引擎配置
"""

import logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

logger = logging.getLogger("truthtrace.db")

settings = get_settings()


def _get_async_db_url() -> str:
    """Resolve async DB URL, falling back to SQLite when nothing is configured."""
    url = settings.database_url or ""
    if url:
        return url
    # No DATABASE_URL configured — use SQLite
    try:
        __import__("aiosqlite")
        return "sqlite+aiosqlite:///data/truthtrace.db"
    except ImportError:
        logger.warning("aiosqlite not available, using in-memory SQLite")
        return "sqlite:///data/truthtrace.db"


# Async engine
_db_url = _get_async_db_url()
_is_sqlite = _db_url.startswith("sqlite")
engine_kwargs: dict = dict(echo=settings.debug)
if not _is_sqlite:
    engine_kwargs.update(pool_size=20, max_overflow=10)

engine = create_async_engine(_db_url, **engine_kwargs)
logger.info(f"Database engine: {_db_url.split('@')[-1] if '@' in _db_url else _db_url[:60]}")

# 异步会话工厂
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入：获取数据库会话"""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


class Base(DeclarativeBase):
    pass
