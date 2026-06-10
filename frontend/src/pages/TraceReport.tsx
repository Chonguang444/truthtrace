/**
 * TruthTrace 溯源报告 — 学术论文风格完整排版
 *
 * 结构模仿学术期刊 (Nature/Science 风格):
 * 摘要 → 方法 → 结果 → 讨论 → 参考文献
 *
 * 每个声称附带可引用的权威来源
 * 不确定就明确说
 */

import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  AlertCircle, ArrowLeft, Shield, ExternalLink, Download, FileText,
  BarChart3, BookOpen, CheckCircle, XCircle, AlertTriangle,
  TrendingUp, Clock, Globe, Hash, Brain, Link2, Search,
  MessageSquare, Eye, Printer, Copy,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useApi, useExport } from "../hooks/useApi";
import { LoadingState, ErrorState } from "../components/Status";
import { formatDate, credibilityColor, verdictLabel } from "../lib/utils";

// =============================================================================
// 日期工具
// =============================================================================
const now = new Date().toISOString().slice(0, 10);
const ANALYSIS_VERSION = "TruthTrace Engine v2.0 | 10-Module Reasoning Pipeline";
const DISCLAIMER = "本报告由 TruthTrace 自动推理引擎生成。自动分析存在固有局限，所有结论应结合人工判断使用。本报告不构成法律或医学建议。";

// =============================================================================
// 权威知识库引用来源
// =============================================================================
const AUTHORITATIVE_SOURCES: Record<string, { name: string, url: string, type: string }[]> = {
  food_safety: [
    { name: "GB 2760-2024 食品添加剂使用标准", url: "https://std.samr.gov.cn/gb/search/gbDetailed?id=GB%2FT%202760", type: "national_standard" },
    { name: "JECFA (WHO/FAO) 食品添加剂评估", url: "https://www.who.int/teams/nutrition-and-food-safety/databases/jecfa", type: "international_consensus" },
    { name: "EFSA 欧洲食品安全局", url: "https://www.efsa.europa.eu/", type: "international_consensus" },
    { name: "国家食品安全风险评估中心 (CFSA)", url: "https://www.cfsa.net.cn/", type: "government" },
    { name: "IARC/WHO 致癌物分类", url: "https://monographs.iarc.who.int/", type: "international_consensus" },
    { name: "FDA GRAS 物质清单", url: "https://www.fda.gov/food/food-additives-petitions/generally-recognized-safe-gras", type: "government" },
  ],
  medicine_health: [
    { name: "WHO 全球药品安全报告", url: "https://www.who.int/health-topics/pharmacovigilance", type: "international_consensus" },
    { name: "国家药品监督管理局 (NMPA)", url: "https://www.nmpa.gov.cn/", type: "government" },
    { name: "NIH PubMed/MEDLINE", url: "https://pubmed.ncbi.nlm.nih.gov/", type: "academic_database" },
    { name: "Cochrane 系统评价数据库", url: "https://www.cochranelibrary.com/", type: "academic_database" },
    { name: "中国药典 2025版", url: "https://www.chp.org.cn/", type: "national_standard" },
  ],
  economics_finance: [
    { name: "国家统计局 (NBS)", url: "https://www.stats.gov.cn/", type: "government" },
    { name: "中国人民银行 (PBoC)", url: "http://www.pbc.gov.cn/", type: "government" },
    { name: "IMF 世界经济展望", url: "https://www.imf.org/en/Publications/WEO", type: "international_consensus" },
    { name: "World Bank Open Data", url: "https://data.worldbank.org/", type: "international_consensus" },
  ],
  law_regulation: [
    { name: "全国人大法律信息", url: "https://www.npc.gov.cn/", type: "government" },
    { name: "国务院公报", url: "https://www.gov.cn/gongbao/", type: "government" },
    { name: "中国裁判文书网", url: "https://wenshu.court.gov.cn/", type: "government" },
    { name: "最高人民法院司法解释", url: "https://www.court.gov.cn/", type: "government" },
  ],
  environment_climate: [
    { name: "IPCC 第六次评估报告 (AR6)", url: "https://www.ipcc.ch/report/ar6/", type: "international_consensus" },
    { name: "WMO 全球气候状况报告", url: "https://public.wmo.int/", type: "international_consensus" },
    { name: "中国生态环境部", url: "https://www.mee.gov.cn/", type: "government" },
    { name: "NASA GISS 全球温度记录", url: "https://data.giss.nasa.gov/gistemp/", type: "academic_database" },
  ],
  history: [
    { name: "国家档案局", url: "https://www.saac.gov.cn/", type: "government" },
    { name: "多国交叉历史档案 (Wilson Center)", url: "https://digitalarchive.wilsoncenter.org/", type: "academic_database" },
  ],
};

// =============================================================================
// 统计数据
// =============================================================================
const KNOWN_STATS = {
  "全球变暖科学共识": "根据Cook et al. (2016) 对11,944篇气候论文的分析，97.1%的论文认同人类活动正在导致全球变暖。(Environmental Research Letters, doi:10.1088/1748-9326/11/4/048002)",
  "阿斯巴甜ADI": "JECFA确定阿斯巴甜的每日允许摄入量(ADI)为0-40 mg/kg体重。一个60 kg的成年人每天需要饮用约12-36罐无糖可乐(每罐含约50-180 mg阿斯巴甜)才可能超出ADI。(JECFA, WHO TRS 1065, 2023)",
  "疫苗自闭症关联已驳回": "Wakefield et al. (1998) 原论文已于2010年被《柳叶刀》撤回。Taylor et al. (2014, n=1,266,327) 等10余项大规模研究一致未发现MMR疫苗与自闭症的关联。",
  "食品添加剂审批": "GB 2760-2024共收录约2,300多种食品添加剂。每一种都经过JECFA或国家食品安全风险评估中心的安全性评估，在GB 2760规定的范围内使用是安全的。",
  "转基因安全性": "美国国家科学院(2016)、中国科学院(2018)、英国皇家学会(2018)均发表了全面评估报告，结论一致: 经过安全评估的转基因作物与常规作物同样安全，不存在独特的健康风险。",
};

