/**
 * 推理引擎分析仪表盘 — 10 维度可视化面板
 *
 * 每个引擎维度一张卡片:
 * - 颜色编码风险等级 (绿/黄/橙/红)
 * - 关键指标数字
 * - 可展开查看详细匹配列表
 */

import { useState } from "react";
import {
  AlertTriangle, Brain, Hash, Link2, Search, Globe,
  BookOpen, MessageSquare, BarChart3, ChevronDown, ChevronRight,
  Shield, TrendingUp, Eye, Zap, FileText,
} from "lucide-react";

interface AnalysisDashboardProps {
  analysis: Record<string, any> | null;
  loading?: boolean;
  compact?: boolean;
}

function riskColor(score: number): string {
  if (score >= 70) return "text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800";
  if (score >= 40) return "text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-950/30 border-yellow-200 dark:border-yellow-800";
  return "text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800";
}

function riskColorBar(score: number): string {
  if (score >= 70) return "bg-red-500";
  if (score >= 40) return "bg-yellow-500";
  return "bg-green-500";
}

interface DimensionCardProps {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  count: number;
  risk: number; // 0-100
  children?: React.ReactNode;
  defaultOpen?: boolean;
}

function DimensionCard({ icon: Icon, title, count, risk, children, defaultOpen = false }: DimensionCardProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={`rounded-lg border p-4 transition-all ${riskColor(risk)}`}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between gap-3"
      >
        <div className="flex items-center gap-2.5">
          <Icon className="h-4 w-4 flex-shrink-0" />
          <span className="text-sm font-semibold">{title}</span>
          {count > 0 && (
            <span className={`px-1.5 py-0.5 rounded-full text-xs font-bold ${riskColorBar(risk)} text-white`}>
              {count}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="w-20 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden hidden sm:block">
            <div className={`h-full rounded-full transition-all ${riskColorBar(risk)}`} style={{ width: `${Math.min(100, risk)}%` }} />
          </div>
          {children && (open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />)}
        </div>
      </button>

      {open && children && (
        <div className="mt-3 pt-3 border-t border-inherit text-xs space-y-1.5">
          {children}
        </div>
      )}
    </div>
  );
}

function MatchItem({ text, detail }: { text: string; detail?: string }) {
  return (
    <div className="flex items-start gap-2 py-1">
      <div className="h-1.5 w-1.5 rounded-full bg-current mt-1.5 flex-shrink-0 opacity-50" />
      <div>
        <p className="leading-relaxed">{text}</p>
        {detail && <p className="text-[10px] opacity-60 mt-0.5">{detail}</p>}
      </div>
    </div>
  );
}

export function AnalysisDashboard({ analysis, loading, compact = false }: AnalysisDashboardProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-muted-foreground text-sm gap-2">
        <BarChart3 className="h-4 w-4 animate-pulse" />
        加载分析数据...
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground text-sm gap-2">
        <AlertTriangle className="h-5 w-5" />
        暂无可用的引擎分析数据
      </div>
    );
  }

  const verdict = analysis.verdict || "unverifiable";
  const score = analysis.credibility_score || 50;
  const distortion = analysis.distortion_analysis || {};
  const fallacy = analysis.fallacy_analysis || {};
  const statistical = analysis.statistical_analysis || {};
  const composite = analysis.composite_analysis || {};
  const trace = analysis.trace_analysis || {};
  const domain = analysis.domain_analysis || {};
  const narrative = analysis.narrative_analysis || {};
  const modality = analysis.modality_analysis || {};

  const distortionMatches = distortion.matches || [];
  const fallacyMatches = fallacy.matches || [];
  const statMatches = statistical.matches || [];
  const compositeMatches = composite.matches || [];
  const narrativeMatches = narrative.matches || [];
  const modalityMatches = modality.matches || [];

  const verdictLabel: Record<string, string> = {
    true: "✅ 真实", likely_true: "✅ 可能真实", misleading: "⚠️ 误导性",
    likely_false: "🚫 可能虚假", false: "🚫 虚假", unverifiable: "❓ 无法验证",
  };

  return (
    <div className="space-y-3">
      {/* Header */}
      {!compact && (
        <div className="flex items-center justify-between p-4 rounded-lg border bg-card">
          <div className="flex items-center gap-3">
            <div className={`h-12 w-12 rounded-full flex items-center justify-center text-2xl ${
              score >= 60 ? "bg-green-100 dark:bg-green-900/30" :
              score >= 40 ? "bg-yellow-100 dark:bg-yellow-900/30" :
              "bg-red-100 dark:bg-red-900/30"
            }`}>
              {score >= 60 ? "🛡️" : score >= 40 ? "⚠️" : "🚨"}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold">{score}/100</span>
                <span className={`text-sm font-medium ${riskColor(100 - score).split(" ")[0]}`}>
                  {verdictLabel[verdict] || verdict}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">TruthTrace 推理引擎综合判定</p>
            </div>
          </div>
        </div>
      )}

      {/* 10 Engine Dimensions */}
      <div className="space-y-2">
        {/* 1. 失真检测 */}
        <DimensionCard icon={AlertTriangle} title="信息失真检测 (7 种模式)" count={distortionMatches.length} risk={distortionMatches.length * 12}>
          {distortionMatches.slice(0, 5).map((m: any, i: number) => (
            <MatchItem key={i} text={m.description} detail={m.evidence_snippet?.slice(0, 80)} />
          ))}
        </DimensionCard>

        {/* 2. 逻辑谬误 */}
        <DimensionCard icon={Brain} title="逻辑谬误 (12 种)" count={fallacy.fallacy_count || 0} risk={(fallacy.fallacy_count || 0) * 7}>
          {fallacyMatches.slice(0, 4).map((m: any, i: number) => (
            <MatchItem key={i} text={m.description} detail={m.correction_hint?.slice(0, 80)} />
          ))}
        </DimensionCard>

        {/* 3. 统计滥用 */}
        <DimensionCard icon={BarChart3} title="统计滥用 (8 种)" count={statMatches.length} risk={statistical.risk_score || 0}>
          {statMatches.slice(0, 4).map((m: any, i: number) => (
            <MatchItem key={i} text={m.description} detail={m.education?.slice(0, 80)} />
          ))}
        </DimensionCard>

        {/* 4. 拼接式造谣 */}
        <DimensionCard icon={Link2} title="拼接式造谣 (5 种)" count={compositeMatches.length} risk={composite.composite_risk_score || 0}>
          {compositeMatches.slice(0, 3).map((m: any, i: number) => (
            <MatchItem key={i} text={m.description} detail={m.leap_gap?.slice(0, 80)} />
          ))}
        </DimensionCard>

        {/* 5. 溯源深度 */}
        <DimensionCard icon={Search} title="溯源深度" count={trace.depth_achieved ? 1 : 0} risk={trace.source_credibility_score ? (100 - trace.source_credibility_score) : 50}>
          <div className="text-xs">
            <p>达到深度: <strong>{trace.depth_achieved || "未知"}</strong></p>
            <p>来源可信度: <strong>{trace.source_credibility_score?.toFixed(0) || "?"}/100</strong></p>
            {trace.content_tampering_detected !== undefined && (
              <p>内容篡改检测: <strong>{trace.content_tampering_detected ? "⚠️ 是" : "✅ 否"}</strong></p>
            )}
          </div>
        </DimensionCard>

        {/* 6. 领域知识 */}
        <DimensionCard icon={BookOpen} title={`领域知识验证 (${domain.domain || "通用"})`} count={(domain.unverified_claims?.length || 0) + (domain.refuted_claims?.length || 0)} risk={domain.refuted_claims?.length ? domain.refuted_claims.length * 20 : 10}>
          {domain.refuted_claims?.slice(0, 3).map((c: any, i: number) => (
            <MatchItem key={i} text={`🚫 ${c.text?.slice(0, 60)}`} detail={c.verification?.explanation?.slice(0, 80)} />
          ))}
          {domain.knowledge_gaps?.slice(0, 2).map((k: string, i: number) => (
            <MatchItem key={`gap-${i}`} text={k} />
          ))}
        </DimensionCard>

        {/* 7. 叙事框架 (12种) */}
        <DimensionCard icon={Eye} title="叙事框架 (12 种)" count={narrativeMatches.length} risk={narrative.manipulation_score || 0}>
          {narrativeMatches.slice(0, 4).map((m: any, i: number) => (
            <MatchItem key={i} text={m.description} detail={`标记: ${(m.markers || []).slice(0, 3).join(", ")}`} />
          ))}
          {narrative.dominant_narrative && (
            <p className="text-[10px] opacity-60 pt-1">
              主导叙事框架: {narrative.dominant_narrative} | 操纵性评分: {narrative.manipulation_score?.toFixed(0)}/100
            </p>
          )}
        </DimensionCard>

        {/* 8. 模态漂移 */}
        <DimensionCard icon={MessageSquare} title="模态梯度漂移 (5 种)" count={modalityMatches.length} risk={modality.drift_score || 0}>
          {modalityMatches.slice(0, 4).map((m: any, i: number) => (
            <MatchItem key={i} text={m.description} detail={`${m.tentative_part || ""} → ${m.certain_part || ""}`} />
          ))}
        </DimensionCard>
      </div>

      {/* Correction */}
      {analysis.correction && (
        <div className="p-4 rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/30">
          <div className="flex items-center gap-2 mb-2">
            <FileText className="h-4 w-4 text-blue-600" />
            <span className="text-sm font-semibold text-blue-700 dark:text-blue-400">纠偏建议</span>
          </div>
          <p className="text-xs text-blue-700 dark:text-blue-400 whitespace-pre-line">{analysis.correction}</p>
        </div>
      )}

      {/* Uncertainty */}
      {analysis.uncertainty_statement && (
        <div className="p-3 rounded-lg border bg-muted/30">
          <p className="text-[11px] text-muted-foreground">
            <strong>⚠️ 不确定性声明:</strong> {analysis.uncertainty_statement}
          </p>
        </div>
      )}
    </div>
  );
}
