"""
协作众包验证 API -- 专家验证/信誉系统/悬赏求证/贡献排行榜
"人工智能 + 人群智慧" = 更高准确率的辟谣
"""

import uuid
import random
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, field_validator

from app.auth.jwt import get_current_active_user, get_current_user
from app.models.user import User

router = APIRouter()

# =============================================================================
# 数据模型
# =============================================================================

class ExpertApplication(BaseModel):
    domain: str  # medicine/food_safety/journalism/data_science/law/environment
    credentials: str  # 资历描述
    proof_url: str = ""  # 证明材料链接

    @field_validator("domain")
    @classmethod
    def valid_domain(cls, v: str) -> str:
        valid = {"medicine", "food_safety", "journalism", "data_science", "law", "environment", "education"}
        if v not in valid:
            raise ValueError(f"领域必须是: {', '.join(valid)}")
        return v


class ExpertVerification(BaseModel):
    verdict: str  # confirmed/likely_true/misleading/likely_false/false/unverifiable
    evidence_links: list[str] = []
    notes: str = ""


class BountyRequest(BaseModel):
    url: str
    question: str
    reward_points: int = 50

    @field_validator("reward_points")
    @classmethod
    def valid_reward(cls, v: int) -> int:
        if v < 10 or v > 500:
            raise ValueError("悬赏积分需在 10-500 之间")
        return v

    @field_validator("url")
    @classmethod
    def valid_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL 必须以 http:// 或 https:// 开头")
        return v


class BountySubmission(BaseModel):
    findings: str
    evidence_urls: list[str] = []
    verdict: str = ""


# =============================================================================
# 内存存储
# =============================================================================

_expert_applications: list[dict] = []
_verified_experts: dict[str, dict] = {}  # user_id -> {domain, credentials, verified_at, total_verifications}
_expert_verifications: list[dict] = []  # [{event_id, expert_id, verdict, evidence, notes, at}]
_reputation: dict[str, dict] = {}  # user_id -> {score, level, contributions, upvotes, downvotes}
_bounties: list[dict] = []  # [{id, creator_id, url, question, reward, status(open/claimed/completed/awarded), ...}]
_contributions: list[dict] = []  # [{user_id, type, event_id, points, at}]

EXPERT_DOMAINS = {
    "medicine": "医学健康",
    "food_safety": "食品安全",
    "journalism": "新闻传播",
    "data_science": "数据科学",
    "law": "法律法规",
    "environment": "环境科学",
    "education": "教育",
}

REPUTATION_LEVELS = [
    (0, "Novice", "新手"),
    (100, "Contributor", "贡献者"),
    (500, "Expert", "专家"),
    (2000, "Master", "大师"),
    (5000, "Grandmaster", "宗师"),
]


def _get_level(score: int) -> dict:
    for threshold, level_en, level_cn in reversed(REPUTATION_LEVELS):
        if score >= threshold:
            nxt = threshold * 2 if threshold > 0 else 100
            return {"level_en": level_en, "level_cn": level_cn, "next_threshold": nxt}
    return {"level_en": "Novice", "level_cn": "新手", "next_threshold": 100}


def _add_reputation(user_id: str, username: str, points: int, reason: str):
    if user_id not in _reputation:
        _reputation[user_id] = {"score": 100, "username": username, "upvotes": 0, "downvotes": 0, "history": []}
    rep = _reputation[user_id]
    rep["score"] = max(0, rep["score"] + points)
    rep["history"].append({"points": points, "reason": reason, "at": datetime.now(timezone.utc).isoformat()})
    # 保持历史记录在合理范围
    if len(rep["history"]) > 100:
        rep["history"] = rep["history"][-50:]


# =============================================================================
# 社区数据存储 (内存, 等待数据库模型迁移)
# 不再预置虚假样例数据——首次使用时为空,用户通过POST端点提交数据后自然积累。
# =============================================================================


# =============================================================================
# 端点: 专家验证
# =============================================================================

