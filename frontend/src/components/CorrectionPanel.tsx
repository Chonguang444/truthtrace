import { useState, useEffect, useRef } from "react";
import { MessageSquare, Copy, Check, Shield, Heart, BookOpen, Zap, FileText } from "lucide-react";

interface CorrectionData {
  short_correction: string;
  full_correction: string;
  truth_sandwich: string;
  fact_wedge: string;
  tone_used: string;
  error_type: string;
  source_count: number;
  audience: string;
  alternative_narrative: string;
  cognitive_bridge: string;
}

interface CorrectionPanelProps {
  data: CorrectionData | null;
  compact?: boolean;
}

const TONES = [
  { id: "neutral", label: "中立", icon: FileText, desc: "客观陈述事实" },
  { id: "authoritative", label: "权威", icon: Shield, desc: "机构正式辟谣" },
  { id: "empathetic", label: "共情", icon: Heart, desc: "理解受众关切" },
  { id: "educational", label: "科普", icon: BookOpen, desc: "教育启迪方式" },
  { id: "concise", label: "简洁", icon: Zap, desc: "社交媒体适用" },
];

const TONE_COLORS: Record<string, string> = {
  neutral: "border-blue-200 bg-blue-50 dark:bg-blue-950/20 text-blue-700",
  authoritative: "border-red-200 bg-red-50 dark:bg-red-950/20 text-red-700",
  empathetic: "border-green-200 bg-green-50 dark:bg-green-950/20 text-green-700",
  educational: "border-purple-200 bg-purple-50 dark:bg-purple-950/20 text-purple-700",
  concise: "border-amber-200 bg-amber-50 dark:bg-amber-950/20 text-amber-700",
};

