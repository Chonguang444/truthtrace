"""
事件 API — 事件详情、时间线、传播图、来源列表
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.models.base import get_db
from app.models.event import (
    Event, Source, PropagationEdge, TimelineNode, RumorReport,
)

router = APIRouter()


@router.get("/events/{event_id}")
async def get_event_detail(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取事件详情，含来源列表统计"""
    stmt = (
        select(Event)
        .where(Event.id == event_id)
        .options(
            selectinload(Event.sources),
            selectinload(Event.rumor_report),
        )
    )
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    # 统计来源平台分布
    platform_counts = {}
    for s in event.sources:
        p = s.platform.value if s.platform else "unknown"
        platform_counts[p] = platform_counts.get(p, 0) + 1

    return {
        "id": str(event.id),
        "title": event.title,
        "summary": event.summary,
        "keywords": event.keywords,
        "status": event.status.value if event.status else None,
        "credibility_score": event.credibility_score,
        "first_seen_at": event.first_seen_at.isoformat() if event.first_seen_at else None,
        "last_updated_at": event.last_updated_at.isoformat() if event.last_updated_at else None,
        "source_count": len(event.sources),
        "platform_distribution": platform_counts,
        "original_sources": [
            {
                "id": str(s.id),
                "url": s.url,
                "platform": s.platform.value if s.platform else None,
                "author": s.author,
                "published_at": s.published_at.isoformat() if s.published_at else None,
                "authority_score": s.authority_score,
            }
            for s in event.sources if s.is_original
        ],
        "has_rumor_report": event.rumor_report is not None,
        "rumor_verdict": event.rumor_report.verdict if event.rumor_report else None,
        "has_engine_analysis": event.engine_analysis is not None,
        "engine_summary": {
            "verdict": event.engine_analysis.get("verdict"),
            "credibility_score": event.engine_analysis.get("credibility_score"),
            "distortion_count": len(event.engine_analysis.get("distortion_analysis", {}).get("matches", [])),
            "fallacy_count": event.engine_analysis.get("fallacy_analysis", {}).get("fallacy_count", 0),
            "narrative_count": len(event.engine_analysis.get("narrative_analysis", {}).get("matches", [])),
            "manipulation_score": event.engine_analysis.get("narrative_analysis", {}).get("manipulation_score", 0),
            "stat_risk": event.engine_analysis.get("statistical_analysis", {}).get("risk_score", 0),
        } if event.engine_analysis else None,
    }


