import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { useApi } from "../../hooks/useApi";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export function UsersTab() {
  const { data, loading, request } = useApi<any>();
  useEffect(() => { request("/api/admin/users?limit=30"); }, []);

  const users = data?.users || [];
  const toggleActive = async (userId: string) => {
    await fetch(`${API_BASE}/api/admin/users/${userId}/toggle-active`, { method: "POST" });
    request("/api/admin/users?limit=30");
  };

  if (loading) return <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>;

  return (
    <div className="space-y-2">
      {users.map((u: any) => (
        <div key={u.id} className="flex items-center justify-between p-3 rounded-lg border bg-card">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm">{u.username}</span>
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium capitalize ${u.role === "admin" ? "bg-purple-100 text-purple-700" : "bg-muted text-muted-foreground"}`}>{u.role}</span>
            </div>
            <p className="text-[10px] text-muted-foreground">{u.email} · 注册: {u.created_at ? new Date(u.created_at).toLocaleDateString("zh-CN") : "?"}</p>
          </div>
          <button onClick={() => toggleActive(u.id)} className={`px-3 py-1 rounded-lg text-xs font-medium ${u.is_active ? "bg-red-50 text-red-700 hover:bg-red-100" : "bg-green-50 text-green-700 hover:bg-green-100"} transition-colors`}>
            {u.is_active ? "禁用" : "启用"}
          </button>
        </div>
      ))}
    </div>
  );
}
