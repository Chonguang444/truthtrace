"""
用户模型 — JWT 认证、收藏、订阅
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String, Text, Integer, Float, Boolean,
    DateTime, ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid as SA_Uuid
import enum

from app.models.base import Base


class UserRole(str, enum.Enum):
    USER = "user"
    ANALYST = "analyst"
    ADMIN = "admin"


class User(Base):
    """用户表"""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid, primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole), default=UserRole.USER
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    display_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    # 关系
    favorites: Mapped[list["UserFavorite"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["UserSubscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.username}>"


class UserFavorite(Base):
    """用户收藏 — 收藏感兴趣的事件"""
    __tablename__ = "user_favorites"

    id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid, ForeignKey("events.id", ondelete="CASCADE"), index=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # 关系
    user: Mapped["User"] = relationship(back_populates="favorites")

    def __repr__(self):
        return f"<Favorite user={self.user_id} event={self.event_id}>"


class UserSubscription(Base):
    """用户订阅 — 订阅事件更新通知"""
    __tablename__ = "user_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        SA_Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        SA_Uuid, ForeignKey("events.id", ondelete="CASCADE"),
        nullable=True, index=True,
        comment="订阅特定事件，NULL 表示全局订阅"
    )
    keyword: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True,
        comment="订阅关键词，匹配新事件"
    )
    notify_rumor: Mapped[bool] = mapped_column(
        Boolean, default=True,
        comment="辟谣报告更新时通知"
    )
    notify_propagation: Mapped[bool] = mapped_column(
        Boolean, default=True,
        comment="传播链路更新时通知"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # 关系
    user: Mapped["User"] = relationship(back_populates="subscriptions")

    def __repr__(self):
        return f"<Subscription user={self.user_id} keyword={self.keyword}>"
