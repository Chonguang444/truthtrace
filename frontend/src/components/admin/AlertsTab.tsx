import { useEffect } from "react";
import { Loader2, Trash2 } from "lucide-react";
import { useApi } from "../../hooks/useApi";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export function AlertsTab() {
  const { data, loading, request } = useApi<any>();
  useEffect(() => { request("/api/admin/alerts"); }, []);

  const alerts = data?.alerts || [];
  const dismiss = async (id: string) => {
    await fetch(`${API_BASE}/api/admin/alerts/${id}/dismiss`, { method: "POST" });
    request("/api/admin/alerts");
  };

  if (loading) return <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>;
  if (!alerts.length) return <div className="text-center py-12 text-muted-foreground text-sm">✅ 暂无活跃告警</div>;

  return (
    <div className="space-y-3">
      {alerts.map((a: any) => (
        <div key={a.id} className={`p-4 rounded-lg border ${a.severity === "critical" ? "border-l-4 border-l-red-600 bg-red-50/30" : a.severity === "high" ? "border-l-4 border-l-red-500 bg-red-50/30" : a.severity === "medium" ? "border-l-4 border-l-yellow-500 bg-yellow-50/30" : "bg-card"}`}>
          <div className="flex items-start justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${a.severity === "critical" ? "bg-red-200 text-red-800" : a.severity === "high" ? "bg-red-100 text-red-700" : a.severity === "medium" ? "bg-yellow-100 text-yellow-700" : "bg-blue-100 text-blue-700"}`}>{a.severity}</span>
                <span className="font-semibold text-sm">{a.title}</span>
              </div>
              <p className="text-xs text-muted-foreground mt-1">{a.description}</p>
              <div className="flex items-center gap-2 mt-2 text-[10px] text-muted-foreground">
                <span>{a.detected_items?.length || 0} 条热点</span>
                <span>操纵评分: {a.manipulation_score?.toFixed(0)}/100</span>
                {a.created_at && <span>{new Date(a.created_at).toLocaleString("zh-CN")}</span>}
              </div>
            </div>
            <button onClick={() => dismiss(a.id)} className="flex-shrink-0 p-1.5 rounded hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors"><Trash2 className="h-4 w-4 text-red-500" /></button>
          </div>
        </div>
      ))}
    </div>
  );
}
