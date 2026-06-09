"""
TruthTrace 测试配置 — pytest fixtures

通过 DATABASE_URL 环境变量覆盖为 SQLite 内存数据库，
避免在测试环境中启动完整的 PostgreSQL。
"""

import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.models.base import Base
from app.models.event import (
    Event, Source, PropagationEdge, TimelineNode, RumorReport,
    EventStatus, Platform, EdgeType,
)

TEST_DB_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture
async def db_session():
    """创建测试数据库会话"""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session
        await session.rollback()

    await engine.dispose()


@pytest.fixture
def sample_event_data():
    return {
        "title": "测试食品安全事件",
        "summary": "测试摘要，涉及食品安全问题。",
        "keywords": ["食品", "安全", "测试"],
        "status": EventStatus.EMERGING,
        "credibility_score": 50.0,
    }


@pytest.fixture
def sample_source_data():
    return {
        "url": "https://weibo.com/12345/test",
        "platform": Platform.WEIBO,
        "author": "测试用户",
        "title": "测试帖子标题",
        "content": "测试内容，包含食品安全相关信息。",
        "content_hash": "abc123def456",
        "authority_score": 65.0,
        "is_original": True,
    }
