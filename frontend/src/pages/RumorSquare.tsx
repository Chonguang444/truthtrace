import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Shield, Filter } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useRumors } from "../hooks/useApi";
import { LoadingState, ErrorState, EmptyState } from "../components/Status";
import { formatDate, verdictLabel } from "../lib/utils";

export function RumorSquare() {
  const { t } = useTranslation();
  const { data, loading, error, fetch } = useRumors();
  const [verdictFilter, setVerdictFilter] = useState("");

  useEffect(() => {
    fetch(verdictFilter || undefined);
  }, [verdictFilter]);

  const rumors = data?.rumors || [];

  const verdictStats = rumors.length > 0 ? {
    total: rumors.length,
    false: rumors.filter((r: any) => r.verdict === "false").length,
    misleading: rumors.filter((r: any) => r.verdict === "misleading").length,
    unverified: rumors.filter((r: any) => r.verdict === "unverified").length,
  } : null;

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-4">
          <Shield className="h-8 w-8 text-red-500" />
          <div>
            <h1 className="text-3xl font-bold">{t("rumor.square")}</h1>
            <p className="text-muted-foreground">
              已核实的虚假信息和谣言，帮助你识别真相
            </p>
          </div>
        </div>

        {/* Stats */}
        {verdictStats && (
          <div className="grid grid-cols-4 gap-4 mb-6">
            <div className="p-4 rounded-lg border bg-card text-center">
              <div className="text-2xl font-bold">{verdictStats.total}</div>
              <div className="text-xs text-muted-foreground">总计</div>
            </div>
            <div className="p-4 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30 text-center">
              <div className="text-2xl font-bold text-red-600 dark:text-red-400">{verdictStats.false}</div>
              <div className="text-xs text-red-600 dark:text-red-400">确认为假</div>
            </div>
            <div className="p-4 rounded-lg border border-yellow-200 dark:border-yellow-800 bg-yellow-50 dark:bg-yellow-950/30 text-center">
              <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{verdictStats.misleading}</div>
              <div className="text-xs text-yellow-600 dark:text-yellow-400">误导性</div>
            </div>
            <div className="p-4 rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30 text-center">
              <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">{verdictStats.unverified}</div>
              <div className="text-xs text-blue-600 dark:text-blue-400">待验证</div>
            </div>
          </div>
        )}

        {/* Filter */}
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          {[
            { value: "", label: t("rumor.all") },
            { value: "false", label: t("verdict.false") },
            { value: "misleading", label: t("verdict.misleading") },
            { value: "unverified", label: t("verdict.unverified") },
          ].map(({ value, label }) => (
            <button
              key={value}
              onClick={() => setVerdictFilter(value)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                verdictFilter === value
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Loading / Error */}
      {loading && <LoadingState>加载辟谣数据...</LoadingState>}

      {error && (
        <ErrorState message={error} onRetry={() => fetch(verdictFilter || undefined)} />
      )}

      {/* Cards */}
      <div className="grid md:grid-cols-2 gap-4">
        {rumors.map((rumor: any) => (
          <div
            key={rumor.id}
            className={`p-5 rounded-lg border bg-card hover:shadow-md transition-all ${
              rumor.verdict === "false"
                ? "border-l-4 border-l-red-500"
                : rumor.verdict === "misleading"
                ? "border-l-4 border-l-yellow-500"
                : "border-l-4 border-l-blue-500"
            }`}
          >
            <div className="flex items-start justify-between mb-3">
              <span
                className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                  rumor.verdict === "false"
                    ? "bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400"
                    : rumor.verdict === "misleading"
                    ? "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-800 dark:text-yellow-400"
                    : "bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-400"
                }`}
              >
                {verdictLabel(rumor.verdict)}
              </span>
              <span className="text-xs text-muted-foreground">
                {formatDate(rumor.published_at)}
              </span>
            </div>

            <h3 className="font-semibold mb-2">{rumor.event_title}</h3>

            <div className="mb-3 p-3 rounded bg-muted/50">
              <p className="text-sm text-muted-foreground mb-1">🚨 谣言内容：</p>
              <p className="text-sm">{rumor.rumor_claim}</p>
            </div>

            {rumor.fact_check_result && (
              <div className="mb-3 p-3 rounded bg-green-50 dark:bg-green-950/30">
                <p className="text-sm text-green-800 dark:text-green-400 mb-1">✅ 事实核查：</p>
                <p className="text-sm">{rumor.fact_check_result}</p>
              </div>
            )}

            {rumor.correction && (
              <div className="mb-3 p-3 rounded bg-blue-50 dark:bg-blue-950/30">
                <p className="text-sm text-blue-800 dark:text-blue-400 mb-1">📝 纠正：</p>
                <p className="text-sm">{rumor.correction}</p>
              </div>
            )}

            <div className="flex justify-between items-center">
              <Link
                to={`/events/${rumor.event_id}`}
                className="text-sm text-primary hover:underline"
              >
                查看事件详情 →
              </Link>
              {rumor.verified_sources?.length > 0 && (
                <span className="text-xs text-muted-foreground">
                  {rumor.verified_sources.length} 个验证来源
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Empty */}
      {!loading && rumors.length === 0 && (
        <EmptyState
          icon="shield"
          title={t("rumor.no_rumors")}
          description="辟谣广场会展示经过核实的虚假信息，帮助大家避免被误导。提交溯源任务后，系统会自动生成辟谣报告。"
        />
      )}
    </div>
  );
}
