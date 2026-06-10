import { useState, useEffect } from "react";
import { Code, Key, BookOpen, CreditCard, Copy, Terminal, CheckCircle, Zap, Loader2 } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { useAuth } from "../contexts/AuthContext";

const API = import.meta.env.VITE_API_BASE_URL || "";
const TABS = [
  { id: "register", label: "注册", icon: Key },
  { id: "dashboard", label: "仪表盘", icon: Zap },
  { id: "docs", label: "API 文档", icon: BookOpen },
  { id: "pricing", label: "定价", icon: CreditCard },
];

export default function DeveloperPortal() {
  const [tab, setTab] = useState("register");
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Code className="h-7 w-7 text-primary" />
        <div><h1 className="text-2xl font-bold">API 开放平台</h1><p className="text-xs text-muted-foreground">让第三方产品接入 TruthTrace 的检测能力</p></div>
      </div>
      <div className="flex flex-wrap gap-1 mb-6 border-b pb-2 overflow-x-auto">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-t-lg text-xs font-medium whitespace-nowrap ${tab === t.id ? "bg-primary/10 text-primary border-b-2 border-primary" : "text-muted-foreground hover:text-foreground"}`}>
            <t.icon className="h-3.5 w-3.5" />{t.label}
          </button>
        ))}
      </div>
      {tab === "register" && <RegisterTab />}
      {tab === "dashboard" && <DashboardTab />}
      {tab === "docs" && <DocsTab />}
      {tab === "pricing" && <PricingTab />}
    </div>
  );
}

// =============================================================================
// Tab: Register
// =============================================================================

function RegisterTab() {
  const { isAuthenticated } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [website, setWebsite] = useState("");
  const [useCase, setUseCase] = useState("");
  const [result, setResult] = useState<any>(null);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(false);

  const register = async () => {
    setLoading(true);
    const res = await fetch(API + "/api/developer/register", {
      method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
      body: JSON.stringify({ name, email, website, use_case: useCase }),
    });
    setResult(await res.json());
    setLoading(false);
  };

  const copyKey = () => { navigator.clipboard.writeText(result?.api_key || ""); setCopied(true); setTimeout(() => setCopied(false), 2000); };

  return (
    <div className="max-w-lg mx-auto space-y-4">
      {!result ? (
        <div className="p-6 rounded-xl border bg-card space-y-3">
          <h3 className="font-semibold">注册 API 开发者</h3>
          <input placeholder="名称" value={name} onChange={e => setName(e.target.value)} className="w-full px-3 py-2 rounded-lg border text-sm" />
          <input placeholder="邮箱" type="email" value={email} onChange={e => setEmail(e.target.value)} className="w-full px-3 py-2 rounded-lg border text-sm" />
          <input placeholder="网站 (可选)" value={website} onChange={e => setWebsite(e.target.value)} className="w-full px-3 py-2 rounded-lg border text-sm" />
          <textarea placeholder="使用场景 (至少10字)" value={useCase} onChange={e => setUseCase(e.target.value)} className="w-full px-3 py-2 rounded-lg border text-sm" rows={3} />
          <button onClick={register} disabled={!name || !email || useCase.length < 10 || loading || !isAuthenticated}
            className="w-full py-2.5 rounded-lg bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50">
            {!isAuthenticated ? "请先登录" : loading ? "注册中..." : "注册并获取 API Key"}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="p-6 rounded-xl border bg-green-50/30 dark:bg-green-950/10 border-green-200 text-center">
            <CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-3" />
            <h3 className="font-bold mb-2">注册成功!</h3>
            <p className="text-sm text-muted-foreground mb-4">{result.message}</p>
            <div className="p-3 rounded-lg bg-muted font-mono text-sm break-all relative">
              <code>{result.api_key}</code>
              <button onClick={copyKey} className="absolute right-2 top-2 p-1 rounded hover:bg-accent">{copied ? <CheckCircle className="h-4 w-4 text-green-500" /> : <Copy className="h-4 w-4" />}</button>
            </div>
            <p className="text-xs text-red-500 mt-2 font-semibold">⚠ 请立即保存 API Key — 关闭后不可恢复!</p>
          </div>

          {/* Code examples */}
          <div className="p-4 rounded-xl border bg-card">
            <h4 className="text-sm font-semibold mb-2 flex items-center gap-2"><Terminal className="h-4 w-4" />快速开始</h4>
            <div className="space-y-3">
              <div>
                <p className="text-[10px] text-muted-foreground mb-1">cURL</p>
                <pre className="p-2 rounded bg-muted text-xs overflow-x-auto">{result.quick_start?.curl_example}</pre>
              </div>
              <div>
                <p className="text-[10px] text-muted-foreground mb-1">Python</p>
                <pre className="p-2 rounded bg-muted text-xs overflow-x-auto">{result.quick_start?.python_example}</pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Tab: Dashboard
// =============================================================================

function DashboardTab() {
  const { data, loading, request } = useApi<any>();

  useEffect(() => { request("/api/developer/dashboard"); }, []);

  if (loading) return <div className="flex items-center gap-2 p-8"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>;
  if (!data) return <div className="p-8 text-center text-muted-foreground">请先注册 API 开发者</div>;

  const usage = data.usage || {};
  const plan = data.plan || {};
  const usagePct = Math.min(usage.usage_pct || 0, 100);
  const barColor = usagePct < 50 ? "bg-green-500" : usagePct < 80 ? "bg-yellow-500" : "bg-red-500";

  return (
    <div className="max-w-lg mx-auto space-y-4">
      <div className="p-6 rounded-xl border bg-card">
        <h3 className="font-semibold mb-4">{plan.name} · ${plan.monthly_price}/月</h3>
        <div className="text-center mb-4">
          <div className="text-4xl font-bold">{usage.used || 0}<span className="text-lg text-muted-foreground"> / {plan.monthly_quota}</span></div>
          <p className="text-xs text-muted-foreground mt-1">本月调用量</p>
        </div>
        <div className="h-3 rounded-full bg-muted overflow-hidden">
          <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${usagePct}%` }} />
        </div>
        <p className="text-xs text-muted-foreground mt-2">剩余 {usage.remaining || 0} 次 · 速率限制 {plan.rate_limit_per_min}次/分钟</p>
      </div>

      <div className="p-4 rounded-xl border bg-card">
        <h4 className="text-sm font-semibold mb-2">可用端点</h4>
        <div className="space-y-2">
          {(data.available_endpoints || []).map((ep: any) => (
            <div key={ep.path} className="flex items-center gap-2 p-2 rounded hover:bg-accent text-xs">
              <span className="px-1.5 py-0.5 rounded bg-primary/10 text-primary font-mono text-[10px]">{ep.method}</span>
              <code className="flex-1">{ep.path}</code>
              <span className="text-muted-foreground">{ep.desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Tab: API Docs
// =============================================================================

function DocsTab() {
  const { data, loading, request } = useApi<any>();

  useEffect(() => { request("/api/developer/docs"); }, []);

  if (loading) return <div className="flex items-center gap-2 p-8"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>;

  return (
    <div className="space-y-4">
      <div className="p-6 rounded-xl border bg-card">
        <h3 className="font-bold mb-2">{data?.api_version} API</h3>
        <p className="text-sm text-muted-foreground mb-4">Base URL: {data?.base_url}</p>
        <div className="p-3 rounded-lg bg-muted/50 mb-4">
          <p className="text-xs font-semibold mb-1">认证方式</p>
          <code className="text-xs">{data?.authentication?.method}: {data?.authentication?.example}</code>
        </div>
        {(data?.endpoints || []).map((ep: any) => (
          <div key={ep.path} className="p-4 rounded-lg border mb-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2 py-0.5 rounded bg-primary/10 text-primary font-mono text-xs">{ep.method}</span>
              <code className="text-sm font-semibold">{ep.path}</code>
              <span className="text-xs text-muted-foreground">限速: {ep.rate_limit}</span>
            </div>
            <p className="text-xs text-muted-foreground mb-2">{ep.description}</p>
            {ep.request_body && (
              <div className="p-2 rounded bg-muted text-xs font-mono">
                {JSON.stringify(ep.request_body, null, 2)}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// Tab: Pricing
// =============================================================================

function PricingTab() {
  const { data, loading, request } = useApi<any>();

  useEffect(() => { request("/api/developer/pricing"); }, []);

  if (loading) return <div className="flex items-center gap-2 p-8"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>;

  const plans = data?.plans || [];
  const faq = data?.faq || [];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {plans.map((p: any) => (
          <div key={p.id} className={`p-6 rounded-xl border bg-card relative ${p.recommended ? "ring-2 ring-primary" : ""}`}>
            {p.recommended && <span className="absolute -top-2 right-4 px-2 py-0.5 rounded-full bg-primary text-primary-foreground text-[10px] font-bold">推荐</span>}
            <h3 className="font-bold text-lg mb-1">{p.name}</h3>
            <div className="text-3xl font-bold mb-4">{p.price}</div>
            <ul className="space-y-2 mb-6">
              {p.features.map((f: string) => (
                <li key={f} className="flex items-center gap-2 text-sm"><CheckCircle className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />{f}</li>
              ))}
            </ul>
            <button className={`w-full py-2.5 rounded-lg text-sm font-medium ${p.recommended ? "bg-primary text-primary-foreground" : "bg-accent"}`}>{p.cta}</button>
          </div>
        ))}
      </div>

      {/* FAQ */}
      <div className="p-6 rounded-xl border bg-card">
        <h3 className="font-bold mb-4">常见问题</h3>
        <div className="space-y-3">
          {faq.map((item: any, i: number) => (
            <details key={i} className="p-3 rounded-lg bg-muted/30"><summary className="text-sm font-semibold cursor-pointer">{item.q}</summary><p className="text-xs text-muted-foreground mt-2">{item.a}</p></details>
          ))}
        </div>
      </div>
    </div>
  );
}
