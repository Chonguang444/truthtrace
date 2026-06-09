"""
API 集成测试 — 使用 FastAPI TestClient 测试全部端点

使用文件型 SQLite 确保表在请求间持久化。
"""

import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_api.db"

import asyncio
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


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_search_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/search?q=nonexistent_xyz_test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


@pytest.mark.asyncio
async def test_search_validation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/search")
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_by_url_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/search/url?url=https://nonexistent-test.com")
        assert resp.status_code == 200
        data = resp.json()
        assert data["found"] is False


@pytest.mark.asyncio
async def test_trace_and_search_e2e():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 提交追踪 (异步模式)
        resp = await client.post(
            "/api/trace",
            json={"url": "https://example.com", "title": "E2E集成测试事件"},
        )
        assert resp.status_code == 200
        trace_data = resp.json()
        task_id = trace_data["task_id"]

        # 轮询直到任务完成
        event_id = None
        for _ in range(60):  # 最多等 60 秒
            await asyncio.sleep(0.5)
            resp = await client.get(f"/api/tasks/{task_id}")
            assert resp.status_code == 200
            task_data = resp.json()
            if task_data["status"] == "SUCCESS":
                event_id = task_data["result"]["event_id"]
                break
            elif task_data["status"] == "FAILURE":
                raise AssertionError(f"Task failed: {task_data.get('error')}")

        assert event_id, "Trace task did not complete within timeout"

        # 事件详情
        resp = await client.get(f"/api/events/{event_id}")
        assert resp.status_code == 200

        # 时间线
        resp = await client.get(f"/api/events/{event_id}/timeline")
        assert resp.status_code == 200

        # 传播图
        resp = await client.get(f"/api/events/{event_id}/graph")
        assert resp.status_code == 200

        # 来源
        resp = await client.get(f"/api/events/{event_id}/sources")
        assert resp.status_code == 200

        # 报告
        resp = await client.get(f"/api/events/{event_id}/report")
        assert resp.status_code == 200

        # 搜索
        resp = await client.get("/api/search?q=E2E集成测试")
        assert resp.status_code == 200
        search_data = resp.json()
        assert search_data["total"] >= 1


@pytest.mark.asyncio
async def test_rumors():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/rumors")
        assert resp.status_code == 200
        data = resp.json()
        assert "rumors" in data


@pytest.mark.asyncio
async def test_rumors_filter():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/rumors?verdict=false")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_trace_url_chain():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/trace/url-chain?url=https://t.cn/test123")
        assert resp.status_code == 200
        data = resp.json()
        assert "redirect_chain" in data


@pytest.mark.asyncio
async def test_stats():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_events" in data


@pytest.mark.asyncio
async def test_stats_platforms():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/stats/platforms")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_stats_rumors():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/stats/rumors")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_event_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/events/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_batch_trace():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/trace/batch",
            json={"urls": ["https://example.com/a", "https://example.com/b"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for task in data["tasks"]:
            assert "task_id" in task


@pytest.mark.asyncio
async def test_wechat_crawler_import():
    """微信爬虫可导入"""
    from app.crawler.wechat import WechatCrawler
    c = WechatCrawler()
    assert c.BASE_URL == "https://mp.weixin.qq.com"
    assert WechatCrawler.is_wechat_url("https://mp.weixin.qq.com/s/test") is True
    assert WechatCrawler.is_wechat_url("https://weibo.com/test") is False


def teardown_module():
    """清理测试数据库文件"""
    import os
    db_file = os.path.join(os.path.dirname(__file__), "..", "test_api.db")
    if os.path.exists(db_file):
        os.remove(db_file)
