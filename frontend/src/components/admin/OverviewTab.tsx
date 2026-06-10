import { useEffect } from "react";
import { Loader2 } from "lucide-react";
import { useApi } from "../../hooks/useApi";
import { StatCard } from "./StatCard";

export function OverviewTab() {
  const { data, loading, request } = useApi<any>();
  useEffect(() => { request("/api/admin/overview"); }, []);

  if (loading) return <div className="flex items-center gap-2 p-8 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>;

  const d = data || {};
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <StatCard label="事件总数" value={(d.total_events || 0).toLocaleString()} color="blue" />
      <StatCard label="信息来源" value={(d.total_sources || 0).toLocaleString()} color="green" />
      <StatCard label="用户" value={(d.total_users || 0).toLocaleString()} color="purple" />
      <StatCard label="辟谣报告" value={(d.total_rumor_reports || 0).toLocaleString()} color="red" />
      <StatCard label="24h新增" value={(d.recent_24h_events || 0).toLocaleString()} color="blue" />
      <StatCard label="低可信度" value={(d.low_credibility_events || 0).toLocaleString()} color="yellow" />
      <div className="col-span-2 md:col-span-2 p-4 rounded-xl border bg-card">
        <p className="text-xs text-muted-foreground">系统时间</p>
        <p className="font-mono text-sm">{d.timestamp ? new Date(d.timestamp).toLocaleString("zh-CN") : "—"}</p>
      </div>
    </div>
  );
}
