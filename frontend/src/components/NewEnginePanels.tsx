/**
 * NewEnginePanels — 多个新引擎的紧凑面板集合
 * 包含: 知识图谱推理 / 个性化辟谣 / 深度伪造检测 / 信息污染 / 教学助手
 */
import { useState, useEffect } from "react";
import { Brain, Sparkles, Shield, Activity, BookOpen, Loader2, Target, Zap, Globe } from "lucide-react";

const API = `${(import.meta as any).env?.VITE_API_BASE_URL || ""}/api`;

// ============================================================================
// 1. KG Reasoning Panel
// ============================================================================
export function KGReasoningPanel({ text, title }: { text?: string; title?: string }) {
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    if (!text) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/kg-reasoning`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, title: title || "" }),
      });
      if (res.ok) setResult(await res.json());
    } catch {}
    setLoading(false);
  };

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/20 flex items-center justify-between">
        <h3 className="text-sm font-semibold flex items-center gap-2"><Brain size={14} /> 知识图谱推理</h3>
        <button onClick={run} disabled={loading || !text} className="px-3 py-1 rounded-lg bg-primary text-primary-foreground text-xs font-medium disabled:opacity-50">
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "运行"}
        </button>
      </div>
      {result && (
        <div className="p-4 space-y-2">
          <p className="text-xs text-muted-foreground">{result.summary}</p>
          {result.verified_claims?.length > 0 && (
            <div className="space-y-1">
              <span className="text-[10px] font-medium text-green-600">✅ 验证 ({result.verified_claims.length})</span>
              {result.verified_claims.slice(0, 3).map((c: any, i: number) => (
                <p key={i} className="text-[10px] text-muted-foreground">{c.claim?.slice(0, 80)} → {c.target}</p>
              ))}
            </div>
          )}
          {result.refuted_claims?.length > 0 && (
            <div className="space-y-1">
              <span className="text-[10px] font-medium text-red-600">❌ 反驳 ({result.refuted_claims.length})</span>
              {result.refuted_claims.slice(0, 3).map((c: any, i: number) => (
                <p key={i} className="text-[10px] text-muted-foreground">{c.claim?.slice(0, 80)} → {c.target}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// 2. Personalized Debunking Panel
// ============================================================================
export function PersonalizedDebunkingPanel({ rumor, facts }: { rumor?: string; facts?: string[] }) {
  const [tone, setTone] = useState("neutral");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/personalized-debunking`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rumor: rumor || "", verified_facts: facts || [], query: rumor }),
      });
      if (res.ok) setResult(await res.json());
    } catch {}
    setLoading(false);
  };

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/20">
        <h3 className="text-sm font-semibold flex items-center gap-2"><Sparkles size={14} /> 个性化辟谣</h3>
      </div>
      <div className="p-4 space-y-3">
        <button onClick={run} disabled={loading} className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-medium disabled:opacity-50">
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "生成辟谣"}
        </button>
        {result && (
          <>
            <div className="p-2 rounded-lg bg-muted/30 text-xs space-y-1">
              <p className="font-medium">{result.headline}</p>
              <p className="text-muted-foreground">{result.summary}</p>
              <div className="flex gap-2 text-[10px] text-muted-foreground">
                <span>语气: {result.tone_used}</span>
                <span>预期效果: +{result.confidence_boost}%</span>
              </div>
            </div>
            <div className="text-xs whitespace-pre-wrap">{result.full_correction?.slice(0, 500)}</div>
          </>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// 3. Deepfake Panel
// ============================================================================
export function DeepfakePanel({ text }: { text?: string }) {
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    if (!text) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/deepfake/check`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (res.ok) setResult(await res.json());
    } catch {}
    setLoading(false);
  };

  const riskColor = (s: string) => {
    const m: Record<string, string> = { low: "text-green-600", medium: "text-amber-600", high: "text-red-600", critical: "text-red-700" };
    return m[s] || "text-muted-foreground";
  };

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/20 flex items-center justify-between">
        <h3 className="text-sm font-semibold flex items-center gap-2"><Shield size={14} /> 深度伪造检测</h3>
        <button onClick={run} disabled={loading || !text} className="px-3 py-1 rounded-lg bg-primary text-primary-foreground text-xs font-medium disabled:opacity-50">
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "检测"}
        </button>
      </div>
      {result && (
        <div className="p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className={`text-sm font-bold ${riskColor(result.overall_risk)}`}>
              风险: {result.risk_score?.toFixed(0)}/100
            </span>
            <span className="text-[10px] text-muted-foreground">篡改概率 {(result.tampering_probability * 100).toFixed(0)}%</span>
          </div>
          {result.findings?.map((f: any, i: number) => (
            <div key={i} className="flex items-start gap-2 text-xs p-2 rounded-lg bg-muted/20">
              <span className={`font-medium shrink-0 ${riskColor(f.severity)}`}>[{f.category}]</span>
              <div>
                <p className="font-medium">{f.finding_type}</p>
                <p className="text-muted-foreground">{f.description?.slice(0, 100)}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// 4. Pollution Index Dashboard
// ============================================================================
export function PollutionIndexDashboard() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/pollution-index`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center gap-2 p-4 text-xs text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" /> 加载...</div>;

  const levelColors: Record<string, string> = {
    good: "#16a34a", mild: "#ca8a04", moderate: "#ea580c", severe: "#dc2626", hazardous: "#7c3aed", dangerous: "#881337",
  };
  const levelEmojis: Record<string, string> = {
    good: "🟢", mild: "🟡", moderate: "🟠", severe: "🔴", hazardous: "🟣", dangerous: "🟤",
  };

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/20">
        <h3 className="text-sm font-semibold flex items-center gap-2"><Globe size={14} /> 信息污染指数</h3>
      </div>
      <div className="p-4 space-y-3">
        {data && (
          <>
            <div className="flex items-center justify-between">
              <span className="text-2xl font-bold" style={{ color: levelColors[data.risk_level] || "#6b7280" }}>
                {levelEmojis[data.risk_level]} {data.overall_ipi?.toFixed(0)}
              </span>
              <span className="text-xs text-muted-foreground">{data.risk_level} · {data.total_analyzed} 样本</span>
            </div>
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {data.platforms?.map((p: any, i: number) => (
                <div key={i} className="flex items-center justify-between text-xs">
                  <span>{p.platform}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-1.5 bg-muted rounded-full overflow-hidden">
                      <div className="h-full rounded-full" style={{
                        width: `${Math.min(100, p.ipi_score / 3)}%`,
                        backgroundColor: levelColors[p.risk_level] || "#6b7280",
                      }} />
                    </div>
                    <span className="text-[10px] font-mono w-8 text-right">{p.ipi_score?.toFixed(0)}</span>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// 5. Teach Assistant Panel
// ============================================================================
export function TeachAssistantPanel() {
  const [claim, setClaim] = useState("");
  const [level, setLevel] = useState("guided");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    if (!claim) return;
    setLoading(true);
    try {
      const res = await fetch(`${API}/teach/lesson`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ claim, level }),
      });
      if (res.ok) setResult(await res.json());
    } catch {}
    setLoading(false);
  };

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/20">
        <h3 className="text-sm font-semibold flex items-center gap-2"><BookOpen size={14} /> AI核查教学</h3>
      </div>
      <div className="p-4 space-y-3">
        <div className="flex gap-2">
          <input type="text" value={claim} onChange={e => setClaim(e.target.value)}
            placeholder="粘贴你想验证的信息..."
            className="flex-1 px-3 py-2 rounded-lg border text-xs" />
          <select value={level} onChange={e => setLevel(e.target.value)}
            className="px-2 py-2 rounded-lg border text-xs">
            <option value="guided">引导式</option>
            <option value="coached">教练式</option>
            <option value="autonomous">自主式</option>
          </select>
        </div>
        <button onClick={run} disabled={loading || !claim}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-xs font-medium disabled:opacity-50">
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "开始教学"}
        </button>
        {result && (
          <div className="space-y-2">
            <div className="p-2 rounded-lg bg-muted/30 text-center">
              <span className="text-lg font-bold">{result.total_score?.toFixed(0)}%</span>
              <p className="text-[10px] text-muted-foreground">{result.certificate_level} · {result.feedback}</p>
            </div>
            <div className="space-y-1.5 max-h-64 overflow-y-auto">
              {result.steps?.slice(0, 5).map((s: any, i: number) => (
                <div key={i} className="p-2 rounded-lg bg-muted/20 text-xs">
                  <p className="font-medium">{s.dimension}</p>
                  <p className="text-muted-foreground">{s.question}</p>
                  {s.hint && <p className="text-[10px] text-blue-600 mt-0.5">💡 {s.hint}</p>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
