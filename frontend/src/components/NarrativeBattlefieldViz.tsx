/**
 * NarrativeBattlefieldViz — 叙事战场可视化
 * 展示同一事件的多竞争叙事 + 证据/逻辑/伦理三维评判
 */
import { Crosshair, Scale, Brain, Eye } from "lucide-react";

interface NarrativeFrame {
  narrative_id: string; narrative_label: string; core_claim: string;
  evidence_quality: number; logical_coherence: number;
  ethical_assessment: string; emotional_appeal: string;
  target_audience: string; spreaders: string[]; strength: number; color: string;
}

interface Props {
  result?: {
    event_title?: string; narratives?: NarrativeFrame[];
    dominant_narrative?: NarrativeFrame | null;
    contested_areas?: { title: string; narratives: string[] }[];
    narrative_conflicts?: { narrative_a: string; narrative_b: string; tension: string }[];
    moral_ambiguity_score?: number; summary?: string; disclaimer?: string;
  } | null;
}

const EMOTION_COLORS: Record<string, string> = {
  "愤怒+悲情": "#dc2626", "自豪+愤怒": "#2563eb", "中性": "#6b7280",
  "恐惧": "#ea580c", "实用主义": "#ca8a04", "焦虑+怀旧": "#7c3aed",
};

export function NarrativeBattlefieldViz({ result }: Props) {
  if (!result || !result.narratives || result.narratives.length === 0) return null;

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/20 flex items-center justify-between">
        <h3 className="text-sm font-semibold flex items-center gap-2">
          <Crosshair size={14} /> 叙事战场
        </h3>
        <span className="text-[10px] text-muted-foreground">
          道德模糊度 {(result.moral_ambiguity_score || 0) * 100 > 1 ? ((result.moral_ambiguity_score || 0) * 100).toFixed(0) + "%" : "N/A"}
        </span>
      </div>
      <div className="p-4 space-y-3">
        {/* Disclaimer */}
        {result.disclaimer && (
          <div className="p-2 rounded-lg bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 text-xs text-muted-foreground">
            ⚠️ {result.disclaimer.slice(0, 200)}
          </div>
        )}

        {/* Battlefield visualization */}
        <div className="relative min-h-[200px] bg-muted/10 rounded-xl p-4">
          {/* Dominant narrative - center */}
          {result.dominant_narrative && (
            <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10">
              <div className="p-3 rounded-xl border-2 shadow-lg bg-card min-w-[180px] text-center"
                style={{ borderColor: result.dominant_narrative.color }}>
                <div className="text-lg mb-1">👑</div>
                <p className="text-xs font-bold">{result.dominant_narrative.narrative_label}</p>
                <div className="flex justify-center gap-2 mt-1 text-[9px] text-muted-foreground">
                  <span>证据 {(result.dominant_narrative.evidence_quality * 100).toFixed(0)}%</span>
                  <span>逻辑 {(result.dominant_narrative.logical_coherence * 100).toFixed(0)}%</span>
                </div>
              </div>
            </div>
          )}

          {/* Competing narratives - positioned around center */}
          {result.narratives
            .filter(n => n.narrative_label !== result.dominant_narrative?.narrative_label)
            .slice(0, 5)
            .map((n, i) => {
              const otherCount = Math.max(1, (result.narratives?.length || 1) - 1);
              const angle = (i * 360 / Math.min(5, otherCount)) * Math.PI / 180;
              const radius = 100;
              const x = 50 + Math.cos(angle) * 40;
              const y = 50 + Math.sin(angle) * 40;
              return (
                <div key={i} className="absolute p-2 rounded-lg border bg-card/80 text-center"
                  style={{
                    left: `${x}%`, top: `${y}%`,
                    transform: "translate(-50%, -50%)",
                    borderColor: n.color,
                    minWidth: 120,
                  }}>
                  <p className="text-[10px] font-medium">{n.narrative_label}</p>
                  <p className="text-[10px] text-muted-foreground">{n.emotional_appeal}</p>
                  <div className="w-full h-1 bg-muted rounded-full mt-1 overflow-hidden">
                    <div className="h-full rounded-full" style={{
                      width: `${(n.strength * 100).toFixed(0)}%`,
                      backgroundColor: n.color,
                    }} />
                  </div>
                </div>
              );
            })}
        </div>

        {/* Narrative details */}
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {result.narratives.map((n, i) => (
            <div key={i} className="p-3 rounded-lg bg-muted/20 text-xs space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: n.color }} />
                <span className="font-semibold">{n.narrative_label}</span>
                <span className="text-[10px] text-muted-foreground">
                  {EMOTION_COLORS[n.emotional_appeal] ? (
                    <span style={{ color: EMOTION_COLORS[n.emotional_appeal] }}>
                      {n.emotional_appeal}
                    </span>
                  ) : n.emotional_appeal}
                </span>
              </div>
              <p className="text-muted-foreground">{n.core_claim?.slice(0, 120)}</p>
              <div className="flex gap-3 text-[10px]">
                <span className="flex items-center gap-0.5">
                  <Scale size={10} /> 证据: {(n.evidence_quality * 100).toFixed(0)}%
                </span>
                <span className="flex items-center gap-0.5">
                  <Brain size={10} /> 逻辑: {(n.logical_coherence * 100).toFixed(0)}%
                </span>
              </div>
              {n.ethical_assessment && (
                <p className="text-[10px] text-amber-600 dark:text-amber-400">
                  ⚖️ 伦理考量: {n.ethical_assessment?.slice(0, 150)}
                </p>
              )}
            </div>
          ))}
        </div>

        {/* Conflicts */}
        {result.narrative_conflicts && result.narrative_conflicts.length > 0 && (
          <div className="space-y-1">
            <p className="text-[10px] font-medium text-muted-foreground uppercase">叙事冲突</p>
            {result.narrative_conflicts.slice(0, 3).map((c, i) => (
              <div key={i} className="flex items-start gap-1.5 text-[10px] text-muted-foreground">
                <Eye size={10} className="mt-0.5 shrink-0" />
                <span>
                  <span style={{ color: (result.narratives || []).find(n => n.narrative_label === c.narrative_a)?.color }}>{c.narrative_a}</span>
                  {" vs "}
                  <span style={{ color: (result.narratives || []).find(n => n.narrative_label === c.narrative_b)?.color }}>{c.narrative_b}</span>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
