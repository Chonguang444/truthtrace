/**
 * CredibilityIndexGraph — 溯源可信度传播图
 * 展示传播链中每个节点的可信度评分和衰减
 */
import { useState } from "react";
import { Shield, TrendingDown, TrendingUp, Link2, AlertTriangle } from "lucide-react";

interface NodeData {
  node_id: string; node_url: string; node_platform: string;
  source_authority: number; content_integrity: number; citation_quality: number;
  initial_credibility: number; final_credibility: number;
  is_original: boolean; distortion_detected: boolean;
  amplification_role: string; edge_confidence: number;
}

interface Props {
  result?: {
    nodes?: NodeData[];
    root_credibility?: number;
    chain_integrity_score?: number;
    average_decay_rate?: number;
    weakest_link?: NodeData | null;
    strongest_link?: NodeData | null;
    total_nodes?: number;
    summary?: string;
    recommendations?: string[];
  } | null;
}

function credColor(v: number): string {
  if (v >= 0.75) return "#16a34a";
  if (v >= 0.5) return "#ca8a04";
  if (v >= 0.3) return "#ea580c";
  return "#dc2626";
}

export function CredibilityIndexGraph({ result }: Props) {
  if (!result || !result.nodes || result.nodes.length === 0) return null;

  const nodes = result.nodes;
  const maxCred = Math.max(...nodes.map(n => n.final_credibility));

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/20 flex items-center justify-between">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <Shield size={14} /> 溯源可信度指数
        </h3>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-muted">
          {result.total_nodes} 节点 · 完整性 {((result.chain_integrity_score || 0) * 100).toFixed(0)}%
        </span>
      </div>

      <div className="p-4 space-y-3">
        {/* Root credibility gauge */}
        <div className="flex items-center gap-3">
          <div className="text-2xl font-bold" style={{ color: credColor(result.root_credibility || 0.5) }}>
            {((result.root_credibility || 0) * 100).toFixed(0)}
          </div>
          <div className="text-xs text-muted-foreground">
            根节点可信度
            {result.average_decay_rate !== undefined && (
              <span className="ml-2 text-[10px]">
                平均衰减 {(result.average_decay_rate * 100).toFixed(1)}%
              </span>
            )}
          </div>
        </div>

        {/* Node credibility bars */}
        <div className="space-y-1.5 max-h-64 overflow-y-auto">
          {nodes.map((node, i) => {
            const final = node.final_credibility;
            const barW = (final / maxCred * 100).toFixed(0);
            return (
              <div key={i} className="group">
                <div className="flex items-center justify-between text-[10px] mb-0.5">
                  <span className="truncate max-w-[200px] flex items-center gap-1">
                    {node.is_original && <span className="text-[9px] px-1 py-0 rounded bg-amber-100 text-amber-700">原始</span>}
                    {node.amplification_role === "originator" && "📌 "}
                    {node.node_url?.slice(0, 50) || `节点 ${i + 1}`}
                  </span>
                  <span className="font-mono font-medium" style={{ color: credColor(final) }}>
                    {(final * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="flex items-center gap-1">
                  <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                    <div className="h-full rounded-full transition-all" style={{
                      width: `${barW}%`,
                      backgroundColor: credColor(final),
                    }} />
                  </div>
                  {/* 3 dimensions mini bars */}
                  <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <div className="w-1.5 h-4 bg-muted rounded relative" title="来源权威度">
                      <div className="absolute bottom-0 w-full rounded bg-blue-400" style={{ height: `${(node.source_authority * 100).toFixed(0)}%` }} />
                    </div>
                    <div className="w-1.5 h-4 bg-muted rounded relative" title="内容完整度">
                      <div className="absolute bottom-0 w-full rounded bg-green-400" style={{ height: `${(node.content_integrity * 100).toFixed(0)}%` }} />
                    </div>
                    <div className="w-1.5 h-4 bg-muted rounded relative" title="引用质量">
                      <div className="absolute bottom-0 w-full rounded bg-purple-400" style={{ height: `${(node.citation_quality * 100).toFixed(0)}%` }} />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Weakest/Strongest */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          {result.weakest_link && (
            <div className="p-2 rounded-lg bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800">
              <span className="text-red-600 font-medium flex items-center gap-1">
                <TrendingDown size={12} /> 最弱链接
              </span>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                {result.weakest_link.node_url?.slice(0, 60)}
              </p>
              <p className="text-xs font-bold text-red-600">
                可信度 {(result.weakest_link.final_credibility * 100).toFixed(0)}%
              </p>
            </div>
          )}
          {result.strongest_link && (
            <div className="p-2 rounded-lg bg-green-50 dark:bg-green-950/20 border border-green-200 dark:border-green-800">
              <span className="text-green-600 font-medium flex items-center gap-1">
                <TrendingUp size={12} /> 最强链接
              </span>
              <p className="text-[10px] text-muted-foreground mt-0.5">
                {result.strongest_link.node_url?.slice(0, 60)}
              </p>
              <p className="text-xs font-bold text-green-600">
                可信度 {(result.strongest_link.final_credibility * 100).toFixed(0)}%
              </p>
            </div>
          )}
        </div>

        {result.recommendations && result.recommendations.length > 0 && (
          <div className="space-y-1">
            {result.recommendations.map((r, i) => (
              <div key={i} className="flex items-start gap-1.5 text-xs text-amber-600 dark:text-amber-400">
                <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                <span>{r}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
