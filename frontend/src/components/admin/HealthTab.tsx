import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { useApi } from "../../hooks/useApi";

export function HealthTab() {
  const { data, loading, request } = useApi<any>();
  useEffect(() => { request("/api/admin/health"); }, []);

  if (loading) return <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>;

  const checks = data?.checks || {};
  const status = data?.status || "unknown";

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <span className={`h-3 w-3 rounded-full ${status === "healthy" ? "bg-green-500" : "bg-yellow-500 animate-pulse"}`} />
        <span className="font-semibold">系统状态: {status}</span>
        <span className="text-xs text-muted-foreground">{data?.timestamp ? new Date(data.timestamp).toLocaleString("zh-CN") : ""}</span>
      </div>
      {Object.entries(checks).map(([key, value]: [string, any]) => (
        <div key={key} className="p-4 rounded-lg border bg-card">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-sm capitalize">{key}</span>
            {typeof value === "string" ? (
              <span className={`px-2 py-0.5 rounded text-xs font-medium ${value === "healthy" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>{value}</span>
            ) : (
              <div className="text-xs text-muted-foreground">
                {value && typeof value === "object" ? JSON.stringify(value).slice(0, 80) : String(value)}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
