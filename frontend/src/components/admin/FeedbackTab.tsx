import { useEffect } from "react";
import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useApi } from "../../hooks/useApi";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

export function FeedbackTab() {
  const { data: fbData, loading, request } = useApi<any>();
  const { data: appealData, request: reqAppeal } = useApi<any>();
  useEffect(() => {
    request("/api/admin/feedback/queue");
    reqAppeal("/api/admin/appeal/queue");
  }, []);

  const feedbacks = fbData?.feedbacks || [];
  const appeals = appealData?.appeals || [];

  const reviewAppeal = async (id: string, action: string) => {
    await fetch(`${API_BASE}/api/admin/appeal/${id}/review?action=${action}`, { method: "POST" });
    reqAppeal("/api/admin/appeal/queue");
  };

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold mb-3">用户反馈 ({feedbacks.length})</h3>
        <div className="space-y-2">
          {feedbacks.slice(0, 15).map((f: any, i: number) => (
            <div key={i} className={`p-3 rounded-lg border text-xs ${f.rating === "inaccurate" ? "border-red-200 bg-red-50/30 dark:bg-red-950/10" : "bg-card"}`}>
              <div className="flex items-center justify-between">
                <div>
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${f.rating === "helpful" ? "bg-green-100 text-green-700" : f.rating === "inaccurate" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"}`}>{f.rating}</span>
                  <span className="ml-2">{f.username}</span>
                  <span className="ml-2 text-muted-foreground">{f.comment?.slice(0, 60)}</span>
                </div>
                <Link to={`/events/${f.event_id}`} className="text-primary hover:underline">查看</Link>
              </div>
            </div>
          ))}
          {feedbacks.length === 0 && !loading && <p className="text-center py-8 text-muted-foreground text-sm">暂无反馈</p>}
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-3">申诉审核 ({appeals.length})</h3>
        <div className="space-y-2">
          {appeals.slice(0, 15).map((a: any) => (
            <div key={a.id} className={`p-4 rounded-lg border ${a.status === "pending" ? "border-orange-300 bg-orange-50/30 dark:bg-orange-950/10" : "bg-card"}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-sm">{a.username} 的申诉</span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${a.status === "pending" ? "bg-orange-100 text-orange-700" : a.status === "accepted" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"}`}>{a.status}</span>
              </div>
              <p className="text-xs mb-1"><strong>事件:</strong> {a.event_title?.slice(0, 50)} (引擎判定: {a.engine_verdict}, 用户认为: {a.correct_verdict || "未指定"})</p>
              <p className="text-xs text-muted-foreground mb-2">{a.reason?.slice(0, 150)}</p>
              {a.status === "pending" && (
                <div className="flex gap-2">
                  <button onClick={() => reviewAppeal(a.id, "accepted")} className="px-3 py-1 rounded bg-green-500 text-white text-xs hover:bg-green-600">接受</button>
                  <button onClick={() => reviewAppeal(a.id, "rejected")} className="px-3 py-1 rounded bg-red-500 text-white text-xs hover:bg-red-600">驳回</button>
                </div>
              )}
            </div>
          ))}
          {appeals.length === 0 && !loading && <p className="text-center py-8 text-muted-foreground text-sm">暂无申诉</p>}
        </div>
      </div>
    </div>
  );
}
