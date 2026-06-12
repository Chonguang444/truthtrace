/**
 * IFCN Compliance Panel — Shows IFCN rating, export options, and compliance status
 *
 * Integrates with backend ifcn_compliance.py and claimreview_export.py
 */
import { useState } from "react";
import {
  Award, CheckCircle, Download, Copy, ExternalLink,
  FileJson, FileText, Share2, Shield, Info, ChevronDown, ChevronUp,
} from "lucide-react";

interface IFCNReviewData {
  ifcn_rating?: string;
  claimreview_jsonld?: Record<string, unknown>;
  ifcn_feed?: Record<string, unknown>;
  generated_at?: string;
}

interface Props {
  ifcnReview?: IFCNReviewData | null;
  eventId?: string;
  credibilityScore?: number;
  verdict?: string;
}

const IFCN_RATING_INFO: Record<string, { color: string; bg: string; label: string; desc: string }> = {
  "True": { color: "#16a34a", bg: "#dcfce7", label: "真实", desc: "主张准确，有充分证据支持" },
  "Mostly True": { color: "#65a30d", bg: "#ecfccb", label: "基本真实", desc: "主张基本准确，但需要补充说明" },
  "Misleading": { color: "#ca8a04", bg: "#fef9c3", label: "误导性", desc: "主张部分真实但被歪曲或脱离语境" },
  "Mostly False": { color: "#ea580c", bg: "#fff7ed", label: "基本虚假", desc: "主张大部分不准确" },
  "False": { color: "#dc2626", bg: "#fef2f2", label: "虚假", desc: "主张完全不准确" },
  "Unverifiable": { color: "#6b7280", bg: "#f3f4f6", label: "无法验证", desc: "现有证据不足以判定真伪" },
};

export function IFCNCompliancePanel({ ifcnReview, eventId, credibilityScore, verdict }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState("");

  if (!ifcnReview?.ifcn_rating && !verdict) return null;

  const rating = ifcnReview?.ifcn_rating || "Unverifiable";
  const info = IFCN_RATING_INFO[rating] || IFCN_RATING_INFO["Unverifiable"];

  const handleCopy = (content: string, label: string) => {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(label);
      setTimeout(() => setCopied(""), 2000);
    });
  };

  const jsonldStr = ifcnReview?.claimreview_jsonld
    ? JSON.stringify(ifcnReview.claimreview_jsonld, null, 2)
    : "";

  const feedStr = ifcnReview?.ifcn_feed
    ? JSON.stringify(ifcnReview.ifcn_feed, null, 2)
    : "";

  // Build ClaimReview URL for Google Fact Check Tools
  const googleFCSearchUrl = eventId
    ? `https://factchecktools.googleapis.com/v1alpha1/claims:search?query=${encodeURIComponent(eventId)}`
    : "";

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-muted/30 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <Award className="h-5 w-5 text-amber-500" />
          <div className="text-left">
            <h3 className="text-sm font-semibold">IFCN 合规核查报告</h3>
            <p className="text-[11px] text-muted-foreground">
              International Fact-Checking Network 标准格式
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className="px-2 py-0.5 rounded-full text-[10px] font-bold"
            style={{ backgroundColor: info.bg, color: info.color }}
          >
            {info.label}
          </span>
          {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t">
          {/* Rating details */}
          <div className="grid grid-cols-3 gap-2 pt-3">
            <div className="p-2 rounded-lg bg-muted/30 text-center">
              <div className="text-[10px] text-muted-foreground mb-0.5">IFCN 评级</div>
              <div className="text-sm font-bold" style={{ color: info.color }}>{info.label}</div>
            </div>
            <div className="p-2 rounded-lg bg-muted/30 text-center">
              <div className="text-[10px] text-muted-foreground mb-0.5">可信度</div>
              <div className="text-sm font-bold">{(credibilityScore || 50).toFixed(0)}/100</div>
            </div>
            <div className="p-2 rounded-lg bg-muted/30 text-center">
              <div className="text-[10px] text-muted-foreground mb-0.5">状态</div>
              <div className="text-sm font-bold text-green-600 flex items-center justify-center gap-1">
                <CheckCircle className="h-3 w-3" /> 合规
              </div>
            </div>
          </div>

          <p className="text-xs text-muted-foreground">{info.desc}</p>

          {/* Export buttons */}
          <div className="space-y-1.5">
            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">导出格式</p>
            <div className="grid grid-cols-2 gap-1.5">
              <button
                onClick={() => handleCopy(jsonldStr, "JSON-LD")}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border text-xs font-medium hover:bg-accent transition-colors"
              >
                <FileJson className="h-3.5 w-3.5" />
                {copied === "JSON-LD" ? "已复制!" : "ClaimReview JSON-LD"}
              </button>
              <button
                onClick={() => handleCopy(feedStr, "Feed")}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg border text-xs font-medium hover:bg-accent transition-colors"
              >
                <FileText className="h-3.5 w-3.5" />
                {copied === "Feed" ? "已复制!" : "IFCN Feed 条目"}
              </button>
            </div>
          </div>

          {/* External links */}
          <div className="space-y-1">
            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">外部提交</p>
            <a
              href={googleFCSearchUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg border text-xs font-medium hover:bg-accent transition-colors text-blue-600"
            >
              <ExternalLink className="h-3.5 w-3.5" />
              Google Fact Check Tools
            </a>
            <a
              href="https://ifcncodeofprinciples.poynter.org/application"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg border text-xs font-medium hover:bg-accent transition-colors text-blue-600"
            >
              <Shield className="h-3.5 w-3.5" />
              IFCN 认证申请
            </a>
          </div>

          {/* Compliance checklist */}
          <div className="space-y-1.5">
            <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">合规检查清单</p>
            {[
              { label: "非匿名审查者", ok: true },
              { label: "证据来源可查证", ok: true },
              { label: "方法论透明", ok: true },
              { label: "Schema.org ClaimReview", ok: !!jsonldStr },
              { label: "IFCN Feed 格式", ok: !!feedStr },
            ].map((item) => (
              <div key={item.label} className="flex items-center gap-2 text-xs">
                <CheckCircle className={`h-3 w-3 ${item.ok ? "text-green-500" : "text-muted-foreground/30"}`} />
                <span className={item.ok ? "" : "text-muted-foreground"}>{item.label}</span>
              </div>
            ))}
          </div>

          {/* Generated time */}
          {ifcnReview?.generated_at && (
            <p className="text-[10px] text-muted-foreground text-right">
              生成于 {new Date(ifcnReview.generated_at).toLocaleString()}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
