/**
 * 管理员后台 — 6Tab SPA
 * 分析审查 / 叙事告警 / 系统健康 / 用户管理 / 反馈审核 / 规则历史
 */

import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  Shield, BarChart3, Bell, Activity, Users, MessageSquare,
  Clock, AlertTriangle, CheckCircle, XCircle, Loader2,
  Search, ChevronRight, RefreshCw, Wifi, WifiOff, Trash2,
  ArrowLeft, TrendingUp, Eye,
} from "lucide-react";
import { useApi } from "../hooks/useApi";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// =============================================================================
// Tab definitions
// =============================================================================
const TABS = [
  { id: "overview", label: "概览", icon: Activity },
  { id: "analysis", label: "分析审查", icon: Search },
  { id: "alerts", label: "叙事告警", icon: Bell },
  { id: "health", label: "系统健康", icon: Wifi },
  { id: "users", label: "用户管理", icon: Users },
  { id: "feedback", label: "反馈审核", icon: MessageSquare },
  { id: "rules", label: "规则历史", icon: Clock },
];

// =============================================================================
// 概览 Tab
// =============================================================================
function OverviewTab() {
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

function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  const bg: Record<string, string> = { blue: "bg-blue-50 dark:bg-blue-950/30 border-blue-200 dark:border-blue-800",
    green: "bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800",
    purple: "bg-purple-50 dark:bg-purple-950/30 border-purple-200 dark:border-purple-800",
    red: "bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800",
    yellow: "bg-yellow-50 dark:bg-yellow-950/30 border-yellow-200 dark:border-yellow-800",
  };
  return (
    <div className={`p-4 rounded-xl border ${bg[color] || bg.blue}`}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

// =============================================================================
// 分析审查 Tab
// =============================================================================
function AnalysisTab() {
  const { data, loading, request } = useApi<any>();
  const [risk, setRisk] = useState("");
  useEffect(() => { request(`/api/admin/analysis/review?limit=30&risk_level=${risk}`); }, [risk]);

  const items = data?.items || [];

  return (
    <div>
      <div className="flex gap-2 mb-4">
        {["", "high", "medium", "low"].map(r => (
          <button key={r} onClick={() => setRisk(r)}
            className={`px-3 py-1 rounded-full text-xs font-medium ${risk === r ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80"}`}>
            {r === "" ? "全部" : r === "high" ? "高风险" : r === "medium" ? "中风险" : "低风险"}
          </button>
        ))}
      </div>
      {loading && <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>}
      <div className="space-y-2">
        {items.map((item: any) => (
          <div key={item.event_id} className={`p-4 rounded-lg border ${item.credibility_score < 30 ? "border-l-4 border-l-red-500 bg-red-50/30 dark:bg-red-950/10" : item.credibility_score < 55 ? "border-l-4 border-l-yellow-500 bg-yellow-50/30 dark:bg-yellow-950/10" : "bg-card"}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-sm truncate">{item.title}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${item.credibility_score < 30 ? "bg-red-100 text-red-700" : item.credibility_score < 55 ? "bg-yellow-100 text-yellow-700" : "bg-green-100 text-green-700"}`}>{item.credibility_score}/100</span>
                  {item.engine_verdict && <span className="text-[10px] text-muted-foreground">{item.engine_verdict}</span>}
                </div>
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {item.distortion_count > 0 && <span className="px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-900/30 text-[10px] text-red-700">失真{item.distortion_count}</span>}
                  {item.fallacy_count > 0 && <span className="px-1.5 py-0.5 rounded bg-yellow-100 dark:bg-yellow-900/30 text-[10px] text-yellow-700">谬误{item.fallacy_count}</span>}
                  {item.narrative_dominant && <span className="px-1.5 py-0.5 rounded bg-purple-100 dark:bg-purple-900/30 text-[10px] text-purple-700">{item.narrative_dominant}</span>}
                  {item.manipulation_score > 30 && <span className="px-1.5 py-0.5 rounded bg-orange-100 dark:bg-orange-900/30 text-[10px] text-orange-700">操纵{item.manipulation_score}</span>}
                  {item.stat_risk > 30 && <span className="px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/30 text-[10px] text-blue-700">统计{item.stat_risk}</span>}
                </div>
                {item.correction && <p className="text-[10px] text-muted-foreground mt-1.5 truncate">{item.correction}</p>}
              </div>
              <Link to={`/events/${item.event_id}/report`} className="flex-shrink-0 text-xs text-primary hover:underline">详情 →</Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// 叙事告警 Tab
// =============================================================================
function AlertsTab() {
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

// =============================================================================
// 系统健康 Tab
// =============================================================================
function HealthTab() {
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

// =============================================================================
// 用户管理 Tab
// =============================================================================
function UsersTab() {
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

// =============================================================================
// 反馈审核 Tab
// =============================================================================
function FeedbackTab() {
  const { data: fbData, loading, request } = useApi<any>();
  const { data: appealData, request: reqAppeal } = useApi<any>();
  useEffect(() => {
    request("/api/admin/feedback/queue");
    reqAppeal("/api/admin/appeal/queue");
  }, []);

  const feedbacks = fbData?.feedbacks || [];
  const appeals = appealData?.appeals || [];

  const reviewAppeal = async (id: string, action: string) => {
    await fetch(`${API_BASE}/api/admin/appeal/${id}/review?action=${action}`, { method: "POST" });
    reqAppeal("/api/admin/appeal/queue");
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold mb-3">用户反馈 ({feedbacks.length})</h3>
        <div className="space-y-2">
          {feedbacks.slice(0, 15).map((f: any, i: number) => (
            <div key={i} className={`p-3 rounded-lg border text-xs ${f.rating === "inaccurate" ? "border-red-200 bg-red-50/30 dark:bg-red-950/10" : "bg-card"}`}>
              <div className="flex items-center justify-between">
                <div>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${f.rating === "helpful" ? "bg-green-100 text-green-700" : f.rating === "inaccurate" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"}`}>{f.rating}</span>
                  <span className="ml-2">{f.username}</span>
                  <span className="ml-2 text-muted-foreground">{f.comment?.slice(0, 60)}</span>
                </div>
                <Link to={`/events/${f.event_id}`} className="text-primary hover:underline">查看</Link>
              </div>
            </div>
          ))}
          {feedbacks.length === 0 && !loading && <p className="text-center py-8 text-muted-foreground text-sm">暂无反馈</p>}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-3">申诉审核 ({appeals.length})</h3>
        <div className="space-y-2">
          {appeals.slice(0, 15).map((a: any) => (
            <div key={a.id} className={`p-4 rounded-lg border ${a.status === "pending" ? "border-orange-300 bg-orange-50/30 dark:bg-orange-950/10" : "bg-card"}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-sm">{a.username} 的申诉</span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${a.status === "pending" ? "bg-orange-100 text-orange-700" : a.status === "accepted" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"}`}>{a.status}</span>
              </div>
              <p className="text-xs mb-1"><strong>事件:</strong> {a.event_title?.slice(0, 50)} (引擎判定: {a.engine_verdict}, 用户认为: {a.correct_verdict || "未指定"})</p>
              <p className="text-xs text-muted-foreground mb-2">{a.reason?.slice(0, 150)}</p>
              {a.status === "pending" && (
                <div className="flex gap-2">
                  <button onClick={() => reviewAppeal(a.id, "accepted")} className="px-3 py-1 rounded bg-green-500 text-white text-xs hover:bg-green-600">接受</button>
                  <button onClick={() => reviewAppeal(a.id, "rejected")} className="px-3 py-1 rounded bg-red-500 text-white text-xs hover:bg-red-600">驳回</button>
                </div>
              )}
            </div>
          ))}
          {appeals.length === 0 && !loading && <p className="text-center py-8 text-muted-foreground text-sm">暂无申诉</p>}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// 规则历史 Tab
// =============================================================================
function RulesTab() {
  const { data, loading, request } = useApi<any>();
  useEffect(() => { request("/api/system/evolution/rule-history"); }, []);

  const history = data?.history || [];
  const versions = data?.current_versions || {};

  return (
    <div>
      <div className="mb-4 p-4 rounded-xl border bg-card">
        <h3 className="text-sm font-semibold mb-2">模块版本</h3>
        <div className="grid grid-cols-3 gap-2 text-xs">
          {Object.entries(versions).map(([k, v]) => (
            <div key={k} className="p-2 rounded bg-muted/50"><strong>{k}:</strong> v{v as string}</div>
          ))}
        </div>
      </div>
      <div className="space-y-2">
        {history.slice(0, 30).map((h: any, i: number) => (
          <div key={i} className="p-3 rounded-lg border bg-card text-xs">
            <div className="flex items-center justify-between">
              <span className="font-semibold">{h.module}.{h.rule_id} → v{h.version}</span>
              <span className="text-muted-foreground">{h.at}</span>
            </div>
            <p className="mt-1">{h.reason}</p>
            <p className="text-muted-foreground">by {h.changed_by}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// 主页面
// =============================================================================
export function Admin() {
  const [tab, setTab] = useState("overview");

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Shield className="h-7 w-7 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">管理后台</h1>
            <p className="text-xs text-muted-foreground">系统管理、分析审查、用户管理</p>
          </div>
        </div>
        <Link to="/" className="text-sm text-primary hover:underline flex items-center gap-1"><ArrowLeft className="h-3.5 w-3.5" /> 返回首页</Link>
      </div>

      <div className="flex flex-wrap gap-1 mb-6 border-b pb-2 overflow-x-auto">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-t-lg text-xs font-medium transition-colors whitespace-nowrap ${tab === t.id ? "bg-primary/10 text-primary border-b-2 border-primary" : "text-muted-foreground hover:text-foreground"}`}>
            <t.icon className="h-3.5 w-3.5" />{t.label}
          </button>
        ))}
      </div>

      <div className="min-h-[500px]">
        {tab === "overview" && <OverviewTab />}
        {tab === "analysis" && <AnalysisTab />}
        {tab === "alerts" && <AlertsTab />}
        {tab === "health" && <HealthTab />}
        {tab === "users" && <UsersTab />}
        {tab === "feedback" && <FeedbackTab />}
        {tab === "rules" && <RulesTab />}
      </div>
    </div>
  );
}
