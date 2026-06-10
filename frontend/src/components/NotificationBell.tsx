/**
 * 通知铃铛 — NavBar 实时通知
 * WebSocket 实时接收 + 下拉通知列表
 */

import { useState, useEffect, useCallback } from "react";
import { Bell, BellRing, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";
import { useWebSocket } from "../hooks/useWebSocket";

interface Notification {
  id: string; type: string; title: string; body: string;
  event_id?: string; read: boolean; created_at: string;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export function NotificationBell() {
  const { isAuthenticated, getAuthHeaders } = useAuth();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  // Fetch initial notifications
  useEffect(() => {
    if (!isAuthenticated) return;
    setLoading(true);
    const headers = getAuthHeaders();
    fetch(`${API_BASE}/api/auth/me/notifications?limit=10`, { headers })
      .then(r => r.json())
      .then(d => { setNotifications(d.notifications || []); setLoading(false); })
      .catch(() => setLoading(false));
  }, [isAuthenticated]);

  // WebSocket real-time
  const onNotification = useCallback((notif: any) => {
    setNotifications(prev => [notif, ...prev].slice(0, 50));
  }, []);

  const { connected } = useWebSocket({
    onMessage: (msg) => {
      if (msg.type === "notification") onNotification(msg.notification);
    },
  });

  const markAllRead = async () => {
    const headers = getAuthHeaders();
    await fetch(`${API_BASE}/api/auth/me/notifications/read-all`, { method: "POST", headers });
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
  };

  const unread = notifications.filter(n => !n.read).length;

  if (!isAuthenticated) return null;

  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} className="relative p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
        {unread > 0 ? <BellRing className="h-4 w-4 text-primary" /> : <Bell className="h-4 w-4" />}
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 h-4.5 w-4.5 rounded-full bg-red-500 text-white text-[9px] font-bold flex items-center justify-center leading-none">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-2 w-80 rounded-xl border bg-card shadow-xl z-50 overflow-hidden">
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <span className="text-sm font-semibold">通知 {connected ? "🟢" : "⚪"}</span>
              {unread > 0 && (
                <button onClick={markAllRead} className="text-[11px] text-primary hover:underline">全部已读</button>
              )}
            </div>
            <div className="max-h-72 overflow-y-auto">
              {loading && <div className="p-6 text-center text-sm text-muted-foreground">加载中...</div>}
              {!loading && notifications.length === 0 && (
                <div className="p-6 text-center text-sm text-muted-foreground">暂无通知</div>
              )}
              {notifications.slice(0, 15).map(n => (
                <div key={n.id} className={`px-4 py-3 border-b last:border-0 hover:bg-accent/50 transition-colors ${!n.read ? "bg-primary/5" : ""}`}>
                  <p className="text-xs font-medium leading-relaxed">{n.title}</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5">{n.body}</p>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-[9px] text-muted-foreground">{n.created_at ? new Date(n.created_at).toLocaleString("zh-CN") : ""}</span>
                    {n.event_id && (
                      <Link to={`/events/${n.event_id}`} onClick={() => setOpen(false)} className="text-[10px] text-primary hover:underline flex items-center gap-0.5">查看 <ChevronRight className="h-2.5 w-2.5" /></Link>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
