import { useEffect, useRef, useState, useCallback } from "react";

const WS_BASE = import.meta.env.VITE_WS_URL
  || (import.meta.env.VITE_API_BASE_URL
    ? import.meta.env.VITE_API_BASE_URL.replace(/^http/, "ws")
    : (typeof window !== "undefined" && window.location.origin.replace(/^http/, "ws"))
    || "ws://localhost:8000");

interface WSMessage {
  type: string;
  [key: string]: any;
}

interface UseWebSocketOptions {
  onMessage?: (msg: WSMessage) => void;
  onTaskProgress?: (taskId: string, progress: string, status: string) => void;
  onTaskComplete?: (taskId: string, result: any) => void;
  onEventUpdate?: (eventId: string, update: any) => void;
  onRumorUpdate?: (data: any) => void;
  autoReconnect?: boolean;
  reconnectInterval?: number;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    onMessage,
    onTaskProgress,
    onTaskComplete,
    onEventUpdate,
    onRumorUpdate,
    autoReconnect = true,
    reconnectInterval = 5000,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const subscribedChannels = useRef<Set<string>>(new Set());

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(`${WS_BASE}/api/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      setError(null);

      // Re-subscribe to all channels
      for (const channel of subscribedChannels.current) {
        ws.send(JSON.stringify({ action: "subscribe", channel }));
      }
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        onMessage?.(msg);

        switch (msg.type) {
          case "task_progress":
            onTaskProgress?.(msg.task_id, msg.progress, msg.status);
            break;
          case "task_complete":
            onTaskComplete?.(msg.task_id, msg.result);
            break;
          case "event_update":
            onEventUpdate?.(msg.event_id, msg);
            break;
          case "rumor_update":
            onRumorUpdate?.(msg);
            break;
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      setConnected(false);
      if (autoReconnect) {
        reconnectTimer.current = setTimeout(connect, reconnectInterval);
      }
    };

    ws.onerror = () => {
      setError("WebSocket connection error");
    };
  }, [onMessage, onTaskProgress, onTaskComplete, onEventUpdate, onRumorUpdate, autoReconnect, reconnectInterval]);

  const disconnect = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
    }
    wsRef.current?.close();
    wsRef.current = null;
    setConnected(false);
    subscribedChannels.current.clear();
  }, []);

  const subscribe = useCallback((channel: string) => {
    subscribedChannels.current.add(channel);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: "subscribe", channel }));
    }
  }, []);

  const unsubscribe = useCallback((channel: string) => {
    subscribedChannels.current.delete(channel);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: "unsubscribe", channel }));
    }
  }, []);

  const send = useCallback((data: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return { connected, error, subscribe, unsubscribe, send, disconnect, connect };
}
