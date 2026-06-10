/**
 * 可视证据链展示系统
 *
 * 对标抖音"求真卡"的可视化证据呈现:
 *   - 逐条证据的声明-验证-来源三栏对比
 *   - 颜色编码: 绿色=验证通过 / 红色=被反驳 / 灰色=无法验证
 *   - 一键分享证据卡片
 *   - 权威来源链接可视化
 *   - 打印友好
 */

import { useState } from "react";
import {
  CheckCircle, XCircle, HelpCircle, ExternalLink, FileText,
  Share2, Copy, Download, Printer, ShieldAlert, Search, Zap,
  AlertTriangle, BarChart3, Clock, ChevronDown, ChevronRight,
} from "lucide-react";

interface EvidenceItem {
  claim: string;
  verdict: string; // "supported" | "refuted" | "unverifiable" | "partially_supported"
  explanation: string;
  sources?: Array<{ title: string; url: string; source_type: string; excerpt?: string }>;
  confidence: number;
}

interface EvidenceChainData {
  title: string;
  verdict: string;
  credibility_score: number;
  distortion_count?: number;
  fallacy_count?: number;
  ai_risk_score?: number;
  manipulation_score?: number;
  propagation_risk?: string;
  items: EvidenceItem[];
  authoritative_sources?: string[];
  correction?: string;
}

interface EvidenceChainProps {
  data: EvidenceChainData | null;
  compact?: boolean;
  showShare?: boolean;
}

function verdictColor(verdict: string): string {
  switch (verdict) {
    case "supported": return "text-green-700 bg-green-50 border-green-200 dark:bg-green-950/20 dark:text-green-400 dark:border-green-800";
    case "refuted": return "text-red-700 bg-red-50 border-red-200 dark:bg-red-950/20 dark:text-red-400 dark:border-red-800";
    case "partially_supported": return "text-yellow-700 bg-yellow-50 border-yellow-200 dark:bg-yellow-950/20 dark:text-yellow-400 dark:border-yellow-800";
    default: return "text-gray-500 bg-gray-50 border-gray-200 dark:bg-gray-950/20 dark:text-gray-400 dark:border-gray-700";
  }
}

function verdictIcon(verdict: string) {
  switch (verdict) {
    case "supported": return <CheckCircle className="h-4 w-4 text-green-600" />;
    case "refuted": return <XCircle className="h-4 w-4 text-red-600" />;
    case "partially_supported": return <AlertTriangle className="h-4 w-4 text-yellow-600" />;
    default: return <HelpCircle className="h-4 w-4 text-gray-400" />;
  }
}

function evidenceBadge(supported: number, refuted: number, unverified: number) {
  const total = supported + refuted + unverified;
  return (
    <div className="flex items-center gap-1.5 text-xs">
      <span className="flex items-center gap-0.5"><span className="w-2 h-2 rounded-full bg-green-500" />{supported}</span>
      <span className="flex items-center gap-0.5"><span className="w-2 h-2 rounded-full bg-red-500" />{refuted}</span>
      <span className="flex items-center gap-0.5"><span className="w-2 h-2 rounded-full bg-gray-300" />{unverified}</span>
      <span className="text-muted-foreground ml-1">/ {total}</span>
    </div>
  );
}

