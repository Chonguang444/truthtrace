import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Search, Globe, Shield, TrendingUp, Clock, ArrowRight,
  Activity, BarChart3, AlertTriangle, CheckCircle, Loader2,
  Zap, Radio,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import { formatRelativeTime, credibilityBg, verdictLabel } from "../lib/utils";

interface DashboardData {
  overview: {
    total_events: number;
    total_sources: number;
    total_rumor_reports: number;
    avg_credibility: number;
  };
  today: {
    new_events: number;
    new_traces: number;
  };
  trend_7d: { date: string; count: number }[];
  hot_events: {
    id: string;
    title: string;
    status: string;
    credibility_score: number;
    source_count: number;
    last_updated_at: string;
  }[];
  verdicts: { verdict: string; count: number }[];
  platforms: { platform: string; count: number; percentage: number }[];
  credibility_distribution: {
    high: number;
    medium: number;
    low: number;
  };
}

const PLATFORM_LABELS: Record<string, string> = {
  weibo: "微博",
  zhihu: "知乎",
  wechat: "微信",
  twitter: "Twitter",
  reddit: "Reddit",
  news: "新闻",
  general: "通用",
};

export function Home() {
  const [query, setQuery] = useState("");
  const [url, setUrl] = useState("");
  const [mode, setMode] = useState<"keyword" | "url">("keyword");
  const navigate = useNavigate();
  const { t } = useTranslation();

  const { data: dashboard, loading: dashboardLoading, request } = useApi<DashboardData>();

  useEffect(() => {
    request("/api/stats/dashboard");
    // Refresh every 60s
    const interval = setInterval(() => request("/api/stats/dashboard"), 60_000);
    return () => clearInterval(interval);
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    const q = mode === "url" ? url : query;
    if (q.trim()) {
      navigate(`/search?q=${encodeURIComponent(q.trim())}`);
    }
  };

  const stats = dashboard?.overview;
  const today = dashboard?.today;

  return (
    <div>
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-b from-primary/5 to-background dark:from-primary/10 dark:to-background">
        <div className="container mx-auto px-4 py-16 md:py-24">
          <div className="max-w-3xl mx-auto text-center">
            <h1 className="text-4xl md:text-6xl font-bold tracking-tight mb-6">
              {t("home.hero_title")}
              <span className="text-primary"> {t("home.hero_title_highlight")}</span>
            </h1>
            <p className="text-lg md:text-xl text-muted-foreground mb-10 max-w-2xl mx-auto">
              {t("home.hero_desc")}
            </p>

            {/* Search Form */}
            <form onSubmit={handleSearch} className="max-w-2xl mx-auto">
              <div className="flex gap-2 mb-4 justify-center">
                <button
                  type="button"
                  onClick={() => setMode("keyword")}
                  className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                    mode === "keyword"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  }`}
                >
                  {t("home.keyword_search")}
                </button>
                <button
                  type="button"
                  onClick={() => setMode("url")}
                  className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                    mode === "url"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  }`}
                >
                  {t("home.url_trace")}
                </button>
              </div>

              <div className="relative">
                <input
                  type="text"
                  value={mode === "url" ? url : query}
                  onChange={(e) =>
                    mode === "url" ? setUrl(e.target.value) : setQuery(e.target.value)
                  }
                  placeholder={
                    mode === "keyword"
                      ? "输入事件关键词，如「XX食品安全事件」..."
                      : "粘贴链接，如 https://weibo.com/... 或 https://mp.weixin.qq.com/..."
                  }
                  className="w-full h-14 px-6 pr-14 rounded-xl border-2 border-primary/20 bg-background text-lg shadow-lg focus:border-primary focus:outline-none focus:ring-4 focus:ring-primary/10 transition-all"
                />
                <button
                  type="submit"
                  className="absolute right-2 top-1/2 -translate-y-1/2 h-10 w-10 rounded-lg bg-primary text-primary-foreground flex items-center justify-center hover:bg-primary/90 transition-colors"
                >
                  <Search className="h-5 w-5" />
                </button>
              </div>

              {mode === "url" && (
                <p className="text-xs text-muted-foreground mt-2">
                  支持微博、知乎、微信公众号、Twitter、新闻网站等全平台链接
                </p>
              )}
            </form>
          </div>
        </div>
      </section>

      {/* Live Stats Bar */}
      {stats && (
        <section className="border-b bg-card/50">
          <div className="container mx-auto px-4 py-4">
            <div className="flex items-center gap-2 mb-3">
              <Radio className="h-4 w-4 text-green-500 animate-pulse" />
              <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">实时数据</span>
              <span className="text-xs text-muted-foreground ml-auto">
                每 60 秒自动刷新
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="flex items-center gap-3 p-3 rounded-lg bg-card border">
                <div className="h-10 w-10 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                  <Activity className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <div className="text-2xl font-bold">{stats.total_events.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">事件总数</div>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg bg-card border">
                <div className="h-10 w-10 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                  <Globe className="h-5 w-5 text-green-600 dark:text-green-400" />
                </div>
                <div>
                  <div className="text-2xl font-bold">{stats.total_sources.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">信息来源</div>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg bg-card border">
                <div className="h-10 w-10 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                  <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400" />
                </div>
                <div>
                  <div className="text-2xl font-bold">{stats.total_rumor_reports.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">辟谣报告</div>
                </div>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg bg-card border">
                <div className="h-10 w-10 rounded-lg bg-yellow-100 dark:bg-yellow-900/30 flex items-center justify-center">
                  <BarChart3 className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
                </div>
                <div>
                  <div className="text-2xl font-bold">{stats.avg_credibility}</div>
                  <div className="text-xs text-muted-foreground">平均可信度</div>
                </div>
              </div>
            </div>

            {/* Today's activity + mini trend */}
            {today && (
              <div className="flex flex-wrap items-center gap-4 mt-3 text-xs text-muted-foreground">
                <span>
                  📅 今日新增: <strong className="text-foreground">{today.new_events}</strong> 个事件
                  {" | "}
                  <strong className="text-foreground">{today.new_traces}</strong> 次溯源
                </span>
                {dashboard?.credibility_distribution && (
                  <span className="hidden sm:inline">
                    ✅ 可信: <strong className="text-green-600">{dashboard.credibility_distribution.high}</strong>
                    {" | "}⚠️ 存疑: <strong className="text-yellow-600">{dashboard.credibility_distribution.medium}</strong>
                    {" | "}🚫 低可信: <strong className="text-red-600">{dashboard.credibility_distribution.low}</strong>
                  </span>
                )}
              </div>
            )}
          </div>
        </section>
      )}

      {/* Hot Events + Platform Distribution */}
      {dashboard?.hot_events && dashboard.hot_events.length > 0 && (
        <section className="container mx-auto px-4 py-12">
          <div className="grid md:grid-cols-3 gap-8">
            {/* Hot Events */}
            <div className="md:col-span-2">
              <div className="flex items-center gap-2 mb-4">
                <Zap className="h-5 w-5 text-yellow-500" />
                <h2 className="text-lg font-bold">热点事件</h2>
              </div>
              <div className="space-y-3">
                {dashboard.hot_events.map((event) => (
                  <Link
                    key={event.id}
                    to={`/events/${event.id}`}
                    className="block p-4 rounded-xl border bg-card hover:shadow-md hover:border-primary/30 transition-all group"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <h3 className="font-semibold truncate group-hover:text-primary transition-colors">
                          {event.title}
                        </h3>
                        <div className="flex flex-wrap items-center gap-2 mt-2">
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${credibilityBg(event.credibility_score)}`}>
                            可信度 {event.credibility_score}
                          </span>
                          <span className="text-xs text-muted-foreground flex items-center gap-1">
                            <Globe className="h-3 w-3" /> {event.source_count} 个来源
                          </span>
                          {event.last_updated_at && (
                            <span className="text-xs text-muted-foreground flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {formatRelativeTime(event.last_updated_at)}
                            </span>
                          )}
                        </div>
                      </div>
                      <ArrowRight className="h-4 w-4 text-muted-foreground/0 group-hover:text-muted-foreground flex-shrink-0 transition-all" />
                    </div>
                  </Link>
                ))}
              </div>
              <Link
                to="/search"
                className="inline-flex items-center gap-1 mt-4 text-sm text-primary hover:underline"
              >
                查看全部事件 <ArrowRight className="h-3 w-3" />
              </Link>
            </div>

            {/* Platform Distribution */}
            {dashboard.platforms && dashboard.platforms.length > 0 && (
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <Globe className="h-5 w-5 text-blue-500" />
                  <h2 className="text-lg font-bold">平台分布</h2>
                </div>
                <div className="p-4 rounded-xl border bg-card space-y-3">
                  {dashboard.platforms.map((p) => (
                    <div key={p.platform}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium">
                          {PLATFORM_LABELS[p.platform] || p.platform}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {p.count.toLocaleString()} ({p.percentage}%)
                        </span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full transition-all duration-500"
                          style={{ width: `${Math.max(p.percentage, 2)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>

                {/* Verdicts mini */}
                {dashboard.verdicts && dashboard.verdicts.length > 0 && (
                  <div className="mt-4 p-4 rounded-xl border bg-card">
                    <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                      <Shield className="h-4 w-4 text-red-500" />
                      辟谣判定分布
                    </h3>
                    <div className="space-y-2">
                      {dashboard.verdicts.map((v) => (
                        <div key={v.verdict} className="flex items-center justify-between text-sm">
                          <span className="flex items-center gap-1.5">
                            {v.verdict === "false" ? "🚫" :
                             v.verdict === "misleading" ? "⚠️" :
                             v.verdict === "true" ? "✅" :
                             v.verdict === "unverified" ? "❓" : "📋"}
                            {verdictLabel(v.verdict)}
                          </span>
                          <span className="font-mono text-muted-foreground">{v.count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </section>
      )}

      {/* Loading state for dashboard */}
      {dashboardLoading && !dashboard && (
        <section className="container mx-auto px-4 py-12 text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-muted-foreground" />
          <p className="text-sm text-muted-foreground mt-2">加载实时数据...</p>
        </section>
      )}

      {/* Features */}
      <section className="container mx-auto px-4 py-20">
        <div className="grid md:grid-cols-3 gap-8">
          <div className="p-6 rounded-xl border bg-card hover:shadow-lg transition-shadow">
            <div className="h-12 w-12 rounded-lg bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center mb-4">
              <Globe className="h-6 w-6 text-blue-600 dark:text-blue-400" />
            </div>
            <h3 className="text-lg font-semibold mb-2">全网溯源</h3>
            <p className="text-muted-foreground text-sm">
              覆盖微博、知乎、Twitter、Reddit、新闻网站等全平台，
              URL 跳转链完整解析，找到信息的最初发布者。
            </p>
          </div>

          <div className="p-6 rounded-xl border bg-card hover:shadow-lg transition-shadow">
            <div className="h-12 w-12 rounded-lg bg-green-100 dark:bg-green-900/30 flex items-center justify-center mb-4">
              <TrendingUp className="h-6 w-6 text-green-600 dark:text-green-400" />
            </div>
            <h3 className="text-lg font-semibold mb-2">传播链路分析</h3>
            <p className="text-muted-foreground text-sm">
              可视化展示信息的传播网络，从源头到爆发再到全网扩散，
              一目了然看到信息如何传播演变。
            </p>
          </div>

          <div className="p-6 rounded-xl border bg-card hover:shadow-lg transition-shadow">
            <div className="h-12 w-12 rounded-lg bg-red-100 dark:bg-red-900/30 flex items-center justify-center mb-4">
              <Shield className="h-6 w-6 text-red-600 dark:text-red-400" />
            </div>
            <h3 className="text-lg font-semibold mb-2">智能辟谣</h3>
            <p className="text-muted-foreground text-sm">
              基于 NLP 和传播模式分析的谣言检测，多源交叉验证，
              自动生成辟谣报告，帮你识别虚假信息。
            </p>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="container mx-auto px-4 py-20 border-t">
        <h2 className="text-3xl font-bold text-center mb-12">如何工作</h2>
        <div className="grid md:grid-cols-4 gap-6 max-w-4xl mx-auto">
          {[
            { step: "01", title: "提交链接/关键词", desc: "输入你想追溯的信息链接或关键词" },
            { step: "02", title: "智能爬取分析", desc: "系统自动爬取相关内容，分析事件要素" },
            { step: "03", title: "传播链路构建", desc: "构建信息传播网络，识别源头" },
            { step: "04", title: "生成溯源报告", desc: "输出完整的溯源分析和辟谣结论" },
          ].map((item) => (
            <div key={item.step} className="text-center">
              <div className="h-12 w-12 rounded-full bg-primary/10 text-primary font-bold flex items-center justify-center mx-auto mb-3">
                {item.step}
              </div>
              <h4 className="font-semibold mb-1">{item.title}</h4>
              <p className="text-sm text-muted-foreground">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="container mx-auto px-4 py-20 text-center border-t">
        <h2 className="text-2xl font-bold mb-4">遇到让你不确定的信息？</h2>
        <p className="text-muted-foreground mb-8 max-w-md mx-auto">
          把链接粘贴过来，让 TruthTrace 帮你查个水落石出。
        </p>
        <Link
          to="/search"
          className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors"
        >
          开始追溯 <ArrowRight className="h-4 w-4" />
        </Link>
      </section>
    </div>
  );
}
