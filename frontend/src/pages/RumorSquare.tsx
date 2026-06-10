import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Shield, Filter, ExternalLink, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { formatDate, verdictLabel } from "../lib/utils";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

interface Rumor {
  id: string;
  event_id: string;
  event_title: string;
  rumor_claim: string;
  verdict: string;
  fact_check_result: string;
  correction: string;
  verified_sources?: Array<{ url: string; title: string }>;
  published_at: string;
}

export function RumorSquare() {
  const { t } = useTranslation();
  const [rumors, setRumors] = useState<Rumor[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [verdictFilter, setVerdictFilter] = useState("");

  const fetchRumors = async (verdict?: string) => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams({ limit: "20", offset: "0" });
      if (verdict) params.set("verdict", verdict);
      const res = await fetch(`${API_BASE}/api/rumors?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setRumors(data.rumors || []);
    } catch (e: any) {
      setError(e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRumors(verdictFilter || undefined);
  }, [verdictFilter]);

  const stats = rumors.length > 0 ? {
    total: rumors.length,
    false: rumors.filter(r => r.verdict === "false").length,
    misleading: rumors.filter(r => r.verdict === "misleading").length,
    unverified: rumors.filter(r => r.verdict === "unverified").length,
  } : null;

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-4">
          <Shield className="h-8 w-8 text-red-500" />
          <div>
            <h1 className="text-3xl font-bold">辟谣广场</h1>
            <p className="text-muted-foreground">已核实的虚假信息和谣言</p>
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="p-4 rounded-lg border bg-card text-center">
              <div className="text-2xl font-bold">{stats.total}</div>
              <div className="text-xs text-muted-foreground">总计</div>
            </div>
            <div className="p-4 rounded-lg border border-red-200 bg-red-50 dark:bg-red-950/20 text-center">
              <div className="text-2xl font-bold text-red-600">{stats.false}</div>
              <div className="text-xs text-red-600">确认为假</div>
            </div>
            <div className="p-4 rounded-lg border border-yellow-200 bg-yellow-50 dark:bg-yellow-950/20 text-center">
              <div className="text-2xl font-bold text-yellow-600">{stats.misleading}</div>
              <div className="text-xs text-yellow-600">误导性</div>
            </div>
            <div className="p-4 rounded-lg border border-blue-200 bg-blue-50 dark:bg-blue-950/20 text-center">
              <div className="text-2xl font-bold text-blue-600">{stats.unverified}</div>
              <div className="text-xs text-blue-600">待验证</div>
            </div>
          </div>
        )}

        {/* Filter */}
        <div className="flex items-center gap-2 mb-6">
          <Filter className="h-4 w-4 text-muted-foreground" />
          {[
            { value: "", label: "全部" },
            { value: "false", label: "确认为假" },
            { value: "misleading", label: "误导性" },
            { value: "unverified", label: "待验证" },
          ].map(({ value, label }) => (
            <button key={value} onClick={() => setVerdictFilter(value)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition ${
                verdictFilter === value ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Loading / Error */}
      {loading && (
        <div className="flex items-center gap-2 py-12 justify-center text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" /> 加载中...
        </div>
      )}
      {error && (
        <div className="py-12 text-center">
          <p className="text-red-600 mb-2">{error}</p>
          <button onClick={() => fetchRumors(verdictFilter || undefined)}
            className="text-sm text-primary hover:underline">重试</button>
        </div>
      )}

      {/* Rumor Cards */}
      {!loading && !error && (
        <div className="space-y-4">
          {rumors.map((rumor) => (
            <div key={rumor.id} className="p-5 rounded-xl border bg-card hover:shadow-sm transition-shadow">
              <div className="flex items-start justify-between gap-4 mb-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${
                      rumor.verdict === "false" ? "bg-red-100 text-red-700" :
                      rumor.verdict === "misleading" ? "bg-yellow-100 text-yellow-700" :
                      "bg-blue-100 text-blue-700"
                    }`}>
                      {rumor.verdict === "false" ? "虚假" : rumor.verdict === "misleading" ? "误导" : "待验证"}
                    </span>
                    <span className="text-xs text-muted-foreground">{formatDate(rumor.published_at)}</span>
                  </div>
                  <h3 className="font-semibold">{rumor.rumor_claim}</h3>
                  {rumor.event_title && (
                    <p className="text-xs text-muted-foreground mt-1">事件: {rumor.event_title}</p>
                  )}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-green-50 dark:bg-green-950/20 border border-green-100 dark:border-green-900 mb-3">
                <p className="text-xs font-medium text-green-700 dark:text-green-400 mb-1">事实核查</p>
                <p className="text-sm">{rumor.fact_check_result}</p>
              </div>

              {rumor.correction && (
                <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-900 mb-3">
                  <p className="text-xs font-medium text-blue-700 dark:text-blue-400 mb-1">纠偏建议</p>
                  <p className="text-sm">{rumor.correction}</p>
                </div>
              )}

              {rumor.verified_sources && rumor.verified_sources.length > 0 && (
                <div className="mt-2 pt-2 border-t">
                  <p className="text-xs text-muted-foreground mb-1">参考来源:</p>
                  {rumor.verified_sources!.slice(0, 3).map((src, i) => (
                    <a key={i} href={src.url} target="_blank" rel="noopener noreferrer"
                      className="flex items-center gap-1 text-xs text-primary hover:underline">
                      <ExternalLink className="h-3 w-3" /> {src.title || src.url}
                    </a>
                  ))}
                </div>
              )}

              {rumor.event_id && (
                <Link to={`/events/${rumor.event_id}`}
                  className="inline-flex items-center gap-1.5 mt-3 text-sm text-primary hover:underline">
                  查看事件详情 <ExternalLink className="h-3 w-3" />
                </Link>
              )}
            </div>
          ))}
          {rumors.length === 0 && !loading && (
            <div className="py-12 text-center text-muted-foreground">暂无辟谣记录</div>
          )}
        </div>
      )}
    </div>
  );
}
