/**
 * PrebunkingCard — 预揭露提示卡片组件
 *
 * 基于 Inoculation Theory (心理免疫理论):
 * - 33实验元分析 (N=37,075) 证实有效
 * - 命名操纵手法→解释为何有效→提供检测线索
 * - 不直接说"这是假的" → 不触发心理防御
 */
import { useState } from "react";
import { Shield, AlertTriangle, Eye, ChevronDown, ChevronUp, Brain, Lightbulb } from "lucide-react";

interface TechniqueDetection {
  technique: string;
  name: string;
  match_count: number;
  confidence: number;
  snippets: string[];
  short_desc: string;
  detection_clues: string[];
}

interface Props {
  result?: {
    techniques_detected?: TechniqueDetection[];
    primary_technique?: string;
    prebunking_card?: string;
    inoculations?: string[];
    detection_count?: number;
    risk_level?: string;
    summary?: string;
  } | null;
  compact?: boolean;
}

const TECHNIQUE_ICONS: Record<string, string> = {
  emotional_manipulation: "😱",
  false_authority: "🎓",
  context_stripping: "✂️",
  false_dichotomy: "⚔️",
  conspiracy_framing: "🕵️",
  cherry_picking: "🍒",
  bandwagon: "👥",
  fear_mongering: "💀",
};

const RISK_COLORS: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  high: {
    bg: "bg-red-50 dark:bg-red-950/20",
    border: "border-red-200 dark:border-red-800",
    text: "text-red-700 dark:text-red-300",
    badge: "bg-red-100 text-red-700 border-red-200",
  },
  medium: {
    bg: "bg-amber-50 dark:bg-amber-950/20",
    border: "border-amber-200 dark:border-amber-800",
    text: "text-amber-700 dark:text-amber-300",
    badge: "bg-amber-100 text-amber-700 border-amber-200",
  },
  low: {
    bg: "bg-blue-50 dark:bg-blue-950/20",
    border: "border-blue-200 dark:border-blue-800",
    text: "text-blue-700 dark:text-blue-300",
    badge: "bg-blue-100 text-blue-700 border-blue-200",
  },
};

export function PrebunkingCard({ result, compact = false }: Props) {
  const [expanded, setExpanded] = useState(!compact);

  if (!result || !result.techniques_detected || result.techniques_detected.length === 0) {
    if (compact) return null;
    return (
      <div className="rounded-xl border bg-card p-4 space-y-2">
        <div className="flex items-center gap-2">
          <Shield className="h-4 w-4 text-green-500" />
          <span className="text-sm font-medium text-muted-foreground">
            未检测到明显的操纵手法
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          这段内容可能以较为中立的方式呈现信息。但请注意，这并不意味着内容一定准确——仍需交叉验证。
        </p>
      </div>
    );
  }

  const colors = RISK_COLORS[result.risk_level || "low"] || RISK_COLORS.low;
  const techniques = result.techniques_detected;

  return (
    <div className={`rounded-xl border ${colors.border} ${colors.bg} overflow-hidden`}>
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className={`w-full px-4 py-3 flex items-center justify-between hover:bg-black/5 dark:hover:bg-white/5 transition-colors ${colors.text}`}
      >
        <div className="flex items-center gap-2.5">
          <Brain className="h-5 w-5" />
          <div className="text-left">
            <h3 className="text-sm font-semibold">批判思维预揭露</h3>
            <p className="text-[11px] opacity-70">
              检测到 {result.detection_count} 种操纵手法 · 风险: {result.risk_level === "high" ? "高" : result.risk_level === "medium" ? "中" : "低"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${colors.badge}`}>
            {result.primary_technique ? TECHNIQUE_ICONS[result.primary_technique] || "" : ""}
            {techniques[0]?.name || ""}
          </span>
          {expanded ? (
            <ChevronUp className="h-4 w-4 opacity-50" />
          ) : (
            <ChevronDown className="h-4 w-4 opacity-50" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-inherit pt-3">
          {/* Theory context */}
          <div className="flex items-start gap-2 p-2 rounded-lg bg-background/50 text-xs text-muted-foreground">
            <Lightbulb className="h-3.5 w-3.5 mt-0.5 text-amber-500 shrink-0" />
            <p>
              信息的操纵手法是"套路"——识别套路本身就能增强你的抵抗力。
              这与"这是假的"不同，我们只是提醒你注意常见的信息操纵模式。
            </p>
          </div>

          {/* Technique cards */}
          <div className="space-y-2">
            {techniques.slice(0, compact ? 1 : 3).map((tech, i) => (
              <div key={i} className="rounded-lg border bg-background/60 p-3 space-y-1.5">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{TECHNIQUE_ICONS[tech.technique] || "📌"}</span>
                  <span className="text-sm font-semibold">{tech.name}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted">
                    置信度 {Math.round(tech.confidence * 100)}%
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">{tech.short_desc}</p>
                {tech.detection_clues && tech.detection_clues.length > 0 && (
                  <div className="space-y-0.5">
                    <p className="text-[10px] font-medium uppercase text-muted-foreground/70">检测线索</p>
                    {tech.detection_clues.slice(0, 2).map((clue, j) => (
                      <div key={j} className="flex items-start gap-1.5 text-xs text-muted-foreground">
                        <Eye className="h-3 w-3 mt-0.5 shrink-0" />
                        <span>{clue}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Inoculation tips */}
          {!compact && result.inoculations && result.inoculations.length > 0 && (
            <div className="rounded-lg border bg-background/60 p-3 space-y-1.5">
              <p className="text-xs font-semibold flex items-center gap-1">
                <Shield className="h-3.5 w-3.5" /> 批判思维建议
              </p>
              {result.inoculations.map((inoc, i) => (
                <p key={i} className="text-xs text-muted-foreground leading-relaxed">
                  {inoc}
                </p>
              ))}
            </div>
          )}

          {/* Action tips */}
          <div className="flex items-start gap-2 p-2 rounded-lg bg-background/50 text-xs text-muted-foreground">
            <AlertTriangle className="h-3.5 w-3.5 mt-0.5 text-amber-500 shrink-0" />
            <p>
              在看到情绪化或确定性的断言时，请暂停，深呼吸。独立核实来源，寻找原始证据。批判思维是你可以培养的"认知免疫力"。
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
