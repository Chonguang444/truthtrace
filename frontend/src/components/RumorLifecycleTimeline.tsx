/**
 * RumorLifecycleTimeline — 谣言6阶段生命周期可视化
 * 诞生→潜伏→放大→高峰→辟谣→衰退
 */
import { Clock, TrendingUp, AlertTriangle, CheckCircle2, BarChart3, Activity } from "lucide-react";

interface LifecycleStage {
  stage: string; timestamp: string; description: string;
  reach_estimate: number; key_event: string; propagation_speed: number;
}

interface Props {
  result?: {
    rumor_text?: string; lifecycle_stages?: LifecycleStage[];
    total_lifetime_hours?: number; peak_reach?: number;
    time_to_peak_hours?: number; time_to_debunk_hours?: number;
    debunk_effectiveness?: number; survival_rank?: string;
    amplification_factors?: string[]; key_amplifiers?: string[];
  } | null;
}

const STAGE_ICONS: Record<string, string> = {
  birth: "👶", incubation: "🥚", amplification: "📢",
  peak: "🔥", debunking: "🛡️", decay: "📉",
};
const STAGE_COLORS: Record<string, string> = {
  birth: "#6b7280", incubation: "#ca8a04", amplification: "#ea580c",
  peak: "#dc2626", debunking: "#16a34a", decay: "#8b5cf6",
};

export function RumorLifecycleTimeline({ result }: Props) {
  if (!result || !result.lifecycle_stages) return null;

  const stages = result.lifecycle_stages;
  const maxReach = Math.max(...stages.map(s => s.reach_estimate), 1);

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/20">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <Activity size={14} /> 谣言生命追踪
        </h3>
      </div>
      <div className="p-4 space-y-4">
        {/* Survival rank */}
        {result.survival_rank && (
          <div className="p-3 rounded-lg bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-950/20 dark:to-purple-950/20 border text-center">
            <p className="text-xs text-muted-foreground">{result.survival_rank}</p>
          </div>
        )}

        {/* Stats grid */}
        <div className="grid grid-cols-3 gap-2 text-center">
          <div className="p-2 rounded-lg bg-muted/30">
            <div className="text-lg font-bold">{result.total_lifetime_hours?.toFixed(0)}h</div>
            <div className="text-[10px] text-muted-foreground">存活时间</div>
          </div>
          <div className="p-2 rounded-lg bg-muted/30">
            <div className="text-lg font-bold">{result.peak_reach?.toLocaleString()}</div>
            <div className="text-[10px] text-muted-foreground">峰值触达</div>
          </div>
          <div className="p-2 rounded-lg bg-muted/30">
            <div className="text-lg font-bold">{(result.debunk_effectiveness || 0) * 100 > 1 ? ((result.debunk_effectiveness || 0) * 100).toFixed(0) + "%" : "N/A"}</div>
            <div className="text-[10px] text-muted-foreground">辟谣效果</div>
          </div>
        </div>

        {/* Timeline */}
        <div className="relative">
          {/* Horizontal line */}
          <div className="absolute top-5 left-0 right-0 h-0.5 bg-muted" />

          <div className="grid grid-cols-6 gap-1 relative">
            {stages.map((stage, i) => (
              <div key={i} className="text-center relative z-10">
                {/* Dot */}
                <div className="w-10 h-10 mx-auto rounded-full flex items-center justify-center text-lg border-2 mb-1"
                  style={{ borderColor: STAGE_COLORS[stage.stage] || "#6b7280", backgroundColor: "var(--background)" }}>
                  {STAGE_ICONS[stage.stage] || "●"}
                </div>
                <div className="text-[9px] font-medium" style={{ color: STAGE_COLORS[stage.stage] }}>
                  {stage.stage === "birth" ? "诞生" :
                   stage.stage === "incubation" ? "潜伏" :
                   stage.stage === "amplification" ? "放大" :
                   stage.stage === "peak" ? "高峰" :
                   stage.stage === "debunking" ? "辟谣" : "衰退"}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Stage details */}
        <div className="space-y-1.5 max-h-48 overflow-y-auto">
          {stages.map((stage, i) => {
            const barW = (stage.reach_estimate / maxReach * 100).toFixed(0);
            return (
              <div key={i} className="p-2 rounded-lg bg-muted/20 text-xs">
                <div className="flex items-center justify-between mb-0.5">
                  <span className="font-medium flex items-center gap-1">
                    <span>{STAGE_ICONS[stage.stage]}</span>
                    <span style={{ color: STAGE_COLORS[stage.stage] }}>
                      {stage.stage === "birth" ? "诞生" :
                       stage.stage === "incubation" ? "潜伏期" :
                       stage.stage === "amplification" ? "放大期" :
                       stage.stage === "peak" ? "高峰期" :
                       stage.stage === "debunking" ? "辟谣期" : "衰退期"}
                    </span>
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    {stage.reach_estimate?.toLocaleString()} 人触及
                  </span>
                </div>
                <div className="h-1.5 bg-muted rounded-full overflow-hidden mb-1">
                  <div className="h-full rounded-full transition-all" style={{
                    width: `${barW}%`,
                    backgroundColor: STAGE_COLORS[stage.stage] || "#6b7280",
                  }} />
                </div>
                <p className="text-[10px] text-muted-foreground">{stage.key_event}</p>
              </div>
            );
          })}
        </div>

        {/* Amplifiers */}
        {result.key_amplifiers && result.key_amplifiers.length > 0 && (
          <div className="p-2 rounded-lg bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800 text-xs">
            <span className="font-medium text-amber-700">📢 关键放大节点: </span>
            {result.key_amplifiers.join(", ")}
          </div>
        )}
      </div>
    </div>
  );
}