export function EvidenceChain({ data, compact = false, showShare = true }: EvidenceChainProps) {
  const [expandedItems, setExpandedItems] = useState<Set<number>>(new Set());
  const [copied, setCopied] = useState(false);

  if (!data) return null;

  const toggle = (idx: number) => {
    const next = new Set(expandedItems);
    next.has(idx) ? next.delete(idx) : next.add(idx);
    setExpandedItems(next);
  };

  const supported = data.items.filter(i => i.verdict === "supported").length;
  const refuted = data.items.filter(i => i.verdict === "refuted").length;
  const unverified = data.items.filter(i => i.verdict === "unverifiable").length;

  const handleCopyShare = () => {
    const text = data.items.map((item, i) =>
      `[${i + 1}] ${item.verdict === "supported" ? "✅" : item.verdict === "refuted" ? "❌" : "❓"} ${item.claim}\n` +
      `   ${item.explanation}\n` +
      (item.sources?.map(s => `   📎 ${s.title}: ${s.url}`).join("\n") || "")
    ).join("\n\n");
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`rounded-xl border bg-card ${compact ? "p-4" : "p-6"}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`h-10 w-10 rounded-lg ${
            data.credibility_score >= 60 ? "bg-green-100 dark:bg-green-950/30" :
            data.credibility_score >= 40 ? "bg-yellow-100 dark:bg-yellow-950/30" :
            "bg-red-100 dark:bg-red-950/30"
          } flex items-center justify-center`}>
            <ShieldAlert className={`h-5 w-5 ${
              data.credibility_score >= 60 ? "text-green-600" :
              data.credibility_score >= 40 ? "text-yellow-600" : "text-red-600"
            }`} />
          </div>
          <div>
            <h3 className="font-bold text-sm">{data.title || "证据链分析"}</h3>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-xs font-mono font-bold">{data.credibility_score}/100</span>
              <span className="text-xs text-muted-foreground">{data.verdict}</span>
              {evidenceBadge(supported, refuted, unverified)}
            </div>
          </div>
        </div>

        {showShare && (
          <div className="flex gap-1">
            <button onClick={handleCopyShare}
              className="p-1.5 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
              title={copied ? "已复制!" : "复制证据文本"}>
              {copied ? <CheckCircle className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}
            </button>
            <button onClick={() => window.print()}
              className="p-1.5 rounded-md hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
              title="打印证据链">
              <Printer className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      {/* Summary metrics */}
      {!compact && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
          {data.distortion_count !== undefined && (
            <div className="p-2 rounded-lg bg-muted/30 text-center">
              <div className="text-lg font-bold text-red-600">{data.distortion_count}</div>
              <div className="text-[10px] text-muted-foreground">信息失真</div>
            </div>
          )}
          {data.fallacy_count !== undefined && (
            <div className="p-2 rounded-lg bg-muted/30 text-center">
              <div className="text-lg font-bold text-yellow-600">{data.fallacy_count}</div>
              <div className="text-[10px] text-muted-foreground">逻辑谬误</div>
            </div>
          )}
          {data.ai_risk_score !== undefined && data.ai_risk_score > 0 && (
            <div className="p-2 rounded-lg bg-muted/30 text-center">
              <div className="text-lg font-bold text-purple-600">{data.ai_risk_score}%</div>
              <div className="text-[10px] text-muted-foreground">AI风险</div>
            </div>
          )}
          {data.manipulation_score !== undefined && (
            <div className="p-2 rounded-lg bg-muted/30 text-center">
              <div className="text-lg font-bold text-orange-600">{data.manipulation_score}</div>
              <div className="text-[10px] text-muted-foreground">操纵评分</div>
            </div>
          )}
        </div>
      )}

      {/* Evidence Items */}
      <div className="space-y-2">
        {data.items.map((item, idx) => (
          <div key={idx} className={`p-3 rounded-lg border ${verdictColor(item.verdict)}`}>
            <button onClick={() => toggle(idx)}
              className="w-full flex items-start gap-3 text-left">
              <div className="flex-shrink-0 mt-0.5">
                {verdictIcon(item.verdict)}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-bold opacity-70">#{idx + 1}</span>
                  <span className="text-xs px-1.5 py-0.5 rounded-full font-medium bg-white/50 dark:bg-black/20">
                    {item.verdict === "supported" ? "已证实" :
                     item.verdict === "refuted" ? "已反驳" :
                     item.verdict === "partially_supported" ? "部分支持" : "待验证"}
                  </span>
                  {item.confidence > 0 && (
                    <span className="text-[10px] opacity-50">置信度 {(item.confidence * 100).toFixed(0)}%</span>
                  )}
                </div>
                <p className="text-sm leading-relaxed">{item.claim}</p>

                {expandedItems.has(idx) && (
                  <div className="mt-2 pt-2 border-t border-current/10 space-y-2">
                    <p className="text-xs opacity-80">{item.explanation}</p>
                    {item.sources && item.sources.length > 0 && (
                      <div className="space-y-1">
                        <p className="text-[10px] font-semibold uppercase opacity-60">权威来源</p>
                        {item.sources.slice(0, 3).map((src, si) => (
                          <a key={si} href={src.url} target="_blank" rel="noopener noreferrer"
                            onClick={e => e.stopPropagation()}
                            className="flex items-center gap-1 text-xs text-primary hover:underline">
                            <ExternalLink className="h-3 w-3 flex-shrink-0" />
                            <span className="truncate">{src.title}</span>
                            <span className="text-[10px] opacity-50 flex-shrink-0">({src.source_type})</span>
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
              <ChevronDown className={`h-4 w-4 flex-shrink-0 transition-transform ${expandedItems.has(idx) ? "rotate-180" : ""}`} />
            </button>
          </div>
        ))}
      </div>

      {/* Authoritative Sources */}
      {data.authoritative_sources && data.authoritative_sources.length > 0 && (
        <div className="mt-4 pt-4 border-t">
          <p className="text-xs font-semibold text-muted-foreground mb-2 flex items-center gap-1">
            <Search className="h-3 w-3" /> 交叉验证的权威来源
          </p>
          <div className="flex flex-wrap gap-1.5">
            {data.authoritative_sources.map((src, i) => (
              <span key={i} className="px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-400 text-[11px]">
                {src}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Correction */}
      {data.correction && (
        <div className="mt-4 p-3 rounded-lg bg-blue-50 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-900">
          <div className="flex items-center gap-2 mb-1">
            <Zap className="h-4 w-4 text-blue-600" />
            <span className="text-xs font-bold text-blue-700 dark:text-blue-400">纠偏建议</span>
          </div>
          <p className="text-xs text-blue-800 dark:text-blue-300 leading-relaxed">{data.correction}</p>
        </div>
      )}
    </div>
  );
}

/**
 * 从引擎分析JSON中提取证据链数据
 */
export function buildEvidenceChain(analysis: any): EvidenceChainData | null {
  if (!analysis) return null;

  const items: EvidenceItem[] = [];

  // 失真匹配
  const distortion = analysis.distortion_analysis || {};
  (distortion.matches || []).forEach((m: any) => {
    items.push({
      claim: m.description || m.desc || String(m),
      verdict: "refuted",
      explanation: m.reasoning || m.evidence_snippet || "",
      confidence: m.confidence === "high" ? 0.85 : m.confidence === "moderate" ? 0.6 : 0.3,
    });
  });

  // 逻辑谬误
  const fallacy = analysis.fallacy_analysis || {};
  (fallacy.matches || []).forEach((f: any) => {
    items.push({
      claim: f.description || String(f),
      verdict: "refuted",
      explanation: f.correction_hint || "",
      confidence: 0.6,
    });
  });

  // AI检测
  const ai = analysis.ai_detection || {};
  if (ai.risk_score > 0) {
    items.push({
      claim: `AI内容鉴伪: 风险评分 ${ai.risk_score}/100`,
      verdict: ai.risk_score >= 60 ? "refuted" : "unverifiable",
      explanation: ai.summary || "检测到AI生成或深度伪造特征",
      confidence: ai.confidence || 0.5,
    });
  }

  // RAG验证
  const rag = analysis.rag_verification || {};
  (rag.verified_claims || []).forEach((c: any) => {
    items.push({
      claim: c.claim || String(c),
      verdict: c.verdict || "unverifiable",
      explanation: c.explanation || "",
      sources: c.sources,
      confidence: c.confidence || 0.5,
    });
  });

  return {
    title: analysis.input_title || "证据链分析",
    verdict: analysis.verdict || "unverifiable",
    credibility_score: analysis.credibility_score || 50,
    distortion_count: (analysis.distortion_analysis?.matches || []).length,
    fallacy_count: analysis.fallacy_analysis?.fallacy_count || 0,
    ai_risk_score: analysis.ai_detection?.risk_score || 0,
    manipulation_score: analysis.narrative_analysis?.manipulation_score || 0,
    items,
    authoritative_sources: analysis.correction_references || [],
    correction: analysis.correction || "",
  };
}
