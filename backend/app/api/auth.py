"""
用户认证 API — 注册、登录、个人中心、收藏、订阅
"""

import uuid
from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.base import get_db
from app.models.user import User, UserFavorite, UserSubscription, UserRole
from app.models.event import Event
from app.auth.jwt import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    get_current_user, get_current_active_user,
)

logger = logging.getLogger("truthtrace.auth")
router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """设置 httpOnly 认证 Cookie (防 XSS 窃取)"""
    secure = False  # 开发环境 False; 生产环境通过 Nginx 设置
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=60 * 60 * 24,  # 24 hours
        path="/api",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,  # 30 days
        path="/api/auth",
    )


def _clear_auth_cookies(response: Response):
    """清除认证 Cookie"""
    response.delete_cookie("access_token", path="/api")
    response.delete_cookie("refresh_token", path="/api/auth")


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    display_name: str | None = None

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if len(v) < 3 or len(v) > 64:
            raise ValueError("用户名长度需在 3-64 字符之间")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("用户名只能包含字母、数字、下划线和连字符")
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("密码长度至少 8 位")
        if len(v) > 72:
            raise ValueError("密码长度不能超过 72 位")
        # 强度要求: 至少包含大写字母、小写字母、数字、特殊字符中的三类
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:',.<>?/`~" for c in v)
        score = sum([has_upper, has_lower, has_digit, has_special])
        if score < 3:
            raise ValueError(
                "密码强度不足，需要至少包含以下三类字符: "
                "大写字母、小写字母、数字、特殊字符"
            )
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class UserProfile(BaseModel):
    id: str
    username: str
    email: str
    display_name: str | None
    role: str
    is_verified: bool
    created_at: str


class RefreshRequest(BaseModel):
    refresh_token: str


class FavoriteRequest(BaseModel):
    event_id: str
    note: str | None = None


class SubscriptionRequest(BaseModel):
    event_id: str | None = None
    keyword: str | None = None
    notify_rumor: bool = True
    notify_propagation: bool = True


# ---------------------------------------------------------------------------
# Auth Endpoints
# ---------------------------------------------------------------------------

@router.post("/auth/register", status_code=201)
async def register(
    req: RegisterRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    用户注册

    创建新用户账号，返回 JWT 访问令牌并通过 httpOnly Cookie 持久化。
    """
    # 注册频率限制 (防批量注册)
    from app.middleware.rate_limit import check_register_rate_limit
    client_ip = request.client.host if request.client else "unknown"
    if not check_register_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="注册请求过于频繁，请稍后再试",
        )

    # 检查用户名/邮箱是否已存在
    existing = await db.execute(
        select(User).where(
            (User.username == req.username) | (User.email == req.email)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail="用户名或邮箱已被注册"
        )

    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
        display_name=req.display_name or req.username,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(user.id, user.username, user.role.value)
    refresh_token = create_refresh_token(user.id)

    _set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_to_dict(user),
    )


@router.post("/auth/login")
async def login(
    req: LoginRequest,
    req_obj: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    用户登录

    支持用户名或邮箱登录。返回 JWT 并通过 httpOnly Cookie 持久化。
    频率限制: 每 IP 每 60 秒最多 5 次尝试。
    """
    # 速率限制检查
    from app.middleware.rate_limit import check_login_rate_limit
    client_ip = req_obj.client.host if req_obj.client else "unknown"
    if not check_login_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="登录尝试过于频繁，请 60 秒后重试",
        )

    # 支持用户名或邮箱
    result = await db.execute(
        select(User).where(
            (User.username == req.username) | (User.email == req.username)
        )
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")

    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 更新最后登录时间
    user.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    access_token = create_access_token(user.id, user.username, user.role.value)
    refresh_token = create_refresh_token(user.id)

    _set_auth_cookies(response, access_token, refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=_user_to_dict(user),
    )


@router.post("/auth/logout")
async def logout(response: Response):
    """登出 — 清除 httpOnly Cookie"""
    _clear_auth_cookies(response)
    return {"status": "logged_out"}


@router.post("/auth/refresh")
async def refresh_token_endpoint(
    req: RefreshRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """刷新访问令牌"""
    payload = decode_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="无效的刷新令牌")

    user_id = payload.get("sub")
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="无效的令牌")

    result = await db.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="用户不存在或已禁用")

    access_token = create_access_token(user.id, user.username, user.role.value)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24,
        path="/api",
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/auth/csrf-token")
async def get_csrf_token(
    current_user: User = Depends(get_current_active_user),
):
    """获取 CSRF 保护令牌 (用于 SPA 的追加防护)"""
    from app.security import generate_csrf_token
    token = generate_csrf_token()
    return {"csrf_token": token}


# ---------------------------------------------------------------------------
# User Profile
# ---------------------------------------------------------------------------

