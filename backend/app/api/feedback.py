"""
用户反馈 API — 分析反馈/误判申诉/审核队列

闭环: 用户反馈 → 管理员审核 → 引擎规则更新
"""

import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, field_validator

from app.models.base import get_db
from app.models.event import Event
from app.auth.jwt import get_current_active_user
from app.models.user import User

router = APIRouter()

# 内存存储 (实际应有数据库模型)
_feedback_store: dict[str, list[dict]] = {}  # event_id → [feedbacks]
_appeal_store: list[dict] = []  # 申诉列表


# =============================================================================
# 数据模型
# =============================================================================

class FeedbackRequest(BaseModel):
    event_id: str
    rating: str          # "helpful" / "not_helpful" / "inaccurate"
    comment: str = ""
    dimension: str = ""  # "verdict" / "distortion" / "fallacy" / "statistical" / "narrative"

    @field_validator("rating")
    @classmethod
    def valid_rating(cls, v: str) -> str:
        if v not in ("helpful", "not_helpful", "inaccurate"):
            raise ValueError("rating 必须是 helpful / not_helpful / inaccurate")
        return v


class AppealRequest(BaseModel):
    event_id: str
    reason: str
    correct_verdict: str = ""  # 用户认为应该是什么判定
    evidence: str = ""         # 用户提供的反证


# =============================================================================
# 反馈提交
# =============================================================================

@router.post("/feedback", status_code=201)
async def submit_feedback(
    req: FeedbackRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """提交对分析结果的反馈"""
    # 验证事件存在
    try:
        event_uid = uuid.UUID(req.event_id)
    except ValueError:
        raise HTTPException(400, "无效的事件 ID")

    event = await db.get(Event, event_uid)
    if not event:
        raise HTTPException(404, "事件不存在")

    feedback = {
        "id": str(uuid.uuid4()),
        "event_id": req.event_id,
        "user_id": str(current_user.id),
        "username": current_user.username,
        "rating": req.rating,
        "comment": req.comment,
        "dimension": req.dimension,
        "event_title": event.title,
        "current_credibility": event.credibility_score,
        "created_at": datetime.utcnow().isoformat(),
        "reviewed": False,
        "reviewed_by": None,
        "review_note": "",
    }

    if req.event_id not in _feedback_store:
        _feedback_store[req.event_id] = []
    _feedback_store[req.event_id].append(feedback)

    return {"id": feedback["id"], "status": "submitted"}


# =============================================================================
# 申诉提交
# =============================================================================

@router.post("/appeal", status_code=201)
async def submit_appeal(
    req: AppealRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """提交对分析判定的申诉"""
    try:
        event_uid = uuid.UUID(req.event_id)
    except ValueError:
        raise HTTPException(400, "无效的事件 ID")

    event = await db.get(Event, event_uid)
    if not event:
        raise HTTPException(404, "事件不存在")

    appeal = {
        "id": str(uuid.uuid4()),
        "event_id": req.event_id,
        "user_id": str(current_user.id),
        "username": current_user.username,
        "reason": req.reason,
        "correct_verdict": req.correct_verdict,
        "evidence": req.evidence,
        "event_title": event.title,
        "engine_verdict": event.engine_analysis.get("verdict") if event.engine_analysis else None,
        "credibility_score": event.credibility_score,
        "status": "pending",  # pending / accepted / rejected
        "reviewed_by": None,
        "review_note": "",
        "created_at": datetime.utcnow().isoformat(),
    }
    _appeal_store.append(appeal)

    return {"id": appeal["id"], "status": "submitted"}


# =============================================================================
# 查询反馈
# =============================================================================

@router.get("/feedback/stats/{event_id}")
async def get_feedback_stats(event_id: str):
    """获取某个事件的反馈统计"""
    feedbacks = _feedback_store.get(event_id, [])
    if not feedbacks:
        return {"event_id": event_id, "total": 0, "helpful": 0, "not_helpful": 0, "inaccurate": 0}

    ratings = {"helpful": 0, "not_helpful": 0, "inaccurate": 0}
    for f in feedbacks:
        ratings[f["rating"]] = ratings.get(f["rating"], 0) + 1

    return {
        "event_id": event_id,
        "total": len(feedbacks),
        **ratings,
    }


# =============================================================================
# 管理员审核队列
# =============================================================================

@router.get("/admin/feedback/queue")
async def get_feedback_queue(
    status: str | None = Query(None, description="筛选: reviewed / unreviewed"),
    limit: int = Query(50, ge=1, le=200),
):
    """管理员获取待审核的反馈列表"""
    all_feedback = []
    for event_id, feedbacks in _feedback_store.items():
        for f in feedbacks:
            f["event_id"] = event_id
            all_feedback.append(f)

    if status == "reviewed":
        all_feedback = [f for f in all_feedback if f.get("reviewed")]
    elif status == "unreviewed":
        all_feedback = [f for f in all_feedback if not f.get("reviewed")]

    all_feedback.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return {
        "total": len(all_feedback),
        "feedbacks": all_feedback[:limit],
    }


@router.get("/admin/appeal/queue")
async def get_appeal_queue(
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """管理员获取待审核的申诉列表"""
    appeals = _appeal_store[:]
    if status:
        appeals = [a for a in appeals if a.get("status") == status]
    appeals.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"total": len(appeals), "appeals": appeals[:limit]}


@router.post("/admin/appeal/{appeal_id}/review")
async def review_appeal(
    appeal_id: str,
    action: str = Query(..., description="accepted / rejected"),
    note: str = Query(""),
):
    """管理员审核申诉"""
    for a in _appeal_store:
        if a["id"] == appeal_id:
            a["status"] = action
            a["reviewed_by"] = "admin"
            a["review_note"] = note
            return {"appeal_id": appeal_id, "status": action}

    raise HTTPException(404, "申诉不存在")


# =============================================================================
# 反馈统计汇总 (管理用)
# =============================================================================

@router.get("/admin/feedback/summary")
async def feedback_summary():
    """反馈全局统计"""
    total = sum(len(v) for v in _feedback_store.values())
    inaccurate = sum(
        sum(1 for f in v if f["rating"] == "inaccurate")
        for v in _feedback_store.values()
    )
    total_appeals = len(_appeal_store)
    pending_appeals = sum(1 for a in _appeal_store if a["status"] == "pending")

    return {
        "total_feedback": total,
        "inaccurate_count": inaccurate,
        "inaccuracy_rate": round(inaccurate / max(1, total) * 100, 1),
        "total_appeals": total_appeals,
        "pending_appeals": pending_appeals,
    }
