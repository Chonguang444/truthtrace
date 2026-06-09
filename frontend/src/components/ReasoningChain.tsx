/**
 * 推理链可视化 — 将引擎推理步骤渲染为可展开的时间线
 *
 * 每一步显示:
 * - 步骤编号 + 描述
 * - 结论 + 置信度标签
 * - 证据列表 (可展开)
 * - 不确定性声明
 */

import { useState } from "react";
import { ChevronDown, ChevronRight, FileText, AlertCircle, CheckCircle, HelpCircle } from "lucide-react";

interface ReasoningStep {
  step_id: number;
  description: string;
  conclusion: string;
  confidence: string;
  evidence?: { description: string; source_url: string; quote: string }[];
  counter_evidence?: any[];
  uncertainty_note?: string;
}

interface ReasoningChainProps {
  chain: ReasoningStep[] | null;
}

function confidenceBadge(conf: string) {
  const map: Record<string, { label: string; color: string }> = {
    certain: { label: "确定", color: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400" },
    high: { label: "高", color: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400" },
    moderate: { label: "中", color: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400" },
    low: { label: "低", color: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400" },
    uncertain: { label: "不确定", color: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400" },
  };
  return map[conf] || { label: conf, color: "bg-gray-100" };
}

export function ReasoningChain({ chain }: ReasoningChainProps) {
  if (!chain || chain.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-8 text-muted-foreground text-sm">
        暂无推理链数据
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Vertical line */}
      <div className="absolute left-5 top-0 bottom-0 w-0.5 bg-border" />

      <div className="space-y-4">
        {chain.map((step, i) => (
          <ReasoningStepItem key={step.step_id || i} step={step} isLast={i === chain.length - 1} />
        ))}
      </div>
    </div>
  );
}

function ReasoningStepItem({ step, isLast }: { step: ReasoningStep; isLast: boolean }) {
  const [open, setOpen] = useState(false);
  const badge = confidenceBadge(step.confidence || "moderate");

  return (
    <div className="relative pl-10">
      {/* Circle indicator */}
      <div className={`absolute left-2.5 h-5 w-5 rounded-full border-2 bg-card flex items-center justify-center z-10 ${
        step.confidence === "certain" || step.confidence === "high"
          ? "border-green-500"
          : step.confidence === "moderate"
          ? "border-yellow-500"
          : "border-gray-300"
      }`}>
        <div className={`h-2 w-2 rounded-full ${
          step.confidence === "certain" || step.confidence === "high" ? "bg-green-500" :
          step.confidence === "moderate" ? "bg-yellow-500" : "bg-gray-300"
        }`} />
      </div>

      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[10px] font-mono text-muted-foreground">Step {step.step_id}</span>
              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${badge.color}`}>
                {badge.label}
              </span>
            </div>
            <p className="text-sm font-medium truncate">{step.description}</p>
          </div>
          <div className="flex-shrink-0">
            {open ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
          </div>
        </div>

        <p className="text-xs text-muted-foreground mt-1.5 truncate">{step.conclusion}</p>
      </button>

      {/* Expanded detail */}
      {open && (
        <div className="mt-2 ml-2 pl-4 border-l-2 border-muted space-y-3">
          {/* Conclusion */}
          <div className="flex items-start gap-2">
            <CheckCircle className="h-3.5 w-3.5 text-green-500 mt-0.5 flex-shrink-0" />
            <p className="text-xs">{step.conclusion}</p>
          </div>

          {/* Evidence */}
          {step.evidence && step.evidence.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">支撑证据</p>
              {step.evidence.slice(0, 3).map((ev, i) => (
                <div key={i} className="flex items-start gap-2 mb-1.5">
                  <FileText className="h-3 w-3 text-blue-500 mt-0.5 flex-shrink-0" />
                  <div className="text-xs">
                    <p className="leading-relaxed">{ev.description}</p>
                    {ev.quote && <p className="text-[10px] text-muted-foreground mt-0.5 italic">“{ev.quote.slice(0, 120)}”</p>}
                    {ev.source_url && <p className="text-[10px] text-primary mt-0.5 truncate">{ev.source_url}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Counter evidence */}
          {step.counter_evidence && step.counter_evidence.length > 0 && (
            <div>
              <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider mb-1">反面证据</p>
              {step.counter_evidence.slice(0, 3).map((ev: any, i: number) => (
                <div key={i} className="flex items-start gap-2 mb-1">
                  <AlertCircle className="h-3 w-3 text-yellow-500 mt-0.5 flex-shrink-0" />
                  <p className="text-xs">{ev.description}</p>
                </div>
              ))}
            </div>
          )}

          {/* Uncertainty */}
          {step.uncertainty_note && (
            <div className="flex items-start gap-2">
              <HelpCircle className="h-3.5 w-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
              <p className="text-[11px] text-muted-foreground">{step.uncertainty_note}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
