"""
WebSocket 实时推送端点 — 任务进度、事件更新、辟谣通知

协议：
- 客户端连接后发送 JSON 消息订阅频道
- 服务端实时推送进度更新

频道格式：
- task:{task_id} — 任务进度
- event:{event_id} — 事件更新
- rumors — 辟谣报告更新（全局）
"""

import json
import asyncio
import logging
from typing import Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

logger = logging.getLogger("truthtrace.ws")
router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器 — 频道订阅模式"""

    def __init__(self):
        # channel -> set of WebSocket connections
        self._channels: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()

    async def disconnect(self, ws: WebSocket):
        """从所有频道移除连接"""
        async with self._lock:
            for channel in list(self._channels.keys()):
                conns = self._channels.get(channel)
                if conns:
                    conns.discard(ws)
                    if not conns:
                        del self._channels[channel]

    async def subscribe(self, ws: WebSocket, channel: str):
        """订阅频道"""
        async with self._lock:
            if channel not in self._channels:
                self._channels[channel] = set()
            self._channels[channel].add(ws)

    async def unsubscribe(self, ws: WebSocket, channel: str):
        """退订频道"""
        async with self._lock:
            conns = self._channels.get(channel)
            if conns:
                conns.discard(ws)
                if not conns:
                    del self._channels[channel]

    async def publish(self, channel: str, data: dict[str, Any]):
        """向频道的所有订阅者推送消息"""
        async with self._lock:
            conns = self._channels.get(channel, set()).copy()

        if not conns:
            return

        message = json.dumps(data, ensure_ascii=False, default=str)
        dead: list[WebSocket] = []

        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                conns = self._channels.get(channel, set())
                for ws in dead:
                    conns.discard(ws)
                if not conns and channel in self._channels:
                    del self._channels[channel]

    @property
    def channel_count(self) -> int:
        return len(self._channels)

    @property
    def connection_count(self) -> int:
        all_ws = set()
        for conns in self._channels.values():
            all_ws.update(conns)
        return len(all_ws)


# 全局连接管理器
manager = ConnectionManager()


# --- 便捷推送函数 (供其他模块调用) ---

async def notify_task_progress(task_id: str, progress: str, status: str = "STARTED"):
    """推送任务进度更新"""
    await manager.publish(f"task:{task_id}", {
        "type": "task_progress",
        "task_id": task_id,
        "progress": progress,
        "status": status,
    })


async def notify_task_complete(task_id: str, result: dict):
    """推送任务完成"""
    await manager.publish(f"task:{task_id}", {
        "type": "task_complete",
        "task_id": task_id,
        "result": result,
    })


async def notify_event_update(event_id: str, update: dict):
    """推送事件更新"""
    await manager.publish(f"event:{event_id}", {
        "type": "event_update",
        "event_id": event_id,
        **update,
    })


async def notify_rumor_update(rumor_data: dict):
    """推送辟谣报告更新"""
    await manager.publish("rumors", {
        "type": "rumor_update",
        **rumor_data,
    })


# --- WebSocket 端点 ---

@router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket,
    token: str = Query(None, description="JWT 令牌（可选）"),
):
    """
    WebSocket 实时推送端点

    客户端连接后发送 JSON 控制消息：
    - {"action": "subscribe", "channel": "task:<id>"}
    - {"action": "subscribe", "channel": "event:<id>"}
    - {"action": "subscribe", "channel": "rumors"}
    - {"action": "unsubscribe", "channel": "..."}
    - {"action": "ping"}

    服务端推送格式：
    - {"type": "task_progress", "task_id": "...", "progress": "...", "status": "..."}
    - {"type": "task_complete", "task_id": "...", "result": {...}}
    - {"type": "event_update", "event_id": "...", ...}
    - {"type": "rumor_update", ...}
    - {"type": "pong"}
    """
    await manager.connect(ws)
    subscribed: set[str] = set()

    try:
        # 发送欢迎消息
        await ws.send_json({
            "type": "connected",
            "message": "已连接到 TruthTrace 实时推送",
            "channels": list(manager._channels.keys()),
        })

        while True:
            try:
                raw = await ws.receive_text()
            except WebSocketDisconnect:
                break

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "无效的 JSON"})
                continue

            action = msg.get("action", "")

            if action == "subscribe":
                channel = msg.get("channel", "")
                if channel:
                    await manager.subscribe(ws, channel)
                    subscribed.add(channel)
                    await ws.send_json({
                        "type": "subscribed",
                        "channel": channel,
                    })

            elif action == "unsubscribe":
                channel = msg.get("channel", "")
                if channel:
                    await manager.unsubscribe(ws, channel)
                    subscribed.discard(channel)
                    await ws.send_json({
                        "type": "unsubscribed",
                        "channel": channel,
                    })

            elif action == "ping":
                await ws.send_json({"type": "pong"})

            else:
                await ws.send_json({
                    "type": "error",
                    "message": f"未知的操作: {action}",
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # 清理所有订阅
        for channel in list(subscribed):
            await manager.unsubscribe(ws, channel)
        await manager.disconnect(ws)


@router.get("/ws/stats")
async def ws_stats():
    """WebSocket 连接统计"""
    return {
        "connections": manager.connection_count,
        "channels": manager.channel_count,
    }
