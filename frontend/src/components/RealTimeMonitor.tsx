import { useState, useEffect, useRef } from "react";
import { Activity, Bell, Radio, AlertTriangle, TrendingUp, RefreshCw, Play, Loader2, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

interface HotItem {
  event_id: string;
  title: string;
  platform: string;
  credibility_score: number;
  propagation_speed: number;
  source_count: number;
  first_seen_at?: string;
  rumor_verdict?: string;
  tags?: string[];
}

interface Alert {
  id: string;
  title: string;
  narrative_type: string;
  severity: string;
  created_at: string;
  affected_events: number;
  description: string;
}

interface MonitorState {
  total: number;
  platforms: string[];
  updated_at: string | null;
  items: HotItem[];
  cached: boolean;
}

export function RealTimeMonitor() {
  const [state, setState] = useState<MonitorState | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [crawling, setCrawling] = useState(false);
  const [error, setError] = useState("");
  const intervalRef = useRef<any>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const API = (import.meta as any).env?.VITE_API_BASE_URL || "";

  const fetchData = async () => {
    try {
      const [hotRes, alertRes] = await Promise.all([
        fetch(`${API}/api/monitor/hot?limit=50`, { credentials: "include" }),
        fetch(`${API}/api/monitor/alerts`, { credentials: "include" }),
      ]);
      if (hotRes.ok) {
        const hotData = await hotRes.json();
        setState(hotData);
      }
      if (alertRes.ok) {
        const alertData = await alertRes.json();
        setAlerts(alertData.alerts || []);
      }
      setLastRefresh(new Date());
      setError("");
    } catch (e: any) {
      setError(e.message || "获取失败");
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
    intervalRef.current = setInterval(fetchData, 30000); // 30s auto-refresh
    return () => clearInterval(intervalRef.current);
  }, []);

  const triggerCrawl = async () => {
    setCrawling(true);
    try {
      await fetch(`${API}/api/monitor/crawl`, { method: "POST", credentials: "include" });
      await fetchData();
    } catch {}
    setCrawling(false);
  };

  const activeAlerts = alerts.filter((a) => a.severity !== "resolved");
  const criticalAlerts = activeAlerts.filter((a) => a.severity === "critical" || a.severity === "high");

  return (
    <div className="space-y-4">
      {/* Top bar */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold flex items-center gap-2">
            <Radio className="h-5 w-5 text-green-500" />
            实时监控
          </h2>
          {lastRefresh && (
            <span className="text-[10px] text-muted-foreground">
              上次刷新: {lastRefresh.toLocaleTimeString()}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium hover:bg-accent transition-colors"
          >
            <RefreshCw size={12} className={loading ? "animate-spin" : ""} />
            刷新
          </button>
          <button
            onClick={triggerCrawl}
            disabled={crawling}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {crawling ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <Play size={12} />
            )}
            触发采集
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-lg border border-red-200 bg-red-50 text-red-700 text-xs">{error}</div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MonitorCard
          icon={<Activity size={16} />}
          label="监控热点"
          value={state?.total || 0}
          color="blue"
        />
        <MonitorCard
          icon={<AlertTriangle size={16} />}
          label="活跃告警"
          value={activeAlerts.length}
          color={criticalAlerts.length > 0 ? "red" : "amber"}
        />
        <MonitorCard
          icon={<TrendingUp size={16} />}
          label="覆盖平台"
          value={state?.platforms?.length || 0}
          color="green"
        />
        <MonitorCard
          icon={<RefreshCw size={16} />}
          label="缓存状态"
          value={state?.cached ? "缓存" : "实时"}
          color="purple"
          isText
        />
      </div>

      {/* Alerts section */}
      {activeAlerts.length > 0 && (
        <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/20 overflow-hidden">
          <div className="px-4 py-3 border-b border-red-200 dark:border-red-800 bg-red-100 dark:bg-red-950/30">
            <div className="flex items-center gap-2">
              <Bell className="h-4 w-4 text-red-600" />
              <h3 className="text-sm font-semibold text-red-700 dark:text-red-400">
                {activeAlerts.length} 条活跃叙事告警
                {criticalAlerts.length > 0 && ` (${criticalAlerts.length} 严重)`}
              </h3>
            </div>
          </div>
          <div className="divide-y divide-red-100 dark:divide-red-900/30">
            {activeAlerts.slice(0, 5).map((alert) => (
              <div key={alert.id} className="px-4 py-2.5 flex items-start gap-3 hover:bg-red-100/50 dark:hover:bg-red-950/40 transition-colors">
                <span className={`mt-0.5 w-1.5 h-1.5 rounded-full shrink-0 ${
                  alert.severity === "critical" ? "bg-red-500" :
                  alert.severity === "high" ? "bg-orange-500" :
                  "bg-yellow-500"
                }`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium">{alert.title}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-900/50 text-red-600 dark:text-red-400">
                      {alert.narrative_type}
                    </span>
                  </div>
                  <p className="text-[11px] text-red-600/70 dark:text-red-400/70 mt-0.5">{alert.description}</p>
                  <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground">
                    <span>影响 {alert.affected_events} 个事件</span>
                    <span>·</span>
                    <span>{alert.created_at?.slice(0, 10)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Hot items list */}
      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-4 py-3 border-b bg-muted/20">
          <h3 className="text-sm font-semibold flex items-center gap-2">
            热点排行
            {state?.updated_at && (
              <span className="text-[10px] font-normal text-muted-foreground">
                (数据更新于 {new Date(state.updated_at).toLocaleString()})
              </span>
            )}
          </h3>
        </div>

        {loading && !state ? (
          <div className="flex items-center gap-2 p-8 justify-center text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> 加载监控数据...
          </div>
        ) : state?.items?.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            <Radio className="h-8 w-8 mx-auto mb-2 opacity-30" />
            <p>暂无监控数据</p>
            <p className="text-xs mt-1">点击"触发采集"开始监控</p>
          </div>
        ) : (
          <div className="divide-y">
            {state?.items?.slice(0, 30).map((item: HotItem, i: number) => (
              <Link
                key={item.event_id}
                to={`/events/${item.event_id}`}
                className="flex items-center gap-3 px-4 py-2.5 hover:bg-muted/30 transition-colors group"
              >
                {/* Rank */}
                <span className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${
                  i < 3 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
                }`}>
                  {i + 1}
                </span>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate group-hover:text-primary transition-colors">
                      {item.title}
                    </span>
                    {item.rumor_verdict && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 shrink-0">
                        {item.rumor_verdict}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-[10px] text-muted-foreground mt-0.5">
                    <span>{item.platform || "多平台"}</span>
                    <span>·</span>
                    <span>{item.source_count || 0} 来源</span>
                    <span>·</span>
                    <span>传播速度 {item.propagation_speed || 0}/h</span>
                    {item.tags?.map((t) => (
                      <span key={t} className="text-[9px] px-1 py-0.5 rounded bg-muted">{t}</span>
                    ))}
                  </div>
                </div>

                {/* Score */}
                <div className="shrink-0 text-right">
                  <div className={`text-sm font-bold ${
                    item.credibility_score >= 60 ? "text-green-600" :
                    item.credibility_score >= 40 ? "text-amber-600" :
                    "text-red-600"
                  }`}>
                    {item.credibility_score?.toFixed(0) || "?"}
                  </div>
                  <div className="text-[9px] text-muted-foreground">可信度</div>
                </div>

                <ChevronRight size={14} className="text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function MonitorCard({ icon, label, value, color, isText }: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  color: "blue" | "red" | "amber" | "green" | "purple";
  isText?: boolean;
}) {
  const colors = {
    blue: "bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800 text-blue-700",
    red: "bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-800 text-red-700",
    amber: "bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800 text-amber-700",
    green: "bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-800 text-green-700",
    purple: "bg-purple-50 dark:bg-purple-950/20 border-purple-200 dark:border-purple-800 text-purple-700",
  };
  return (
    <div className={`rounded-lg border p-3 ${colors[color]}`}>
      <div className="flex items-center gap-1.5 mb-1 text-xs opacity-70">
        {icon}
        {label}
      </div>
      <div className={`font-bold ${isText ? "text-sm" : "text-xl"}`}>
        {value}
      </div>
    </div>
  );
}