@router.post("/community/expert/apply")
async def apply_expert(
    req: ExpertApplication,
    current_user: User = Depends(get_current_active_user),
):
    """申请成为领域验证者"""
    user_id = str(current_user.id)

    # 检查是否已是专家
    if user_id in _verified_experts:
        raise HTTPException(409, "您已经是认证专家")

    # 检查是否已有待处理申请
    for app in _expert_applications:
        if app["user_id"] == user_id and app["status"] == "pending":
            raise HTTPException(409, "您已有待审核的申请")

    application = {
        "id": str(uuid.uuid4())[:8],
        "user_id": user_id,
        "username": current_user.username,
        "domain": req.domain,
        "credentials": req.credentials,
        "proof_url": req.proof_url,
        "status": "pending",
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_at": None,
    }
    _expert_applications.append(application)

    return {
        "status": "submitted",
        "application_id": application["id"],
        "message": f"您的{EXPERT_DOMAINS.get(req.domain, req.domain)}领域专家申请已提交,审核通常需要1-3个工作日。",
    }


@router.get("/community/expert/queue")
async def expert_verification_queue(
    domain: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_active_user),
):
    """待验证事件队列(给专家)"""
    user_id = str(current_user.id)

    # 检查是否是专家
    is_expert = user_id in _verified_experts
    expert_domain = _verified_experts.get(user_id, {}).get("domain")

    # 从态势感知获取热点事件
    from app.api.situational import _generate_hotspot_events
    events = _generate_hotspot_events()

    if domain:
        events = [e for e in events if domain in e.get("narrative_type", "")]

    if is_expert:
        # 专家看到自己领域的优先
        if expert_domain:
            events.sort(key=lambda e: 0 if expert_domain in e.get("narrative_type", "") else 1)

    queue = []
    for e in events[:limit]:
        # 检查是否已被验证
        verified = any(v["event_id"] == e["event_id"] for v in _expert_verifications)
        queue.append({
            "event_id": e["event_id"],
            "title": e["title"],
            "credibility_score": e["credibility_score"],
            "narrative_type": e["narrative_type"],
            "first_seen_at": e["first_seen_at"],
            "already_verified": verified,
            "expert_verifications_count": sum(1 for v in _expert_verifications if v["event_id"] == e["event_id"]),
        })

    return {
        "queue": queue,
        "is_expert": is_expert,
        "expert_domain": expert_domain,
        "domain_name": EXPERT_DOMAINS.get(expert_domain, "") if expert_domain else "",
        "total_pending": len([e for e in queue if not e["already_verified"]]),
    }


