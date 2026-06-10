import { useState, useEffect } from "react";
import { BookOpen, Trophy, Star, ArrowRight, CheckCircle, XCircle, Lightbulb, Loader2 } from "lucide-react";
import { useApi } from "../hooks/useApi";
import { useAuth } from "../contexts/AuthContext";

const TABS = [
  { id: "challenge", label: "每日挑战", icon: Trophy },
  { id: "cases", label: "案例图书馆", icon: BookOpen },
  { id: "certification", label: "认证考试", icon: Star },
];

export default function LiteracyAcademy() {
  const [tab, setTab] = useState("challenge");
  return (
    <div className="container mx-auto px-4 py-8">
      <div className="flex items-center gap-3 mb-6">
        <BookOpen className="h-7 w-7 text-primary" />
        <div>
          <h1 className="text-2xl font-bold">信息素养学院</h1>
          <p className="text-xs text-muted-foreground">学会识别信息操纵，成为批判性思维者</p>
        </div>
      </div>
      <div className="flex flex-wrap gap-1 mb-6 border-b pb-2 overflow-x-auto">
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-t-lg text-xs font-medium transition-colors whitespace-nowrap ${tab === t.id ? "bg-primary/10 text-primary border-b-2 border-primary" : "text-muted-foreground hover:text-foreground"}`}>
            <t.icon className="h-3.5 w-3.5" />{t.label}
          </button>
        ))}
      </div>
      <div className="min-h-[500px]">
        {tab === "challenge" && <ChallengeTab />}
        {tab === "cases" && <CaseLibraryTab />}
        {tab === "certification" && <CertificationTab />}
      </div>
    </div>
  );
}

// =============================================================================
// Tab 1: Daily Challenge
// =============================================================================

function ChallengeTab() {
  const { isAuthenticated } = useAuth();
  const { data: questionsData, loading, request } = useApi<any>();
  const { data: streakData, request: streakReq } = useApi<any>();
  const { data: tipData, request: tipReq } = useApi<any>();
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);
  const [result, setResult] = useState<any>(null);

  useEffect(() => {
    request("/api/literacy/challenges");
    streakReq("/api/literacy/challenges/streak");
    tipReq("/api/literacy/challenges/daily-tip");
  }, []);

  const handleSubmit = async () => {
    const answerList = Object.entries(answers).map(([question_id, selected_type]) => ({ question_id, selected_type }));
    const res = await fetch((import.meta.env.VITE_API_BASE_URL || "") + "/api/literacy/challenges/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(localStorage.getItem("truthtrace-token") ? { Authorization: `Bearer ${localStorage.getItem("truthtrace-token")}` } : {}) },
      body: JSON.stringify({ challenge_id: questionsData?.challenge_id || "", answers: answerList }),
      credentials: "include",
    });
    const data = await res.json();
    setResult(data);
    setSubmitted(true);
  };

  if (loading) return <div className="flex items-center gap-2 p-8 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />加载挑战中...</div>;

  const questions = questionsData?.questions || [];
  const streak = streakData || {};

  return (
    <div className="space-y-6">
      {/* Streak + Tip bar */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="p-4 rounded-xl border bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-950/20 dark:to-orange-950/20">
          <div className="flex items-center gap-2 mb-2"><Trophy className="h-4 w-4 text-amber-500" /><span className="text-sm font-semibold">连续挑战</span></div>
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold text-amber-600">{streak.current_streak || 0}</span>
            <span className="text-sm text-muted-foreground">天 · 最高 {streak.longest_streak || 0} 天</span>
          </div>
          {streak.current_streak >= 2 && <p className="text-xs text-amber-600 mt-1">连击奖励: +{streak.streak_bonus_xp} 经验值</p>}
        </div>
        <div className="p-4 rounded-xl border bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/20 dark:to-indigo-950/20">
          <div className="flex items-center gap-2 mb-2"><Lightbulb className="h-4 w-4 text-blue-500" /><span className="text-sm font-semibold">今日提示</span></div>
          <p className="text-sm">{tipData?.tip || "学会识别信息操纵，做聪明的信息消费者。"}</p>
        </div>
      </div>

      {/* Quiz */}
      {!submitted ? (
        <div className="space-y-4">
          {questions.map((q: any, i: number) => (
            <div key={q.id} className="p-4 rounded-xl border bg-card">
              <p className="text-sm font-semibold mb-3"><span className="text-muted-foreground mr-1">Q{i + 1}.</span>{q.text}</p>
              <div className="space-y-2">
                {q.options.map((opt: string) => (
                  <label key={opt} className={`flex items-center gap-2 p-2.5 rounded-lg border cursor-pointer transition-colors ${answers[q.id] === opt ? "border-primary bg-primary/5" : "hover:bg-accent"}`}>
                    <input type="radio" name={q.id} value={opt} checked={answers[q.id] === opt} onChange={() => setAnswers({ ...answers, [q.id]: opt })} className="text-primary" />
                    <span className="text-sm">{opt}</span>
                  </label>
                ))}
              </div>
            </div>
          ))}
          <button onClick={handleSubmit} disabled={Object.keys(answers).length < questions.length || !isAuthenticated}
            className="w-full py-3 rounded-xl bg-primary text-primary-foreground font-semibold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
            {isAuthenticated ? "提交答案" : "请先登录后提交"}
          </button>
        </div>
      ) : result && (
        <div className="space-y-4">
          {/* Score */}
          <div className="text-center p-6 rounded-xl border bg-card">
            <div className="inline-flex items-center justify-center h-24 w-24 rounded-full border-4 border-primary mb-4">
              <span className="text-3xl font-bold">{result.percentage}%</span>
            </div>
            <p className="text-lg font-semibold">{result.message}</p>
            <p className="text-sm text-muted-foreground">得分 {result.score}/{result.total} · 获得 {result.earned_xp} XP</p>
            <button onClick={() => { setSubmitted(false); setAnswers({}); setResult(null); }} className="mt-3 px-4 py-2 rounded-lg bg-accent text-sm hover:bg-accent/80">再做一次</button>
          </div>
          {/* Per-question results */}
          {result.results?.map((r: any) => (
            <div key={r.question_id} className={`p-4 rounded-xl border ${r.correct ? "border-green-200 bg-green-50/30 dark:bg-green-950/10" : "border-red-200 bg-red-50/30 dark:bg-red-950/10"}`}>
              <div className="flex items-start gap-2">
                {r.correct ? <CheckCircle className="h-5 w-5 text-green-500 mt-0.5" /> : <XCircle className="h-5 w-5 text-red-500 mt-0.5" />}
                <div className="flex-1">
                  {!r.correct && <p className="text-xs font-semibold text-red-600 mb-1">你的答案: {r.your_answer} · 正确答案: {r.correct_type}</p>}
                  <p className="text-xs text-muted-foreground">{r.explanation}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// Tab 2: Case Library
// =============================================================================

function CaseLibraryTab() {
  const { data, loading, request } = useApi<any>();
  const [category, setCategory] = useState<string>("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    const params = category ? `?category=${category}` : "";
    request(`/api/literacy/cases${params}`);
  }, [category]);

  if (loading) return <div className="flex items-center gap-2 p-8"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>;

  const cases = data?.items || [];

  return (
    <div>
      <div className="flex gap-2 mb-4 flex-wrap">
        {["", "fallacy", "distortion", "narrative", "statistical"].map(cat => (
          <button key={cat} onClick={() => setCategory(cat)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium ${category === cat ? "bg-primary text-primary-foreground" : "bg-muted hover:bg-muted/80"}`}>
            {cat === "" ? "全部" : cat === "fallacy" ? "逻辑谬误" : cat === "distortion" ? "信息失真" : cat === "narrative" ? "叙事框架" : "统计滥用"}
          </button>
        ))}
      </div>
      <div className="space-y-3">
        {cases.map((c: any) => (
          <div key={c.id} className="rounded-xl border bg-card overflow-hidden">
            <button onClick={() => setExpandedId(expandedId === c.id ? null : c.id)} className="w-full text-left p-4 hover:bg-accent/50 transition-colors">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-semibold text-sm">{c.title}</p>
                  <p className="text-xs text-muted-foreground mt-1">{c.summary}</p>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                    c.credibility_score < 20 ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"}`}>
                    可信度 {c.credibility_score}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-muted text-[10px]">{c.category}</span>
                </div>
              </div>
            </button>
            {expandedId === c.id && (
              <div className="px-4 pb-4 border-t pt-3">
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">引擎标注分析</p>
                {c.annotated_text.split("\n").map((line: string, i: number) => (
                  <div key={i} className="flex items-start gap-2 mb-2 text-xs">
                    <ArrowRight className="h-3 w-3 text-primary mt-0.5 flex-shrink-0" />
                    <span className="leading-relaxed">{line}</span>
                  </div>
                ))}
                {c.source_url && <p className="text-[10px] text-muted-foreground mt-2">来源: {c.source_url}</p>}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// Tab 3: Certification
// =============================================================================

function CertificationTab() {
  const { isAuthenticated } = useAuth();
  const { data: status, loading, request } = useApi<any>();
  const [examStarted, setExamStarted] = useState(false);
  const [examAnswers, setExamAnswers] = useState<Record<string, string>>({});
  const [examResult, setExamResult] = useState<any>(null);
  const [examQuestions, setExamQuestions] = useState<any[]>([]);

  useEffect(() => { request("/api/literacy/certification/status"); }, []);

  const startExam = async () => {
    // The exam questions come from the certification submit endpoint
    // We generate them locally for the user to answer
    const res = await fetch((import.meta.env.VITE_API_BASE_URL || "") + "/api/literacy/challenges");
    const challengeData = await res.json();
    // Certification uses 20 questions - we display them all
    setExamQuestions(challengeData?.questions || []);
    setExamStarted(true);
  };

  const submitExam = async () => {
    const answerList = Object.entries(examAnswers).map(([question_id, selected_type]) => ({ question_id, selected_type }));
    const res = await fetch((import.meta.env.VITE_API_BASE_URL || "") + "/api/literacy/certification/exam", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers: answerList }),
      credentials: "include",
    });
    const data = await res.json();
    setExamResult(data);
  };

  if (loading) return <div className="flex items-center gap-2 p-8"><Loader2 className="h-4 w-4 animate-spin" />加载中...</div>;

  // Already certified
  if (status?.certification_passed) {
    return (
      <div className="max-w-md mx-auto text-center p-8 rounded-xl border bg-gradient-to-b from-amber-50 to-yellow-50 dark:from-amber-950/20 dark:to-yellow-950/20">
        <Trophy className="h-16 w-16 text-amber-500 mx-auto mb-4" />
        <h2 className="text-xl font-bold mb-2">批判思维大师</h2>
        <p className="text-sm text-muted-foreground mb-4">{status.badge_description || "认证通过！"}</p>
        <div className="inline-block px-4 py-2 rounded-full bg-amber-100 dark:bg-amber-900/30 text-amber-700 font-semibold text-sm mb-2">
          认证通过 · {status.completed_at?.slice(0, 10)}
        </div>
        <p className="text-xs text-muted-foreground mt-4">分享你的认证: {window.location.origin}/badge</p>
      </div>
    );
  }

  // Exam in progress
  if (examStarted && !examResult) {
    return (
      <div className="space-y-4">
        <div className="p-4 rounded-xl border bg-card">
          <h3 className="font-semibold mb-2">认证考试 (20题)</h3>
          <p className="text-xs text-muted-foreground">每题选择一个答案。通过线: 16/20 (80%)</p>
        </div>
        {examQuestions.slice(0, 20).map((q: any, i: number) => (
          <div key={q.id} className="p-4 rounded-xl border bg-card">
            <p className="text-sm font-semibold mb-3"><span className="text-muted-foreground mr-1">{i + 1}.</span>{q.text}</p>
            <div className="space-y-2">
              {q.options?.map((opt: string) => (
                <label key={opt} className={`flex items-center gap-2 p-2 rounded-lg border cursor-pointer ${examAnswers[q.id] === opt ? "border-primary bg-primary/5" : "hover:bg-accent"}`}>
                  <input type="radio" name={`exam-${q.id}`} value={opt} checked={examAnswers[q.id] === opt} onChange={() => setExamAnswers({ ...examAnswers, [q.id]: opt })} className="text-primary" />
                  <span className="text-sm">{opt}</span>
                </label>
              ))}
            </div>
          </div>
        ))}
        <button onClick={submitExam} disabled={Object.keys(examAnswers).length < 20}
          className="w-full py-3 rounded-xl bg-primary text-primary-foreground font-semibold hover:bg-primary/90 disabled:opacity-50 transition-colors">
          提交认证考试
        </button>
      </div>
    );
  }

  // Exam result
  if (examResult) {
    return (
      <div className="max-w-md mx-auto text-center p-8 rounded-xl border bg-card">
        <div className={`inline-flex items-center justify-center h-24 w-24 rounded-full border-4 mb-4 ${examResult.passed ? "border-green-500" : "border-red-300"}`}>
          <span className="text-3xl font-bold">{examResult.percentage}%</span>
        </div>
        <h2 className="text-xl font-bold mb-2">{examResult.passed ? "恭喜通过!" : "差一点!"}</h2>
        <p className="text-sm text-muted-foreground mb-4">{examResult.message}</p>
        <p className="text-sm">得分: {examResult.score}/{examResult.total}</p>
        {examResult.passed && <p className="text-lg font-bold text-amber-600 mt-2">🏅 {examResult.badge_name}</p>}
        {!examResult.passed && <button onClick={() => { setExamStarted(false); setExamResult(null); setExamAnswers({}); }} className="mt-4 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm">重新准备</button>}
      </div>
    );
  }

  // Eligibility check
  const eligible = status?.eligible_for_exam;

  return (
    <div className="max-w-md mx-auto space-y-4">
      <div className="p-6 rounded-xl border bg-card">
        <h3 className="font-semibold mb-3">认证进度</h3>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between"><span>完成挑战</span><span className="font-semibold">{status?.challenges_completed || 0} / {status?.requirement?.challenges_needed || 3}</span></div>
          <div className="flex justify-between"><span>平均得分</span><span className="font-semibold">{status?.average_score || 0} / {status?.requirement?.min_avg_score || 3.5}</span></div>
          <div className="flex justify-between"><span>考试通过线</span><span className="font-semibold">{status?.requirement?.exam_pass_threshold || 16} / 20</span></div>
        </div>
        <div className="mt-4 h-2 rounded-full bg-muted overflow-hidden">
          <div className="h-full bg-primary rounded-full transition-all" style={{ width: `${Math.min((status?.challenges_completed || 0) / 3 * 100, 100)}%` }} />
        </div>
      </div>
      <button onClick={startExam} disabled={!eligible || !isAuthenticated}
        className="w-full py-3 rounded-xl bg-primary text-primary-foreground font-semibold hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
        {!isAuthenticated ? "请先登录" : eligible ? "开始认证考试" : `需要完成 ${status?.requirement?.challenges_needed || 3} 次挑战 (平均 ${status?.requirement?.min_avg_score || 3.5}/5) 才能参加考试`}
      </button>
    </div>
  );
}
