import { useState, useEffect } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Search as SearchIcon, Loader2, ExternalLink,
  Shield, Clock, Filter, SlidersHorizontal, Zap,
} from "lucide-react";
import { useSearch } from "../hooks/useApi";
import { formatRelativeTime, credibilityBg } from "../lib/utils";
import { TaskTracker } from "../components/TaskTracker";
import { LoadingState, ErrorState, EmptyState } from "../components/Status";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

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
  source_count?: number;
  source_urls?: Array<{ url: string; platform: string; author: string }>;
}

const STATUS_OPTS = [
  { value: "", label: "全部状态" },
  { value: "emerging", label: "新出现" },
  { value: "active", label: "热议中" },
  { value: "resolved", label: "已定论" },
];
const CRED_OPTS = [
  { value: "", label: "全部可信度" },
  { value: "high", label: "可信 (>=70)" },
  { value: "medium", label: "存疑 (40-69)" },
  { value: "low", label: "低可信 (<40)" },
];

export function Search() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const query = searchParams.get("q") || "";
  const urlParam = searchParams.get("url") || "";

  const { data, loading, error, search } = useSearch();
  const [showFilters, setShowFilters] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [credibilityFilter, setCredibilityFilter] = useState("");

  // Trace state
  const [traceUrl, setTraceUrl] = useState(urlParam || "");
  const [submitting, setSubmitting] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [traceError, setTraceError] = useState("");

  // Search
  useEffect(() => {
    if (query) {
      const filters: Record<string, string> = {};
      if (statusFilter) filters.status = statusFilter;
      if (credibilityFilter) filters.credibility = credibilityFilter;
      search(query, filters);
    }
  }, [query, statusFilter, credibilityFilter]);

  // Trace
  const handleTrace = async () => {
    const u = traceUrl.trim();
    if (!u) return;
    setSubmitting(true);
    setTaskId(null);
    setTraceError("");
    try {
      const res = await fetch(`${API_BASE}/api/trace`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: u, deep_trace: false }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error((err as any).detail || `HTTP ${res.status}`);
      }
      const result = await res.json();
      if (result?.task_id) {
        setTaskId(result.task_id);
      } else {
        setTraceError("未获取到任务 ID，请重试");
      }
    } catch (e: any) {
      setTraceError(e.message || "提交失败");
    } finally {
      setSubmitting(false);
    }
  };

  const activeFilters = (statusFilter ? 1 : 0) + (credibilityFilter ? 1 : 0);

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <h1 className="text-2xl font-bold mb-6">
          {query ? <>搜索: <span className="text-primary">{query}</span></> : "事件搜索与溯源"}
        </h1>

        {/* URL Trace Box */}
        <div className="p-5 rounded-xl border bg-gradient-to-r from-primary/5 to-blue-500/5 mb-6">
          <div className="flex items-center gap-2 mb-3">
            <Zap className="h-5 w-5 text-primary" />
            <h3 className="text-sm font-semibold">快速 URL 溯源</h3>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={traceUrl}
              onChange={(e) => setTraceUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleTrace()}
              placeholder="粘贴微博/知乎/微信/新闻链接..."
              className="flex-1 h-10 px-4 rounded-lg border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
            <button
              onClick={handleTrace}
              disabled={submitting || !traceUrl.trim()}
              className="px-5 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50 flex items-center gap-2"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Shield className="h-4 w-4" />}
              {submitting ? "提交中..." : "开始追溯"}
            </button>
          </div>
          {traceError && <p className="text-xs text-red-600 mt-2">{traceError}</p>}
          {taskId && (
            <div className="mt-4">
              <TaskTracker taskId={taskId} />
            </div>
          )}
        </div>

        {/* Search input */}
        {!query && !taskId && (
          <div className="text-center py-12">
            <SearchIcon className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <p className="text-muted-foreground mb-4">输入关键词搜索已有事件，或在上面粘贴链接进行全链路溯源</p>
          </div>
        )}

        {/* Filters */}
        {query && (
          <div className="mb-6">
            <div className="flex items-center justify-between mb-3">
              <button
                onClick={() => setShowFilters(!showFilters)}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition ${
                  showFilters || activeFilters > 0 ? "bg-primary/10 text-primary" : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                <SlidersHorizontal className="h-4 w-4" />
                筛选 {activeFilters > 0 && `(${activeFilters})`}
              </button>
              <span className="text-xs text-muted-foreground">
                {data?.total != null ? `${data.total} 个结果` : ""}
              </span>
            </div>
            {showFilters && (
              <div className="p-4 rounded-xl border bg-card grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1 block">状态</label>
                  <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
                    className="w-full h-9 px-3 rounded-lg border bg-background text-sm">
                    {STATUS_OPTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground mb-1 block">可信度</label>
                  <select value={credibilityFilter} onChange={(e) => setCredibilityFilter(e.target.value)}
                    className="w-full h-9 px-3 rounded-lg border bg-background text-sm">
                    {CRED_OPTS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Results */}
        {loading && <LoadingState>搜索中...</LoadingState>}
        {error && <ErrorState message={error} onRetry={() => query && search(query)} />}
        {data?.events?.length === 0 && !loading && query && (
          <EmptyState icon="search" title="未找到相关事件"
            description="试试不同关键词，或粘贴 URL 进行溯源分析" />
        )}
        {data?.events?.length > 0 && (
          <div className="space-y-4">
            {data.events.map((event: SearchResult) => (
              <Link key={event.id} to={`/events/${event.id}`}
                className="block p-5 rounded-xl border bg-card hover:shadow-md hover:border-primary/30 transition-all group">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-lg truncate group-hover:text-primary transition-colors">
                      {event.title}
                    </h3>
                    {event.summary && (
                      <p className="text-sm text-muted-foreground line-clamp-2 mb-3">{event.summary}</p>
                    )}
                    {/* Source URLs */}
                    {event.source_urls && event.source_urls.length > 0 && (
                      <div className="mb-3 space-y-1">
                        {event.source_urls!.slice(0, 3).map((src, i) => (
                          <div key={i} className="flex items-center gap-1.5 text-xs">
                            <ExternalLink className="h-3 w-3 text-muted-foreground flex-shrink-0" />
                            <a href={src.url} target="_blank" rel="noopener noreferrer" onClick={e => e.stopPropagation()}
                              className="text-primary hover:underline truncate max-w-[500px]">{src.url}</a>
                            <span className="text-muted-foreground flex-shrink-0">({src.platform})</span>
                          </div>
                        ))}
                        {event.source_count && event.source_count > 3 && (
                          <span className="text-xs text-muted-foreground">+{event.source_count - 3} 更多</span>
                        )}
                      </div>
                    )}
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${credibilityBg(event.credibility_score)}`}>
                        可信度: {event.credibility_score}
                      </span>
                      {event.engine_verdict && (
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          event.engine_verdict === "false" || event.engine_verdict === "likely_false"
                            ? "bg-red-100 text-red-800" : event.engine_verdict === "misleading"
                            ? "bg-yellow-100 text-yellow-800" : "bg-green-100 text-green-800"
                        }`}>
                          {event.engine_verdict === "likely_false" ? "可能虚假" : event.engine_verdict}
                        </span>
                      )}
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" /> {formatRelativeTime(event.first_seen_at)}
                      </span>
                    </div>
                  </div>
                  <ExternalLink className="h-4 w-4 text-muted-foreground/0 group-hover:text-muted-foreground flex-shrink-0" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
