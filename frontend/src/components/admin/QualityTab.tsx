/**
 * 质量管理仪表盘 — 质量监控/引擎健康/反馈趋势/校准状态/去重/知识健康
 *
 * 可视化 TruthTrace 引擎的自我进化状态。
 * 各模块评分用颜色编码: 绿=健康 / 黄=需关注 / 红=异常
 */

import { useEffect, useState } from "react";
import {
  Activity, BarChart3, Brain, Shield, TrendingUp,
  AlertTriangle, CheckCircle, Clock, Database,
  RefreshCw, Zap, Target, Layers, Cpu,
} from "lucide-react";
import { useApi } from "../../hooks/useApi";

interface DashboardData {
  overview: Record<string, number>;
  engine_health: { modules: EngineModule[] };
  feedback_trends: Record<string, number>;
  calibration: Record<string, any>;
  misjudgment: { active_patterns: number; patterns: any[] };
  dedup_status: Record<string, any>;
  knowledge_health: { entries_needing_review: number; entries: any[] };
  anomalies: string[];
  feedback_loop?: Record<string, any>;
  timestamp: string;
}

interface EngineModule {
  name: string;
  weight: number;
  healthy: boolean;
  deviation: number;
  trend: string;
}

function healthColor(healthy: boolean, value: number, goodRange: [number, number] = [0, 0]): string {
  if (healthy) return "text-green-600 bg-green-50 dark:bg-green-950/20";
  return "text-yellow-600 bg-yellow-50 dark:bg-yellow-950/20";
}

