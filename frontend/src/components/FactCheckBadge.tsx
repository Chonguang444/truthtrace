import { CheckCircle, XCircle, AlertTriangle, HelpCircle, ExternalLink } from "lucide-react";

interface FactCheckMatch {
  claim_text: string;
  fact_check_url: string;
  publisher_name: string;
  publisher_site: string;
  review_date: string;
  textual_rating: string;
  rating_normalized: string;
  match_confidence: number;
  snippet: string;
}

interface FactCheckBadgeProps {
  matches: FactCheckMatch[];
  totalSearched?: number;
  summary?: string;
  compact?: boolean;
}

const RATING_CONFIG: Record<string, { icon: typeof CheckCircle; color: string; bg: string; label: string }> = {
  true: { icon: CheckCircle, color: "text-green-600", bg: "bg-green-50 dark:bg-green-950", label: "真实" },
  false: { icon: XCircle, color: "text-red-600", bg: "bg-red-50 dark:bg-red-950", label: "虚假" },
  misleading: { icon: AlertTriangle, color: "text-amber-600", bg: "bg-amber-50 dark:bg-amber-950", label: "误导" },
  unverified: { icon: HelpCircle, color: "text-gray-500", bg: "bg-gray-50 dark:bg-gray-900", label: "未验证" },
};

export function FactCheckBadge({ matches, totalSearched, summary, compact = false }: FactCheckBadgeProps) {
  if (!matches || matches.length === 0) {
    return (
      <div className={`rounded-lg border p-3 text-sm ${compact ? "text-xs" : ""}`}>
        <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
          <HelpCircle size={compact ? 14 : 16} />
          <span>
            {totalSearched
              ? `已搜索 ${totalSearched} 条主张，未找到第三方核查结果`
              : summary || "未找到第三方事实核查数据"}
          </span>
        </div>
      </div>
    );
  }

  if (compact) {
    // Compact mode: single-line summary with count badges
    const tally: Record<string, number> = {};
    matches.forEach((m) => {
      tally[m.rating_normalized] = (tally[m.rating_normalized] || 0) + 1;
    });
    return (
      <div className="flex items-center gap-1.5 flex-wrap text-xs">
        <span className="text-gray-500">第三方核查:</span>
        {Object.entries(tally).map(([key, count]) => {
          const cfg = RATING_CONFIG[key] || RATING_CONFIG.unverified;
          const Icon = cfg.icon;
          return (
            <span
              key={key}
              className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full ${cfg.bg} ${cfg.color}`}
            >
              <Icon size={11} />
              <span className="font-medium">{cfg.label}</span>
              <span>×{count}</span>
            </span>
          );
        })}
        {summary && (
          <span className="text-gray-400 ml-1 truncate max-w-[200px]">{summary}</span>
        )}
      </div>
    );
  }

  // Full mode: card with detailed matches
  return (
    <div className="rounded-lg border bg-white dark:bg-gray-900 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2.5 bg-gray-50 dark:bg-gray-800 border-b flex items-center justify-between">
        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
          第三方事实核查 ({matches.length})
        </h4>
        {totalSearched && (
          <span className="text-xs text-gray-400">
            共搜索 {totalSearched} 条主张
          </span>
        )}
      </div>

      {/* Match list */}
      <div className="divide-y dark:divide-gray-800">
        {matches.slice(0, 8).map((match, i) => {
          const cfg = RATING_CONFIG[match.rating_normalized] || RATING_CONFIG.unverified;
          const Icon = cfg.icon;
          return (
            <div key={i} className="px-4 py-2.5 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
              <div className="flex items-start gap-2.5">
                <span className={`mt-0.5 shrink-0 ${cfg.color}`}>
                  <Icon size={16} />
                </span>
                <div className="min-w-0 flex-1">
                  {/* Rating + Publisher */}
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${cfg.bg} ${cfg.color}`}>
                      {match.textual_rating || cfg.label}
                    </span>
                    <span className="text-xs text-gray-500">
                      {match.publisher_name}
                    </span>
                    {match.match_confidence > 0 && (
                      <span className="text-[10px] text-gray-400">
                        匹配度 {(match.match_confidence * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>

                  {/* Claim text */}
                  {match.claim_text && (
                    <p className="text-xs text-gray-600 dark:text-gray-400 mb-1 line-clamp-2">
                      "{match.claim_text}"
                    </p>
                  )}

                  {/* Snippet */}
                  {match.snippet && (
                    <p className="text-xs text-gray-500 mb-1 line-clamp-2">
                      {match.snippet}
                    </p>
                  )}

                  {/* Source link + Date */}
                  <div className="flex items-center gap-2 text-xs">
                    {match.fact_check_url && (
                      <a
                        href={match.fact_check_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-blue-500 hover:underline inline-flex items-center gap-1"
                      >
                        <ExternalLink size={11} />
                        查看原文
                      </a>
                    )}
                    {match.review_date && (
                      <span className="text-gray-400">
                        {match.review_date.slice(0, 10)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer summary */}
      {summary && (
        <div className="px-4 py-2 bg-gray-50 dark:bg-gray-800 border-t text-xs text-gray-500">
          {summary}
        </div>
      )}
    </div>
  );
}

export default FactCheckBadge;
