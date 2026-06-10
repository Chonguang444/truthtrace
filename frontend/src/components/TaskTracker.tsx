import { useEffect, useState, useRef, useCallback } from "react";
import { Loader2, CheckCircle2, XCircle, Clock, ArrowRight, Wifi, WifiOff } from "lucide-react";
import { Link } from "react-router-dom";
import { formatRelativeTime } from "../lib/utils";
import { useWebSocket } from "../hooks/useWebSocket";

interface TaskTrackerProps {
  taskId: string;
  onComplete?: (result: any) => void;
}

interface TaskState {
  status: string;
  progress?: string;
  result?: any;
  error?: string;
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

const PROGRESS_STEPS = [
  "解析 URL 跳转链...",
  "爬取目标页面",
  "NLP 事件提取...",
  "实体识别...",
  "内容指纹计算...",
  "搜索相关引用和传播链...",
  "识别原始/权威来源...",
  "保存溯源结果到数据库...",
  "生成辟谣报告...",
];

export function TaskTracker({ taskId, onComplete }: TaskTrackerProps) {
  const [task, setTask] = useState<TaskState | null>(null);
  const [pollCount, setPollCount] = useState(0);
  const completedRef = useRef(false);

  // --- WebSocket for live progress ---
  const wsTaskProgress = useCallback(
    (tid: string, progress: string, status: string) => {
      if (tid !== taskId) return;
      setTask((prev) => ({ ...prev, progress, status }));
      if (status === "SUCCESS" || status === "FAILURE") {
        // Fetch full result via REST
        fetch(`${API_BASE}/api/tasks/${taskId}`)
          .then((r) => r.json())
          .then((data) => {
            setTask(data);
            if (data.status === "SUCCESS" && !completedRef.current) {
              completedRef.current = true;
              onComplete?.(data.result);
            }
          })
          .catch(() => {});
      }
    },
    [taskId, onComplete]
  );

  const { connected, subscribe } = useWebSocket({
    onTaskProgress: wsTaskProgress,
  });

  useEffect(() => {
    if (taskId) subscribe(`task:${taskId}`);
  }, [taskId, subscribe]);

  // --- Polling fallback (every 3s) ---
  useEffect(() => {
    if (!taskId) return;

    let timer: ReturnType<typeof setInterval>;

    const poll = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/tasks/${taskId}`);
        if (!res.ok) return;
        const data = await res.json();
        setTask(data);
        setPollCount((c) => c + 1);

        if (data.status === "SUCCESS" || data.status === "FAILURE") {
          clearInterval(timer);
          if (data.status === "SUCCESS" && !completedRef.current) {
            completedRef.current = true;
            onComplete?.(data.result);
          }
        }
      } catch {
        // retry next interval
      }
    };

    // Initial poll
    poll();
    timer = setInterval(poll, 3000);

    return () => clearInterval(timer);
  }, [taskId, onComplete]);

  if (!task) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground p-4">
        <Loader2 className="h-4 w-4 animate-spin" />
        正在连接任务...
      </div>
    );
  }

  const currentStepIndex = PROGRESS_STEPS.findIndex(
    (s) => task.progress && s.startsWith(task.progress.slice(0, 10))
  );

  const isRunning = task.status !== "SUCCESS" && task.status !== "FAILURE";
  const isDone = task.status === "SUCCESS";
  const isFailed = task.status === "FAILURE";

  // Real progress: use the more accurate of WebSocket status or poll step
  const progressPct = isDone
    ? 100
    : currentStepIndex >= 0
    ? ((currentStepIndex + 1) / PROGRESS_STEPS.length) * 100
    : pollCount > 0
    ? Math.min(pollCount * 2, 90)
    : 2;

  return (
    <div className="p-5 rounded-xl border bg-card shadow-sm">
      {/* Status Header */}
      <div className="flex items-center gap-3 mb-4">
        {isRunning && (
          <div className="h-10 w-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
            <Loader2 className="h-5 w-5 text-blue-600 dark:text-blue-400 animate-spin" />
          </div>
        )}
        {isDone && (
          <div className="h-10 w-10 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
            <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
          </div>
        )}
        {isFailed && (
          <div className="h-10 w-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
            <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-sm">
            {isRunning && "正在追溯分析..."}
            {isDone && "追溯完成"}
            {isFailed && "追溯失败"}
          </h3>
          <p className="text-xs text-muted-foreground flex items-center gap-1.5">
            <span className="truncate">任务: {taskId.slice(0, 12)}...</span>
            {isRunning && (
              <span className="flex items-center gap-1">
                {connected ? (
                  <span title="WebSocket 已连接"><Wifi className="h-3 w-3 text-green-500" /></span>
                ) : (
                  <span title="使用轮询模式"><WifiOff className="h-3 w-3 text-muted-foreground" /></span>
                )}
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Progress Bar */}
      {isRunning && (
        <div className="mb-4">
          <div className="flex justify-between text-xs text-muted-foreground mb-1">
            <span className="truncate">{task.progress || "初始化..."}</span>
            <span className="flex-shrink-0">
              {currentStepIndex >= 0
                ? `步骤 ${currentStepIndex + 1}/${PROGRESS_STEPS.length}`
                : ""}
            </span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-700 ease-out"
              style={{ width: `${progressPct}%` }}
            />
          </div>

          {/* Step indicators */}
          <div className="mt-3 space-y-1">
            {PROGRESS_STEPS.map((step, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <div
                  className={`h-1.5 w-1.5 rounded-full flex-shrink-0 ${
                    i < currentStepIndex
                      ? "bg-green-500"
                      : i === currentStepIndex
                      ? "bg-blue-500 animate-pulse"
                      : "bg-muted-foreground/20"
                  }`}
                />
                <span
                  className={
                    i <= currentStepIndex
                      ? "text-foreground"
                      : "text-muted-foreground/40"
                  }
                >
                  {step}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Done */}
      {isDone && task.result && (
        <div className="space-y-2 mb-4">
          <div className="p-3 rounded-lg bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800">
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-muted-foreground">发现来源: </span>
                <span className="font-semibold">{task.result.sources_found}</span>
              </div>
              <div>
                <span className="text-muted-foreground">原始来源: </span>
                <span className="font-semibold">
                  {task.result.original_sources?.length || 0}
                </span>
              </div>
              {task.result.rumor_analysis && (
                <>
                  <div>
                    <span className="text-muted-foreground">辟谣判定: </span>
                    <span className="font-semibold">
                      {task.result.rumor_analysis.verdict === "false"
                        ? "🚨 虚假信息"
                        : task.result.rumor_analysis.verdict === "misleading"
                        ? "⚠️ 误导性"
                        : "📋 待验证"}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground">可信度: </span>
                    <span className="font-semibold">
                      {task.result.rumor_analysis.credibility_score}/100
                    </span>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Engine Analysis Summary */}
          {task.result.engine_analysis && (
            <div className={`p-3 rounded-lg border text-xs ${
              (task.result.engine_analysis.credibility_score || 50) >= 60
                ? "bg-green-50 dark:bg-green-950/30 border-green-200 dark:border-green-800"
                : (task.result.engine_analysis.credibility_score || 50) >= 40
                ? "bg-yellow-50 dark:bg-yellow-950/30 border-yellow-200 dark:border-yellow-800"
                : "bg-red-50 dark:bg-red-950/30 border-red-200 dark:border-red-800"
            }`}>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-base">{
                  (task.result.engine_analysis.credibility_score || 50) >= 60 ? "🛡️" :
                  (task.result.engine_analysis.credibility_score || 50) >= 40 ? "⚠️" : "🚨"
                }</span>
                <span className="font-semibold">推理引擎分析完成</span>
                <span className="text-[10px] text-muted-foreground">10 维度深度分析</span>
              </div>
              <div className="grid grid-cols-3 gap-1.5 mb-2">
                <div>可信度: <strong>{task.result.engine_analysis.credibility_score}/100</strong></div>
                <div>判定: <strong>{task.result.engine_analysis.verdict}</strong></div>
                <div>置信度: <strong>{task.result.engine_analysis.confidence}</strong></div>
              </div>
              <div className="flex flex-wrap gap-1">
                {(task.result.engine_analysis.distortion_analysis?.matches?.length || 0) > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-red-100 dark:bg-red-900/30 text-[10px]">
                    失真 {(task.result.engine_analysis.distortion_analysis?.matches?.length || 0)}处
                  </span>
                )}
                {(task.result.engine_analysis.fallacy_analysis?.fallacy_count || 0) > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-yellow-100 dark:bg-yellow-900/30 text-[10px]">
                    谬误 {(task.result.engine_analysis.fallacy_analysis?.fallacy_count || 0)}处
                  </span>
                )}
                {(task.result.engine_analysis.statistical_analysis?.matches?.length || 0) > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-orange-100 dark:bg-orange-900/30 text-[10px]">
                    统计滥用 {(task.result.engine_analysis.statistical_analysis?.matches?.length || 0)}处
                  </span>
                )}
              </div>
            </div>
          )}

          {task.result.event_id && (
            <Link
              to={`/events/${task.result.event_id}`}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              查看事件详情 <ArrowRight className="h-4 w-4" />
            </Link>
          )}
        </div>
      )}

      {/* Failed */}
      {isFailed && (
        <div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 mb-4">
          <p className="text-sm text-red-700 dark:text-red-400">
            {task.error || "未知错误，请重试"}
          </p>
        </div>
      )}

      {/* Time estimate */}
      {isRunning && (
        <p className="text-xs text-muted-foreground flex items-center gap-1">
          <Clock className="h-3 w-3" />
          预计耗时 15-60 秒，请耐心等待...
        </p>
      )}
    </div>
  );
}