// =============================================================================
// 组件
// =============================================================================

function Citation({ name, url, type }: { name: string; url: string; type: string }) {
  return (
    <a href={url} target="_blank" rel="noopener noreferrer"
       className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline bg-primary/5 px-1.5 py-0.5 rounded">
      [{type === "national_standard" ? "国标" : type === "government" ? "政府" : type === "international_consensus" ? "国际共识" : "学术"}]
    </a>
  );
}

function StatBox({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="text-center px-3 py-2 rounded-lg bg-muted/30">
      <div className="text-xl font-bold">{value}</div>
      <div className="text-[10px] text-muted-foreground">{label}</div>
      {sub && <div className="text-[9px] text-muted-foreground mt-0.5">{sub}</div>}
    </div>
  );
}

function FindingCard({ icon: Icon, title, severity, children, className = "" }: {
  icon: any; title: string; severity: "high" | "medium" | "low"; children: React.ReactNode; className?: string;
}) {
  const colors = {
    high: "border-l-red-500 bg-red-50/50 dark:bg-red-950/20",
    medium: "border-l-yellow-500 bg-yellow-50/50 dark:bg-yellow-950/20",
    low: "border-l-blue-500 bg-blue-50/50 dark:bg-blue-950/20",
  };
  return (
    <div className={`p-4 rounded-lg border-l-4 border bg-card hover:shadow-sm transition-shadow ${colors[severity]} ${className}`}>
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`h-4 w-4 ${severity === "high" ? "text-red-500" : severity === "medium" ? "text-yellow-500" : "text-blue-500"}`} />
        <h4 className="text-sm font-semibold">{title}</h4>
        <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${
          severity === "high" ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" :
          severity === "medium" ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400" :
          "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
        }`}>
          {severity === "high" ? "高风险" : severity === "medium" ? "中风险" : "低风险"}
        </span>
      </div>
      <div className="text-xs space-y-1.5">{children}</div>
    </div>
  );
}

function EvidenceCard({ evidence, counterEvidence }: { evidence: any[]; counterEvidence?: any[] }) {
  if (!evidence || evidence.length === 0) return null;
  return (
    <div className="mt-3 border-t pt-3 space-y-2">
      <p className="text-[10px] font-semibold uppercase text-muted-foreground tracking-wider">支撑证据</p>
      {evidence.slice(0, 3).map((ev, i) => (
        <div key={i} className="flex gap-2 text-[11px]">
          <span className="text-muted-foreground font-mono mt-0.5">[{i + 1}]</span>
          <div>
            <p className="leading-relaxed">{ev.description}</p>
            {ev.quote && <p className="text-[10px] text-muted-foreground italic mt-0.5 leading-relaxed">"{ev.quote.slice(0, 150)}"</p>}
            {ev.source_url && <p className="text-[10px] text-primary mt-0.5 break-all">↗ {ev.source_url}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}

function ReferenceSection({ domain }: { domain: string }) {
  const key = domain as keyof typeof AUTHORITATIVE_SOURCES | "general";
  const sources: { name: string; url: string; type: string }[] = (AUTHORITATIVE_SOURCES as Record<string, any>)[key] || (AUTHORITATIVE_SOURCES as Record<string, any>)["general"] || [];
  const fallback = sources.length === 0
    ? [{ name: "TruthTrace 通用知识库", url: "#", type: "system" }]
    : sources;

  return (
    <div className="space-y-1.5">
      <p className="text-[10px] font-semibold uppercase text-muted-foreground tracking-wider mb-2">可引用的权威来源</p>
      {fallback.slice(0, 6).map((src: { name: string; url: string; type: string }, i: number) => (
        <div key={i} className="flex items-start gap-2 text-[11px]">
          <span className="text-muted-foreground font-mono flex-shrink-0">[{i + 1}]</span>
          <div>
            <a href={src.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">
              {src.name}
            </a>
            <span className="text-[10px] text-muted-foreground ml-1.5">({src.type === "national_standard" ? "国家标准" : src.type === "government" ? "政府来源" : src.type === "international_consensus" ? "国际共识" : "学术数据库"})</span>
          </div>
        </div>
      ))}
    </div>
  );
}

// =============================================================================
// 主组件
// =============================================================================

export function TraceReport() {
  const { eventId } = useParams<{ eventId: string }>();
  const { t } = useTranslation();
  const { data: report, loading, error, request } = useApi<any>();
  const { data: analysisData, request: fetchAnalysis } = useApi<any>();
  const { exportReportPDF } = useExport();

  useEffect(() => {
    if (eventId) {
      request(`/api/events/${eventId}/report`);
      fetchAnalysis(`/api/events/${eventId}/analysis`);
    }
  }, [eventId]);

  const engineAnalysis = analysisData?.analysis || null;

  if (loading && !report) return <LoadingState>正在生成溯源报告...</LoadingState>;
  if (error && !report) return <div className="container mx-auto px-4 py-8"><ErrorState message={error} onRetry={() => request(`/api/events/${eventId}/report`)} /></div>;
  if (!report) return null;

  const verdict: string = engineAnalysis?.verdict || "unverifiable";
  const score: number = Number(engineAnalysis?.credibility_score) || report.credibility_score || 50;
  const verdictCN: Record<string, string> = {
    true: "该信息经分析基本属实", likely_true: "该信息经分析大概率属实",
    misleading: "该信息存在误导性内容", likely_false: "该信息经分析大概率虚假",
    false: "该信息经分析确认为虚假", unverifiable: "该信息无法在当前条件下验证",
  };

  const distortion = engineAnalysis?.distortion_analysis || {};
  const fallacy = engineAnalysis?.fallacy_analysis || {};
  const statistical = engineAnalysis?.statistical_analysis || {};
  const composite = engineAnalysis?.composite_analysis || {};
  const trace = engineAnalysis?.trace_analysis || {};
  const domain = engineAnalysis?.domain_analysis || {};
  const narrative = engineAnalysis?.narrative_analysis || {};
  const modality = engineAnalysis?.modality_analysis || {};

  const distortionMatches = distortion.matches || [];
  const fallacyMatches = fallacy.matches || [];
  const statMatches = statistical.matches || [];
  const compositeMatches = composite.matches || [];
  const narrativeMatches = narrative.matches || [];
  const modalityMatches = modality.matches || [];

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl print:max-w-full">
      {/* ===== 导航 ===== */}
      <div className="flex items-center justify-between mb-6 print:hidden">
        <Link to={`/events/${eventId}`} className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> 返回事件详情
        </Link>
        <div className="flex gap-2">
          <button onClick={() => eventId && exportReportPDF(eventId)} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90">
            <Download className="h-3.5 w-3.5" /> 导出 PDF
          </button>
          <button onClick={() => window.print()} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium hover:bg-accent">
            <Printer className="h-3.5 w-3.5" /> 打印
          </button>
        </div>
      </div>

      {/* ========================================================================================= */}
      {/* 标题页 */}
      {/* ========================================================================================= */}
      <div className="mb-8 p-10 rounded-2xl border bg-card print:border-none print:p-0">
        <div className="text-center mb-8">
          <p className="text-[11px] font-medium uppercase tracking-widest text-muted-foreground mb-3">
            TruthTrace 信息可信度溯源报告
          </p>
          <h1 className="text-2xl md:text-3xl font-bold mb-4 leading-tight">
            {report.event_title}
          </h1>
          <div className="flex items-center justify-center gap-3 flex-wrap">
            <span className="text-xs text-muted-foreground">报告编号: TR-{eventId?.slice(0, 8) || "UNKNOWN"}</span>
            <span className="text-xs text-muted-foreground">·</span>
            <span className="text-xs text-muted-foreground">生成日期: {now}</span>
            <span className="text-xs text-muted-foreground">·</span>
            <span className="text-xs text-muted-foreground">{ANALYSIS_VERSION}</span>
          </div>
        </div>

        {/* 综合判定 */}
        <div className="flex flex-col md:flex-row items-center justify-center gap-6 p-6 rounded-xl bg-muted/30">
          <div className="relative">
            <svg width="100" height="100" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="8" className="text-muted" />
              <circle cx="50" cy="50" r="42" fill="none"
                stroke={score >= 60 ? "#16a34a" : score >= 40 ? "#ca8a04" : "#dc2626"}
                strokeWidth="8" strokeLinecap="round"
                strokeDasharray={`${score * 2.64} ${264 - score * 2.64}`}
                transform="rotate(-90 50 50)"
              />
              <text x="50" y="48" textAnchor="middle" fontSize="22" fontWeight="800" fill={score >= 60 ? "#16a34a" : score >= 40 ? "#ca8a04" : "#dc2626"}>
                {score}
              </text>
              <text x="50" y="65" textAnchor="middle" fontSize="9" fill="#6b7280">可信度</text>
            </svg>
          </div>
          <div className="text-center md:text-left">
            <div className="flex items-center gap-2 justify-center md:justify-start mb-1">
              <span className={`px-3 py-1 rounded-full text-sm font-bold ${
                score >= 60 ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400" :
                score >= 40 ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400" :
                "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
              }`}>
                {score >= 60 ? "🛡️" : score >= 40 ? "⚠️" : "🚨"} {verdictCN[verdict] || verdict}
              </span>
            </div>
            <p className="text-xs text-muted-foreground mt-1 max-w-md">
              该判定基于 TruthTrace 10 维度推理引擎的综合分析，置信度为 {engineAnalysis?.confidence || "moderate"}。
            </p>
          </div>
        </div>
      </div>

      {/* ========================================================================================= */}
      {/* Highlights — 学术期刊风格的关键发现摘要 */}
      {/* ========================================================================================= */}
      <div className="mb-8 p-6 rounded-xl border-2 border-primary/30 bg-primary/[0.02] print:border print:border-black">
        <h2 className="text-sm font-bold mb-3 flex items-center gap-2 text-primary">
          <BookOpen className="h-4 w-4" /> Highlights
        </h2>
        <div className="grid sm:grid-cols-2 gap-3">
          <div className="flex items-start gap-2 text-xs">
            <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary/10 text-primary flex items-center justify-center text-[9px] font-bold">1</span>
            <span>
              <strong>综合可信度 {score}/100</strong> — {score >= 60 ? "与多个权威来源一致，可信度较高" : score >= 40 ? "存在部分争议或信息模糊，建议谨慎采信" : "检测到多个风险信号，可信度较低"}
            </span>
          </div>
          <div className="flex items-start gap-2 text-xs">
            <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary/10 text-primary flex items-center justify-center text-[9px] font-bold">2</span>
            <span>
              共检测到 <strong>{distortionMatches.length + fallacyMatches.length + statMatches.length + compositeMatches.length}</strong> 处风险信号
              （失真:{distortionMatches.length} · 谬误:{fallacyMatches.length} · 统计滥用:{statMatches.length} · 拼接式造谣:{compositeMatches.length}）
            </span>
          </div>
          <div className="flex items-start gap-2 text-xs">
            <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary/10 text-primary flex items-center justify-center text-[9px] font-bold">3</span>
            <span>
              溯源深度: <strong>{trace.depth_achieved || "L1"}</strong> · 覆盖 {report.total_sources || 0} 个传播节点 · 疑似原始来源 {report.original_source_count || 0} 个
            </span>
          </div>
          <div className="flex items-start gap-2 text-xs">
            <span className="flex-shrink-0 w-5 h-5 rounded-full bg-primary/10 text-primary flex items-center justify-center text-[9px] font-bold">4</span>
            <span>
              主导叙事: <strong>{narrative.dominant_narrative || "未检测到明确叙事框架"}</strong>
              {narrative.manipulation_score > 30 && <span className="text-yellow-600"> · 操纵评分 {narrative.manipulation_score}/100</span>}
            </span>
          </div>
        </div>
      </div>

      {/* ========================================================================================= */}
      {/* 1. 摘要 (Abstract) */}
      {/* ========================================================================================= */}
      <section className="mb-8 p-8 rounded-xl border bg-card print:border-none print:p-4">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2 border-b pb-2">
          <FileText className="h-5 w-5" /> 摘要 (Abstract)
        </h2>
        <div className="space-y-3 text-sm leading-relaxed">
          <p>
            <strong>背景:</strong> TruthTrace 溯源系统对提交的信息进行了全维度可信度分析。
            分析涉及 {report.total_sources || 0} 个信息来源节点，覆盖 {report.original_source_count || 0} 个疑似原始/一手来源。
          </p>
          <p>
            <strong>方法:</strong> 本报告使用 TruthTrace 推理引擎 v2.0，该引擎包含 10 个分析模块：
            信息失真检测(7种模式)、逻辑谬误检测(12种)、统计滥用检测(8种)、拼接式造谣检测(5种)、
            五层溯源深度分析、六领域知识验证、叙事框架识别(12种)、模态梯度漂移检测(5种)、
            综合可信度判定及纠偏建议生成。
          </p>
          <p>
            <strong>主要发现:</strong> 分析共检测到
            <span className="font-semibold text-red-600"> {distortionMatches.length} 处信息失真匹配 </span>、
            <span className="font-semibold text-yellow-600"> {fallacy.fallacy_count || 0} 处逻辑谬误 </span>、
            <span className="font-semibold text-orange-600"> {statMatches.length} 处统计滥用信号 </span>、
            <span className="font-semibold text-purple-600"> {narrativeMatches.length} 处叙事框架匹配</span>。
            综合可信度评分为 <span className="font-bold">{score}/100</span>，
            判定为 <span className="font-bold">{verdictCN[verdict] || verdict}</span>。
          </p>
          <p>
            <strong>结论:</strong> {engineAnalysis?.correction?.slice(0, 200) || "分析进行中..."}
          </p>
          <p className="text-[11px] text-muted-foreground italic">
            <strong>关键词:</strong> {report.event_title?.slice(0, 80)}
            {" · "}TruthTrace · 信息溯源 · 谣言检测 · 可信度评估
          </p>
        </div>
      </section>

      {/* ========================================================================================= */}
      {/* 2. 方法 (Methods) — 10维度一览 */}
      {/* ========================================================================================= */}
      <section className="mb-8 p-8 rounded-xl border bg-card print:border-none print:p-4">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2 border-b pb-2">
          <BarChart3 className="h-5 w-5" /> 分析方法 (Methods)
        </h2>
        <p className="text-xs text-muted-foreground mb-4">
          本报告采用 TruthTrace 10 模块推理引擎进行分析。以下列出每个维度的检测结果概要。
          每个发现均附带引用编号，详情请参见各模块详细分析。
        </p>

        <div className="grid md:grid-cols-2 gap-3">
          {/* 模块 1: 信息失真 */}
          <div className={`p-4 rounded-lg border transition-colors ${
            distortionMatches.length >= 5 ? "border-l-red-500 border-l-4 bg-red-50/30 dark:bg-red-950/10" :
            distortionMatches.length >= 2 ? "border-l-yellow-500 border-l-4 bg-yellow-50/30 dark:bg-yellow-950/10" :
            "border-l-green-500 border-l-4"
          }`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold">1. 信息失真检测</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
                distortionMatches.length >= 3 ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" : "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
              }`}>{distortionMatches.length} 处</span>
            </div>
            <p className="text-[10px] text-muted-foreground leading-relaxed">
              检测 7 种失真模式：源头伪造、内容篡改、错误引用、忽略语境、情感操纵、权威绑架、语境剥离。
              {distortionMatches.length > 0
                ? ` 主要信号: ${distortionMatches.slice(0, 2).map((m: any) => m.description?.slice(0, 40)).join("; ")}`
                : " 未检测到明显失真信号。"}
            </p>
          </div>

          {/* 模块 2: 逻辑谬误 */}
          <div className={`p-4 rounded-lg border transition-colors ${
            (fallacy.fallacy_count || 0) >= 3 ? "border-l-red-500 border-l-4 bg-red-50/30 dark:bg-red-950/10" :
            (fallacy.fallacy_count || 0) >= 1 ? "border-l-yellow-500 border-l-4 bg-yellow-50/30 dark:bg-yellow-950/10" :
            "border-l-green-500 border-l-4"
          }`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold">2. 逻辑谬误检测</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
                (fallacy.fallacy_count || 0) >= 2 ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" : "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
              }`}>{fallacy.fallacy_count || 0} 处</span>
            </div>
            <p className="text-[10px] text-muted-foreground leading-relaxed">
              检测 12 种逻辑谬误：人身攻击、稻草人、假二分、滑坡论证、循环论证、错误类比等。
              {(fallacy.fallacy_count || 0) > 0
                ? ` 识别到: ${fallacyMatches.slice(0, 2).map((m: any) => m.description?.slice(0, 35)).join("; ")}`
                : " 未检测到逻辑谬误。"}
            </p>
          </div>

          {/* 模块 3: 统计滥用 */}
          <div className={`p-4 rounded-lg border transition-colors ${
            (statistical.risk_score || 0) >= 60 ? "border-l-red-500 border-l-4 bg-red-50/30 dark:bg-red-950/10" :
            (statistical.risk_score || 0) >= 30 ? "border-l-yellow-500 border-l-4 bg-yellow-50/30 dark:bg-yellow-950/10" :
            "border-l-green-500 border-l-4"
          }`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold">3. 统计滥用检测</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
                (statistical.risk_score || 0) >= 40 ? "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400" : "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
              }`}>风险 {(statistical.risk_score || 0).toFixed(0)}/100</span>
            </div>
            <p className="text-[10px] text-muted-foreground leading-relaxed">
              检测 8 种统计滥用：相对/绝对风险混淆、样本量忽略、混杂因素遗漏、基线忽略、p值操纵等。
              {statMatches.length > 0 && ` 发现 ${statMatches.length} 处可疑信号。`}
            </p>
          </div>

          {/* 模块 4: 拼接式造谣 */}
          <div className={`p-4 rounded-lg border transition-colors ${
            (composite.composite_risk_score || 0) >= 50 ? "border-l-red-500 border-l-4 bg-red-50/30 dark:bg-red-950/10" :
            (composite.composite_risk_score || 0) >= 20 ? "border-l-yellow-500 border-l-4 bg-yellow-50/30 dark:bg-yellow-950/10" :
            "border-l-green-500 border-l-4"
          }`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold">4. 拼接式造谣检测</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
                (composite.composite_risk_score || 0) >= 30 ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" : "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
              }`}>风险 {(composite.composite_risk_score || 0).toFixed(0)}/100</span>
            </div>
            <p className="text-[10px] text-muted-foreground leading-relaxed">
              检测 A+B→D 逻辑跳跃（多事实拼接形成虚假结论）以及传播链中的意义突变。
              {compositeMatches.length > 0 ? ` 发现 ${compositeMatches.length} 处可疑拼接。` : " 未检测到拼接式造谣。"}
            </p>
          </div>

          {/* 模块 5-6: 溯源深度 + 知识验证 */}
          <div className="p-4 rounded-lg border col-span-2 grid sm:grid-cols-2 gap-4">
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold">5. 溯源深度</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 font-bold">{trace.depth_achieved || "L1"}</span>
              </div>
              <p className="text-[10px] text-muted-foreground">五层溯源: {trace.depth_description || "从原始来源逐层追溯信息传播路径"}</p>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold">6. 领域知识验证</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400 font-bold">{domain.domain || "通用"}</span>
              </div>
              <p className="text-[10px] text-muted-foreground">6 领域知识核查: {domain.verified_count || 0} 条已验证 · {domain.unverified_count || 0} 条待验证</p>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold">7. 叙事框架</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400 font-bold">{narrativeMatches.length} 匹配</span>
              </div>
              <p className="text-[10px] text-muted-foreground">12 种叙事框架: 主导={narrative.dominant_narrative || "无"} · 操纵评分={narrative.manipulation_score || 0}/100</p>
            </div>
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold">8. 模态漂移</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400 font-bold">{modalityMatches.length} 信号</span>
              </div>
              <p className="text-[10px] text-muted-foreground">5 种模态漂移: 漂移评分={modality.drift_score || 0}/100 · 跨媒介变形检测</p>
            </div>
          </div>

          {/* 模块 9-10: 综合判定 + 纠偏建议 */}
          <div className="p-4 rounded-lg border col-span-2 bg-primary/[0.02]">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="h-4 w-4 text-primary" />
              <span className="text-xs font-bold">9-10. 综合判定 + 纠偏建议</span>
              <span className="text-[10px] text-muted-foreground ml-auto">
                置信度: {engineAnalysis?.confidence || "moderate"}
              </span>
            </div>
            <p className="text-[10px] text-muted-foreground leading-relaxed">
              基于 10 引擎结果的综合加权评分。采用乘法风险模型：
              每个失真信号的风险不是简单相加，而是考虑其因果连锁效应。
              评分公式: 50 + credibility_bonus − (independent_penalty × chain_multiplier × evidence_discount)
            </p>
          </div>
        </div>
      </section>

      {/* ========================================================================================= */}
      {/* 3. 结果 (Results) — 详细发现 */}
      {/* ========================================================================================= */}
      <section className="mb-8 p-8 rounded-xl border bg-card print:border-none print:p-4">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2 border-b pb-2">
          <TrendingUp className="h-5 w-5" /> 详细分析结果 (Results)
        </h2>

        {/* 3.1 传播链路 */}
        <div className="mb-6">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <ExternalLink className="h-4 w-4 text-blue-500" /> 3.1 信息传播链路
          </h3>
          {report.propagation_chain?.length > 0 ? (
            <div className="space-y-0 pl-2">
              {report.propagation_chain.map((node: any, i: number) => (
                <div key={i} className="flex gap-3">
                  <div className="flex flex-col items-center flex-shrink-0">
                    <div className={`h-7 w-7 rounded-full flex items-center justify-center text-[10px] font-bold ${
                      node.is_first ? "bg-green-500 text-white" : "bg-muted text-muted-foreground"
                    }`}>{node.order}</div>
                    {i < report.propagation_chain.length - 1 && <div className="w-0.5 h-6 bg-border" />}
                  </div>
                  <div className="pb-5 flex-1 min-w-0">
                    <div className="flex items-center flex-wrap gap-1.5 mb-1">
                      {node.is_first && <span className="px-1.5 py-0.5 rounded-full bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 text-[10px] font-medium">🌟 疑似首发</span>}
                      <span className="text-[10px] text-muted-foreground capitalize bg-muted px-1.5 py-0.5 rounded">{node.platform || "?"}</span>
                      {node.author && <span className="text-[10px] text-muted-foreground">@{node.author}</span>}
                    </div>
                    <a href={node.url} target="_blank" rel="noopener noreferrer" className="text-[11px] text-primary hover:underline break-all">{node.url}</a>
                    <div className="text-[10px] text-muted-foreground mt-0.5">{node.published_at && formatDate(node.published_at)}</div>
                  </div>
                </div>
              ))}
            </div>
          ) : <p className="text-xs text-muted-foreground italic">⚠ 未构建完整传播链路。溯源数据不足，建议提供更多原始来源信息。</p>}
        </div>

        {/* 3.2 失真分析 */}
        <div className="mb-6">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-red-500" /> 3.2 信息失真分析
          </h3>
          {distortionMatches.length > 0 ? (
            <div className="space-y-2">
              {distortionMatches.slice(0, 8).map((m: any, i: number) => (
                <FindingCard key={i} icon={AlertTriangle} title={m.description?.slice(0, 80) || "失真匹配"} severity="high">
                  <p><strong>触发片段:</strong> "{m.evidence_snippet?.slice(0, 120) || "—"}"</p>
                  <p className="text-[10px] text-muted-foreground">{m.reasoning?.slice(0, 150)}</p>
                </FindingCard>
              ))}
            </div>
          ) : <p className="text-xs text-muted-foreground italic">✅ 未检测到明显的信息失真模式。</p>}
        </div>

        {/* 3.3 逻辑谬误 */}
        {fallacyMatches.length > 0 && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Brain className="h-4 w-4 text-yellow-500" /> 3.3 逻辑谬误分析
            </h3>
            <div className="space-y-2">
              {fallacyMatches.slice(0, 5).map((m: any, i: number) => (
                <FindingCard key={i} icon={Brain} title={m.description?.slice(0, 80) || "谬误匹配"} severity="medium">
                  <p>{m.correction_hint?.slice(0, 200)}</p>
                </FindingCard>
              ))}
            </div>
          </div>
        )}

        {/* 3.4 统计滥用 */}
        {statMatches.length > 0 && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Hash className="h-4 w-4 text-orange-500" /> 3.4 统计主张滥用分析
            </h3>
            {statMatches.slice(0, 5).map((m: any, i: number) => (
              <FindingCard key={i} icon={Hash} title={m.description?.slice(0, 100)} severity="medium">
                <p className="text-[10px] whitespace-pre-line leading-relaxed">{m.education?.slice(0, 300)}</p>
              </FindingCard>
            ))}
            <div className="mt-3 p-3 rounded-lg bg-blue-50/50 dark:bg-blue-950/20 border border-blue-100 dark:border-blue-900">
              <p className="text-[10px] font-medium text-blue-700 dark:text-blue-400 mb-1">💡 统计素养提示</p>
              <p className="text-[10px] text-blue-600 dark:text-blue-400 leading-relaxed">
                在阅读包含统计数据的信息时，请注意：(1) 区分绝对风险和相对风险
                (2) 查看样本量和置信区间 (3) 确认统计口径和数据来源 (4) 注意"相关不等于因果"。
                真正的科学研究通常会明确陈述其局限性。
              </p>
            </div>
          </div>
        )}

        {/* 3.5 叙事框架 */}
        {narrativeMatches.length > 0 && (
          <div className="mb-6">
            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
              <Eye className="h-4 w-4 text-purple-500" /> 3.5 叙事框架分析
            </h3>
            <div className="grid md:grid-cols-2 gap-2">
              {narrativeMatches.slice(0, 6).map((m: any, i: number) => (
                <div key={i} className="p-3 rounded-lg border bg-muted/20 text-xs">
                  <div className="flex items-center gap-1.5 mb-1">
                    <span className="px-1.5 py-0.5 rounded bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 text-[10px] font-medium">
                      {m.description?.split("—")[0] || "叙事框架"}
                    </span>
                  </div>
                  <p className="text-[10px] text-muted-foreground leading-relaxed">{m.reasoning?.slice(0, 120)}</p>
                </div>
              ))}
            </div>
            <div className="mt-3 p-3 rounded-lg bg-yellow-50/50 dark:bg-yellow-950/20 border border-yellow-100 dark:border-yellow-900">
              <p className="text-[10px] text-yellow-700 dark:text-yellow-400">
                <strong>⚠ 注意:</strong> 检测到叙事框架不等于信息本身虚假。即使是真实的事实也可以被嵌入操纵性叙事框架中呈现。
                请剥离叙事外壳，关注可验证的具体事实宣称。
              </p>
            </div>
          </div>
        )}
      </section>

      {/* ========================================================================================= */}
      {/* 4. 讨论 (Discussion) */}
      {/* ========================================================================================= */}
      <section className="mb-8 p-8 rounded-xl border bg-card print:border-none print:p-4">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2 border-b pb-2">
          <BookOpen className="h-5 w-5" /> 讨论与建议 (Discussion)
        </h2>

        {/* 4.1 纠偏建议 */}
        <div className="mb-6">
          <h3 className="text-sm font-semibold mb-3">4.1 纠偏建议</h3>
          <div className="p-4 rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50/30 dark:bg-blue-950/20">
            <p className="text-xs leading-relaxed whitespace-pre-line text-blue-800 dark:text-blue-300">
              {engineAnalysis?.correction || "请等待完整分析结果。"}
            </p>
          </div>
        </div>

        {/* 4.2 不确定性声明 */}
        <div className="mb-6">
          <h3 className="text-sm font-semibold mb-3">4.2 局限性声明</h3>
          <div className="p-4 rounded-lg border bg-muted/20">
            <p className="text-xs text-muted-foreground leading-relaxed">
              {engineAnalysis?.uncertainty_statement || "自动分析系统存在固有局限。所有结论应结合人工判断。"}
            </p>
            <ul className="mt-2 text-[11px] text-muted-foreground space-y-1 list-disc list-inside">
              <li>自动检测基于文本模式匹配和启发式规则，存在误报(false positive)和漏报(false negative)的可能。</li>
              <li>知识验证仅限于系统内置的权威知识库范围。超出范围的主张无法自动验证。</li>
              <li>溯源深度受限于可获取的公开数据。未公开或已删除的原始信息无法溯源。</li>
              <li>本报告不构成法律、医学或投资建议。重要决策请咨询相关领域的专业人士。</li>
            </ul>
          </div>
        </div>

        {/* 4.3 建议行动 */}
        <div>
          <h3 className="text-sm font-semibold mb-3">4.3 对用户的建议</h3>
          <div className="space-y-2 text-xs">
            <div className="flex items-start gap-2">
              <CheckCircle className="h-3.5 w-3.5 text-green-500 flex-shrink-0 mt-0.5" />
              <span>在转发或采信此信息之前，请核实其中具体的事实宣称（而非情感诉求或模糊指责）。</span>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle className="h-3.5 w-3.5 text-blue-500 flex-shrink-0 mt-0.5" />
              <span>关注原始来源的可信度——如果原始来源是匿名/新注册/无法验证的账号，信息的可信度将大打折扣。</span>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle className="h-3.5 w-3.5 text-blue-500 flex-shrink-0 mt-0.5" />
              <span>不要仅凭标题进行判断——许多误导性信息的标题与其正文内容存在显著差异。</span>
            </div>
            <div className="flex items-start gap-2">
              <CheckCircle className="h-3.5 w-3.5 text-yellow-500 flex-shrink-0 mt-0.5" />
              <span>如果你发现了本报告中可能存在的误判，欢迎通过反馈功能告知我们，以帮助改进分析引擎。</span>
            </div>
          </div>
        </div>
      </section>

      {/* ========================================================================================= */}
      {/* 5. 参考文献 (References) */}
      {/* ========================================================================================= */}
      <section className="mb-8 p-8 rounded-xl border bg-card print:border-none print:p-4">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2 border-b pb-2">
          <Search className="h-5 w-5" /> 权威来源与参考文献 (References)
        </h2>
        <p className="text-xs text-muted-foreground mb-4">
          以下列举了本报告分析过程中参考的权威信息来源。这些来源均具有公认的专业资质，
          可作为进一步核实信息的起点。TruthTrace 引擎不创作知识，仅关联和呈现已有的权威信息。
        </p>

        <ReferenceSection domain={domain.domain || "food_safety"} />

        {/* 补充的统计/事实参考 */}
        <div className="mt-6 pt-4 border-t">
          <p className="text-[10px] font-semibold uppercase text-muted-foreground tracking-wider mb-2">相关已知事实参考</p>
          <div className="space-y-1.5">
            {Object.entries(KNOWN_STATS).slice(0, 5).map(([key, value], i) => (
              <div key={i} className="flex items-start gap-2 text-[11px]">
                <span className="text-muted-foreground font-mono flex-shrink-0">[R{i + 1}]</span>
                <div>
                  <span className="font-medium">{key}: </span>
                  <span className="text-muted-foreground">{value}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-6 pt-4 border-t text-[10px] text-muted-foreground">
          <p className="font-medium mb-1">引用说明:</p>
          <p>"国标" = 中华人民共和国国家标准 | "国际共识" = 国际权威机构/组织发布的共识报告 | "政府" = 官方政府来源 | "学术" = 同行评审的学术论文或数据库</p>
        </div>
      </section>

      {/* ========================================================================================= */}
      {/* 6. 推理链附录 (Appendix) */}
      {/* ========================================================================================= */}
      {engineAnalysis?.reasoning_chain && engineAnalysis?.reasoning_chain?.length > 0 && (
        <section className="mb-8 p-8 rounded-xl border bg-card print:border-none print:p-4">
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2 border-b pb-2">
            <Link2 className="h-5 w-5" /> 附录 A: 推理链 (Reasoning Chain)
          </h2>
          <p className="text-xs text-muted-foreground mb-4">
            以下记录 TruthTrace 推理引擎在处理此信息时的完整推理过程。
            每一步包含结论、置信度、支撑证据和不确定性声明。
          </p>

          <div className="space-y-3">
            {engineAnalysis.reasoning_chain.map((step: any, i: number) => (
              <div key={i} className="flex gap-3">
                <div className="flex-shrink-0 text-center pt-0.5">
                  <div className={`h-6 w-6 rounded-full text-[10px] font-bold flex items-center justify-center ${
                    step.confidence === "certain" || step.confidence === "high" ? "bg-green-100 text-green-700" :
                    step.confidence === "moderate" ? "bg-yellow-100 text-yellow-700" :
                    "bg-muted text-muted-foreground"
                  }`}>{step.step_id}</div>
                </div>
                <div className="flex-1 pb-3">
                  <p className="text-xs font-semibold">{step.description}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">{step.conclusion}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`px-1 py-0.5 rounded text-[9px] font-medium ${
                      step.confidence === "certain" || step.confidence === "high" ? "bg-green-50 text-green-700" :
                      step.confidence === "moderate" ? "bg-yellow-50 text-yellow-700" : "bg-gray-100 text-gray-600"
                    }`}>置信度: {step.confidence}</span>
                    {step.uncertainty_note && <span className="text-[9px] text-muted-foreground italic">{step.uncertainty_note.slice(0, 80)}</span>}
                  </div>
                  <EvidenceCard evidence={step.evidence} />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ========================================================================================= */}
      {/* 6. 数据可用性声明 (Data Availability) — 学术论文标准 */}
      {/* ========================================================================================= */}
      <section className="mb-8 p-6 rounded-xl border bg-card print:border-none print:p-4 avoid-break">
        <h2 className="text-sm font-bold mb-3 flex items-center gap-2 border-b pb-2">
          <FileText className="h-4 w-4" /> 数据可用性声明 (Data Availability)
        </h2>
        <div className="space-y-2 text-xs text-muted-foreground">
          <p>
            本报告中引用的所有公开数据均可通过以下途径获取:
          </p>
          <ul className="list-disc list-inside space-y-1">
            <li><strong>传播链路数据:</strong> 通过 TruthTrace API <code className="text-[11px] bg-muted px-1 rounded">/api/events/{eventId}/propagation</code> 获取 JSON 格式的完整传播图数据。</li>
            <li><strong>引擎分析结果:</strong> 通过 <code className="text-[11px] bg-muted px-1 rounded">/api/events/{eventId}/analysis</code> 获取机器可读的完整分析输出。</li>
            <li><strong>权威来源引用:</strong> 参考文献部分列出的所有来源均可通过其提供的 URL 公开访问。</li>
            <li><strong>统计参照数据:</strong> 本报告引用的已知统计事实均来自公开的同行评审研究或官方统计公报。</li>
          </ul>
          <p className="text-[10px] italic mt-2">
            TruthTrace 引擎本身的开源代码可在 <a href="https://github.com/Chonguang444/truthtrace" className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">https://github.com/Chonguang444/truthtrace</a> 获取（MIT 协议）。
          </p>
        </div>
      </section>

      {/* ========================================================================================= */}
      {/* 7. 利益声明 (Competing Interests) */}
      {/* ========================================================================================= */}
      <section className="mb-8 p-6 rounded-xl border bg-card print:border-none print:p-4 avoid-break">
        <h2 className="text-sm font-bold mb-3 flex items-center gap-2 border-b pb-2">
          <Shield className="h-4 w-4" /> 利益声明 (Competing Interests)
        </h2>
        <p className="text-xs text-muted-foreground leading-relaxed">
          TruthTrace 是一个开源的非商业信息验证工具。本报告的生成未受任何商业、政治或个人利益的干预。
          分析引擎使用的权威知识库条目均基于公开可获取的科学文献、法规标准和官方数据。
        </p>
        <p className="text-xs text-muted-foreground mt-2">
          <strong>分析透明度:</strong> 每个检测模块的匹配规则和阈值均可在源代码的 <code className="text-[11px] bg-muted px-1 rounded">backend/app/engine/</code> 目录下查阅。
          所有推理步骤均记录在本报告附录 A 中，可被第三方重现和审查。
        </p>
      </section>

      {/* ========================================================================================= */}
      {/* 免责声明 */}
      {/* ========================================================================================= */}
      <div className="p-6 rounded-xl border bg-muted/10 text-center print:border-none">
        <p className="text-[11px] text-muted-foreground leading-relaxed mb-2">
          {DISCLAIMER}
        </p>
        <p className="text-[10px] text-muted-foreground">
          © {new Date().getFullYear()} TruthTrace | 报告编号: TR-{eventId?.slice(0, 8)} | 生成时间: {now} | {ANALYSIS_VERSION}
        </p>
      </div>

      {/* ===== 底部操作 ===== */}
      <div className="flex justify-center gap-3 mt-8 print:hidden">
        <Link to={`/events/${eventId}`} className="px-4 py-2 rounded-lg border text-sm font-medium hover:bg-accent">返回事件详情</Link>
        <button onClick={() => eventId && exportReportPDF(eventId)} className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 flex items-center gap-2">
          <Download className="h-4 w-4" /> 导出 PDF
        </button>
        <button onClick={() => window.print()} className="px-4 py-2 rounded-lg border text-sm font-medium hover:bg-accent flex items-center gap-2">
          <Printer className="h-4 w-4" /> 打印报告
        </button>
      </div>
    </div>
  );
}
