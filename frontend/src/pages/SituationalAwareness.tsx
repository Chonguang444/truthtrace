import { useState, useEffect, useRef } from "react";
import { Activity, Map, TrendingUp, Layers, AlertTriangle, ArrowUp, ArrowDown, Minus, Loader2 } from "lucide-react";
import { useApi } from "../hooks/useApi";

const TABS = [
  { id: "hotspots", label: "热点排行", icon: Activity },
  { id: "map", label: "传播地图", icon: Map },
  { id: "trends", label: "叙事趋势", icon: TrendingUp },
  { id: "platforms", label: "平台对比", icon: Layers },
];

export default function SituationalAwareness() {
  const [tab, setTab] = useState("hotspots");
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Activity className="h-7 w-7 text-primary" />
        <div>
          <h1 className="text-2xl font-bold">实时态势感知</h1>
          <p className="text-xs text-muted-foreground">像看天气预报一样了解信息环境</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-1 mb-6 border-b pb-2 overflow-x-auto">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-t-lg text-xs font-medium whitespace-nowrap ${tab === t.id ? "bg-primary/10 text-primary border-b-2 border-primary" : "text-muted-foreground hover:text-foreground"}`}>
            <t.icon className="h-3.5 w-3.5" />{t.label}
          </button>
        ))}
      </div>
      {tab === "hotspots" && <HotspotsTab />}
      {tab === "map" && <MapTab />}
      {tab === "trends" && <TrendsTab />}
      {tab === "platforms" && <PlatformsTab />}
    </div>
  );
}

// =============================================================================
// Tab: Hotspots
// =============================================================================

