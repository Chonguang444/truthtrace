import { useState, useEffect } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Search as SearchIcon, Loader2, AlertCircle, ExternalLink,
  Shield, Clock, Filter, SlidersHorizontal, Zap, ChevronDown,
} from "lucide-react";
import { useSearch, useTrace } from "../hooks/useApi";
import { formatRelativeTime, credibilityBg, verdictLabel } from "../lib/utils";
import { TaskTracker } from "../components/TaskTracker";
import { LoadingState, ErrorState, EmptyState } from "../components/Status";

interface SearchResult {
  id: string;
  title: string;
  summary: string;
  status: string;
  credibility_score: number;
  first_seen_at: string;
  last_updated_at: string;
  has_engine_analysis?: boolean;
  engine_verdict?: string;
  engine_distortion_count?: number;
  engine_fallacy_count?: number;
}

const EVENT_STATUS_OPTIONS = [
  { value: "", label: "全部状态" },
  { value: "emerging", label: "🆕 新出现" },
  { value: "active", label: "🔥 热议中" },
  { value: "resolved", label: "✅ 已定论" },
];

const CREDIBILITY_OPTIONS = [
  { value: "", label: "全部可信度" },
  { value: "high", label: "可信 (≥70)" },
  { value: "medium", label: "存疑 (40-69)" },
  { value: "low", label: "低可信 (<40)" },
];

const TIME_RANGE_OPTIONS = [
  { value: "", label: "全部时间" },
  { value: "day", label: "最近 24 小时" },
  { value: "week", label: "最近一周" },
  { value: "month", label: "最近一月" },
];