export function CorrectionPanel({ data, compact = false }: CorrectionPanelProps) {
  const [activeTone, setActiveTone] = useState(data?.tone_used || "neutral");
  const [copied, setCopied] = useState<string | null>(null);

  if (!data || !data.short_correction) {
    return (
      <div className="rounded-lg border p-4 text-sm">
        <div className="flex items-center gap-2 text-muted-foreground">
          <MessageSquare size={16} />
          <span>辟谣叙事待生成</span>
        </div>
      </div>
    );
  }

const API_BASE = (import.meta as any).env?.VITE_API_BASE_URL || "";
  const viewed = useRef(false);

  const track = (action: string, extra: Record<string,string> = {}) => {
    try {
      fetch(API_BASE + "/api/analytics/debunk-" + action, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_id: "",
          tone: activeTone,
          format: "full",
          ...extra,
        }),
      });
    } catch {}
  };

  // Track view on first render
  useEffect(() => {
    if (!viewed.current) { viewed.current = true; track("view"); }
  }, []);

  const handleCopy = async (text: string, label: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(label);
      setTimeout(() => setCopied(null), 2000);
    track("copy", { section: label });
    } catch {}
  };

  // Show the current tone's content
  // For the full correction, we show what was generated
  const sections = [
    { key: "short", label: "一句话辟谣", content: data.short_correction },
    { key: "wedge", label: "事实楔子", content: data.fact_wedge },
    { key: "narrative", label: "替代叙事", content: data.alternative_narrative },
    { key: "bridge", label: "认知桥梁", content: data.cognitive_bridge },
    { key: "sandwich", label: "真相三明治", content: data.truth_sandwich },
  ].filter((s) => s.content);

  if (compact) {
    return (
      <div className="rounded-lg border p-3 text-xs space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <MessageSquare size={14} />
            <span className="font-semibold">辟谣建议</span>
          </div>
          <span className="text-[10px] text-muted-foreground">{data.error_type}</span>
        </div>
        <p className="text-muted-foreground line-clamp-2">{data.short_correction}</p>
        <div className="flex gap-1">
          {TONES.slice(0, 3).map((t) => (
            <span key={t.id} className={`px-1.5 py-0.5 rounded text-[10px] border ${activeTone === t.id ? TONE_COLORS[t.id] : "text-muted-foreground"}`}>
              {t.label}
            </span>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border bg-card overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b bg-muted/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare size={18} className="text-primary" />
            <h3 className="font-semibold text-sm">叙事替代辟谣</h3>
          </div>
          <span className="text-xs font-mono opacity-60">引擎 #22</span>
        </div>
        <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
          <span className="px-2 py-0.5 rounded-full bg-background border">
            {data.error_type === "fabricated" ? "编造信息" :
             data.error_type === "misleading" ? "存在误导" :
             data.error_type === "missing_context" ? "缺少背景" :
             data.error_type === "distorted" ? "信息曲解" :
             data.error_type === "unverifiable" ? "无法验证" : data.error_type}
          </span>
          {data.source_count > 0 && (
            <span>{data.source_count}个可验证来源</span>
          )}
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Tone Selector */}
        <div>
          <h4 className="text-xs font-semibold mb-2 text-muted-foreground">辟谣语气</h4>
          <div className="flex flex-wrap gap-1.5">
            {TONES.map((tone) => (
              <button
                key={tone.id}
                onClick={() => setActiveTone(tone.id)}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border text-xs transition-all ${
                  activeTone === tone.id
                    ? TONE_COLORS[tone.id] + " border-current shadow-sm"
                    : "text-muted-foreground hover:bg-muted border-transparent"
                }`}
                title={tone.desc}
              >
                <tone.icon size={12} />
                {tone.label}
              </button>
            ))}
          </div>
          {/* Tone description */}
          <p className="mt-1.5 text-[10px] text-muted-foreground">
            {activeTone === "neutral" && "适用于任何场景的客观辟谣。基于事实，不带情绪。适合转发给任何人。"}
            {activeTone === "authoritative" && "以权威机构口吻发布。适合官方账号、政府/媒体辟谣。语气坚定，引用权威信源。"}
            {activeTone === "empathetic" && "先理解受众的关切和担忧，再提供正确信息。适合面对焦虑、愤怒的受众。建立信任而非对立。"}
            {activeTone === "educational" && "以教育者的角度帮助受众理解背后的原理。适合科普、深度解析。不只说'假的'，更说'为什么'。"}
            {activeTone === "concise" && "极简直接，适合微博/朋友圈/短视频标题。一句话击穿虚假叙事的核心。"}
          </p>
        </div>

        {/* Content sections */}
        <div className="space-y-3">
          {sections.map((section) => (
            <div key={section.key} className="rounded-lg border overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2 bg-muted/30">
                <span className="text-xs font-semibold">{section.label}</span>
                <button
                  onClick={() => handleCopy(section.content, section.key)}
                  className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors"
                >
                  {copied === section.key ? (
                    <>
                      <Check size={12} className="text-green-500" />
                      已复制
                    </>
                  ) : (
                    <>
                      <Copy size={12} />
                      复制
                    </>
                  )}
                </button>
              </div>
              <div className="p-3">
                {/* Truth Sandwich gets special rendering */}
                {section.key === "sandwich" ? (
                  <div className="space-y-2 text-xs">
                    {section.content.split("\n\n").map((part, i) => {
                      const isFact = part.startsWith("【事实】");
                      const isWarning = part.startsWith("【注意】");
                      const isVerify = part.startsWith("【核实】");
                      return (
                        <div
                          key={i}
                          className={`p-2 rounded-md ${
                            isFact ? "bg-green-50 dark:bg-green-950/20 border-l-2 border-green-400" :
                            isWarning ? "bg-red-50 dark:bg-red-950/20 border-l-2 border-red-400" :
                            isVerify ? "bg-blue-50 dark:bg-blue-950/20 border-l-2 border-blue-400" :
                            "bg-muted/20"
                          }`}
                        >
                          {part}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-xs leading-relaxed text-muted-foreground whitespace-pre-line">
                    {section.content}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Full correction text */}
        {data.full_correction && (
          <div className="rounded-lg border overflow-hidden">
            <div className="flex items-center justify-between px-3 py-2 bg-muted/30">
              <span className="text-xs font-semibold">完整辟谣文本</span>
              <button
                onClick={() => handleCopy(data.full_correction, "full")}
                className="flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors"
              >
                {copied === "full" ? (
                  <>
                    <Check size={12} className="text-green-500" />
                    已复制
                  </>
                ) : (
                  <>
                    <Copy size={12} />
                    复制全文
                  </>
                )}
              </button>
            </div>
            <pre className="p-3 text-xs leading-relaxed whitespace-pre-wrap font-sans text-muted-foreground max-h-[400px] overflow-y-auto">
              {data.full_correction}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
