/**
 * TruthTranslate 内容脚本 — 社交媒体可信度浮窗
 *
 * 在支持的平台上注入可信度提示:
 * - 微博: 在帖子旁显示可信度标签
 * - 知乎: 在回答旁显示可信度标签
 * - 微信公众号: 在文章顶部显示可信度提醒
 */

let overlayEl = null;

// =============================================================================
// 消息监听
// =============================================================================

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "SHOW_CREDIBILITY_OVERLAY") {
    showOverlay(message.data);
  }
});

// =============================================================================
// 浮窗显示
// =============================================================================

function showOverlay(data) {
  // 移除旧浮窗
  if (overlayEl) {
    overlayEl.remove();
  }

  const analysis = data.engineAnalysis;
  if (!analysis) return;

  const score = analysis.credibility_score || 50;
  const verdict = analysis.verdict || "unknown";
  const scoreColor = score >= 60 ? "#16a34a" : score >= 40 ? "#ca8a04" : "#dc2626";
  const bgColor = score >= 60 ? "#f0fdf4" : score >= 40 ? "#fefce8" : "#fef2f2";
  const borderColor = score >= 60 ? "#bbf7d0" : score >= 40 ? "#fef08a" : "#fecaca";

  overlayEl = document.createElement("div");
  overlayEl.id = "truthtrace-overlay";
  overlayEl.innerHTML = `
    <div style="
      position:fixed; bottom:20px; right:20px; z-index:99999;
      background:${bgColor}; border:2px solid ${borderColor};
      border-radius:12px; padding:16px; max-width:300px;
      font-family:system-ui,sans-serif; font-size:13px; box-shadow:0 4px 24px rgba(0,0,0,0.12);
    ">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <span style="font-weight:700;color:#1a1a2e">🛡️ TruthTrace</span>
        <button id="truthtrace-close" style="background:none;border:none;cursor:pointer;color:#6b7280;font-size:18px">&times;</button>
      </div>
      <div style="font-size:24px;font-weight:800;color:${scoreColor};margin-bottom:4px">${score}/100</div>
      <div style="font-size:12px;color:#6b7280;margin-bottom:8px">信息可信度评分</div>
      <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px">
        ${(analysis.distortion_analysis?.matches?.length || 0) > 0 ? `<span style="background:#fef2f2;color:#dc2626;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:600">⚠️${analysis.distortion_analysis.matches.length}处失真</span>` : ""}
        ${(analysis.fallacy_analysis?.fallacy_count || 0) > 0 ? `<span style="background:#fef9c3;color:#ca8a04;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:600">🧠${analysis.fallacy_analysis.fallacy_count}处谬误</span>` : ""}
      </div>
      <a href="http://localhost:5173/events/${data.eventId}" target="_blank" style="color:#2563eb;font-size:11px;text-decoration:none">查看完整分析报告 →</a>
    </div>
  `;

  document.body.appendChild(overlayEl);

  // 关闭按钮
  document.getElementById("truthtrace-close").addEventListener("click", () => {
    overlayEl.remove();
    overlayEl = null;
  });
}

// =============================================================================
// 转发前警告 (社交媒体检测)
// =============================================================================

function setupShareGuard() {
  // 检测转发/分享按钮
  const shareSelectors = [
    '[action-type="feed_list_forward"]',  // 微博转发
    '[data-type="repost"]',
    'button[aria-label*="转发"]',
    'button[aria-label*="分享"]',
    'button[aria-label*="Share"]',
    'button[aria-label*="Retweet"]',
  ];

  shareSelectors.forEach(selector => {
    document.querySelectorAll(selector).forEach(btn => {
      if (!btn.dataset.truthtraceGuarded) {
        btn.dataset.truthtraceGuarded = "1";
        btn.addEventListener("click", (e) => {
          // 检查当前页面是否有可信度评分
          chrome.storage.local.get("lastAnalysis", (data) => {
            const analysis = data.lastAnalysis?.engineAnalysis;
            if (analysis && analysis.credibility_score < 40) {
              const warning = confirm(
                `⚠️ TruthTrace 警告\n\n` +
                `该页面信息的可信度评分仅为 ${analysis.credibility_score}/100。\n` +
                `判定: ${analysis.verdict}\n\n` +
                `建议核实后再转发。是否仍要转发？`
              );
              if (!warning) {
                e.preventDefault();
                e.stopPropagation();
              }
            }
          });
        }, { capture: true });
      }
    });
  });
}

// 初始化
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", setupShareGuard);
} else {
  setupShareGuard();
}

// 监听动态加载的内容
const observer = new MutationObserver(() => {
  setupShareGuard();
});
observer.observe(document.body, { childList: true, subtree: true });
