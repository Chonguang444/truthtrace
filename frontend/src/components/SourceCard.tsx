import { ExternalLink, Shield, ThumbsUp, MessageCircle, Repeat } from "lucide-react";
import { formatDate } from "../lib/utils";

interface SourceProps {
  source: {
    id: string;
    url: string;
    platform: string;
    author: string;
    title?: string;
    content?: string;
    published_at?: string;
    is_original?: boolean;
    authority_score: number;
    engagement?: Record<string, number>;
  };
  detailed?: boolean;
}

const PLATFORM_LABELS: Record<string, string> = {
  weibo: "微博",
  zhihu: "知乎",
  wechat: "微信",
  twitter: "Twitter/X",
  reddit: "Reddit",
  news: "新闻媒体",
  general: "网页",
  unknown: "未知",
};

export function SourceCard({ source, detailed }: SourceProps) {
  const authorityLevel =
    source.authority_score >= 70
      ? { label: "高权威", color: "text-green-600 bg-green-100" }
      : source.authority_score >= 40
      ? { label: "中等", color: "text-yellow-600 bg-yellow-100" }
      : { label: "待验证", color: "text-gray-500 bg-gray-100" };

  return (
    <div className={`p-4 rounded-lg border bg-card hover:shadow-sm transition-shadow ${
      source.is_original ? "ring-2 ring-yellow-400 border-yellow-300" : ""
    }`}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="px-2 py-0.5 rounded text-xs font-medium capitalize bg-muted">
              {PLATFORM_LABELS[source.platform] || source.platform}
            </span>
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${authorityLevel.color}`}>
              {authorityLevel.label} ({source.authority_score})
            </span>
            {source.is_original && (
              <span className="px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
                🌟 疑似原始来源
              </span>
            )}
          </div>

          {source.author && (
            <div className="text-sm font-medium flex items-center gap-1">
              <Shield className="h-3 w-3 text-muted-foreground" />
              {source.author}
            </div>
          )}
        </div>

        <a
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex-shrink-0 text-muted-foreground hover:text-primary transition-colors"
          title="打开原始链接"
        >
          <ExternalLink className="h-4 w-4" />
        </a>
      </div>

      {detailed && source.content && (
        <p className="text-sm mb-3 line-clamp-3 text-muted-foreground">
          {source.content}
        </p>
      )}

      {source.title && !detailed && (
        <p className="text-sm font-medium mb-2 truncate">{source.title}</p>
      )}

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{formatDate(source.published_at)}</span>

        {source.engagement && (
          <div className="flex items-center gap-3">
            {source.engagement.likes != null && (
              <span className="flex items-center gap-1">
                <ThumbsUp className="h-3 w-3" /> {source.engagement.likes}
              </span>
            )}
            {source.engagement.reposts != null && (
              <span className="flex items-center gap-1">
                <Repeat className="h-3 w-3" /> {source.engagement.reposts}
              </span>
            )}
            {source.engagement.comments != null && (
              <span className="flex items-center gap-1">
                <MessageCircle className="h-3 w-3" /> {source.engagement.comments}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
