import { useState } from "react";
import { Search, Zap, Copy, Check, Loader2 } from "lucide-react";

const API = (import.meta as any).env?.VITE_API_BASE_URL || "";

export function QuickCheck() {
  const [text, setText] = useState("");
  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const doCheck = async () => {
    if (text.trim().length < 10) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch(API + "/api/quick-check/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text.trim().slice(0, 5000), title: "" }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Error" }));
        throw new Error(err.detail || "HTTP " + res.status);
      }
      setResult(await res.json());
    } catch (e: any) {
      setError(e.message || "Failed");
    }
    setLoading(false);
  };

  const copyResult = () => {
    const txt =
      "TruthTrace Lite: " + (result?.credibility_score || "?") + "/100 - " +
      (result?.verdict || "") + "\n" + (result?.summary || "");
    navigator.clipboard.writeText(txt);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const cs = result?.credibility_score ?? 50;
  const vc = cs >= 60 ? "#16a34a" : cs >= 40 ? "#ca8a04" : "#dc2626";
  const vl: Record<string, string> = {
    likely_true: "Likely True", unverifiable: "Unverifiable",
    misleading: "Misleading", likely_false: "Likely False", false: "False",
  };
  const verdictLabel = vl[result?.verdict || ""] || result?.verdict || "-";
  const dists = result?.analysis?.distortion?.matches || [];
  const falls = result?.analysis?.fallacy?.matches || [];
  const causals = result?.analysis?.causal?.fallacies || [];

  return (
    <div className="container mx-auto px-4 py-8 max-w-2xl">
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium mb-4">
          <Zap className="h-3 w-3" /> Quick Check — No login required
        </div>
        <h1 className="text-3xl font-bold mb-2">TruthTrace Lite</h1>
        <p className="text-muted-foreground text-sm">
          Paste any text. Get a credibility score in under a second.
        </p>
      </div>

      <div className="rounded-xl border bg-card p-4 space-y-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Paste suspicious text here... e.g. claims about health, food safety, or breaking news"
          className="w-full h-32 px-4 py-3 rounded-lg border text-sm resize-y focus:outline-none focus:border-primary"
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && doCheck()}
        />
        <div className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">{text.length}/5000</span>
          <button
            onClick={doCheck}
            disabled={text.trim().length < 10 || loading}
            className="inline-flex items-center gap-2 px-6 py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
          >
            {loading ? (
              <><Loader2 className="h-4 w-4 animate-spin" />Analyzing...</>
            ) : (
              <><Search className="h-4 w-4" />Check</>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-4 p-4 rounded-lg border border-red-200 bg-red-50 text-red-700 text-sm">
          {error}
        </div>
      )}

      {result && (
        <div className="mt-6 space-y-4">
          <div className="rounded-xl border bg-card p-6">
            <div className="flex items-center gap-6 mb-4">
              <div
                className="w-20 h-20 rounded-full border-[6px] flex flex-col items-center justify-center"
                style={{ borderColor: vc }}
              >
                <span className="text-2xl font-extrabold" style={{ color: vc }}>
                  {cs}
                </span>
                <span className="text-[9px] text-muted-foreground">/100</span>
              </div>
              <div>
                <div className="text-lg font-bold" style={{ color: vc }}>
                  {verdictLabel}
                </div>
                <p className="text-sm text-muted-foreground mt-1">
                  {result.summary}
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 mb-4">
              {dists.length > 0 && (
                <span className="px-2 py-1 rounded-full text-xs bg-red-50 text-red-700 border border-red-200">
                  {dists.length} distortions
                </span>
              )}
              {falls.length > 0 && (
                <span className="px-2 py-1 rounded-full text-xs bg-amber-50 text-amber-700 border border-amber-200">
                  {falls.length} fallacies
                </span>
              )}
              {causals.length > 0 && (
                <span className="px-2 py-1 rounded-full text-xs bg-purple-50 text-purple-700 border border-purple-200">
                  {causals.length} causal
                </span>
              )}
            </div>

            <div className="flex gap-2">
              <button
                onClick={copyResult}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg border text-xs font-medium hover:bg-accent"
              >
                {copied ? (
                  <><Check size={14} className="text-green-500" />Copied!</>
                ) : (
                  <><Copy size={14} />Copy Result</>
                )}
              </button>
            </div>
          </div>

          {(dists.length > 0 || falls.length > 0 || causals.length > 0) && (
            <div className="rounded-xl border bg-card overflow-hidden">
              <div className="px-4 py-3 border-b bg-muted/20">
                <h3 className="text-sm font-semibold">Findings</h3>
              </div>
              <div className="p-4 space-y-2">
                {dists.slice(0, 2).map((m: any, i: number) => (
                  <div key={"d" + i} className="p-2.5 rounded-lg bg-red-50 border border-red-100 text-xs">
                    <span className="font-semibold text-red-700">DISTORTION:</span>{" "}
                    {m.description}
                  </div>
                ))}
                {falls.slice(0, 2).map((m: any, i: number) => (
                  <div key={"f" + i} className="p-2.5 rounded-lg bg-amber-50 border border-amber-100 text-xs">
                    <span className="font-semibold text-amber-700">FALLACY:</span>{" "}
                    {m.description}
                  </div>
                ))}
                {causals.slice(0, 1).map((m: any, i: number) => (
                  <div key={"c" + i} className="p-2.5 rounded-lg bg-purple-50 border border-purple-100 text-xs">
                    <span className="font-semibold text-purple-700">CAUSAL:</span>{" "}
                    {m.description}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {!result && !loading && (
        <div className="mt-8 rounded-xl border border-dashed p-8 text-center">
          <Zap className="h-10 w-10 mx-auto mb-3 text-muted-foreground/30" />
          <h3 className="font-semibold mb-2">How it works</h3>
          <div className="grid grid-cols-3 gap-4 mt-4 text-xs text-muted-foreground">
            <div className="p-3 rounded-lg bg-muted/20">{/*1*/}<div className="font-medium mb-1">1. Paste</div><p>Any text</p></div>
            <div className="p-3 rounded-lg bg-muted/20">{/*2*/}<div className="font-medium mb-1">2. Check</div><p>Engines in &lt;500ms</p></div>
            <div className="p-3 rounded-lg bg-muted/20">{/*3*/}<div className="font-medium mb-1">3. Decide</div><p>Score + verdict</p></div>
          </div>
        </div>
      )}
    </div>
  );
}

export default QuickCheck;
