import { Shield, Zap, Fingerprint, AlertTriangle, BarChart3, Activity } from "lucide-react";

interface AIDetectionConsensusProps {
  aiDetection?: {
    risk_score?: number;
    matches?: any[];
    summary?: string;
  } | null;
  lmscanDetection?: {
    ai_probability?: number;
    feature_count_flagged?: number;
    confidence?: string;
    model_fingerprint?: string;
    features?: any[];
    summary?: string;
  } | null;
  smellcheckDetection?: {
    anomaly_score?: number;
    total_flags?: number;
    categories_triggered?: number;
    flags?: any[];
    summary?: string;
  } | null;
  compact?: boolean;
}

// Consensus level colors
function consensusColor(agreement: number): string {
  if (agreement >= 0.7) return "text-red-600 dark:text-red-400";
  if (agreement >= 0.4) return "text-amber-600 dark:text-amber-400";
  return "text-green-600 dark:text-green-400";
}

function consensusBg(agreement: number): string {
  if (agreement >= 0.7) return "bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-800";
  if (agreement >= 0.4) return "bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800";
  return "bg-green-50 dark:bg-green-950/20 border-green-200 dark:border-green-800";
}

export function AIDetectionConsensus({
  aiDetection,
  lmscanDetection,
  smellcheckDetection,
  compact = false,
}: AIDetectionConsensusProps) {
  // Collect all available detectors
  const detectors: { name: string; score: number; active: boolean; detail?: string }[] = [];

  if (aiDetection && aiDetection.risk_score !== undefined) {
    detectors.push({
      name: "AI 内容检测",
      score: (aiDetection.risk_score || 0) / 100,
      active: (aiDetection.risk_score || 0) > 20,
      detail: aiDetection.summary,
    });
  }

  if (lmscanDetection && lmscanDetection.ai_probability !== undefined) {
    detectors.push({
      name: "lmscan 统计",
      score: lmscanDetection.ai_probability || 0,
      active: (lmscanDetection.feature_count_flagged || 0) >= 2,
      detail: lmscanDetection.summary,
    });
  }

  if (smellcheckDetection && smellcheckDetection.anomaly_score !== undefined) {
    detectors.push({
      name: "smellcheck 指纹",
      score: (smellcheckDetection.anomaly_score || 0) / 100,
      active: (smellcheckDetection.total_flags || 0) > 0,
      detail: smellcheckDetection.summary,
    });
  }

  if (detectors.length === 0) {
    return null;
  }

  // Compute agreement
  const activeCount = detectors.filter((d) => d.active).length;
  const agreement = activeCount / Math.max(detectors.length, 1);

  // Compute average score
  const avgScore = detectors.reduce((s, d) => s + d.score, 0) / detectors.length;
  const consensusLabel =
    agreement >= 0.7 ? "高度一致 — 多个检测器均发现 AI 信号" :
    agreement >= 0.4 ? "部分一致 — 部分检测器发现 AI 信号" :
    "不一致 — 检测器间信号矛盾，可能为人工内容";

  if (compact) {
    return (
      <div className={`rounded-lg border p-2.5 ${consensusBg(agreement)}`}>
        <div className="flex items-center gap-2 text-xs">
          <Shield size={13} className={consensusColor(agreement)} />
          <span className="font-medium">AI 检测共识:</span>
          <span className={consensusColor(agreement)}>{activeCount}/{detectors.length} 一致</span>
          <span className="text-muted-foreground">
            (综合 {(avgScore * 100).toFixed(0)}%)
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      {/* Header */}
      <div className="px-4 py-2.5 bg-muted/30 border-b">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity size={16} className={consensusColor(agreement)} />
            <h4 className="text-sm font-medium">AI 内容检测共识面板</h4>
          </div>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${consensusBg(agreement)} ${consensusColor(agreement)}`}>
            {activeCount}/{detectors.length} 一致
          </span>
        </div>
      </div>

      {/* Consensus gauge */}
      <div className="px-4 py-3">
        <div className="flex items-center gap-3 mb-3">
          {/* Simple gauge */}
          <div className="relative w-16 h-16 shrink-0">
            <svg viewBox="0 0 64 64" className="w-full h-full -rotate-90">
              <circle cx="32" cy="32" r="28" fill="none" stroke="#e5e7eb" strokeWidth="6" />
              <circle
                cx="32" cy="32" r="28" fill="none"
                stroke={avgScore >= 0.7 ? "#ef4444" : avgScore >= 0.4 ? "#f59e0b" : "#10b981"}
                strokeWidth="6"
                strokeDasharray={`${2 * Math.PI * 28}`}
                strokeDashoffset={`${2 * Math.PI * 28 * (1 - avgScore)}`}
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-sm font-bold">{(avgScore * 100).toFixed(0)}</span>
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium">{consensusLabel}</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              综合 {(avgScore * 100).toFixed(0)}% AI 概率 · {detectors.length} 个检测器
            </p>
          </div>
        </div>

        {/* Per-detector bars */}
        <div className="space-y-1.5">
          {detectors.map((d, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className={`text-[11px] w-24 shrink-0 ${d.active ? "font-medium" : "text-muted-foreground"}`}>
                {d.name}
              </span>
              <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    d.score >= 0.7 ? "bg-red-500" :
                    d.score >= 0.4 ? "bg-amber-500" :
                    "bg-green-500"
                  }`}
                  style={{ width: `${d.score * 100}%` }}
                />
              </div>
              <span className="text-[11px] w-9 text-right tabular-nums">
                {(d.score * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>

        {/* Model fingerprint (lmscan) */}
        {lmscanDetection?.model_fingerprint && lmscanDetection.model_fingerprint !== "likely_human" && (
          <div className="mt-3 flex items-center gap-1.5 text-xs">
            <Fingerprint size={12} className="text-purple-500" />
            <span className="text-muted-foreground">模型指纹:</span>
            <span className="font-medium text-purple-600 dark:text-purple-400">
              {lmscanDetection.model_fingerprint}
            </span>
          </div>
        )}
      </div>

      {/* Top flagged features */}
      {lmscanDetection?.features && lmscanDetection.features.filter((f: any) => f.flagged).length > 0 && (
        <div className="border-t px-4 py-2">
          <div className="flex items-center gap-1 text-[11px] text-muted-foreground mb-1.5">
            <Zap size={11} />
            lmscan 触发特征 ({lmscanDetection.feature_count_flagged}):
          </div>
          <div className="flex flex-wrap gap-1">
            {lmscanDetection.features
              .filter((f: any) => f.flagged)
              .slice(0, 6)
              .map((f: any, i: number) => (
                <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-muted">
                  {f.name}: {f.score.toFixed(2)}
                </span>
              ))}
          </div>
        </div>
      )}

      {/* smellcheck flags summary */}
      {smellcheckDetection?.flags && smellcheckDetection.flags.length > 0 && (
        <div className="border-t px-4 py-2">
          <div className="flex items-center gap-1 text-[11px] text-muted-foreground mb-1">
            <AlertTriangle size={11} />
            smellcheck 指纹 ({smellcheckDetection.categories_triggered}/8 类别):
          </div>
          <div className="space-y-0.5">
            {smellcheckDetection.flags.slice(0, 3).map((f: any, i: number) => (
              <div key={i} className="text-[10px] flex items-start gap-1">
                <span className={`shrink-0 mt-0.5 ${
                  f.severity === "high" ? "text-red-500" :
                  f.severity === "medium" ? "text-amber-500" : "text-gray-400"
                }`}>●</span>
                <span className="text-muted-foreground">{f.description?.slice(0, 100)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default AIDetectionConsensus;
