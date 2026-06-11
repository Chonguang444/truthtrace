import { useState } from "react";
import { PenTool, Image, Video, Share2, Copy, Sparkles, Loader2, CheckCircle } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { CorrectionPanel } from "../components/CorrectionPanel";

const API = import.meta.env.VITE_API_BASE_URL || "";
const TABS = [
  { id: "article", label: "写辟谣文章", icon: PenTool },
  { id: "poster", label: "生成海报", icon: Image },
  { id: "script", label: "视频脚本", icon: Video },
  { id: "distribute", label: "多平台分发", icon: Share2 },
];

export default function DebunkStudio() {
  const [tab, setTab] = useState("article");
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Sparkles className="h-7 w-7 text-primary" />
        <div><h1 className="text-2xl font-bold">辟谣创作工坊</h1><p className="text-xs text-muted-foreground">把引擎分析转化为传播力强的辟谣内容</p></div>
      </div>
      <div className="flex flex-wrap gap-1 mb-6 border-b pb-2 overflow-x-auto">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-t-lg text-xs font-medium whitespace-nowrap ${tab === t.id ? "bg-primary/10 text-primary border-b-2 border-primary" : "text-muted-foreground hover:text-foreground"}`}>
            <t.icon className="h-3.5 w-3.5" />{t.label}
          </button>
        ))}
      </div>
      {tab === "article" && <ArticleTab />}
      {tab === "poster" && <PosterTab />}
      {tab === "script" && <ScriptTab />}
      {tab === "distribute" && <DistributeTab />}
    </div>
  );
}

function SectionLoader() {
  return <div className="flex items-center gap-2 p-8 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />AI 生成中...</div>;
}

// =============================================================================
// Tab: Write Article
// =============================================================================

function ArticleTab() {
  const [eventId, setEventId] = useState("");
  const [eventData, setEventData] = useState<any>(null);
  const [analysisData, setAnalysisData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchAndGenerate = async () => {
    if (!eventId) return;
    setLoading(true);
    setError("");
    try {
      // Fetch event + analysis data
      const [evtRes, anaRes] = await Promise.all([
        fetch(`${API}/api/events/${eventId}`, { credentials: "include" }),
        fetch(`${API}/api/events/${eventId}/analysis`, { credentials: "include" }),
      ]);
      if (!evtRes.ok) throw new Error("事件未找到");
      setEventData(await evtRes.json());
      if (anaRes.ok) setAnalysisData(await anaRes.json());
    } catch (e: any) {
      setError(e.message || "获取失败");
    }
    setLoading(false);
  };

  const engineAnalysis = analysisData?.analysis || null;
  const event = eventData || {};

  return (
    <div className="space-y-4">
      {/* Input */}
      <div className="p-4 rounded-xl border bg-card space-y-3">
        <p className="text-xs text-muted-foreground">
          输入事件 ID，自动获取完整引擎分析结果。引擎 #22 (Sift Correction Agent) 会自动生成辟谣叙事替代方案。
        </p>
        <div className="flex gap-2">
          <input
            placeholder="输入事件 ID (例: evt-abc123)"
            value={eventId}
            onChange={e => setEventId(e.target.value)}
            className="flex-1 px-3 py-2 rounded-lg border text-sm"
            onKeyDown={e => e.key === "Enter" && fetchAndGenerate()}
          />
          <button
            onClick={fetchAndGenerate}
            disabled={!eventId || loading}
            className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50 whitespace-nowrap"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "获取分析"}
          </button>
        </div>
      </div>

      {loading && <SectionLoader />}
      {error && <div className="p-4 rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm">{error}</div>}

      {/* Event summary */}
      {eventData && (
        <div className="p-4 rounded-lg border bg-card">
          <h3 className="font-semibold mb-1">{event.title || "未知事件"}</h3>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <span>可信度: <strong>{event.credibility_score || "?"}/100</strong></span>
            {event.rumor_verdict && <span className="text-red-600 font-medium">判定: {event.rumor_verdict}</span>}
            <span>来源: {event.source_count || 0}</span>
          </div>
        </div>
      )}

      {/* CorrectionPanel with engine data */}
      {engineAnalysis?.correction_alternative && (
        <CorrectionPanel data={engineAnalysis.correction_alternative} />
      )}

      {/* Fallback: show structured content from old API if available */}
      {!engineAnalysis?.correction_alternative && engineAnalysis && (
        <div className="p-6 rounded-lg border bg-muted/20 text-center text-sm text-muted-foreground">
          <p className="mb-2">该事件的引擎分析已完成，但尚未生成叙事替代方案。</p>
          <p>请确认该事件是否已执行完整的 23 步推理管线分析。</p>
          <p className="mt-2 text-xs">如果是旧事件，可通过重新分析获取叙事替代内容。</p>
        </div>
      )}

      {/* No analysis at all */}
      {!engineAnalysis && !loading && eventData && (
        <div className="p-6 rounded-lg border bg-muted/20 text-center text-sm text-muted-foreground">
          <p>该事件暂无完整的引擎分析结果。</p>
        </div>
      )}

      {/* Instructions when empty */}
      {!eventData && !loading && !error && (
        <div className="p-8 rounded-xl border border-dashed bg-muted/10 text-center">
          <Sparkles className="h-10 w-10 mx-auto mb-3 text-muted-foreground" />
          <h3 className="font-semibold mb-1">辟谣文章创作</h3>
          <p className="text-sm text-muted-foreground mb-4">
            输入已分析的事件 ID，直接获取引擎生成的辟谣叙事替代方案。<br/>
            支持 5 种语气策略，一键复制到任意平台。
          </p>
          <div className="inline-flex flex-wrap gap-1.5 justify-center">
            {["中立客观 · 适合任何场景", "权威坚定 · 适合官方发布", "共情理解 · 适合社交传播", "教育科普 · 适合深度解析", "简洁直接 · 适合微博/短视频"].map((t, i) => (
              <span key={i} className="px-2 py-1 rounded text-[10px] bg-muted text-muted-foreground">{t}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Tab: Poster
// =============================================================================

function PosterTab() {
  const [eventId, setEventId] = useState("");
  const [style, setStyle] = useState("minimal");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    const res = await fetch(API + "/api/studio/generate-poster", {
      method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
      body: JSON.stringify({ event_id: eventId, style }),
    });
    setResult(await res.json());
    setLoading(false);
  };

  const card = result?.truth_card;

  return (
    <div className="space-y-4">
      <div className="p-4 rounded-xl border bg-card space-y-3">
        <input placeholder="事件 ID" value={eventId} onChange={e => setEventId(e.target.value)} className="w-full px-3 py-2 rounded-lg border text-sm" />
        <div className="flex gap-2">
          {["minimal", "impact", "infographic"].map(s => (
            <button key={s} onClick={() => setStyle(s)} className={`px-3 py-1.5 rounded-full text-xs font-medium ${style === s ? "bg-primary text-primary-foreground" : "bg-muted"}`}>{s}</button>
          ))}
        </div>
        <button onClick={generate} disabled={!eventId || loading} className="w-full py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50">生成海报</button>
      </div>

      {loading && <SectionLoader />}

      {card && (
        <div className="max-w-sm mx-auto" style={{ backgroundColor: result?.colors?.bg || "#fff", color: result?.colors?.text || "#1a1a2e", borderRadius: 12, padding: 24, border: "2px solid #e5e7eb" }}>
          <h3 style={{ fontWeight: 700, marginBottom: 12, color: result?.colors?.accent || "#2563eb" }}>{card.title}</h3>
          <div style={{ background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, padding: 12, marginBottom: 12 }}>
            <p style={{ fontSize: 11, fontWeight: 600, color: "#dc2626", marginBottom: 4 }}>{card.rumor_label}</p>
            <p style={{ fontSize: 13 }}>{card.rumor_text}</p>
          </div>
          <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: 12, marginBottom: 12 }}>
            <p style={{ fontSize: 11, fontWeight: 600, color: "#16a34a", marginBottom: 4 }}>{card.fact_label}</p>
            <p style={{ fontSize: 13 }}>{card.fact_text}</p>
          </div>
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 12 }}>
            <div style={{ width: 64, height: 64, borderRadius: "50%", border: `3px solid ${result?.colors?.danger || "#ef4444"}`, display: "flex", alignItems: "center", justifyContent: "center", background: "#fef2f2" }}>
              <span style={{ fontSize: 18, fontWeight: 800, color: result?.colors?.danger || "#ef4444" }}>{card.credibility_badge?.score}</span>
            </div>
          </div>
          {card.key_findings?.map((f: any, i: number) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, fontSize: 12 }}>
              <span>{f.text}</span>
            </div>
          ))}
          <p style={{ fontSize: 10, color: "#6b7280", marginTop: 8 }}>{card.share_text}</p>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Tab: Video Script
// =============================================================================

function ScriptTab() {
  const [eventId, setEventId] = useState("");
  const [duration, setDuration] = useState(60);
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    const res = await fetch(API + "/api/studio/generate-script", {
      method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
      body: JSON.stringify({ event_id: eventId, duration_sec: duration }),
    });
    setResult(await res.json());
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      <div className="p-4 rounded-xl border bg-card space-y-3">
        <input placeholder="事件 ID" value={eventId} onChange={e => setEventId(e.target.value)} className="w-full px-3 py-2 rounded-lg border text-sm" />
        <div className="flex gap-2">
          {[30, 60, 90].map(d => (
            <button key={d} onClick={() => setDuration(d)} className={`px-3 py-1.5 rounded-full text-xs font-medium ${duration === d ? "bg-primary text-primary-foreground" : "bg-muted"}`}>{d}秒</button>
          ))}
        </div>
        <button onClick={generate} disabled={!eventId || loading} className="w-full py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50">生成脚本</button>
      </div>

      {loading && <SectionLoader />}

      {result && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold">{result.duration_sec}秒 · {result.total_scenes}个场景</span>
            {result.hashtags?.map((h: string) => <span key={h} className="text-[10px] text-blue-500">{h}</span>)}
          </div>
          {result.scenes?.map((s: any) => (
            <div key={s.scene} className="p-4 rounded-lg border bg-card border-l-4 border-l-primary">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-6 h-6 rounded-full bg-primary text-primary-foreground text-xs font-bold flex items-center justify-center">{s.scene}</span>
                <span className="text-sm font-semibold">{s.duration_sec}秒</span>
                <span className="text-xs text-muted-foreground">{s.transition}</span>
              </div>
              <p className="text-sm mb-2"><strong>旁白:</strong> {s.narration}</p>
              <p className="text-xs text-muted-foreground"><strong>屏幕文字:</strong> {s.on_screen_text}</p>
              <p className="text-xs text-muted-foreground"><strong>视觉:</strong> {s.visual_suggestion}</p>
            </div>
          ))}
          {result.production_tips && (
            <details className="p-3 rounded-lg bg-muted/30"><summary className="text-xs font-semibold cursor-pointer">制作建议</summary>
              <ul className="mt-2 space-y-1 text-xs text-muted-foreground">{result.production_tips.map((t: string, i: number) => <li key={i}>• {t}</li>)}</ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Tab: Distribute
// =============================================================================

function DistributeTab() {
  const [content, setContent] = useState("");
  const [platform, setPlatform] = useState("weibo");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const format = async () => {
    setLoading(true);
    const res = await fetch(API + "/api/studio/format-for-platform", {
      method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
      body: JSON.stringify({ content, platform, include_hashtags: true }),
    });
    setResult(await res.json());
    setLoading(false);
  };

  const copyFormatted = () => {
    navigator.clipboard.writeText(result?.formatted || "");
    setCopied(true); setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-4">
      <div className="p-4 rounded-xl border bg-card space-y-3">
        <textarea placeholder="粘贴辟谣内容..." value={content} onChange={e => setContent(e.target.value)} className="w-full px-3 py-2 rounded-lg border text-sm" rows={6} />
        <div className="flex gap-2 flex-wrap">
          {["weibo", "xiaohongshu", "douyin", "twitter"].map(p => (
            <button key={p} onClick={() => setPlatform(p)} className={`px-3 py-1.5 rounded-full text-xs font-medium ${platform === p ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
              {p === "weibo" ? "微博" : p === "xiaohongshu" ? "小红书" : p === "douyin" ? "抖音" : "Twitter"}
            </button>
          ))}
        </div>
        <button onClick={format} disabled={!content || loading} className="w-full py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50">格式化</button>
      </div>

      {loading && <SectionLoader />}

      {result && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold">{result.platform} 格式</span>
            <button onClick={copyFormatted} className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-accent text-xs">
              {copied ? <><CheckCircle className="h-3 w-3 text-green-500" />已复制</> : <><Copy className="h-3 w-3" />复制</>}
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="p-3 rounded-lg border bg-muted/30">
              <p className="text-[10px] text-muted-foreground mb-1">原始 ({result.original_length}字)</p>
              <p className="text-xs whitespace-pre-wrap">{result.original_content?.slice(0, 300)}</p>
            </div>
            <div className="p-3 rounded-lg border bg-primary/5">
              <p className="text-[10px] text-primary mb-1">格式化 · 限制 {result.max_length || "无"}字</p>
              <p className="text-xs whitespace-pre-wrap">{result.formatted}</p>
            </div>
          </div>
          {result.tips && (
            <ul className="space-y-1 text-xs text-muted-foreground p-3 rounded-lg bg-muted/30">{result.tips.map((t: string, i: number) => <li key={i}>💡 {t}</li>)}</ul>
          )}
        </div>
      )}
    </div>
  );
}