@router.post("/community/expert/verify/{event_id}")
async def expert_verify_event(
    event_id: str,
    req: ExpertVerification,
    current_user: User = Depends(get_current_active_user),
):
    """专家提交验证结果"""
    user_id = str(current_user.id)

    if user_id not in _verified_experts:
        raise HTTPException(403, "只有认证专家才能验证事件")

    expert = _verified_experts[user_id]

    verification = {
        "event_id": event_id,
        "expert_id": user_id,
        "expert_name": expert["username"],
        "expert_domain": expert["domain"],
        "verdict": req.verdict,
        "evidence_links": req.evidence_links,
        "notes": req.notes,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    _expert_verifications.append(verification)
    expert["total_verifications"] += 1

    # 信誉加分
    _add_reputation(user_id, expert["username"], 10, f"验证事件 {event_id}")
    _contributions.append({
        "user_id": user_id,
        "username": expert["username"],
        "type": "expert_verification",
        "event_id": event_id,
        "points": 10,
        "at": datetime.now(timezone.utc).isoformat(),
    })
    if len(_contributions) > 5000:
        _contributions[:] = _contributions[-3000:]

    return {
        "status": "verified",
        "verification": verification,
        "expert_total_verifications": expert["total_verifications"],
    }


@router.get("/community/expert/{user_id}/stats")
async def expert_stats(user_id: str):
    """专家贡献统计"""
    expert = _verified_experts.get(user_id)
    if not expert:
        raise HTTPException(404, "该用户不是认证专家")

    verifications = [v for v in _expert_verifications if v["expert_id"] == user_id]
    verdict_counts = {}
    for v in verifications:
        verdict_counts[v["verdict"]] = verdict_counts.get(v["verdict"], 0) + 1

    rep = _reputation.get(user_id, {"score": 100, "username": expert["username"]})
    level = _get_level(rep["score"])

    return {
        "user_id": user_id,
        "username": expert["username"],
        "domain": EXPERT_DOMAINS.get(expert["domain"], expert["domain"]),
        "total_verifications": len(verifications),
        "verdict_distribution": verdict_counts,
        "reputation_score": rep["score"],
        "level": level,
        "recent_verifications": verifications[-10:],
        "verified_since": expert["verified_at"],
    }


# =============================================================================
# 端点: 信誉系统
# =============================================================================

@router.get("/community/reputation/{user_id}")
async def get_reputation(user_id: str):
    """用户信誉分+等级"""
    rep = _reputation.get(user_id)
    if not rep:
        rep = {"score": 0, "username": "未知用户", "upvotes": 0, "downvotes": 0, "history": []}

    level = _get_level(rep["score"])
    contributions_count = len([c for c in _contributions if c["user_id"] == user_id])

    return {
        "user_id": user_id,
        "username": rep["username"],
        "score": rep["score"],
        "level": level["level_en"],
        "level_cn": level["level_cn"],
        "next_threshold": level["next_threshold"],
        "progress_pct": round(rep["score"] / max(level["next_threshold"], 1) * 100, 1),
        "upvotes": rep["upvotes"],
        "downvotes": rep["downvotes"],
        "total_contributions": contributions_count,
        "badges": _get_badges(rep["score"], contributions_count),
        "recent_history": rep.get("history", [])[-10:],
    }


def _get_badges(score: int, contributions: int) -> list[dict]:
    badges = []
    if score >= 100:
        badges.append({"id": "first-100", "name": "百尺竿头", "icon": "🌟"})
    if score >= 500:
        badges.append({"id": "expert-500", "name": "领域专家", "icon": "🎖️"})
    if score >= 2000:
        badges.append({"id": "master-2000", "name": "辟谣大师", "icon": "👑"})
    if contributions >= 10:
        badges.append({"id": "contributor-10", "name": "十次贡献", "icon": "💪"})
    if contributions >= 50:
        badges.append({"id": "contributor-50", "name": "五十次贡献", "icon": "🔥"})
    return badges


@router.post("/community/reputation/{user_id}/upvote")
async def upvote_user(
    user_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """赞一个用户的贡献"""
    if user_id not in _reputation:
        raise HTTPException(404, "用户不存在")
    _reputation[user_id]["upvotes"] += 1
    _reputation[user_id]["score"] += 2
    return {"status": "upvoted", "new_score": _reputation[user_id]["score"]}


# =============================================================================
# 端点: 悬赏求证
# =============================================================================

@router.post("/community/bounty")
async def create_bounty(
    req: BountyRequest,
    current_user: User = Depends(get_current_active_user),
):
    """发布悬赏"""
    user_id = str(current_user.id)

    # 检查积分是否足够
    rep = _reputation.get(user_id, {"score": 0})
    if rep["score"] < req.reward_points:
        raise HTTPException(400, f"积分不足。需要 {req.reward_points} 积分,当前有 {rep['score']} 积分。")

    bounty = {
        "id": f"bounty-{str(uuid.uuid4())[:8]}",
        "creator_id": user_id,
        "creator_name": current_user.username,
        "url": req.url,
        "question": req.question,
        "reward_points": req.reward_points,
        "status": "open",
        "claimed_by": None,
        "submission": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _bounties.append(bounty)

    # 冻结积分
    _add_reputation(user_id, current_user.username, -req.reward_points, f"发布悬赏: {req.question[:30]}...")

    return {
        "status": "created",
        "bounty": bounty,
        "remaining_points": _reputation.get(user_id, {}).get("score", 0),
    }


@router.get("/community/bounties")
async def list_bounties(
    status: str | None = Query(None, description="open/claimed/completed/awarded"),
    limit: int = Query(20, ge=1, le=50),
):
    """悬赏列表"""
    bounties = _bounties
    if status:
        bounties = [b for b in bounties if b["status"] == status]

    # 按创建时间倒序
    bounties.sort(key=lambda b: b["created_at"], reverse=True)

    return {
        "bounties": bounties[:limit],
        "total": len(bounties),
        "open_count": sum(1 for b in _bounties if b["status"] == "open"),
        "total_reward_available": sum(b["reward_points"] for b in _bounties if b["status"] == "open"),
    }


@router.post("/community/bounty/{bounty_id}/claim")
async def claim_bounty(
    bounty_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """认领悬赏"""
    for b in _bounties:
        if b["id"] == bounty_id:
            if b["status"] != "open":
                raise HTTPException(400, f"悬赏状态为 {b['status']},无法认领")
            if b["creator_id"] == str(current_user.id):
                raise HTTPException(400, "不能认领自己发布的悬赏")
            b["status"] = "claimed"
            b["claimed_by"] = str(current_user.id)
            b["claimed_by_name"] = current_user.username
            b["claimed_at"] = datetime.now(timezone.utc).isoformat()
            return {"status": "claimed", "bounty": b}
    raise HTTPException(404, "悬赏不存在")


@router.post("/community/bounty/{bounty_id}/submit")
async def submit_bounty_findings(
    bounty_id: str,
    req: BountySubmission,
    current_user: User = Depends(get_current_active_user),
):
    """提交求证结果"""
    for b in _bounties:
        if b["id"] == bounty_id:
            if b["claimed_by"] != str(current_user.id):
                raise HTTPException(403, "您未认领此悬赏")
            if b["status"] != "claimed":
                raise HTTPException(400, f"悬赏状态为 {b['status']}")
            b["submission"] = {
                "findings": req.findings,
                "evidence_urls": req.evidence_urls,
                "verdict": req.verdict,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }
            b["status"] = "completed"
            return {"status": "submitted", "bounty": b}
    raise HTTPException(404, "悬赏不存在")


@router.post("/community/bounty/{bounty_id}/award")
async def award_bounty(
    bounty_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """确认并支付悬赏积分"""
    for b in _bounties:
        if b["id"] == bounty_id:
            if b["creator_id"] != str(current_user.id):
                raise HTTPException(403, "只有悬赏发布者可以确认")
            if b["status"] != "completed":
                raise HTTPException(400, "悬赏尚未提交结果")
            b["status"] = "awarded"
            # 支付给完成者
            if b["claimed_by"]:
                _add_reputation(b["claimed_by"], b.get("claimed_by_name", ""), b["reward_points"], f"完成悬赏: {b['question'][:30]}...")
                _contributions.append({
                    "user_id": b["claimed_by"],
                    "username": b.get("claimed_by_name", ""),
                    "type": "bounty_completed",
                    "event_id": bounty_id,
                    "points": b["reward_points"],
                    "at": datetime.now(timezone.utc).isoformat(),
                })
                if len(_contributions) > 5000:
                    _contributions[:] = _contributions[-3000:]
            return {"status": "awarded", "bounty": b}
    raise HTTPException(404, "悬赏不存在")


# =============================================================================
# 端点: 贡献排行榜
# =============================================================================

@router.get("/community/leaderboard")
async def contribution_leaderboard(period: str = Query("weekly")):
    """多维度贡献排行榜"""
    now = datetime.now(timezone.utc)

    if period == "weekly":
        cutoff = now - timedelta(days=7)
    elif period == "monthly":
        cutoff = now - timedelta(days=30)
    elif period == "all":
        cutoff = datetime(2000, 1, 1)
    else:
        cutoff = now - timedelta(days=7)  # default to weekly

    # 过滤时间段内的贡献
    period_contributions = [
        c for c in _contributions
        if datetime.fromisoformat(c["at"]) >= cutoff
    ]

    # 按维度计算排行
    def rank_by(type_filter: str) -> list[dict]:
        filtered = [c for c in period_contributions if type_filter in c["type"]]
        user_stats: dict[str, dict] = {}
        for c in filtered:
            uid = c["user_id"]
            if uid not in user_stats:
                user_stats[uid] = {"user_id": uid, "username": c.get("username", ""), "count": 0, "total_points": 0}
            user_stats[uid]["count"] += 1
            user_stats[uid]["total_points"] += c.get("points", 0)
        return sorted(user_stats.values(), key=lambda x: x["count"], reverse=True)[:20]

    # 总体排行(按信誉分)
    all_ranked = sorted(
        [{"user_id": k, "username": v.get("username", ""), "score": v.get("score", 0)} for k, v in _reputation.items()],
        key=lambda x: x["score"], reverse=True,
    )[:20]

    return {
        "period": period,
        "overall_by_reputation": all_ranked,
        "by_verifications": rank_by("expert_verification"),
        "by_bounties": rank_by("bounty_completed"),
        "total_contributors": len(set(c["user_id"] for c in period_contributions)),
        "total_contributions_this_period": len(period_contributions),
        "updated_at": now.isoformat(),
    }
