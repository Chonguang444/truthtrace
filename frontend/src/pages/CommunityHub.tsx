import { useState, useEffect } from "react";
import { Users, Coins, Trophy, Shield, Search, ArrowUp, Award, Clock, Loader2, CheckCircle } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { useAuth } from "../contexts/AuthContext";

const API = import.meta.env.VITE_API_BASE_URL || "";
const TABS = [
  { id: "expert", label: "专家验证", icon: Shield },
  { id: "bounties", label: "悬赏求证", icon: Coins },
  { id: "leaderboard", label: "排行榜", icon: Trophy },
  { id: "reputation", label: "我的信誉", icon: Award },
];

export default function CommunityHub() {
  const [tab, setTab] = useState("expert");
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <Users className="h-7 w-7 text-primary" />
        <div><h1 className="text-2xl font-bold">协作众包</h1><p className="text-xs text-muted-foreground">人工智能 + 人群智慧 = 更高准确率</p></div>
      </div>
      <div className="flex flex-wrap gap-1 mb-6 border-b pb-2 overflow-x-auto">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-t-lg text-xs font-medium whitespace-nowrap ${tab === t.id ? "bg-primary/10 text-primary border-b-2 border-primary" : "text-muted-foreground hover:text-foreground"}`}>
            <t.icon className="h-3.5 w-3.5" />{t.label}
          </button>
        ))}
      </div>
      {tab === "expert" && <ExpertTab />}
      {tab === "bounties" && <BountiesTab />}
      {tab === "leaderboard" && <LeaderboardTab />}
      {tab === "reputation" && <ReputationTab />}
    </div>
  );
}

// =============================================================================
// Expert Tab
// =============================================================================

function ExpertTab() {
  const { user } = useAuth();
  const { data: queue, loading, request } = useApi<any>();
  const [showApply, setShowApply] = useState(false);
  const [domain, setDomain] = useState("medicine");
  const [credentials, setCredentials] = useState("");
  const [proofUrl, setProofUrl] = useState("");
  const [applyResult, setApplyResult] = useState<string | null>(null);

  useEffect(() => { request("/api/community/expert/queue"); }, []);

  const handleApply = async () => {
    const res = await fetch(API + "/api/community/expert/apply", {
      method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
      body: JSON.stringify({ domain, credentials, proof_url: proofUrl }),
    });
    const d = await res.json();
    setApplyResult(d.message || d.status);
  };

  if (loading) return <div className="flex items-center gap-2 p-8"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>;

  const isExpert = queue?.is_expert;

  return (
    <div className="space-y-4">
      {!isExpert && (
        <div className="p-4 rounded-xl border bg-card">
          <h3 className="font-semibold mb-3">申请成为领域验证者</h3>
          {!showApply ? (
            <button onClick={() => setShowApply(true)} className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm">申请专家资格</button>
          ) : (
            <div className="space-y-3">
              <select value={domain} onChange={e => setDomain(e.target.value)} className="w-full px-3 py-2 rounded-lg border text-sm">
                <option value="medicine">医学健康</option><option value="food_safety">食品安全</option><option value="journalism">新闻传播</option>
                <option value="data_science">数据科学</option><option value="law">法律法规</option><option value="environment">环境科学</option>
              </select>
              <textarea placeholder="资历描述" value={credentials} onChange={e => setCredentials(e.target.value)} className="w-full px-3 py-2 rounded-lg border text-sm" rows={3} />
              <input placeholder="证明材料链接(可选)" value={proofUrl} onChange={e => setProofUrl(e.target.value)} className="w-full px-3 py-2 rounded-lg border text-sm" />
              <button onClick={handleApply} disabled={!credentials} className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm disabled:opacity-50">提交申请</button>
              {applyResult && <p className="text-sm text-green-600">{applyResult}</p>}
            </div>
          )}
        </div>
      )}

      {/* Verification Queue */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold">待验证队列 ({queue?.total_pending || 0})</h3>
          {isExpert && <span className="px-2 py-0.5 rounded bg-green-100 text-green-700 text-xs">已认证 · {queue?.domain_name}</span>}
        </div>
        <div className="space-y-2">
          {(queue?.queue || []).map((e: any) => (
            <div key={e.event_id} className="p-3 rounded-lg border bg-card flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-sm truncate">{e.title}</p>
                <span className={`text-xs ${e.credibility_score < 30 ? "text-red-600" : "text-muted-foreground"}`}>可信度 {e.credibility_score?.toFixed(0)}</span>
                {e.already_verified && <span className="ml-2 text-xs text-green-600">已验证 ({e.expert_verifications_count})</span>}
              </div>
              {isExpert && !e.already_verified && (
                <button onClick={async () => {
                  const verdict = prompt("判定 (confirmed/likely_true/misleading/likely_false/false/unverifiable):", "misleading");
                  if (verdict) {
                    await fetch(API + `/api/community/expert/verify/${e.event_id}`, {
                      method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
                      body: JSON.stringify({ verdict, evidence_links: [], notes: "" }),
                    });
                    request("/api/community/expert/queue");
                  }
                }} className="px-3 py-1 rounded-lg bg-primary text-primary-foreground text-xs flex-shrink-0 ml-2">验证</button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Bounties Tab
// =============================================================================

function BountiesTab() {
  const { user } = useAuth();
  const { data, loading, request } = useApi<any>();
  const [status, setStatus] = useState<string>("");
  const [showCreate, setShowCreate] = useState(false);
  const [bountyUrl, setBountyUrl] = useState("");
  const [question, setQuestion] = useState("");
  const [reward, setReward] = useState(50);

  useEffect(() => {
    const params = status ? `?status=${status}` : "";
    request(`/api/community/bounties${params}`);
  }, [status]);

  if (loading) return <div className="flex items-center gap-2 p-8"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>;

  const bounties = data?.bounties || [];

  const createBounty = async () => {
    await fetch(API + "/api/community/bounty", {
      method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include",
      body: JSON.stringify({ url: bountyUrl, question, reward_points: reward }),
    });
    setShowCreate(false); setBountyUrl(""); setQuestion(""); setReward(50);
    request("/api/community/bounties");
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          {["", "open", "claimed", "completed"].map(s => (
            <button key={s} onClick={() => setStatus(s)} className={`px-3 py-1 rounded-full text-xs font-medium ${status === s ? "bg-primary text-primary-foreground" : "bg-muted hover:bg-muted/80"}`}>
              {s === "" ? "全部" : s}
            </button>
          ))}
        </div>
        <button onClick={() => setShowCreate(!showCreate)} className="px-3 py-1.5 rounded-lg bg-primary text-primary-foreground text-xs font-medium">发布悬赏</button>
      </div>

      {showCreate && (
        <div className="p-4 rounded-xl border bg-card space-y-3">
          <input placeholder="URL" value={bountyUrl} onChange={e => setBountyUrl(e.target.value)} className="w-full px-3 py-2 rounded-lg border text-sm" />
          <textarea placeholder="你想求证什么?" value={question} onChange={e => setQuestion(e.target.value)} className="w-full px-3 py-2 rounded-lg border text-sm" rows={2} />
          <div className="flex items-center gap-3">
            <input type="range" min={10} max={500} value={reward} onChange={e => setReward(Number(e.target.value))} className="flex-1" />
            <span className="text-sm font-semibold">{reward} 积分</span>
          </div>
          <button onClick={createBounty} className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm">发布悬赏</button>
        </div>
      )}

      <div className="space-y-2">
        {bounties.map((b: any) => (
          <div key={b.id} className="p-3 rounded-lg border bg-card">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-sm">{b.question}</p>
                <div className="flex items-center gap-2 mt-1 flex-wrap">
                  <span className="text-[10px] text-muted-foreground truncate max-w-[200px]">{b.url}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${b.status === "open" ? "bg-green-100 text-green-700" : b.status === "claimed" ? "bg-amber-100 text-amber-700" : "bg-blue-100 text-blue-700"}`}>{b.status}</span>
                  <span className="text-xs font-semibold text-amber-600">{b.reward_points} 积分</span>
                </div>
              </div>
              <div className="flex-shrink-0 ml-2">
                {b.status === "open" && (
                  <button onClick={async () => { await fetch(API + `/api/community/bounty/${b.id}/claim`, { method: "POST", credentials: "include" }); request(`/api/community/bounties${status ? `?status=${status}` : ""}`); }}
                    className="px-3 py-1 rounded-lg bg-primary text-primary-foreground text-xs">认领</button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// Leaderboard Tab
// =============================================================================

function LeaderboardTab() {
  const { data, loading, request } = useApi<any>();
  const [period, setPeriod] = useState("weekly");

  useEffect(() => { request(`/api/community/leaderboard?period=${period}`); }, [period]);

  if (loading) return <div className="flex items-center gap-2 p-8"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>;

  const overall = data?.overall_by_reputation || [];
  const verifications = data?.by_verifications || [];
  const bountyCompletions = data?.by_bounties || [];

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        {["weekly", "monthly", "all"].map(p => (
          <button key={p} onClick={() => setPeriod(p)} className={`px-3 py-1.5 rounded-full text-xs font-medium ${period === p ? "bg-primary text-primary-foreground" : "bg-muted"}`}>
            {p === "weekly" ? "本周" : p === "monthly" ? "本月" : "全部"}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Reputation ranking */}
        <div className="md:col-span-2">
          <h3 className="text-sm font-semibold mb-3">信誉排行 Top 20</h3>
          <div className="space-y-1">
            {overall.map((u: any) => (
              <div key={u.user_id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-accent">
                <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${u.score > 500 ? "bg-amber-100 text-amber-700" : "bg-muted text-muted-foreground"}`}>{Array.isArray(overall) ? overall.indexOf(u) + 1 : u.rank}</span>
                <span className="text-sm flex-1">{u.username}</span>
                <span className="text-sm font-semibold">{u.score}</span>
                {u.score >= 500 && <Award className="h-4 w-4 text-amber-500" />}
              </div>
            ))}
          </div>
        </div>
        {/* Side rankings */}
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-semibold mb-2">验证排行</h3>
            <div className="space-y-1">
              {verifications.slice(0, 10).map((u: any) => (
                <div key={u.user_id} className="flex justify-between text-xs p-1 rounded hover:bg-accent"><span>{u.username}</span><span className="font-semibold">{u.count}</span></div>
              ))}
            </div>
          </div>
          <div>
            <h3 className="text-sm font-semibold mb-2">悬赏排行</h3>
            <div className="space-y-1">
              {bountyCompletions.slice(0, 10).map((u: any) => (
                <div key={u.user_id} className="flex justify-between text-xs p-1 rounded hover:bg-accent"><span>{u.username}</span><span className="font-semibold">{u.count}</span></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Reputation Tab
// =============================================================================

function ReputationTab() {
  const { user } = useAuth();
  const { data, loading, request } = useApi<any>();

  useEffect(() => {
    if (user?.id) request(`/api/community/reputation/${user.id}`);
  }, [user?.id]);

  if (loading) return <div className="flex items-center gap-2 p-8"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>;
  if (!data) return <div className="p-8 text-center text-muted-foreground">请先登录查看信誉</div>;

  const progress = Math.min(data.progress_pct || 0, 100);
  const levelColors: Record<string, string> = { Novice: "bg-gray-200", Contributor: "bg-blue-200", Expert: "bg-purple-200", Master: "bg-amber-200", Grandmaster: "bg-red-200" };
  const barColors: Record<string, string> = { Novice: "bg-gray-500", Contributor: "bg-blue-500", Expert: "bg-purple-500", Master: "bg-amber-500", Grandmaster: "bg-red-500" };

  return (
    <div className="max-w-md mx-auto space-y-4">
      {/* Score card */}
      <div className="text-center p-8 rounded-xl border bg-gradient-to-b from-card to-muted/30">
        <div className="text-5xl font-bold mb-2">{data.score}</div>
        <div className="text-lg font-semibold">{data.level_cn} ({data.level})</div>
        <div className="mt-3 h-2.5 rounded-full bg-muted overflow-hidden">
          <div className={`h-full rounded-full transition-all ${barColors[data.level] || "bg-primary"}`} style={{ width: `${progress}%` }} />
        </div>
        <p className="text-xs text-muted-foreground mt-1">距离 {data.level_cn === "宗师" ? "顶峰" : `下一等级`} 还需要 {Math.max(0, (data.next_threshold || 100) - (data.score || 0))} 分</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-2">
        <div className="p-3 rounded-lg border bg-card text-center"><div className="text-xl font-bold">{data.upvotes || 0}</div><div className="text-[10px] text-muted-foreground">赞</div></div>
        <div className="p-3 rounded-lg border bg-card text-center"><div className="text-xl font-bold">{data.downvotes || 0}</div><div className="text-[10px] text-muted-foreground">踩</div></div>
        <div className="p-3 rounded-lg border bg-card text-center"><div className="text-xl font-bold">{data.total_contributions || 0}</div><div className="text-[10px] text-muted-foreground">贡献</div></div>
      </div>

      {/* Badges */}
      <div>
        <h4 className="text-sm font-semibold mb-2">徽章</h4>
        <div className="flex flex-wrap gap-2">
          {(data.badges || []).map((b: any) => (
            <span key={b.id} className="px-3 py-1.5 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 text-xs font-medium">{b.icon} {b.name}</span>
          ))}
          {(!data.badges || data.badges.length === 0) && <p className="text-xs text-muted-foreground">还没有徽章，开始贡献吧!</p>}
        </div>
      </div>

      {/* Recent history */}
      <div>
        <h4 className="text-sm font-semibold mb-2">最近动态</h4>
        <div className="space-y-1">
          {(data.recent_history || []).slice(-5).reverse().map((h: any, i: number) => (
            <div key={i} className="flex items-center justify-between p-2 rounded text-xs hover:bg-accent">
              <span>{h.reason}</span>
              <span className={`font-semibold ${h.points >= 0 ? "text-green-600" : "text-red-600"}`}>{h.points >= 0 ? "+" : ""}{h.points}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
