import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  Loader2, AlertCircle, Clock, Globe, User, BarChart3,
  ArrowLeft, ExternalLink, FileText, Shield, TrendingUp,
  Heart, Download, FileSpreadsheet, BookmarkCheck, Layers, Share2, Copy,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useApi, useFavorites, useExport } from "../hooks/useApi";
import { useAuth } from "../contexts/AuthContext";
import { PropagationGraph } from "../components/PropagationGraph";
import { PropagationGraphV2 } from "../components/PropagationGraphV2";
import { FactCheckBadge } from "../components/FactCheckBadge";
import { EventTimeline } from "../components/EventTimeline";
import { SourceCard } from "../components/SourceCard";
import { CredibilityGauge } from "../components/CredibilityGauge";
import { AnalysisDashboard } from "../components/AnalysisDashboard";
import { CausalGraphCard } from "../components/CausalGraphCard";
import { CorrectionPanel } from "../components/CorrectionPanel";
import { LoadingState, ErrorState } from "../components/Status";
import { formatDate, verdictLabel } from "../lib/utils";

export function EventDetail() {
  const { eventId } = useParams<{ eventId: string }>();
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { data: event, loading, error, request } = useApi<any>();
  const { add: addFav, remove: removeFav, data: favData, request: favReq } = useFavorites();
  const { exportSourcesCSV, exportReportPDF } = useExport();
  const [activeTab, setActiveTab] = useState<"overview" | "analysis" | "graph" | "timeline" | "sources">("overview");
  const [graphVersion, setGraphVersion] = useState<"v1" | "v2">("v2");
  const [graphData, setGraphData] = useState<any>(null);
  const [timelineData, setTimelineData] = useState<any>(null);
  const [sourcesData, setSourcesData] = useState<any>(null);
  const [analysisData, setAnalysisData] = useState<any>(null);
  const [isFaved, setIsFaved] = useState(false);
  const [favLoading, setFavLoading] = useState(false);
  const [mergedGraphData, setMergedGraphData] = useState<any>(null);

  useEffect(() => {
    if (eventId) {
      request(`/api/events/${eventId}`);
      request(`/api/events/${eventId}/graph`).then(setGraphData);
      request(`/api/events/${eventId}/timeline`).then(setTimelineData);
      request(`/api/events/${eventId}/sources`).then(setSourcesData);
      request(`/api/events/${eventId}/analysis`).then(setAnalysisData);
    }
  }, [eventId]);

  // Merge causal edges from analysis into propagation graph
  useEffect(() => {
    if (!graphData?.graph) return;
    const base = { ...graphData.graph };
    const causalEdges = analysisData?.analysis?.causal_graph_result?.graph?.edges || [];
    const causalNodes = analysisData?.analysis?.causal_graph_result?.graph?.nodes || [];

    if (causalEdges.length > 0) {
      // Merge causal nodes that don't exist in propagation graph
      const existingIds = new Set((base.nodes || []).map((n: any) => n.id));
      const newNodes = causalNodes
        .filter((n: any) => !existingIds.has(n.node_id))
        .map((n: any, i: number) => ({
          id: n.node_id,
          label: n.label,
          platform: "general",
          url: "",
          is_original: n.is_root,
          authority_score: n.credibility,
        }));

      // Map causal edges to propagation edge format
      const newEdges = causalEdges.map((e: any, i: number) => ({
        id: e.source_id + "-causal-" + e.target_id,
        source: e.source_id,
        target: e.target_id,
        type: "causal",
        weight: e.confidence / 100,
        causal_type: e.fallacy_detected ? "CONTRADICTS" : "CAUSES",
      }));

      setMergedGraphData({
        nodes: [...(base.nodes || []), ...newNodes],
        edges: [...(base.edges || []), ...newEdges],
      });
    } else {
      setMergedGraphData(base);
    }
  }, [graphData, analysisData]);

  useEffect(() => {
    if (!isAuthenticated || !eventId) return;
    favReq(`/api/auth/me/favorites?limit=100`, { auth: true }).then((data: any) => {
      if (data?.favorites) {
        const found = data.favorites.some((f: any) => f.event_id === eventId);
        setIsFaved(found);
      }
    });
  }, [isAuthenticated, eventId]);

  if (loading && !event) {
    return <LoadingState>{t("event.loading_event")}</LoadingState>;
  }

  if (error && !event) {
    return (
      <div className="container mx-auto px-4 py-8">
        <ErrorState message={error} onRetry={() => request(`/api/events/${eventId}`)} />
      </div>
    );
  }

  if (!event) return null;

  const tabs = [
    { id: "overview" as const, label: t("event.overview"), icon: BarChart3 },
    { id: "analysis" as const, label: "引擎分析", icon: Layers },
    { id: "graph" as const, label: t("event.propagation_graph"), icon: TrendingUp },
    { id: "timeline" as const, label: t("event.timeline"), icon: Clock },
    { id: "sources" as const, label: t("event.sources"), icon: Globe },
  ];

  const handleToggleFav = async () => {
    if (!eventId || !isAuthenticated) return;
    setFavLoading(true);
    try {
      if (isFaved) {
        await removeFav(eventId);
        setIsFaved(false);
      } else {
        await addFav(eventId);
        setIsFaved(true);
      }
    } catch {}
    setFavLoading(false);
  };

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Back */}
      <Link
        to="/search"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-6"
      >
        <ArrowLeft className="h-4 w-4" /> {t("event.back_search")}
      </Link>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-start justify-between gap-6">
          <div className="flex-1">
            <h1 className="text-3xl font-bold mb-3">{event.title}</h1>
            {event.summary && (
              <p className="text-muted-foreground mb-4">{event.summary}</p>
            )}
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <CredibilityGauge score={event.credibility_score} size="md" />
              <span className="px-3 py-1 rounded-full bg-muted text-muted-foreground">
                {event.status === "active"
                  ? "🔥 热议中"
                  : event.status === "emerging"
                  ? "🆕 新出现"
                  : "✅ 已定论"}
              </span>
              {event.rumor_verdict && (
                <span className="px-3 py-1 rounded-full bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-400 font-medium">
                  🚨 {verdictLabel(event.rumor_verdict)}
                </span>
              )}
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex-shrink-0 flex items-center gap-2">
            {/* Favorite */}
            {isAuthenticated && (
              <button
                onClick={handleToggleFav}
                disabled={favLoading}
                className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors border ${
                  isFaved
                    ? "bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800 text-red-700 dark:text-red-400"
                    : "bg-card border text-muted-foreground hover:text-red-600 hover:border-red-200"
                }`}
              >
                {isFaved ? (
                  <BookmarkCheck className="h-4 w-4" />
                ) : (
                  <Heart className="h-4 w-4" />
                )}
                {isFaved ? "已收藏" : "收藏"}
              </button>
            )}

            {/* Export dropdown */}
            <div className="relative group">
              <button className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border bg-card text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                <Download className="h-4 w-4" />
                {t("common.export")}
              </button>
              <div className="absolute right-0 top-full mt-1 w-48 rounded-lg border bg-card shadow-lg opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-20 p-1">
                <button
                  onClick={() => eventId && exportSourcesCSV(eventId)}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm hover:bg-accent transition-colors"
                >
                  <FileSpreadsheet className="h-4 w-4" />
                  {t("common.export_csv")} (来源)
                </button>
                <button
                  onClick={() => eventId && exportReportPDF(eventId)}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-sm hover:bg-accent transition-colors"
                >
                  <FileText className="h-4 w-4" />
                  {t("common.export_pdf")} (报告)
                </button>
              </div>
            </div>

            <Link
              to={`/events/${eventId}/report`}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              <FileText className="h-4 w-4" />
              {t("event.view_report")}
            </Link>
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
          <div className="p-4 rounded-lg border bg-card">
            <div className="text-2xl font-bold">{event.source_count || 0}</div>
            <div className="text-xs text-muted-foreground">{t("event.info_sources")}</div>
          </div>
          <div className="p-4 rounded-lg border bg-card">
            <div className="text-2xl font-bold">
              {event.platform_distribution ? Object.keys(event.platform_distribution).length : 0}
            </div>
            <div className="text-xs text-muted-foreground">{t("event.platforms")}</div>
          </div>
          <div className="p-4 rounded-lg border bg-card">
            <div className="text-2xl font-bold">{event.original_sources?.length || 0}</div>
            <div className="text-xs text-muted-foreground">{t("event.original_sources")}</div>
          </div>
          <div className="p-4 rounded-lg border bg-card">
            <div className="text-2xl font-bold">{formatDate(event.last_updated_at)}</div>
            <div className="text-xs text-muted-foreground">{t("event.last_updated")}</div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b mb-6 overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px whitespace-nowrap ${
              activeTab === tab.id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="min-h-[400px]">
        {activeTab === "overview" && (
          <div className="space-y-6">
            {event.platform_distribution && Object.keys(event.platform_distribution).length > 0 && (
              <div className="p-6 rounded-lg border bg-card">
                <h3 className="font-semibold mb-4">{t("event.platform_distribution")}</h3>
                <div className="space-y-2">
                  {Object.entries(event.platform_distribution).map(([platform, count]) => (
                    <div key={platform} className="flex items-center gap-3">
                      <span className="w-20 text-sm capitalize">{platform}</span>
                      <div className="flex-1 h-6 bg-muted rounded-full overflow-hidden">
                        <div
                          className="h-full bg-primary rounded-full transition-all"
                          style={{ width: `${(Number(count) / event.source_count) * 100}%` }}
                        />
                      </div>
                      <span className="text-sm text-muted-foreground w-8 text-right">
                        {String(count)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {event.original_sources?.length > 0 && (
              <div className="p-6 rounded-lg border bg-card">
                <h3 className="font-semibold mb-4 flex items-center gap-2">
                  <Shield className="h-4 w-4 text-green-600" />
                  {t("event.suspected_original")}
                </h3>
                <div className="space-y-3">
                  {event.original_sources.map((src: any) => (
                    <SourceCard key={src.id} source={src} />
                  ))}
                </div>
              </div>
            )}

            {event.has_rumor_report && (
              <div className="p-6 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/30">
                <h3 className="font-semibold mb-2 flex items-center gap-2 text-red-800 dark:text-red-400">
                  <AlertCircle className="h-5 w-5" />
                  {t("event.rumor_alert")}
                </h3>
                <p className="text-red-700 dark:text-red-400">
                  {t("event.rumor_alert_text", { verdict: verdictLabel(event.rumor_verdict) })}
                </p>
                <Link
                  to={`/events/${eventId}/report`}
                  className="inline-block mt-3 text-sm font-medium text-red-800 dark:text-red-400 underline"
                >
                  {t("event.view_full_report")}
                </Link>
              </div>
            )}

            {/* FactCheck + Citation Integrity Badges */}
            {analysisData && (
              <div className="space-y-4">
                {/* SatyaLens Citation Integrity */}
                {analysisData.satyalens_score && (
                  <div className="p-4 rounded-lg border bg-card">
                    <h4 className="text-sm font-semibold mb-2">引用完整性评分</h4>
                    <div className="flex items-center gap-4">
                      <div className="text-2xl font-bold">
                        {(analysisData.satyalens_score.overall_integrity_score * 100).toFixed(0)}
                        <span className="text-sm text-muted-foreground">/100</span>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {analysisData.satyalens_score.citations_found} 处引用
                        · {analysisData.satyalens_score.citations_verifiable} 可验证
                        · L{analysisData.satyalens_score.citation_chain_depth} 引用链
                      </div>
                    </div>
                    {analysisData.satyalens_score.red_flags?.length > 0 && (
                      <div className="mt-2 space-y-1">
                        {analysisData.satyalens_score.red_flags.slice(0, 2).map((f: any, i: number) => (
                          <div key={i} className="text-xs text-amber-600 flex items-start gap-1">
                            <AlertCircle size={12} className="mt-0.5 shrink-0" />
                            {f.description}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Google Fact Check */}
                {analysisData.fact_check_crossref && (
                  <div className="p-4 rounded-lg border bg-card">
                    <h4 className="text-sm font-semibold mb-2">第三方事实核查</h4>
                    <FactCheckBadge
                      matches={analysisData.fact_check_crossref.matches || []}
                      totalSearched={analysisData.fact_check_crossref.total_claims_searched}
                      summary={analysisData.fact_check_crossref.summary}
                    />
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === "analysis" && analysisData && (
          <div className="space-y-4">
            <AnalysisDashboard analysis={analysisData.analysis || analysisData} />
            {analysisData.analysis?.causal_graph_result && (
              <CausalGraphCard data={analysisData.analysis.causal_graph_result} />
            )}
            {analysisData.analysis?.correction_alternative && (
              <CorrectionPanel data={analysisData.analysis.correction_alternative} compact />
            )}
          </div>
        )}

        {activeTab === "graph" && (
          <div className="p-6 rounded-lg border bg-card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">{t("event.propagation_graph")}</h3>
              <div className="flex items-center gap-1 text-xs">
                <button
                  onClick={() => setGraphVersion("v1")}
                  className={`px-2.5 py-1 rounded-l-md border transition-colors ${
                    graphVersion === "v1"
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-background text-muted-foreground hover:bg-muted"
                  }`}
                >
                  D3.js
                </button>
                <button
                  onClick={() => setGraphVersion("v2")}
                  className={`px-2.5 py-1 rounded-r-md border transition-colors ${
                    graphVersion === "v2"
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-background text-muted-foreground hover:bg-muted"
                  }`}
                >
                  Cytoscape
                </button>
              </div>
            </div>
            {mergedGraphData?.nodes?.length ? (
              graphVersion === "v2" ? (
                <PropagationGraphV2 data={mergedGraphData} showTimeline />
              ) : (
                <PropagationGraph data={mergedGraphData} />
              )
            ) : (
              <div className="flex items-center justify-center h-64 text-muted-foreground">
                {loading ? (
                  <Loader2 className="h-6 w-6 animate-spin" />
                ) : (
                  t("event.no_graph")
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === "timeline" && (
          <div className="p-6 rounded-lg border bg-card">
            <h3 className="font-semibold mb-4">{t("event.timeline")}</h3>
            <EventTimeline nodes={timelineData?.timeline || []} loading={loading} />
          </div>
        )}

        {activeTab === "sources" && (
          <div className="space-y-3">
            {sourcesData?.sources?.map((src: any) => (
              <SourceCard key={src.id} source={src} detailed />
            ))}
            {(!sourcesData?.sources || sourcesData.sources.length === 0) && (
              <div className="text-center py-12 text-muted-foreground">
                {t("event.no_sources")}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Floating Action Bar */}
      <div className="fixed bottom-6 right-6 z-30 flex flex-col gap-2 print:hidden">
        {eventId && (
          <>
            <button
              onClick={() => navigator.clipboard.writeText(JSON.stringify(
                { "@context": "https://schema.org", "@type": "ClaimReview", "claimReviewed": event?.title || "", "reviewRating": { "@type": "Rating", "ratingValue": event?.credibility_score || 50, "alternateName": event?.rumor_verdict || "unverifiable" }, "url": `${window.location.origin}/events/${eventId}/report` }
              , null, 2))}
              className="w-12 h-12 rounded-full bg-white dark:bg-gray-800 shadow-lg border flex items-center justify-center hover:bg-primary/5 transition-colors group"
              title="复制 ClaimReview JSON-LD"
            >
              <Copy size={18} className="text-muted-foreground group-hover:text-primary" />
            </button>
            <button
              onClick={() => {
                const text = event?.title ? `TruthTrace: ${event.title} — 可信度 ${event.credibility_score}/100\n${window.location.origin}/events/${eventId}/report` : "";
                navigator.clipboard.writeText(text);
              }}
              className="w-12 h-12 rounded-full bg-white dark:bg-gray-800 shadow-lg border flex items-center justify-center hover:bg-primary/5 transition-colors group"
              title="复制分享文本"
            >
              <Share2 size={18} className="text-muted-foreground group-hover:text-primary" />
            </button>
            <Link
              to={`/events/${eventId}/report`}
              className="w-12 h-12 rounded-full bg-primary text-primary-foreground shadow-lg flex items-center justify-center hover:bg-primary/90 transition-colors"
              title="查看溯源报告"
            >
              <FileText size={18} />
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