function ScoreBar({ value, max, label, color = "blue" }: { value: number; max: number; label: string; color?: string }) {
  const pct = Math.min(100, Math.max(0, (value / Math.max(1, max)) * 100));
  const colors: Record<string, string> = {
    blue: "bg-blue-500", green: "bg-green-500", yellow: "bg-yellow-500", red: "bg-red-500",
    purple: "bg-purple-500", orange: "bg-orange-500",
  };
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>{label}</span>
        <span className="font-mono">{typeof value === "number" ? value.toFixed(1) : value}</span>
      </div>
      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
        <div className={`h-full rounded-full transition-all ${colors[color] || colors.blue}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, sub, color = "blue" }: {
  icon: any; label: string; value: string | number; sub?: string; color?: string;
}) {
  const colors: Record<string, string> = {
    blue: "text-blue-600 bg-blue-50 dark:bg-blue-950/20",
    green: "text-green-600 bg-green-50 dark:bg-green-950/20",
    yellow: "text-yellow-600 bg-yellow-50 dark:bg-yellow-950/20",
    red: "text-red-600 bg-red-50 dark:bg-red-950/20",
    purple: "text-purple-600 bg-purple-50 dark:bg-purple-950/20",
  };
  return (
    <div className="p-4 rounded-lg border bg-card hover:shadow-sm transition-shadow">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-muted-foreground">{label}</span>
        <Icon className={`h-4 w-4 ${colors[color]}`} />
      </div>
      <div className="text-2xl font-bold">{value}</div>
      {sub && <div className="text-[10px] text-muted-foreground mt-1">{sub}</div>}
    </div>
  );
}

export function QualityTab() {
  const { data, loading, request } = useApi<DashboardData>();
  const [autoRefresh, setAutoRefresh] = useState(false);

  useEffect(() => {
    request("/api/system/quality/dashboard");
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(() => request("/api/system/quality/dashboard"), 10000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  if (loading && !data) return (
    <div className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
      <RefreshCw className="h-4 w-4 animate-spin" />
      加载质量仪表盘...
    </div>
  );

  const d = data;
  if (!d) return <div className="p-6 text-sm text-muted-foreground">无法加载质量数据</div>;

  const overview = d.overview || {};
  const engine = d.engine_health || { modules: [] };
  const feedback = d.feedback_trends || {};
  const cal = d.calibration || {};
  const mis = d.misjudgment || {};
  const dedup = d.dedup_status || {};
  const knowledge = d.knowledge_health || {};
  const anomalies = d.anomalies || [];

  const accPct = cal.estimated_accuracy ? (cal.estimated_accuracy * 100).toFixed(1) : "N/A";

  return (
    <div className="space-y-6">
      {/* 刷新控制 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          <h2 className="text-lg font-bold">质量管理仪表盘</h2>
          {d.timestamp && (
            <span className="text-[10px] text-muted-foreground">
              (更新于 {new Date(d.timestamp).toLocaleTimeString("zh-CN")})
            </span>
          )}
        </div>
        <button
          onClick={() => { setAutoRefresh(!autoRefresh); if (!autoRefresh) request("/api/system/quality/dashboard"); }}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            autoRefresh ? "bg-green-100 text-green-700 dark:bg-green-950/30 dark:text-green-400" : "bg-muted text-muted-foreground hover:bg-accent"
          }`}
        >
          <RefreshCw className={`h-3.5 w-3.5 ${autoRefresh ? "animate-spin" : ""}`} />
          {autoRefresh ? "自动刷新中" : "每10秒刷新"}
        </button>
      </div>

      {/* 异常警报 */}
      {anomalies.length > 0 && (
        <div className="p-4 rounded-lg border border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-950/20">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="h-4 w-4 text-red-600" />
            <span className="text-sm font-bold text-red-700 dark:text-red-400">检测到 {anomalies.length} 个质量异常</span>
          </div>
          <ul className="space-y-1">
            {anomalies.map((a: string, i: number) => (
              <li key={i} className="text-xs text-red-600 dark:text-red-400 flex items-start gap-1.5">
                <span className="mt-0.5">•</span> {a}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 概览面板 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard icon={BarChart3} label="总分析次数" value={overview.total_analyses || 0} color="blue" />
        <StatCard icon={Target} label="平均可信度" value={(overview.credibility_avg || 50).toFixed(1)} color="green"
          sub={`高风险 ${overview.high_risk_pct || 0}%`} />
        <StatCard icon={TrendingUp} label="引擎准确率" value={`${accPct}%`} color={cal.estimated_accuracy > 0.8 ? "green" : "yellow"}
          sub={cal.data_quality === "adequate" ? "足够数据" : "数据积累中"} />
        <StatCard icon={AlertTriangle} label="争议率" value={`${overview.dispute_rate || 0}%`}
          color={(overview.dispute_rate || 0) > 15 ? "red" : (overview.dispute_rate || 0) > 8 ? "yellow" : "green"}
          sub="用户反馈质疑" />
      </div>

      {/* 引擎健康 + 校准 */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* 引擎模块权重 */}
        <div className="p-5 rounded-xl border bg-card">
          <h3 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Cpu className="h-4 w-4 text-primary" /> 引擎模块健康度
          </h3>
          <div className="space-y-3">
            {engine.modules?.map((mod: EngineModule, i: number) => (
              <div key={i} className="flex items-center gap-3">
                <div className="flex-1">
                  <div className="flex justify-between text-xs mb-1">
                    <span>{mod.name}</span>
                    <span className={`font-mono font-bold ${mod.healthy ? "text-green-600" : "text-yellow-600"}`}>
                      w={mod.weight.toFixed(2)}
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${mod.healthy ? "bg-green-500" : mod.trend === "dampened" ? "bg-yellow-500" : "bg-orange-500"}`}
                      style={{ width: `${Math.min(100, mod.weight * 67)}%` }}
                    />
                  </div>
                  {!mod.healthy && (
                    <span className="text-[9px] text-yellow-600 mt-0.5 block">
                      {mod.trend === "dampened" ? "↓ 权重被降低（可能因高误报）" : "↑ 权重被增大（可能因高漏报）"}
                    </span>
                  )}
                </div>
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${mod.healthy ? "bg-green-500" : "bg-yellow-500 animate-pulse"}`} />
              </div>
            ))}
          </div>
        </div>

        {/* 校准状态 */}
        <div className="p-5 rounded-xl border bg-card">
          <h3 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Target className="h-4 w-4 text-primary" /> 评分校准状态
          </h3>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="p-3 rounded-lg bg-muted/30 text-center">
                <div className="text-lg font-bold">{cal.tracked_events || 0}</div>
                <div className="text-[10px] text-muted-foreground">跟踪事件数</div>
              </div>
              <div className="p-3 rounded-lg bg-muted/30 text-center">
                <div className="text-lg font-bold">{cal.avg_score || 50}</div>
                <div className="text-[10px] text-muted-foreground">平均评分</div>
              </div>
              <div className="p-3 rounded-lg bg-muted/30 text-center">
                <div className="text-lg font-bold">{cal.score_std || 15}</div>
                <div className="text-[10px] text-muted-foreground">评分标准差</div>
              </div>
              <div className="p-3 rounded-lg bg-muted/30 text-center">
                <div className="text-lg font-bold">{cal.dispute_rate || 0}%</div>
                <div className="text-[10px] text-muted-foreground">争议率</div>
              </div>
            </div>
            <div className="space-y-2">
              <ScoreBar value={cal.estimated_accuracy * 100 || 0} max={100} label="估计准确率" color="green" />
            </div>
          </div>
        </div>
      </div>

      {/* 反馈趋势 + 误判模式 */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="p-5 rounded-xl border bg-card">
          <h3 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Brain className="h-4 w-4 text-primary" /> 反馈趋势
          </h3>
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="p-3 rounded-lg bg-green-50 dark:bg-green-950/20 text-center">
              <div className="text-xl font-bold text-green-700 dark:text-green-400">{feedback.helpful_count || 0}</div>
              <div className="text-[10px] text-green-600 dark:text-green-400">有帮助</div>
            </div>
            <div className="p-3 rounded-lg bg-yellow-50 dark:bg-yellow-950/20 text-center">
              <div className="text-xl font-bold text-yellow-700 dark:text-yellow-400">{feedback.not_helpful_count || 0}</div>
              <div className="text-[10px] text-yellow-600 dark:text-yellow-400">无帮助</div>
            </div>
            <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/20 text-center">
              <div className="text-xl font-bold text-red-700 dark:text-red-400">{feedback.inaccurate_count || 0}</div>
              <div className="text-[10px] text-red-600 dark:text-red-400">不准确</div>
            </div>
          </div>
          <div className="space-y-2 text-xs text-muted-foreground">
            <div className="flex justify-between">
              <span>总反馈</span>
              <span className="font-mono font-bold">{feedback.total_feedback || 0}</span>
            </div>
            <div className="flex justify-between">
              <span>申诉总数 / 待审核</span>
              <span className="font-mono">{feedback.total_appeals || 0} / {feedback.pending_appeals || 0}</span>
            </div>
            <div className="flex justify-between">
              <span>申诉采纳率</span>
              <span className="font-mono">{feedback.appeal_acceptance_rate || 0}%</span>
            </div>
          </div>
        </div>

        <div className="p-5 rounded-xl border bg-card">
          <h3 className="text-sm font-bold mb-4 flex items-center gap-2">
            <Zap className="h-4 w-4 text-primary" /> 误判模式 & 去重
          </h3>
          <div className="grid grid-cols-2 gap-3 mb-3">
            <div className="p-3 rounded-lg bg-muted/30 text-center">
              <div className={`text-xl font-bold ${mis.active_patterns > 0 ? "text-yellow-600" : "text-green-600"}`}>
                {mis.active_patterns || 0}
              </div>
              <div className="text-[10px] text-muted-foreground">活跃误判模式</div>
            </div>
            <div className="p-3 rounded-lg bg-muted/30 text-center">
              <div className="text-xl font-bold">{knowledge.entries_needing_review || 0}</div>
              <div className="text-[10px] text-muted-foreground">知识待审核</div>
            </div>
          </div>
          <div className="space-y-2 text-xs text-muted-foreground">
            <div className="flex justify-between">
              <span>去重精确条目</span>
              <span className="font-mono">{dedup.exact_entries || 0}</span>
            </div>
            <div className="flex justify-between">
              <span>SimHash 桶</span>
              <span className="font-mono">{dedup.simhash_buckets || 0}</span>
            </div>
            <div className="flex justify-between">
              <span>条目上限</span>
              <span className="font-mono">{dedup.max_entries || "N/A"}</span>
            </div>
          </div>
          {mis.patterns && mis.patterns.length > 0 && (
            <div className="mt-3 pt-3 border-t">
              <p className="text-[10px] font-semibold text-muted-foreground mb-1.5">最近发现的误判模式:</p>
              {mis.patterns.map((p: any, i: number) => (
                <div key={i} className="text-[10px] text-yellow-700 dark:text-yellow-400 flex justify-between py-0.5">
                  <span>{p.pattern_name || p.id}</span>
                  <span className="font-mono">{p.frequency || 0}次</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 反馈闭环状态 */}
      {d.feedback_loop && d.feedback_loop.status !== "unavailable" && (
        <div className="p-5 rounded-xl border bg-card">
          <h3 className="text-sm font-bold mb-4 flex items-center gap-2">
            <RefreshCw className="h-4 w-4 text-primary" /> 反馈闭环状态
          </h3>
          <div className="grid grid-cols-3 gap-3">
            <div className="text-center">
              <div className="text-lg font-bold">{d.feedback_loop.feedback_pipeline?.total_feedbacks_processed || 0}</div>
              <div className="text-[10px] text-muted-foreground">已处理反馈</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold">{d.feedback_loop.feedback_pipeline?.next_calibration_in || 0}</div>
              <div className="text-[10px] text-muted-foreground">距下次校准</div>
            </div>
            <div className="text-center">
              <div className="text-lg font-bold">{d.feedback_loop.rule_versions?.total_changes || 0}</div>
              <div className="text-[10px] text-muted-foreground">规则变更记录</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
