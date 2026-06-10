import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useApi } from "../../hooks/useApi";

export function AnalysisTab() {
  const { data, loading, request } = useApi<any>();
  const [risk, setRisk] = useState("");
  useEffect(() => { request(`/api/admin/analysis/review?limit=30&risk_level=${risk}`); }, [risk]);

  const items = data?.items || [];

  return (
    <div>
      <div className="flex gap-2 mb-4">
        {["", "high", "medium", "low"].map(r => (
          <button key={r} onClick={() => setRisk(r)}
            className={`px-3 py-1 rounded-full text-xs font-medium ${risk === r ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80"}`}>
            {r === "" ? "全部" : r === "high" ? "高风险" : r === "medium" ? "中风险" : "低风险"}
          </button>
        ))}
      </div>
      {loading && <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>}
      <div className="space-y-2">
        {items.map((item: any) => (
          <div key={item.event_id} className={`p-4 rounded-lg border ${item.credibility_score < 30 ? "border-l-4 border-l-red-500 bg-red-50/30 dark:bg-red-950/10" : item.credibility_score < 55 ? "border-l-4 border-l-yellow-500 bg-yellow-50/30 dark:bg-yellow-950/10" : "bg-card"}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-sm truncate">{item.title}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${item.credibility_score < 30 ? "bg-red-100 text-red-700" : item.credibility_score < 55 ? "bg-yellow-100 text-yellow-700" : "bg-green-100 text-green-700"}`}>{item.credibility_score}/100</span>
                  {item.engine_verdict && <span className="text-[10px] text-muted-foreground">{item.engine_verdict}</span>}
                </div>
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {item.distortion_count > 0 && <span className="px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-900/30 text-[10px] text-red-700">失真{item.distortion_count}</span>}
                  {item.fallacy_count > 0 && <span className="px-1.5 py-0.5 rounded bg-yellow-100 dark:bg-yellow-900/30 text-[10px] text-yellow-700">谬误{item.fallacy_count}</span>}
                  {item.narrative_dominant && <span className="px-1.5 py-0.5 rounded bg-purple-100 dark:bg-purple-900/30 text-[10px] text-purple-700">{item.narrative_dominant}</span>}
                  {item.manipulation_score > 30 && <span className="px-1.5 py-0.5 rounded bg-orange-100 dark:bg-orange-900/30 text-[10px] text-orange-700">操纵{item.manipulation_score}</span>}
                  {item.stat_risk > 30 && <span className="px-1.5 py-0.5 rounded bg-blue-100 dark:bg-blue-900/30 text-[10px] text-blue-700">统计{item.stat_risk}</span>}
                </div>
                {item.correction && <p className="text-[10px] text-muted-foreground mt-1.5 truncate">{item.correction}</p>}
              </div>
              <Link to={`/events/${item.event_id}/report`} className="flex-shrink-0 text-xs text-primary hover:underline">详情 →</Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