@router.get("/auth/me")
async def get_profile(
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    """获取当前用户信息 (支持 Cookie 或 Bearer 认证)"""
    user_data = _user_to_dict(current_user)
    # 如果认证是通过 Cookie 完成的, 返回新的 access_token 供前端 Bearer 认证使用
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        access_token = create_access_token(
            current_user.id, current_user.username, current_user.role.value
        )
        return {"user": user_data, "access_token": access_token}
    return {"user": user_data}


@router.get("/auth/me/favorites")
async def get_favorites(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的收藏列表"""
    result = await db.execute(
        select(UserFavorite)
        .where(UserFavorite.user_id == current_user.id)
        .order_by(UserFavorite.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    favorites = result.scalars().all()

    # 批量获取关联事件
    event_ids = [f.event_id for f in favorites]
    events_map: dict = {}
    if event_ids:
        ev_result = await db.execute(
            select(Event).where(Event.id.in_(event_ids))
        )
        events_map = {e.id: e for e in ev_result.scalars().all()}

    count_result = await db.execute(
        select(func.count(UserFavorite.id)).where(
            UserFavorite.user_id == current_user.id
        )
    )
    total = count_result.scalar() or 0

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "favorites": [
            {
                "id": str(fav.id),
                "event_id": str(fav.event_id),
                "note": fav.note,
                "event": {
                    "id": str(events_map[fav.event_id].id),
                    "title": events_map[fav.event_id].title,
                    "credibility_score": events_map[fav.event_id].credibility_score,
                    "status": events_map[fav.event_id].status.value,
                } if fav.event_id in events_map else None,
                "created_at": fav.created_at.isoformat() if fav.created_at else None,
            }
            for fav in favorites
        ],
    }


@router.post("/auth/me/favorites", status_code=201)
async def add_favorite(
    req: FavoriteRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """添加事件到收藏"""
    try:
        event_uid = uuid.UUID(req.event_id)
    except ValueError:
        raise HTTPException(400, "无效的事件 ID")

    # 检查事件存在
    event = await db.get(Event, event_uid)
    if not event:
        raise HTTPException(404, "事件不存在")

    # 检查是否已收藏
    existing = await db.execute(
        select(UserFavorite).where(
            and_(
                UserFavorite.user_id == current_user.id,
                UserFavorite.event_id == event_uid,
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "已收藏过该事件")

    fav = UserFavorite(
        user_id=current_user.id,
        event_id=event_uid,
        note=req.note,
    )
    db.add(fav)
    await db.commit()
    await db.refresh(fav)

    return {"id": str(fav.id), "event_id": str(fav.event_id), "status": "created"}


@router.delete("/auth/me/favorites/{event_id}")
async def remove_favorite(
    event_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """取消收藏"""
    try:
        event_uid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(400, "无效的事件 ID")

    result = await db.execute(
        select(UserFavorite).where(
            and_(
                UserFavorite.user_id == current_user.id,
                UserFavorite.event_id == event_uid,
            )
        )
    )
    fav = result.scalar_one_or_none()
    if not fav:
        raise HTTPException(404, "未收藏该事件")

    await db.delete(fav)
    await db.commit()
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

@router.get("/auth/me/subscriptions")
async def get_subscriptions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的订阅列表"""
    result = await db.execute(
        select(UserSubscription)
        .where(
            and_(
                UserSubscription.user_id == current_user.id,
                UserSubscription.is_active == True,
            )
        )
        .order_by(UserSubscription.created_at.desc())
    )
    subs = result.scalars().all()

    return {
        "subscriptions": [
            {
                "id": str(s.id),
                "event_id": str(s.event_id) if s.event_id else None,
                "keyword": s.keyword,
                "notify_rumor": s.notify_rumor,
                "notify_propagation": s.notify_propagation,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in subs
        ],
    }


@router.post("/auth/me/subscriptions", status_code=201)
async def create_subscription(
    req: SubscriptionRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """创建订阅"""
    if not req.event_id and not req.keyword:
        raise HTTPException(400, "请指定 event_id 或 keyword")

    sub = UserSubscription(
        user_id=current_user.id,
        keyword=req.keyword,
        notify_rumor=req.notify_rumor,
        notify_propagation=req.notify_propagation,
        is_active=True,
    )
    if req.event_id:
        try:
            sub.event_id = uuid.UUID(req.event_id)
        except ValueError:
            raise HTTPException(400, "无效的事件 ID")

    db.add(sub)
    await db.commit()
    await db.refresh(sub)

    return {"id": str(sub.id), "status": "created"}


@router.delete("/auth/me/subscriptions/{sub_id}")
async def cancel_subscription(
    sub_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """取消订阅"""
    try:
        uid = uuid.UUID(sub_id)
    except ValueError:
        raise HTTPException(400, "无效的订阅 ID")

    result = await db.execute(
        select(UserSubscription).where(
            and_(
                UserSubscription.id == uid,
                UserSubscription.user_id == current_user.id,
            )
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        raise HTTPException(404, "订阅不存在")

    sub.is_active = False
    await db.commit()
    return {"status": "cancelled"}


# ---------------------------------------------------------------------------
# Helpers

# ---------------------------------------------------------------------------
# 通知端点
# ---------------------------------------------------------------------------

@router.get("/auth/me/notifications")
async def get_notifications(
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
):
    """获取当前用户的通知列表"""
    from app.notifications.notification_service import get_user_notifications, get_unread_count
    notifications = get_user_notifications(str(current_user.id), limit, unread_only)
    return {
        "unread_count": get_unread_count(str(current_user.id)),
        "notifications": [n.to_dict() for n in notifications],
    }


@router.post("/auth/me/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """标记通知为已读"""
    from app.notifications.notification_service import mark_as_read
    mark_as_read(str(current_user.id), notification_id)
    return {"status": "read"}


@router.post("/auth/me/notifications/read-all")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_active_user),
):
    """标记所有通知为已读"""
    from app.notifications.notification_service import mark_all_read
    mark_all_read(str(current_user.id))
    return {"status": "all_read"}


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------

def _user_to_dict(user: User) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role.value,
        "is_verified": user.is_verified,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