export function Search() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("q") || "";
  const url = searchParams.get("url") || "";

  const { data, loading, error, search } = useSearch();
  const { submit } = useTrace();

  const [traceUrl, setTraceUrl] = useState(url || "");
  const [submitting, setSubmitting] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  // Filters
  const [statusFilter, setStatusFilter] = useState("");
  const [credibilityFilter, setCredibilityFilter] = useState("");
  const [timeRangeFilter, setTimeRangeFilter] = useState("");

  useEffect(() => {
    if (query) {
      const filters: Record<string, string> = {};
      if (statusFilter) filters.status = statusFilter;
      if (credibilityFilter) filters.credibility = credibilityFilter;
      if (timeRangeFilter) filters.time_range = timeRangeFilter;
      search(query, filters);
    }
  }, [query, statusFilter, credibilityFilter, timeRangeFilter]);

  const handleTrace = async () => {
    if (!traceUrl.trim()) return;
    setSubmitting(true);
    setTaskId(null);
    const result = await submit(traceUrl);
    if (result?.task_id) {
      setTaskId(result.task_id);
    }
    setSubmitting(false);
  };

  const activeFilterCount =
    (statusFilter ? 1 : 0) + (credibilityFilter ? 1 : 0) + (timeRangeFilter ? 1 : 0);

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="max-w-4xl mx-auto mb-8">
        <h1 className="text-2xl font-bold mb-4">
          {query ? (
            <span>
              搜索: <span className="text-primary">{query}</span>
            </span>
          ) : (
            "事件搜索"
          )}
        </h1>

        {/* URL Trace Box */}
        <div className="p-5 rounded-xl border bg-gradient-to-r from-primary/5 to-blue-500/5 mb-6">
          <div className="flex items-center gap-3 mb-3">
            <div className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-primary" />
              <h3 className="text-sm font-semibold">快速 URL 溯源</h3>
            </div>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">支持抖音/B站/快手</span>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={traceUrl}
              onChange={(e) => setTraceUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleTrace()}
              placeholder="粘贴微博/知乎/微信/新闻链接..."
              className="flex-1 h-10 px-4 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
            />
            <button
              onClick={handleTrace}
              disabled={submitting || !traceUrl.trim()}
              className="px-5 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors flex items-center gap-2"
            >
              {submitting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Shield className="h-4 w-4" />
              )}
              {submitting ? "提交中..." : "开始追溯"}
            </button>
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            支持微博、知乎、微信公众号、Twitter/X、Reddit、新闻网站等全平台链接
          </p>

          {/* Task Tracker */}
          {taskId && (
            <div className="mt-4">
              <TaskTracker taskId={taskId} />
            </div>
          )}
        </div>
      </div>

      {/* Results Area */}
      <div className="max-w-4xl mx-auto">
        {/* Filter Bar */}
        {query && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowFilters(!showFilters)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    showFilters || activeFilterCount > 0
                      ? "bg-primary/10 text-primary"
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  }`}
                >
                  <SlidersHorizontal className="h-4 w-4" />
                  筛选
                  {activeFilterCount > 0 && (
                    <span className="ml-1 h-5 w-5 rounded-full bg-primary text-primary-foreground text-xs flex items-center justify-center">
                      {activeFilterCount}
                    </span>
                  )}
                </button>
              </div>
              <span className="text-xs text-muted-foreground">
                {data?.total != null ? `找到 ${data.total} 个事件` : ""}
              </span>
            </div>

            {/* Filter Panel */}
            {showFilters && (
              <div className="p-4 rounded-xl border bg-card grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4">
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1 block">
                    事件状态
                  </label>
                  <select
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    className="w-full h-9 px-3 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                  >
                    {EVENT_STATUS_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1 block">
                    可信度
                  </label>
                  <select
                    value={credibilityFilter}
                    onChange={(e) => setCredibilityFilter(e.target.value)}
                    className="w-full h-9 px-3 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                  >
                    {CREDIBILITY_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1 block">
                    时间范围
                  </label>
                  <select
                    value={timeRangeFilter}
                    onChange={(e) => setTimeRangeFilter(e.target.value)}
                    className="w-full h-9 px-3 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                  >
                    {TIME_RANGE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Loading */}
        {loading && query && <LoadingState>正在搜索分析...</LoadingState>}

        {/* Error */}
        {error && (
          <ErrorState
            message={error}
            onRetry={() => search(query)}
          />
        )}

        {/* Empty */}
        {data?.events?.length === 0 && !loading && query && (
          <EmptyState
            icon="search"
            title="未找到相关事件"
            description="试试输入 URL 进行溯源，或使用不同的关键词搜索。新的溯源结果会在后台处理后自动出现在搜索结果中。"
          />
        )}

        {/* No query yet */}
        {!query && !taskId && (
          <EmptyState
            icon="search"
            title="搜索或溯源"
            description="输入关键词搜索已有事件，或在上面粘贴链接进行全链路溯源分析。"
          />
        )}

        {/* Event Cards */}
        {data?.events?.length > 0 && (
          <div className="space-y-4">
            {data.events.map((event: SearchResult) => (
              <Link
                key={event.id}
                to={`/events/${event.id}`}
                className="block p-5 rounded-xl border bg-card hover:shadow-md transition-all hover:border-primary/30 group"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold text-lg truncate group-hover:text-primary transition-colors">
                        {event.title}
                      </h3>
                      <ExternalLink className="h-4 w-4 text-muted-foreground/0 group-hover:text-muted-foreground flex-shrink-0 transition-all" />
                    </div>
                    {event.summary && (
                      <p className="text-sm text-muted-foreground line-clamp-2 mb-3">
                        {event.summary}
                      </p>
                    )}
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${credibilityBg(
                          event.credibility_score
                        )}`}
                      >
                        可信度: {event.credibility_score}
                      </span>
                      {event.has_engine_analysis && event.engine_verdict && (
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          event.engine_verdict === "false" || event.engine_verdict === "likely_false"
                            ? "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
                            : event.engine_verdict === "misleading"
                            ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400"
                            : "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                        }`}>
                          🧠 {event.engine_verdict === "false" ? "虚假" :
                              event.engine_verdict === "likely_false" ? "可能虚假" :
                              event.engine_verdict === "misleading" ? "误导性" :
                              event.engine_verdict === "likely_true" ? "可能真实" :
                              event.engine_verdict === "true" ? "真实" : event.engine_verdict}
                        </span>
                      )}
                      {(event.engine_distortion_count || 0) > 0 && (
                        <span className="px-2 py-0.5 rounded-full bg-red-50 dark:bg-red-950/20 text-red-700 dark:text-red-400 text-xs font-medium">
                          ⚠️ {event.engine_distortion_count}处失真
                        </span>
                      )}
                      {(event.engine_fallacy_count || 0) > 0 && (
                        <span className="px-2 py-0.5 rounded-full bg-yellow-50 dark:bg-yellow-950/20 text-yellow-700 dark:text-yellow-400 text-xs font-medium">
                          🧠 {event.engine_fallacy_count}处谬误
                        </span>
                      )}
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" />
                        {formatRelativeTime(event.first_seen_at)}
                      </span>
                      <span className="text-xs text-muted-foreground capitalize px-2 py-0.5 rounded-full bg-muted">
                        {event.status === "active"
                          ? "🔥 热议中"
                          : event.status === "emerging"
                          ? "🆕 新出现"
                          : "✅ 已定论"}
                      </span>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
