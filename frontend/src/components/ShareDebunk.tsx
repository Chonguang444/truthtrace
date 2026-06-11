import { useState } from "react";
import { Share2, Copy, Check, MessageCircle, Send, Link2 } from "lucide-react";

interface ShareDebunkProps {
  /** Short debunk text (≤280 chars ideal for Twitter/Weibo) */
  text: string;
  /** URL to the full report */
  reportUrl?: string;
  /** Hashtags (without # prefix) */
  hashtags?: string[];
  /** For WeChat: title shown in card */
  title?: string;
}

const PLATFORMS = [
  {
    id: "weibo",
    label: "微博",
    icon: "📢",
    color: "bg-red-500 hover:bg-red-600",
    buildUrl: (text: string, url: string, hashtags: string[]) =>
      `https://service.weibo.com/share/share.php?title=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}&pic=&searchPic=false`,
  },
  {
    id: "twitter",
    label: "Twitter/X",
    icon: "🐦",
    color: "bg-gray-800 hover:bg-black",
    buildUrl: (text: string, url: string, hashtags: string[]) =>
      `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`,
  },
  {
    id: "wechat",
    label: "微信",
    icon: "💬",
    color: "bg-green-500 hover:bg-green-600",
    // WeChat can't share via URL — use copy + open
    buildUrl: () => "#wechat-share",
  },
  {
    id: "copy",
    label: "复制",
    icon: "📋",
    color: "bg-blue-500 hover:bg-blue-600",
    buildUrl: () => "#copy",
  },
];

export function ShareDebunk({
  text,
  reportUrl = "",
  hashtags = [],
  title = "",
}: ShareDebunkProps) {
  const [copied, setCopied] = useState(false);
  const [showQR, setShowQR] = useState(false);

  const shareText = hashtags.length > 0
    ? `${text} ${hashtags.map((h) => `#${h}`).join(" ")}`
    : text;

  const shortText = shareText.slice(0, 280);

  const handleShare = (platformId: string, buildUrl: (t: string, u: string, h: string[]) => string) => {
    if (platformId === "wechat") {
      setShowQR(true);
      return;
    }
    if (platformId === "copy") {
      navigator.clipboard.writeText(`${shortText}\n${reportUrl}`).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
      return;
    }
    const url = buildUrl(shortText, reportUrl, hashtags);
    if (url && !url.startsWith("#")) {
      window.open(url, "_blank", "width=600,height=400");
    }
  };

  // For WeChat: show copy-then-open instructions since WeChat can't be opened via URL
  const handleWeChatCopy = () => {
    navigator.clipboard.writeText(`${shortText}\n${reportUrl}`).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      setShowQR(false);
    });
  };

  return (
    <div className="relative">
      {/* Share buttons */}
      <div className="flex flex-wrap gap-2">
        {PLATFORMS.map((p) => (
          <button
            key={p.id}
            onClick={() => handleShare(p.id, p.buildUrl)}
            className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-white text-xs font-medium transition-colors ${p.color}`}
          >
            <span>{p.icon}</span>
            {p.label}
          </button>
        ))}

        {/* Copy feedback */}
        {copied && (
          <span className="inline-flex items-center gap-1 px-2 py-2 text-xs text-green-600 font-medium">
            <Check size={12} />
            已复制，可直接粘贴分享
          </span>
        )}
      </div>

      {/* WeChat overlay */}
      {showQR && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowQR(false)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-2xl p-6 max-w-sm mx-4" onClick={(e) => e.stopPropagation()}>
            <h4 className="font-semibold mb-3">分享到微信</h4>
            <div className="bg-gray-100 dark:bg-gray-700 rounded-lg p-4 mb-4 text-center">
              <p className="text-xs text-muted-foreground mb-2">微信不支持直接跳转</p>
              <div className="w-32 h-32 mx-auto bg-white rounded-lg flex items-center justify-center border">
                <Link2 size={32} className="text-green-500" />
              </div>
              <p className="text-[10px] text-muted-foreground mt-2">复制内容后打开微信粘贴</p>
            </div>
            <div className="space-y-2">
              <p className="text-xs font-medium line-clamp-3 bg-muted/30 p-2 rounded">{shortText}</p>
              <button
                onClick={handleWeChatCopy}
                className="w-full py-2.5 rounded-lg bg-green-500 text-white text-sm font-medium flex items-center justify-center gap-2"
              >
                {copied ? <Check size={16} /> : <Copy size={16} />}
                {copied ? "已复制" : "复制内容"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Card preview — show what will be shared */}
      {text && (
        <div className="mt-3 p-3 rounded-lg border bg-muted/10 text-xs space-y-2">
          <p className="font-medium text-muted-foreground">分享预览</p>
          <div className="p-2 rounded bg-white dark:bg-gray-900 border">
            <p className="leading-relaxed line-clamp-4">{shortText}</p>
            {reportUrl && (
              <p className="text-blue-500 text-[10px] mt-1 truncate">{reportUrl}</p>
            )}
          </div>
          {hashtags.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {hashtags.map((h) => (
                <span key={h} className="text-[10px] text-blue-500">#{h}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Quick share button — compact version for inline use */
export function ShareButton({ text, reportUrl, hashtags }: { text: string; reportUrl?: string; hashtags?: string[] }) {
  const [open, setOpen] = useState(false);

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium hover:bg-accent transition-colors"
      >
        <Share2 size={14} />
        分享
      </button>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium">分享辟谣</span>
        <button
          onClick={() => setOpen(false)}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          收起
        </button>
      </div>
      <ShareDebunk text={text} reportUrl={reportUrl} hashtags={hashtags} />
    </div>
  );
}
