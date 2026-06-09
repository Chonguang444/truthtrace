"""
数据库基类和引擎配置
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

# 异步引擎
# 根据数据库类型动态设置连接参数 (SQLite 不支持 pool_size/max_overflow)
_is_sqlite = settings.database_url.startswith("sqlite")
engine_kwargs: dict = dict(echo=settings.debug)
if not _is_sqlite:
    engine_kwargs.update(pool_size=20, max_overflow=10)

engine = create_async_engine(settings.database_url, **engine_kwargs)

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
