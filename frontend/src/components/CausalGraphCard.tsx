import { useState } from "react";
import { GitBranch, AlertTriangle, ArrowRight, Circle, Zap, X } from "lucide-react";

interface CausalNode {
  node_id: string;
  label: string;
  description?: string;
  evidence_level: string;
  credibility: number;
  is_root: boolean;
  is_effect: boolean;
}

interface CausalEdge {
  source_id: string;
  target_id: string;
  relation: string;
  claim_type: string;
  evidence_quote?: string;
  confidence: number;
  fallacy_detected: boolean;
  fallacy_type: string;
}

interface Fallacy {
  fallacy_type: string;
  description: string;
  evidence_snippet: string;
  severity: number;
  suggested_correction?: string;
}

interface CausalGraphData {
  total_claims: number;
  causal_claims: Array<{ cause: string; effect: string; type: string; confidence: number; snippet: string }>;
  fallacies: Fallacy[];
  graph: {
    nodes: CausalNode[];
    edges: CausalEdge[];
    total_nodes: number;
    total_edges: number;
  };
  summary: string;
  overall_causal_quality: number;
}

interface CausalGraphCardProps {
  data: CausalGraphData | null;
  compact?: boolean;
}

const FALLACY_LABELS: Record<string, string> = {
  post_hoc: "后此谬误",
  corr_as_cause: "相关即因果",
  reversed: "因果倒置",
  confounder_omit: "遗漏混淆变量",
  slippery_slope: "滑坡论证",
  missing_mechanism: "缺乏因果机制",
  single_cause: "单一原因谬误",
};

function qualityColor(score: number): string {
  if (score >= 70) return "text-green-600 bg-green-50 dark:bg-green-950/30 border-green-200";
  if (score >= 40) return "text-amber-600 bg-amber-50 dark:bg-amber-950/30 border-amber-200";
  return "text-red-600 bg-red-50 dark:bg-red-950/30 border-red-200";
}

