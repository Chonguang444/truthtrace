"""
Phase 5 新增功能集成测试
测试: dashboard, trending, 搜索增强, 批量溯源, 限流

使用文件型 SQLite 确保表在请求间持久化。
"""

import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_api_v2.db"

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from app.main import app
from app.models.base import engine, Base


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """每个测试前确保数据库表和索引存在"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


# ---------------------------------------------------------------------------
# Dashboard & Stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_summary():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/stats/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "overview" in data
        assert "today" in data
        assert "trend_7d" in data
        assert "hot_events" in data
        assert "platforms" in data
        assert "credibility_distribution" in data
        assert "status_distribution" in data
        assert "updated_at" in data

        overview = data["overview"]
        assert "total_events" in overview
        assert "total_sources" in overview
        assert "total_rumor_reports" in overview
        assert "avg_credibility" in overview


@pytest.mark.asyncio
async def test_trending_events():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/stats/trending?hours=24&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "hours" in data
        assert "events" in data
        assert data["hours"] == 24


@pytest.mark.asyncio
async def test_trending_invalid_params():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # hours out of range should 422
        resp = await client.get("/api/stats/trending?hours=999")
        assert resp.status_code == 422

        resp = await client.get("/api/stats/trending?hours=0")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 搜索增强
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_with_filters():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/search?q=test&credibility_min=30&credibility_max=80&sort=newest"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "sort" in data
        assert data["sort"] == "newest"


@pytest.mark.asyncio
async def test_search_date_filter():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/search?q=test&date_from=2025-01-01&date_to=2026-12-31"
        )
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_search_invalid_date():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/search?q=test&date_from=invalid")
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_search_trending():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/search/trending?hours=48&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data


@pytest.mark.asyncio
async def test_search_sanitization():
    """测试搜索输入清洗 (防 SQL 注入)"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/search?q=test';%20DROP%20TABLE%20events;--")
        assert resp.status_code == 200
        # 不应该崩溃，正常返回


@pytest.mark.asyncio
async def test_search_long_query():
    """测试超长查询截断 — 200 字符以内可接受"""
    long_q = "x" * 200
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/search?q={long_q}")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 批量溯源
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_trace_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/trace/batch", json={"urls": []})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_batch_trace_invalid_urls():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/trace/batch",
            json={"urls": ["not-a-url", "ftp://invalid.com"]},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_batch_trace_too_many():
    """测试超过 100 个 URL 被拒绝"""
    urls = [f"https://example.com/{i}" for i in range(101)]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/trace/batch", json={"urls": urls})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_task_list():
    """列出所有任务"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert "tasks" in data
        assert "total" in data


# ---------------------------------------------------------------------------
# 健康检查 & API 根路由
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_root():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/")
        assert resp.status_code == 200
        data = resp.json()
        assert "endpoints" in data
        assert "docs" in data


# ---------------------------------------------------------------------------
# 限流 (不测试实际限流行为，只测试端点可达)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rate_limit_endpoints_accessible():
    """验证限流中间件没有阻止正常请求"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200

        resp = await client.get("/api/search?q=test")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def teardown_module():
    import os
    db_file = os.path.join(os.path.dirname(__file__), "..", "test_api_v2.db")
    if os.path.exists(db_file):
        os.remove(db_file)
