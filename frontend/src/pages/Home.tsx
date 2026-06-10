import { useState, useEffect, useCallback } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useApi } from "../hooks/useApi";
import {
  Search, Globe, Shield, TrendingUp, Clock, ArrowRight, Loader2,
  Activity, BarChart3, AlertTriangle, Zap, BookOpen,
  PenTool, Code, Radio, Map, Users, Coins,
} from "lucide-react";

// =============================================================================
// Home — 简洁可靠首页
// =============================================================================

export function Home() {
  const [query, setQuery] = useState("");
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState<"keyword" | "url">("keyword");
  const navigate = useNavigate();
  const { data: stats } = useApi<any>();
  const { request } = useApi<any>();

  useEffect(() => { request("/api/stats/dashboard"); }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const q = mode === "url" ? url : query;
    if (q.trim()) {
      const encoded = encodeURIComponent(q.trim());
      navigate(`/search?${mode === "url" ? "url" : "q"}=${encoded}`);
    }
  };

  const overview = stats?.overview || {};
  const today = stats?.today || {};

  return (
    <div>
      {/* ================================================================ */}
      {/* HERO */}
      {/* ================================================================ */}
      <section className="relative overflow-hidden bg-gradient-to-b from-primary/5 to-background">
        <div className="container mx-auto px-4 py-16 md:py-24">
          <div className="max-w-3xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium mb-6">
              <Zap className="h-3 w-3" /> 10 引擎推理管线 · 140 API 端点 · 开源
            </div>
            <h1 className="text-4xl md:text-6xl font-bold tracking-tight mb-4">
              TruthTrace <span className="text-primary">平浪散暴</span>
            </h1>
            <p className="text-lg text-muted-foreground mb-8 max-w-2xl mx-auto">
              输入链接或关键词，AI 自动溯源信息传播链路，评估可信度，识别操纵手法
            </p>

            {/* Mode Toggle */}
            <div className="flex gap-2 mb-4 justify-center">
              <button type="button" onClick={() => setMode("keyword")}
                className={`px-4 py-1.5 rounded-full text-sm font-medium transition ${
                  mode === "keyword" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}>关键词搜索</button>
              <button type="button" onClick={() => setMode("url")}
                className={`px-4 py-1.5 rounded-full text-sm font-medium transition ${
                  mode === "url" ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}>URL 溯源</button>
            </div>

            {/* Search Form */}
            <form onSubmit={handleSearch} className="max-w-2xl mx-auto">
              <div className="relative">
                <input
                  type="text"
                  value={mode === "url" ? url : query}
                  onChange={e => mode === "url" ? setUrl(e.target.value) : setQuery(e.target.value)}
                  placeholder={mode === "keyword" ? "搜索事件关键词，如：食品安全、疫苗..." : "粘贴网页链接，支持微博/知乎/微信/新闻..."}
                  className="w-full h-14 px-6 pr-14 rounded-xl border-2 border-primary/20 bg-background text-lg shadow-lg focus:border-primary focus:outline-none focus:ring-4 focus:ring-primary/10 transition-all"
                />
                <button type="submit" disabled={!(mode === "url" ? url : query).trim()}
                  className="absolute right-2 top-1/2 -translate-y-1/2 h-10 w-10 rounded-lg bg-primary text-primary-foreground flex items-center justify-center hover:bg-primary/90 disabled:opacity-50 transition">
                  <Search className="h-5 w-5" />
                </button>
              </div>
            </form>

            {/* Quick Stats Bar */}
            <div className="flex items-center justify-center gap-6 mt-8 text-sm text-muted-foreground">
              <span className="flex items-center gap-1.5"><BarChart3 className="h-4 w-4" /> {overview.total_events || 0} 事件</span>
              <span className="flex items-center gap-1.5"><Globe className="h-4 w-4" /> {overview.total_sources || 0} 来源</span>
              <span className="flex items-center gap-1.5"><Shield className="h-4 w-4" /> {overview.total_rumor_reports || 0} 辟谣</span>
            </div>
          </div>
        </div>
      </section>

      {/* ================================================================ */}
      {/* FEATURE CARDS — 跳转专用页面 */}
      {/* ================================================================ */}
      <section className="container mx-auto px-4 py-12">
        <h2 className="text-xl font-bold text-center mb-8">产品能力</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto">
          {[
            { to: "/search", icon: Search, label: "关键词搜索", desc: "搜索已知事件和分析结果", color: "from-blue-500/10 to-blue-600/5" },
            { to: "/rumors", icon: Shield, label: "辟谣广场", desc: "已核实的虚假信息库", color: "from-red-500/10 to-red-600/5" },
            { to: "/academy", icon: BookOpen, label: "信息素养", desc: "每日挑战 + 案例学习", color: "from-amber-500/10 to-amber-600/5" },
            { to: "/situational", icon: Activity, label: "态势感知", desc: "实时热点 + 叙事趋势", color: "from-blue-500/10 to-indigo-600/5" },
            { to: "/community", icon: Users, label: "协作众包", desc: "悬赏求证 + 专家验证", color: "from-green-500/10 to-green-600/5" },
            { to: "/studio", icon: PenTool, label: "辟谣工坊", desc: "AI 辅助生成辟谣内容", color: "from-purple-500/10 to-purple-600/5" },
            { to: "/developer", icon: Code, label: "API 平台", desc: "集成检测能力到你的应用", color: "from-indigo-500/10 to-indigo-600/5" },
            { to: "/admin", icon: BarChart3, label: "管理后台", desc: "质量仪表盘 · 反馈审核", color: "from-gray-500/10 to-gray-600/5" },
          ].map(card => (
            <Link key={card.to} to={card.to}
              className={`group p-5 rounded-xl border bg-gradient-to-br ${card.color} hover:shadow-md hover:border-primary/30 transition-all`}>
              <card.icon className="h-8 w-8 text-primary mb-3 group-hover:scale-110 transition-transform" />
              <h3 className="font-semibold text-sm mb-1">{card.label}</h3>
              <p className="text-xs text-muted-foreground">{card.desc}</p>
            </Link>
          ))}
        </div>
      </section>

      {/* ================================================================ */}
      {/* TODAY'S HIGHLIGHTS */}
      {/* ================================================================ */}
      <section className="container mx-auto px-4 py-10 border-t">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-lg font-bold mb-4">今日概览</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatBox label="新增事件" value={today.new_events || 0} sub="今日" color="blue" />
            <StatBox label="新增溯源" value={today.new_traces || 0} sub="今日" color="green" />
            <StatBox label="平均可信度" value={(overview.avg_credibility || 50).toFixed(0)} sub="/100" color="amber" />
            <StatBox label="辟谣报告" value={overview.total_rumor_reports || 0} sub="累计" color="red" />
          </div>
        </div>
      </section>

      {/* ================================================================ */}
      {/* CTA */}
      {/* ================================================================ */}
      <section className="container mx-auto px-4 py-16 text-center border-t">
        <h2 className="text-2xl font-bold mb-3">看到不确定的信息？</h2>
        <p className="text-muted-foreground mb-6">粘贴链接，让 TruthTrace 帮你追溯真相</p>
        <Link to="/search"
          className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90">
          开始使用 <ArrowRight className="h-4 w-4" />
        </Link>
      </section>
    </div>
  );
}

function StatBox({ label, value, sub, color }: { label: string; value: string | number; sub: string; color: string }) {
  const colors: Record<string, string> = {
    blue: "bg-blue-50 dark:bg-blue-950/20 text-blue-700 dark:text-blue-400",
    green: "bg-green-50 dark:bg-green-950/20 text-green-700 dark:text-green-400",
    amber: "bg-amber-50 dark:bg-amber-950/20 text-amber-700 dark:text-amber-400",
    red: "bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400",
  };
  return (
    <div className={`p-4 rounded-xl border text-center ${colors[color] || ""}`}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs opacity-70">{label}</div>
      <div className="text-xs opacity-50">{sub}</div>
    </div>
  );
}