export function CausalGraphCard({ data, compact = false }: CausalGraphCardProps) {
  const [showClaims, setShowClaims] = useState(false);
  const [showFallacies, setShowFallacies] = useState(true);

  if (!data || (data.total_claims === 0 && data.fallacies.length === 0)) {
    return (
      <div className="rounded-lg border p-4 text-sm">
        <div className="flex items-center gap-2 text-muted-foreground">
          <GitBranch size={16} />
          <span>未检测到明确的因果关系声明</span>
        </div>
      </div>
    );
  }

  const nodes = data.graph?.nodes || [];
  const edges = data.graph?.edges || [];
  const rootNodes = nodes.filter((n) => n.is_root);
  const effectNodes = nodes.filter((n) => n.is_effect);
  const fallacyEdges = edges.filter((e) => e.fallacy_detected);
  const avgCredibility =
    nodes.length > 0
      ? nodes.reduce((sum, n) => sum + n.credibility, 0) / nodes.length
      : 50;

  if (compact) {
    return (
      <div className={`rounded-lg border p-3 text-xs ${qualityColor(data.overall_causal_quality)}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <GitBranch size={14} />
            <span className="font-semibold">因果分析</span>
          </div>
          <span className="font-mono font-bold">
            {data.total_claims}主张 · {nodes.length}节点 · {edges.length}边
          </span>
        </div>
        {data.fallacies.length > 0 && (
          <div className="mt-1.5 flex items-center gap-1 text-red-600">
            <AlertTriangle size={12} />
            <span>{data.fallacies.length}处因果谬误</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      {/* Header */}
      <div className={`p-4 border-b ${qualityColor(data.overall_causal_quality)}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitBranch size={18} />
            <h3 className="font-semibold text-sm">因果图谱分析</h3>
          </div>
          <span className="text-xs font-mono opacity-60">引擎 #20</span>
        </div>
        <div className="mt-2 flex items-center gap-3 text-xs">
          <span className="font-bold text-lg">{data.overall_causal_quality.toFixed(0)}</span>
          <span>/100 因果推理质量</span>
          <span className="px-1.5 py-0.5 rounded-full bg-background text-[10px]">
            {data.overall_causal_quality >= 70 ? "因果逻辑良好" :
             data.overall_causal_quality >= 40 ? "需进一步验证" :
             "存在严重因果谬误"}
          </span>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Summary */}
        <p className="text-xs text-muted-foreground leading-relaxed">
          {data.summary}
        </p>

        {/* Causal Graph mini-visualization */}
        {nodes.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold flex items-center gap-4">
              因果链
              <span className="font-normal text-muted-foreground">
                {rootNodes.length}源 → {effectNodes.length}果
                · 平均可信度 {avgCredibility.toFixed(0)}/100
              </span>
            </h4>

            <div className="space-y-1.5 max-h-[300px] overflow-y-auto">
              {edges.map((edge, i) => {
                const sourceNode = nodes.find((n) => n.node_id === edge.source_id);
                const targetNode = nodes.find((n) => n.node_id === edge.target_id);
                return (
                  <div
                    key={i}
                    className={`flex items-center gap-2 p-2 rounded-md text-xs border ${
                      edge.fallacy_detected
                        ? "bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-800"
                        : "bg-muted/30 border-transparent"
                    }`}
                  >
                    {edge.fallacy_detected ? (
                      <AlertTriangle size={14} className="text-red-500 shrink-0" />
                    ) : (
                      <Zap size={14} className="text-amber-500 shrink-0" />
                    )}
                    <div className="flex-1 min-w-0 flex items-center gap-1.5 flex-wrap">
                      <span className="font-medium truncate max-w-[120px]">
                        {sourceNode?.label || edge.source_id}
                      </span>
                      <ArrowRight size={12} className="shrink-0 text-muted-foreground" />
                      <span className="font-medium truncate max-w-[120px]">
                        {targetNode?.label || edge.target_id}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 shrink-0">
                      <span
                        className={`px-1 py-0.5 rounded text-[10px] font-mono ${
                          edge.confidence >= 50
                            ? "bg-green-100 text-green-700"
                            : "bg-red-100 text-red-700"
                        }`}
                      >
                        {edge.confidence.toFixed(0)}%
                      </span>
                      {edge.fallacy_detected && (
                        <span className="text-[10px] text-red-500 font-medium">
                          {FALLACY_LABELS[edge.fallacy_type] || edge.fallacy_type}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Stats bar */}
            <div className="flex gap-3 text-[10px] text-muted-foreground">
              <span className="flex items-center gap-1">
                <Circle size={6} className="text-green-400" />
                可信节点: {nodes.filter((n) => n.credibility >= 60).length}
              </span>
              <span className="flex items-center gap-1">
                <Circle size={6} className="text-red-400" />
                因果谬误边: {fallacyEdges.length}
              </span>
              <span className="flex items-center gap-1">
                <Circle size={6} className="text-blue-400" />
                根节点: {rootNodes.length}
              </span>
              <span className="flex items-center gap-1">
                <Circle size={6} className="text-purple-400" />
                结果节点: {effectNodes.length}
              </span>
            </div>
          </div>
        )}

        {/* Fallacies */}
        {data.fallacies.length > 0 && (
          <div>
            <button
              onClick={() => setShowFallacies(!showFallacies)}
              className="flex items-center justify-between w-full text-xs font-semibold"
            >
              <div className="flex items-center gap-1.5">
                <AlertTriangle size={14} className="text-red-500" />
                因果谬误 ({data.fallacies.length}处)
              </div>
              {showFallacies ? <X size={12} className="opacity-40" /> : <span className="text-primary text-[10px]">展开</span>}
            </button>

            {showFallacies && (
              <div className="mt-2 space-y-1.5">
                {data.fallacies.map((f, i) => (
                  <div
                    key={i}
                    className="p-2 rounded-md bg-red-50 dark:bg-red-950/20 border border-red-100 dark:border-red-900/50 text-xs"
                  >
                    <div className="flex items-start gap-2">
                      <AlertTriangle size={12} className="text-red-500 mt-0.5 shrink-0" />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-red-700 dark:text-red-400">
                            {FALLACY_LABELS[f.fallacy_type] || f.fallacy_type}
                          </span>
                          <span className="text-[10px] opacity-50">严重度 {f.severity.toFixed(0)}</span>
                        </div>
                        <p className="text-red-600/70 dark:text-red-400/70 mt-0.5">{f.description}</p>
                        {f.evidence_snippet && (
                          <p className="mt-1 p-1.5 rounded bg-red-100/50 dark:bg-red-900/30 text-[10px] italic line-clamp-2">
                            "{f.evidence_snippet}"
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Claims */}
        {data.causal_claims?.length > 0 && (
          <div>
            <button
              onClick={() => setShowClaims(!showClaims)}
              className="flex items-center justify-between w-full text-xs font-semibold"
            >
              <span className="flex items-center gap-1.5">
                因果主张 ({data.causal_claims.length}条)
              </span>
              {showClaims ? <X size={12} className="opacity-40" /> : <span className="text-primary text-[10px]">展开</span>}
            </button>

            {showClaims && (
              <div className="mt-2 space-y-1">
                {data.causal_claims.slice(0, 8).map((c, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs p-1.5 rounded bg-muted/30">
                    <span className="font-medium truncate max-w-[140px]">{c.cause}</span>
                    <div className="flex items-center gap-1 shrink-0">
                      <span className="text-[10px] text-muted-foreground">{c.type === "direct_cause" ? "导致" : "相关于"}</span>
                      <span className={`px-1 py-0.5 rounded text-[10px] font-mono ${c.confidence >= 50 ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                        {c.confidence.toFixed(0)}%
                      </span>
                    </div>
                    <span className="font-medium truncate max-w-[140px]">{c.effect}</span>
                  </div>
                ))}
                {data.causal_claims.length > 8 && (
                  <div className="text-[10px] text-muted-foreground text-center">
                    +{data.causal_claims.length - 8} 条
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