@router.get("/events/{event_id}/timeline")
async def get_event_timeline(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取事件时间线"""
    stmt = (
        select(TimelineNode)
        .where(TimelineNode.event_id == event_id)
        .order_by(TimelineNode.timestamp.asc())
    )
    result = await db.execute(stmt)
    nodes = result.scalars().all()

    if not nodes:
        return {"event_id": str(event_id), "timeline": [], "message": "暂未构建时间线"}

    return {
        "event_id": str(event_id),
        "timeline": [
            {
                "id": str(n.id),
                "timestamp": n.timestamp.isoformat() if n.timestamp else None,
                "description": n.description,
                "significance": n.significance,
            }
            for n in nodes
        ],
    }


@router.get("/events/{event_id}/graph")
async def get_event_propagation_graph(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取事件传播图数据（节点 + 边）"""
    # 获取事件所有来源
    stmt = (
        select(Event)
        .where(Event.id == event_id)
        .options(
            selectinload(Event.sources).selectinload(Source.outgoing_edges),
        )
    )
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    # 构建图数据
    nodes = []
    edges = []
    seen = set()

    for s in event.sources:
        if s.id not in seen:
            nodes.append({
                "id": str(s.id),
                "label": s.author or "未知",
                "platform": s.platform.value if s.platform else "unknown",
                "url": s.url,
                "is_original": s.is_original,
                "authority_score": s.authority_score,
                "engagement": s.engagement_count or {},
            })
            seen.add(s.id)

        for e in s.outgoing_edges:
            edges.append({
                "id": str(e.id),
                "source": str(e.from_source_id),
                "target": str(e.to_source_id),
                "type": e.edge_type.value if e.edge_type else "reference",
                "weight": e.weight,
            })
            # 确保目标节点也在节点列表中
            if e.to_source_id not in seen:
                to_s = await db.get(Source, e.to_source_id)
                if to_s:
                    nodes.append({
                        "id": str(to_s.id),
                        "label": to_s.author or "未知",
                        "platform": to_s.platform.value if to_s.platform else "unknown",
                        "url": to_s.url,
                        "is_original": to_s.is_original,
                        "authority_score": to_s.authority_score,
                        "engagement": to_s.engagement_count or {},
                    })
                    seen.add(to_s.id)

    return {
        "event_id": str(event_id),
        "graph": {
            "nodes": nodes,
            "edges": edges,
        },
    }


@router.get("/events/{event_id}/sources")
async def get_event_sources(
    event_id: UUID,
    sort_by: str = Query("published_at", pattern="^(published_at|authority_score|engagement)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """获取事件的所有来源列表（可排序）"""
    stmt = (
        select(Source)
        .where(Source.event_id == event_id)
    )

    # 排序
    if sort_by == "authority_score":
        col = Source.authority_score
    elif sort_by == "engagement":
        col = Source.engagement_count
    else:
        col = Source.published_at

    if order == "asc":
        stmt = stmt.order_by(col.asc())
    else:
        stmt = stmt.order_by(col.desc().nulls_last())

    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    sources = result.scalars().all()

    return {
        "event_id": str(event_id),
        "total": len(sources),
        "sources": [
            {
                "id": str(s.id),
                "url": s.url,
                "platform": s.platform.value if s.platform else None,
                "author": s.author,
                "title": s.title,
                "content": s.content[:500] if s.content else None,
                "published_at": s.published_at.isoformat() if s.published_at else None,
                "is_original": s.is_original,
                "authority_score": s.authority_score,
                "engagement": s.engagement_count,
            }
            for s in sources
        ],
    }


@router.get("/events/{event_id}/report")
async def get_event_report(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取溯源报告"""
    stmt = (
        select(Event)
        .where(Event.id == event_id)
        .options(
            selectinload(Event.sources),
            selectinload(Event.timeline_nodes),
            selectinload(Event.rumor_report),
        )
    )
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    # 找出最早的原始来源
    original_sources = [s for s in event.sources if s.is_original]
    original_sources.sort(key=lambda s: s.published_at or s.fetched_at)

    # 构建传播链摘要
    propagation_chain = []
    for i, src in enumerate(original_sources[:10]):
        propagation_chain.append({
            "order": i + 1,
            "url": src.url,
            "platform": src.platform.value if src.platform else None,
            "author": src.author,
            "published_at": src.published_at.isoformat() if src.published_at else None,
            "is_first": i == 0,
        })

    report = {
        "event_id": str(event_id),
        "event_title": event.title,
        "credibility_score": event.credibility_score,
        "status": event.status.value if event.status else None,
        "total_sources": len(event.sources),
        "original_source_count": len(original_sources),
        "propagation_chain": propagation_chain,
        "timeline_summary": [
            {"timestamp": n.timestamp.isoformat() if n.timestamp else None, "description": n.description}
            for n in sorted(event.timeline_nodes, key=lambda n: n.timestamp or n.timestamp)
        ] if event.timeline_nodes else [],
        "rumor_analysis": {
            "has_report": event.rumor_report is not None,
            "verdict": event.rumor_report.verdict if event.rumor_report else None,
            "fact_check": event.rumor_report.fact_check_result if event.rumor_report else None,
        } if event.rumor_report else None,
    }

    return report


@router.get("/events/{event_id}/analysis")
async def get_event_analysis(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取推理引擎全维度分析结果"""
    stmt = select(Event).where(Event.id == event_id)
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    if not event.engine_analysis:
        return {
            "event_id": str(event_id),
            "available": False,
            "message": "该事件尚未完成推理引擎分析。请等待追踪任务完成或重新提交分析。",
        }

    return {
        "event_id": str(event_id),
        "available": True,
        "analysis": event.engine_analysis,
        "analyzed_at": event.last_updated_at.isoformat() if event.last_updated_at else None,
    }
