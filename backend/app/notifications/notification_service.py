"""
订阅通知系统 — 将引擎分析结果与用户订阅匹配，生成多渠道通知

通知渠道: 应用内通知 / WebSocket 实时推送 / 邮件 (可选)
"""

from __future__ import annotations
import uuid
import logging
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger("truthtrace.notifications")


# =============================================================================
# 通知类型
# =============================================================================

@dataclass
class Notification:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    type: str = ""           # rumor_update / propagation_update / narrative_alert / event_match
    title: str = ""
    body: str = ""
    event_id: str | None = None
    data: dict = field(default_factory=dict)
    read: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "body": self.body,
            "event_id": self.event_id,
            "data": self.data,
            "read": self.read,
            "created_at": self.created_at.isoformat(),
        }


# 内存存储 (生产环境应使用数据库)
_notification_store: dict[str, list[Notification]] = {}  # user_id → [Notification]


# =============================================================================
# 匹配引擎
# =============================================================================

async def match_and_notify(
    event_id: str,
    event_title: str,
    engine_analysis: dict,
    event_keywords: list[str] | None = None,
) -> int:
    """
    将新的事件分析结果与所有用户的订阅进行匹配，生成通知。

    返回生成的用户通知总数。
    """
    try:
        from app.models.user import UserSubscription, User
        from app.models.base import async_session_factory
        from sqlalchemy import select, and_

        # 获取所有活跃订阅
        async with async_session_factory() as session:
            stmt = select(UserSubscription).where(
                and_(UserSubscription.is_active == True)
            )
            result = await session.execute(stmt)
            subscriptions = result.scalars().all()

            notified = 0
            for sub in subscriptions:
                matched = False
                match_reason = ""

                # 精确事件匹配
                if sub.event_id and str(sub.event_id) == event_id:
                    matched = True
                    match_reason = f"你订阅的事件「{event_title}」有更新"

                # 关键词匹配
                elif sub.keyword and event_keywords:
                    if any(sub.keyword.lower() in kw.lower() for kw in event_keywords):
                        matched = True
                        match_reason = f"关键词「{sub.keyword}」匹配到新事件「{event_title}」"

                # 全局谣言通知
                elif not sub.event_id and not sub.keyword:
                    verdict = engine_analysis.get("verdict", "")
                    if verdict in ("false", "likely_false", "misleading") and sub.notify_rumor:
                        matched = True
                        match_reason = f"检测到新的谣言/误导信息「{event_title}」"

                if matched:
                    await _create_notification(
                        user_id=str(sub.user_id),
                        event_id=event_id,
                        match_reason=match_reason,
                        engine_analysis=engine_analysis,
                    )
                    notified += 1

            return notified
    except Exception as e:
        logger.warning(f"通知匹配失败 (非致命): {e}")
        return 0


async def _create_notification(
    user_id: str,
    event_id: str,
    match_reason: str,
    engine_analysis: dict,
):
    """创建通知并推送到 WebSocket"""
    verdict = engine_analysis.get("verdict", "unknown")
    score = engine_analysis.get("credibility_score", 50)

    icon = "🛡️" if score >= 60 else "⚠️" if score >= 40 else "🚨"

    notification = Notification(
        user_id=user_id,
        type="event_match",
        title=f"{icon} {match_reason}",
        body=f"可信度评分: {score}/100, 判定: {verdict}",
        event_id=event_id,
        data={
            "verdict": verdict,
            "credibility_score": score,
            "url": f"/events/{event_id}",
        },
    )

    # 存储
    if user_id not in _notification_store:
        _notification_store[user_id] = []
    _notification_store[user_id].insert(0, notification)
    # 限制最多保留100条
    if len(_notification_store[user_id]) > 100:
        _notification_store[user_id] = _notification_store[user_id][:100]

    # WebSocket 推送
    try:
        from app.api.ws import manager as ws_manager
        await ws_manager.publish(f"user:{user_id}", {
            "type": "notification",
            "notification": notification.to_dict(),
        })
    except Exception:
        pass


# =============================================================================
# 查询接口
# =============================================================================

def get_user_notifications(user_id: str, limit: int = 20, unread_only: bool = False) -> list[Notification]:
    """获取指定用户的通知列表"""
    notifications = _notification_store.get(user_id, [])
    if unread_only:
        notifications = [n for n in notifications if not n.read]
    return notifications[:limit]


def mark_as_read(user_id: str, notification_id: str):
    """标记通知为已读"""
    for n in _notification_store.get(user_id, []):
        if n.id == notification_id:
            n.read = True
            return


def mark_all_read(user_id: str):
    """标记所有通知为已读"""
    for n in _notification_store.get(user_id, []):
        n.read = True


def get_unread_count(user_id: str) -> int:
    return sum(1 for n in _notification_store.get(user_id, []) if not n.read)


# =============================================================================
# 叙事告警通知
# =============================================================================

async def notify_narrative_alert(alert: dict):
    """向所有订阅了全局通知的用户推送叙事告警"""
    try:
        from app.models.user import UserSubscription
        from app.models.base import async_session_factory
        from sqlalchemy import select, and_

        async with async_session_factory() as session:
            stmt = select(UserSubscription).where(
                and_(UserSubscription.is_active == True, UserSubscription.event_id.is_(None))
            )
            result = await session.execute(stmt)
            subscriptions = result.scalars().all()

            for sub in subscriptions:
                notification = Notification(
                    user_id=str(sub.user_id),
                    type="narrative_alert",
                    title=f"🚨 叙事告警: {alert.get('title', '')}",
                    body=alert.get("description", ""),
                    data=alert,
                )
                if str(sub.user_id) not in _notification_store:
                    _notification_store[str(sub.user_id)] = []
                _notification_store[str(sub.user_id)].insert(0, notification)

                # WebSocket
                try:
                    from app.api.ws import manager as ws_manager
                    await ws_manager.publish(f"user:{sub.user_id}", {
                        "type": "notification",
                        "notification": notification.to_dict(),
                    })
                except Exception:
                    pass

    except Exception as e:
        logger.debug(f"叙事告警通知跳过: {e}")
