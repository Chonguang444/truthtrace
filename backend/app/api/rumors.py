"""
辟谣 API — 辟谣广场、谣言检测、辟谣报告
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID

from app.models.base import get_db
from app.models.event import RumorReport, Event

router = APIRouter()


@router.get("/rumors")
async def list_rumors(
    verdict: str | None = Query(None, pattern="^(false|misleading|unverified)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    辟谣广场 — 列出已确认的谣言

    可筛选判定类型：
    - false: 确认为假
    - misleading: 误导性信息
    - unverified: 待验证
    """
    stmt = (
        select(RumorReport)
        .options(selectinload(RumorReport.event))
    )

    if verdict:
        stmt = stmt.where(RumorReport.verdict == verdict)

    stmt = stmt.order_by(RumorReport.published_at.desc())
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    reports = result.scalars().all()

    return {
        "total": len(reports),
        "offset": offset,
        "limit": limit,
        "rumors": [
            {
                "id": str(r.id),
                "event_id": str(r.event_id) if r.event else None,
                "event_title": r.event.title if r.event else "未知事件",
                "rumor_claim": r.rumor_claim,
                "verdict": r.verdict,
                "fact_check_result": r.fact_check_result,
                "correction": r.correction,
                "verified_sources": r.verified_sources,
                "published_at": r.published_at.isoformat() if r.published_at else None,
            }
            for r in reports
        ],
    }


@router.get("/rumors/{rumor_id}")
async def get_rumor_detail(
    rumor_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """获取辟谣报告详情"""
    stmt = (
        select(RumorReport)
        .where(RumorReport.id == rumor_id)
        .options(selectinload(RumorReport.event))
    )
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=404, detail="辟谣报告不存在")

    return {
        "id": str(report.id),
        "event_id": str(report.event_id),
        "event_title": report.event.title if report.event else None,
        "rumor_claim": report.rumor_claim,
        "verdict": report.verdict,
        "fact_check_result": report.fact_check_result,
        "correction": report.correction,
        "verified_sources": report.verified_sources,
        "published_at": report.published_at.isoformat() if report.published_at else None,
    }


@router.get("/events/{event_id}/verify")
async def verify_event(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    对事件进行真实性验证

    使用交叉验证引擎，综合多源信息评估事件可信度。
    返回可信度评分和具体分析。
    """
    from app.verifier.cross_ref import CrossReferencer
    from app.verifier.rumor_detect import RumorDetector

    # 获取事件及其所有来源
    stmt = (
        select(Event)
        .where(Event.id == event_id)
        .options(selectinload(Event.sources))
    )
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")

    if not event.sources:
        return {
            "event_id": str(event_id),
            "score": 50.0,
            "verdict": "unverified",
            "reason": "缺少足够的数据源进行验证",
        }

    # 交叉验证
    cross_ref = CrossReferencer()
    cross_result = await cross_ref.analyze(event.sources)

    # 谣言检测
    detector = RumorDetector()
    rumor_result = await detector.detect(event)

    return {
        "event_id": str(event_id),
        "credibility_score": round(
            (cross_result.get("score", 50) + rumor_result.get("score", 50)) / 2, 1
        ),
        "cross_reference": cross_result,
        "rumor_detection": rumor_result,
        "verdict": _determine_verdict(cross_result, rumor_result),
    }


def _determine_verdict(cross_result: dict, rumor_result: dict) -> str:
    """综合判定事件真实性"""
    score = (cross_result.get("score", 50) + rumor_result.get("score", 50)) / 2
    if score >= 70:
        return "likely_true"
    elif score >= 40:
        return "uncertain"
    else:
        return "likely_false"
