"""
数据模型单元测试 — Event, Source, PropagationEdge, TimelineNode, RumorReport
"""

import pytest
import uuid
from datetime import datetime
from sqlalchemy import select

from app.models.event import (
    Event, Source, PropagationEdge, TimelineNode, RumorReport,
    EventStatus, Platform, EdgeType,
)


@pytest.mark.asyncio
async def test_create_event(db_session, sample_event_data):
    """创建 Event 记录"""
    event = Event(**sample_event_data, first_seen_at=datetime.utcnow())
    db_session.add(event)
    await db_session.commit()

    assert event.id is not None
    assert event.title == sample_event_data["title"]
    assert event.status == EventStatus.EMERGING
    assert event.credibility_score == 50.0
    assert isinstance(event.keywords, list)


@pytest.mark.asyncio
async def test_create_source(db_session, sample_event_data, sample_source_data):
    """创建 Source 记录"""
    event = Event(**sample_event_data, first_seen_at=datetime.utcnow())
    db_session.add(event)
    await db_session.flush()

    source = Source(event_id=event.id, **sample_source_data, fetched_at=datetime.utcnow())
    db_session.add(source)
    await db_session.commit()

    assert source.id is not None
    assert source.event_id == event.id
    assert source.platform == Platform.WEIBO
    assert source.is_original is True
    assert source.authority_score == 65.0


@pytest.mark.asyncio
async def test_create_propagation_edge(db_session, sample_event_data, sample_source_data):
    """创建 PropagationEdge 记录"""
    event = Event(**sample_event_data, first_seen_at=datetime.utcnow())
    db_session.add(event)
    await db_session.flush()

    source_a = Source(
        event_id=event.id,
        url="https://weibo.com/a",
        platform=Platform.WEIBO,
        author="A",
        content_hash="hash_a",
        fetched_at=datetime.utcnow(),
    )
    source_b = Source(
        event_id=event.id,
        url="https://zhihu.com/b",
        platform=Platform.ZHIHU,
        author="B",
        content_hash="hash_b",
        fetched_at=datetime.utcnow(),
    )
    db_session.add_all([source_a, source_b])
    await db_session.flush()

    edge = PropagationEdge(
        from_source_id=source_a.id,
        to_source_id=source_b.id,
        edge_type=EdgeType.REPOST,
        weight=2.5,
        propagated_at=datetime.utcnow(),
    )
    db_session.add(edge)
    await db_session.commit()

    assert edge.id is not None
    assert edge.edge_type == EdgeType.REPOST
    assert edge.weight == 2.5


@pytest.mark.asyncio
async def test_create_timeline_node(db_session, sample_event_data, sample_source_data):
    """创建 TimelineNode 记录"""
    event = Event(**sample_event_data, first_seen_at=datetime.utcnow())
    db_session.add(event)
    await db_session.flush()

    source = Source(event_id=event.id, **sample_source_data, fetched_at=datetime.utcnow())
    db_session.add(source)
    await db_session.flush()

    node = TimelineNode(
        event_id=event.id,
        source_id=source.id,
        timestamp=datetime.utcnow(),
        description="首次报道事件",
        significance=1.5,
    )
    db_session.add(node)
    await db_session.commit()

    assert node.id is not None
    assert node.description == "首次报道事件"
    assert node.significance == 1.5


@pytest.mark.asyncio
async def test_create_rumor_report(db_session, sample_event_data):
    """创建 RumorReport 记录"""
    event = Event(**sample_event_data, first_seen_at=datetime.utcnow())
    db_session.add(event)
    await db_session.flush()

    report = RumorReport(
        event_id=event.id,
        rumor_claim="该食品含有致癌物质",
        fact_check_result="经核查，该说法缺乏科学依据",
        verdict="false",
        verified_sources=[{"url": "https://gov.cn/check", "title": "官方澄清"}],
        correction="该食品符合国家安全标准",
        published_at=datetime.utcnow(),
    )
    db_session.add(report)
    await db_session.commit()

    assert report.id is not None
    assert report.verdict == "false"
    assert len(report.verified_sources) == 1


@pytest.mark.asyncio
async def test_event_cascade_delete(db_session, sample_event_data, sample_source_data):
    """级联删除: 删除 Event 时自动删除关联数据"""
    event = Event(**sample_event_data, first_seen_at=datetime.utcnow())
    db_session.add(event)
    await db_session.flush()

    source = Source(event_id=event.id, **sample_source_data, fetched_at=datetime.utcnow())
    db_session.add(source)
    await db_session.commit()

    source_id = source.id

    # 删除 Event
    await db_session.delete(event)
    await db_session.commit()

    # Source 也被删除
    result = await db_session.execute(select(Source).where(Source.id == source_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_unique_rumor_report_per_event(db_session, sample_event_data):
    """每个 Event 只能有一个 RumorReport"""
    event = Event(**sample_event_data, first_seen_at=datetime.utcnow())
    db_session.add(event)
    await db_session.flush()

    report1 = RumorReport(
        event_id=event.id,
        rumor_claim="claim 1",
        fact_check_result="check 1",
        verdict="false",
        published_at=datetime.utcnow(),
    )
    db_session.add(report1)
    await db_session.commit()

    # 第二个报告应触发唯一约束
    report2 = RumorReport(
        event_id=event.id,
        rumor_claim="claim 2",
        fact_check_result="check 2",
        verdict="misleading",
        published_at=datetime.utcnow(),
    )
    db_session.add(report2)
    with pytest.raises(Exception):
        await db_session.commit()


@pytest.mark.asyncio
async def test_search_by_title(db_session):
    """搜索事件 — ILIKE 标题匹配"""
    events = [
        Event(
            title="食品安全事件",
            summary="关于食品安全的报道",
            keywords=["食品", "安全"],
            status=EventStatus.EMERGING,
            first_seen_at=datetime.utcnow(),
        ),
        Event(
            title="交通事故事件",
            summary="关于交通安全的报道",
            keywords=["交通", "事故"],
            status=EventStatus.ACTIVE,
            first_seen_at=datetime.utcnow(),
        ),
    ]
    db_session.add_all(events)
    await db_session.commit()

    stmt = select(Event).where(Event.title.ilike("%食品%"))
    result = await db_session.execute(stmt)
    found = result.scalars().all()

    assert len(found) == 1
    assert found[0].title == "食品安全事件"


@pytest.mark.asyncio
async def test_event_status_transition(db_session, sample_event_data):
    """事件状态流转"""
    event = Event(**sample_event_data, first_seen_at=datetime.utcnow())
    db_session.add(event)
    await db_session.commit()

    assert event.status == EventStatus.EMERGING

    event.status = EventStatus.ACTIVE
    await db_session.commit()

    # 重新查询验证
    stmt = select(Event).where(Event.id == event.id)
    result = await db_session.execute(stmt)
    updated = result.scalar_one()
    assert updated.status == EventStatus.ACTIVE