function HotspotsTab() {
  const { data, loading, request } = useApi<any>();
  const intervalRef = useRef<any>(null);
  const [minScore, setMinScore] = useState("");

  const fetchData = () => request(`/api/situational/hotspots${minScore ? `?min_score=${minScore}` : ""}`);

  useEffect(() => {
    fetchData();
    intervalRef.current = setInterval(fetchData, 60000);
    return () => clearInterval(intervalRef.current);
  }, [minScore]);

  if (loading && !data) return <div className="flex items-center gap-2 p-8"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>;

  const summary = data?.summary || {};
  const hotspots = data?.hotspots || [];

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatBox label="热点总数" value={data?.total || 0} color="blue" />
        <StatBox label="高风险" value={summary.high_risk_count || 0} color="red" />
        <StatBox label="上升中" value={summary.rising_count || 0} color="amber" />
        <StatBox label="平均传播速度" value={`${summary.avg_propagation_speed || 0}/h`} color="green" />
      </div>

      <div className="flex items-center gap-2">
        <input type="number" placeholder="最低可信度筛选" value={minScore} onChange={e => setMinScore(e.target.value)}
          className="px-3 py-1.5 rounded-lg border text-sm w-48" />
        <span className="text-xs text-muted-foreground">每60秒自动刷新</span>
      </div>

      <div className="space-y-2">
        {hotspots.map((h: any) => (
          <div key={h.event_id} className={`p-4 rounded-xl border bg-card border-l-4 ${h.credibility_score < 20 ? "border-l-red-500" : h.credibility_score < 55 ? "border-l-yellow-500" : "border-l-green-500"}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-sm truncate">{h.title}</p>
                <div className="flex items-center gap-2 mt-2 flex-wrap">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${h.credibility_score < 20 ? "bg-red-100 text-red-700" : h.credibility_score < 55 ? "bg-yellow-100 text-yellow-700" : "bg-green-100 text-green-700"}`}>
                    可信度 {h.credibility_score?.toFixed(0)}/100
                  </span>
                  <span className="text-[10px] text-muted-foreground">传播速度 {h.propagation_speed}/h</span>
                  <TrendIcon direction={h.trend_direction} />
                  <span className="px-2 py-0.5 rounded bg-muted text-[10px]">{h.narrative_type}</span>
                  {h.top_platforms?.map((p: string) => <span key={p} className="text-[10px] text-muted-foreground">{p}</span>)}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatBox({ label, value, color }: { label: string; value: string | number; color: string }) {
  const colors: Record<string, string> = {
    blue: "border-blue-200 bg-blue-50/30 dark:bg-blue-950/10",
    red: "border-red-200 bg-red-50/30 dark:bg-red-950/10",
    amber: "border-amber-200 bg-amber-50/30 dark:bg-amber-950/10",
    green: "border-green-200 bg-green-50/30 dark:bg-green-950/10",
  };
  return (
    <div className={`p-3 rounded-xl border ${colors[color]}`}>
      <div className="text-xl font-bold">{value}</div>
      <div className="text-[10px] text-muted-foreground">{label}</div>
    </div>
  );
}

function TrendIcon({ direction }: { direction: string }) {
  if (direction === "rising") return <ArrowUp className="h-3 w-3 text-red-500" />;
  if (direction === "falling") return <ArrowDown className="h-3 w-3 text-green-500" />;
  return <Minus className="h-3 w-3 text-gray-400" />;
}

// =============================================================================
// Tab: Propagation Map
// =============================================================================

function MapTab() {
  const [eventId, setEventId] = useState("");
  const { data, loading, request } = useApi<any>();

  const fetchMap = () => {
    if (eventId.trim()) request(`/api/situational/map/${eventId.trim()}`);
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input type="text" placeholder="输入事件 ID..." value={eventId} onChange={e => setEventId(e.target.value)}
          onKeyDown={e => e.key === "Enter" && fetchMap()}
          className="flex-1 px-3 py-2 rounded-lg border text-sm" />
        <button onClick={fetchMap} className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium">查询</button>
      </div>
      {loading && <div className="flex items-center gap-2 p-4"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>}
      {data && !data.error && (
        <div className="space-y-4">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="px-3 py-1.5 rounded-full bg-primary/10 text-primary text-sm font-semibold">源发地: {data.origin_city}</span>
            <span className="text-sm text-muted-foreground">共 {data.total_cities} 个城市</span>
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${data.propagation_type === "organic" ? "bg-green-100 text-green-700" : data.propagation_type === "coordinated" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"}`}>
              {data.propagation_type}
            </span>
          </div>
          {/* Node list */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {data.nodes?.map((n: any) => (
              <div key={n.city} className={`p-3 rounded-lg border text-sm ${n.is_origin ? "border-primary bg-primary/5" : "bg-card"}`}>
                <p className="font-semibold">{n.city} {n.is_origin ? "📍" : ""}</p>
                <p className="text-xs text-muted-foreground">{n.count} 条传播 · {n.first_seen?.slice(0, 10)}</p>
              </div>
            ))}
          </div>
          {/* Edges list */}
          <div className="p-4 rounded-xl border bg-card">
            <h4 className="text-sm font-semibold mb-3">传播路径</h4>
            <div className="space-y-1">
              {data.edges?.map((e: any, i: number) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <span>{e.from_city}</span>
                  <ArrowUp className="h-3 w-3 rotate-90 text-muted-foreground" />
                  <span className="font-semibold">{e.to_city}</span>
                  <span className="text-xs text-muted-foreground ml-auto">权重: {e.weight}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Tab: Narrative Trends
// =============================================================================

function TrendsTab() {
  const [days, setDays] = useState(7);
  const { data, loading, request } = useApi<any>();

  useEffect(() => { request(`/api/situational/trends?days=${days}`); }, [days]);

  if (loading) return <div className="flex items-center gap-2 p-4"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>;

  const trends = data?.trends || [];
  const deltas = data?.deltas || {};

  const allNarratives = trends.length > 0 ? Object.keys(trends[0].narratives) : [];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        {[7, 14, 30].map(d => (
          <button key={d} onClick={() => setDays(d)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium ${days === d ? "bg-primary text-primary-foreground" : "bg-muted hover:bg-muted/80"}`}>
            过去 {d} 天
          </button>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b">
              <th className="text-left p-2 sticky left-0 bg-card">日期</th>
              {allNarratives.slice(0, 8).map(n => <th key={n} className="p-2 text-left">{n}</th>)}
              <th className="p-2">总计</th>
            </tr>
          </thead>
          <tbody>
            {trends.map((t: any) => (
              <tr key={t.date} className="border-b hover:bg-accent/30">
                <td className="p-2 font-mono sticky left-0 bg-card">{t.date.slice(5)}</td>
                {allNarratives.slice(0, 8).map(n => {
                  const val = t.narratives[n] || 0;
                  const intensity = Math.min(val / 60, 1);
                  return <td key={n} className="p-2" style={{ backgroundColor: `rgba(239, 68, 68, ${intensity * 0.15})` }}>{val}</td>;
                })}
                <td className="p-2 font-semibold">{t.total_events}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Deltas */}
      <div className="p-4 rounded-xl border bg-card">
        <h4 className="text-sm font-semibold mb-2">叙事变化 (周期内)</h4>
        <div className="flex flex-wrap gap-2">
          {Object.entries(deltas).map(([n, delta]: [string, any]) => (
            <span key={n} className={`px-2 py-1 rounded text-[10px] font-medium ${delta > 5 ? "bg-red-100 text-red-700" : delta < -5 ? "bg-green-100 text-green-700" : "bg-muted text-muted-foreground"}`}>
              {n} {delta > 0 ? `+${delta}` : delta}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Tab: Platforms
// =============================================================================

function PlatformsTab() {
  const { data: platData, loading, request } = useApi<any>();
  const { data: topicsData, request: topicsReq } = useApi<any>();

  useEffect(() => {
    request("/api/situational/platforms");
    topicsReq("/api/situational/topics");
  }, []);

  if (loading) return <div className="flex items-center gap-2 p-4"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>;

  const platforms = platData?.platforms || [];
  const summary = platData?.summary || {};
  const topics = topicsData?.topics || [];

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="p-3 rounded-xl border bg-blue-50/30 dark:bg-blue-950/10"><p className="text-xs text-muted-foreground">最多受影响</p><p className="font-bold">{summary.most_affected || "-"}</p></div>
        <div className="p-3 rounded-xl border bg-red-50/30 dark:bg-red-950/10"><p className="text-xs text-muted-foreground">最低可信度</p><p className="font-bold">{summary.lowest_credibility || "-"}</p></div>
        <div className="p-3 rounded-xl border bg-amber-50/30 dark:bg-amber-950/10"><p className="text-xs text-muted-foreground">最高操纵性</p><p className="font-bold">{summary.highest_manipulation || "-"}</p></div>
      </div>

      {/* Platform cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {platforms.map((p: any) => (
          <div key={p.platform} className="p-4 rounded-xl border bg-card">
            <p className="font-semibold text-sm capitalize mb-3">{p.platform}</p>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between"><span>事件数</span><span className="font-semibold">{p.event_count}</span></div>
              <div className="flex justify-between"><span>平均可信度</span><span className={`font-semibold ${p.avg_credibility < 40 ? "text-red-600" : ""}`}>{p.avg_credibility}/100</span></div>
              <div className="flex justify-between"><span>操纵性评分</span><span className={`font-semibold ${p.manipulation_avg > 50 ? "text-red-600" : ""}`}>{p.manipulation_avg}/100</span></div>
              <div className="flex justify-between"><span>已核验来源</span><span className="font-semibold">{p.verified_source_pct}%</span></div>
              <div><span className="px-2 py-0.5 rounded bg-muted text-[10px]">主导叙事: {p.top_narrative}</span></div>
            </div>
          </div>
        ))}
      </div>

      {/* Active topics */}
      <div className="p-4 rounded-xl border bg-card">
        <div className="flex items-center gap-2 mb-3"><AlertTriangle className="h-4 w-4 text-amber-500" /><h4 className="text-sm font-semibold">活跃专题</h4></div>
        <div className="flex flex-wrap gap-2">
          {topics.map((t: any) => (
            <span key={t.topic_id} className={`px-3 py-1.5 rounded-full text-xs font-medium ${t.severity === "critical" ? "bg-red-100 text-red-700" : t.severity === "high" ? "bg-amber-100 text-amber-700" : "bg-muted text-muted-foreground"}`}>
              {t.name} ({t.event_count})
              {t.high_sensitivity && " 🔔"}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
