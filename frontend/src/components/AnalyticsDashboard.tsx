import { useState, useEffect, useRef } from "react";
import { BarChart3, TrendingUp, Share2, Copy, Eye, Target, Loader2, ChevronDown } from "lucide-react";

interface ToneStats {
  views: number;
  copies: number;
  shares: number;
  share_rate: number;
  copy_rate: number;
  effectiveness_score: number;
}

interface ABResult {
  ab_test_results: Record<string, ToneStats>;
  sample_size: number;
  recommendation: string;
  generated_at: string;
}

interface FullStats {
  total: { views: number; copies: number; shares: number };
  by_tone: Record<string, ToneStats>;
  by_platform: Record<string, number>;
  generated_at: string;
}

const TONE_LABELS: Record<string, { label: string; color: string }> = {
  neutral: { label: "中立", color: "#3b82f6" },
  authoritative: { label: "权威", color: "#ef4444" },
  empathetic: { label: "共情", color: "#10b981" },
  educational: { label: "科普", color: "#8b5cf6" },
  concise: { label: "简洁", color: "#f59e0b" },
};

const PLATFORM_LABELS: Record<string, string> = {
  weibo: "微博", twitter: "Twitter/X", wechat: "微信", copy: "复制分享",
};

export function AnalyticsDashboard() {
  const [stats, setStats] = useState<FullStats | null>(null);
  const [abResults, setAbResults] = useState<ABResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedEvent, setSelectedEvent] = useState("");
  const intervalRef = useRef<any>(null);

  const API = `${(import.meta as any).env?.VITE_API_BASE_URL || ""}/api/analytics`;

  const fetchData = async () => {
    try {
      const params = selectedEvent ? `?event_id=${selectedEvent}` : "";
      const [statsRes, abRes] = await Promise.all([
        fetch(`${API}/debunk-stats${params}`),
        fetch(`${API}/debunk-ab-test${params}`),
      ]);
      if (statsRes.ok) setStats(await statsRes.json());
      if (abRes.ok) setAbResults(await abRes.json());
      setError("");
    } catch (e: any) {
      setError(e.message || "获取数据失败");
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
    intervalRef.current = setInterval(fetchData, 30000);
    return () => clearInterval(intervalRef.current);
  }, [selectedEvent]);

  if (loading && !stats) {
    return (
      <div className="flex items-center gap-2 p-8 justify-center text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> 加载分析数据...
      </div>
    );
  }

  const total = stats?.total || { views: 0, copies: 0, shares: 0 };
  const bestTone = abResults?.ab_test_results
    ? Object.entries(abResults.ab_test_results).sort((a, b) => b[1].effectiveness_score - a[1].effectiveness_score)[0]
    : null;

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-3 rounded-lg border border-red-200 bg-red-50 text-red-700 text-xs">{error}</div>
      )}

      {/* Event filter */}
      <div className="flex items-center gap-2">
        <input
          type="text"
          placeholder="按事件ID筛选 (留空=全部)"
          value={selectedEvent}
          onChange={(e) => setSelectedEvent(e.target.value)}
          className="px-3 py-1.5 rounded-lg border text-xs w-48"
        />
        <span className="text-[10px] text-muted-foreground">自动刷新: 30秒</span>
      </div>

      {/* Funnel */}
      <div className="grid grid-cols-3 gap-3">
        <FunnelStep icon={<Eye size={16} />} label="查看" value={total.views} color="blue" />
        <FunnelStep icon={<Copy size={16} />} label="复制" value={total.copies} color="amber"
          conversion={total.views > 0 ? (total.copies / total.views * 100).toFixed(1) + "%" : "-"} />
        <FunnelStep icon={<Share2 size={16} />} label="分享" value={total.shares} color="green"
          conversion={total.views > 0 ? (total.shares / total.views * 100).toFixed(1) + "%" : "-"} />
      </div>

      {/* Best tone recommendation */}
      {bestTone && (
        <div className="p-4 rounded-xl border bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-950/20 dark:to-purple-950/20">
          <div className="flex items-center gap-2 mb-2">
            <Target size={16} className="text-purple-500" />
            <span className="text-sm font-semibold">A/B 测试推荐</span>
          </div>
          <p className="text-sm">
            最佳辟谣语气: <strong style={{ color: TONE_LABELS[bestTone[0]]?.color }}>
              {TONE_LABELS[bestTone[0]]?.label || bestTone[0]}
            </strong>
            — 效果评分 {bestTone[1].effectiveness_score.toFixed(0)}/100
          </p>
          <p className="text-[11px] text-muted-foreground mt-1">
            基于 {abResults?.sample_size || 0} 次查看样本 · 分享率 {bestTone[1].share_rate.toFixed(1)}% · 复制率 {bestTone[1].copy_rate.toFixed(1)}%
          </p>
        </div>
      )}

      {/* Tone comparison */}
      {stats?.by_tone && Object.keys(stats.by_tone).length > 0 && (
        <div className="rounded-xl border bg-card overflow-hidden">
          <div className="px-4 py-3 border-b bg-muted/20">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <BarChart3 size={14} /> 语气效果对比
            </h3>
          </div>
          <div className="p-4 space-y-3">
            {Object.entries(stats.by_tone)
              .sort((a, b) => (b[1].effectiveness_score || 0) - (a[1].effectiveness_score || 0))
              .map(([tone, s]) => {
                const cfg = TONE_LABELS[tone] || { label: tone, color: "#6b7280" };
                const maxViews = Math.max(...Object.values(stats.by_tone).map((v: any) => v.views || 1), 1);
                const barWidth = ((s.views || 0) / maxViews * 100).toFixed(0);
                return (
                  <div key={tone} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-1.5">
                        <span className="w-2 h-2 rounded-full" style={{ backgroundColor: cfg.color }} />
                        {cfg.label}
                      </span>
                      <span className="text-muted-foreground">
                        {s.views || 0} 查看 · {s.copies || 0} 复制 · {s.shares || 0} 分享
                      </span>
                    </div>
                    <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{ width: `${barWidth}%`, backgroundColor: cfg.color }}
                      />
                    </div>
                    <div className="flex gap-3 text-[10px] text-muted-foreground">
                      <span>分享率: {((s.share_rate || 0) * 100).toFixed(1)}%</span>
                      <span>复制率: {((s.copy_rate || 0) * 100).toFixed(1)}%</span>
                      {s.effectiveness_score !== undefined && (
                        <span className="font-medium">效果: {s.effectiveness_score.toFixed(0)}/100</span>
                      )}
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* Platform distribution */}
      {stats?.by_platform && Object.keys(stats.by_platform).length > 0 && (
        <div className="rounded-xl border bg-card overflow-hidden">
          <div className="px-4 py-3 border-b bg-muted/20">
            <h3 className="text-sm font-semibold flex items-center gap-2">
              <Share2 size={14} /> 分享平台分布
            </h3>
          </div>
          <div className="p-4 flex flex-wrap gap-3">
            {Object.entries(stats.by_platform).map(([platform, count]) => (
              <div key={platform} className="px-3 py-2 rounded-lg border bg-muted/10 text-center min-w-[80px]">
                <div className="text-lg font-bold">{count}</div>
                <div className="text-[10px] text-muted-foreground">
                  {PLATFORM_LABELS[platform] || platform}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {(!stats?.total?.views && total.views === 0) && (
        <div className="p-8 text-center text-sm text-muted-foreground rounded-xl border border-dashed">
          <BarChart3 className="h-8 w-8 mx-auto mb-2 opacity-30" />
          <p>暂无辟谣效果数据</p>
          <p className="text-xs mt-1">当用户查看和分享辟谣卡片时，数据将在这里实时展示</p>
        </div>
      )}
    </div>
  );
}

function FunnelStep({ icon, label, value, color, conversion }: {
  icon: React.ReactNode; label: string; value: number; color: string; conversion?: string;
}) {
  const colors: Record<string, string> = {
    blue: "bg-blue-50 dark:bg-blue-950/20 border-blue-200 text-blue-700",
    amber: "bg-amber-50 dark:bg-amber-950/20 border-amber-200 text-amber-700",
    green: "bg-green-50 dark:bg-green-950/20 border-green-200 text-green-700",
  };
  return (
    <div className={`rounded-lg border p-3 text-center ${colors[color] || ""}`}>
      <div className="flex items-center justify-center gap-1 mb-1 opacity-70 text-xs">{icon}{label}</div>
      <div className="text-2xl font-bold">{value}</div>
      {conversion && <div className="text-[10px] mt-0.5 opacity-70">{conversion} 转化</div>}
    </div>
  );
}
