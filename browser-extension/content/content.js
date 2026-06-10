/**
 * TruthTrace 2.0 内容脚本 — 全平台支持
 *
 * 功能:
 * 1. 实时可信度叠加层 (任何页面)
 * 2. 转发前警告 (社交媒体)
 * 3. 链接预扫描 (悬停检测)
 * 4. 划词工具提示 (选中文字显示快捷分析)
 */

let overlayEl = null;
let tooltipEl = null;
let scannedUrls = {};
let pageAnalyzed = false;

// =============================================================================
// 初始化
// =============================================================================

(function init() {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();

function start() {
  // 自动检测当前页面
  autoAnalyzePage();

  // 设置转发守卫
  setupShareGuard();

  // 设置链接预扫描
  setupLinkPreScan();

  // 设置划词工具提示
  setupSelectionTooltip();

  // 监听消息
  chrome.runtime.onMessage.addListener(handleMessage);
}

// =============================================================================
// 自动页面分析
// =============================================================================

async function autoAnalyzePage() {
  if (pageAnalyzed) return;
  const url = window.location.href;

  // 跳过内部页面
  if (url.startsWith("chrome://") || url.startsWith("about:")) return;

  // 从缓存读取
  chrome.storage.local.get("scanCache", (data) => {
    const cache = data.scanCache || {};
    const cached = cache[url];
    if (cached && Date.now() - cached.timestamp < 3600000) {
      // 缓存命中
      if (cached.score && cached.score < 50) {
        showAutoWarning(cached);
      }
      return;
    }
  });

  // 后台检查
  chrome.runtime.sendMessage(
    { type: "GET_CREDIBILITY_OVERLAY", url },
    (response) => {
      if (response && response.found && response.credibility_score < 50) {
        showAutoWarning(response);

        // 更新缓存
        chrome.storage.local.get("scanCache", (data) => {
          const cache = data.scanCache || {};
          cache[url] = { score: response.credibility_score, verdict: response.verdict, timestamp: Date.now() };
          chrome.storage.local.set({ scanCache: cache });
        });
      }
    }
  );

  pageAnalyzed = true;
}

function showAutoWarning(data) {
  const score = data.credibility_score || 50;
  const verdict = data.verdict || "";

  const banner = document.createElement("div");
  banner.id = "truthtrace-auto-banner";
  banner.innerHTML = `
    <div style="
      position:fixed; top:0; left:0; right:0; z-index:99998;
      background:${score < 30 ? '#fef2f2' : '#fefce8'};
      border-bottom:2px solid ${score < 30 ? '#fecaca' : '#fef08a'};
      padding:8px 20px; display:flex; align-items:center; justify-content:center;
      font-family:system-ui,sans-serif; font-size:13px;
      box-shadow:0 2px 8px rgba(0,0,0,0.06);
    ">
      <span style="margin-right:12px">${score < 30 ? '🔴' : '🟡'}</span>
      <span style="font-weight:600;color:#1a1a2e">
        此页面信息可信度评分: <span style="color:${score < 30 ? '#dc2626' : '#ca8a04'};font-size:18px">${score}/100</span>
        ${verdict ? '· 判定: ' + verdict : ''}
      </span>
      <span style="margin-left:12px;font-size:11px;color:#6b7280">
        由 TruthTrace AI 自动检测 ·
        <a href="http://localhost:5173/search?q=${encodeURIComponent(window.location.href)}" target="_blank" style="color:#2563eb">查看详情</a>
      </span>
      <button onclick="document.getElementById('truthtrace-auto-banner').remove()" style="margin-left:16px;background:none;border:none;cursor:pointer;color:#6b7280;font-size:16px">&times;</button>
    </div>
  `;
  document.body.prepend(banner);
}

// =============================================================================
// 消息处理
// =============================================================================

function handleMessage(message, sender, sendResponse) {
  if (message.type === "SHOW_CREDIBILITY_OVERLAY") {
    showOverlay(message.data);
  }
  if (message.type === "SHOW_SELECTION_RESULT") {
    showSelectionResult(message.data);
  }
}

// =============================================================================
// 可信度叠加层
// =============================================================================

function showOverlay(data) {
  if (overlayEl) overlayEl.remove();

  const analysis = data.engineAnalysis || data.result?.engine_analysis || {};
  const score = analysis.credibility_score || data.credibility_score || 50;
  const verdict = analysis.verdict || data.engine_verdict || "unknown";

  const scoreColor = score >= 60 ? "#16a34a" : score >= 40 ? "#ca8a04" : "#dc2626";
  const bgColor = score >= 60 ? "#f0fdf4" : score >= 40 ? "#fefce8" : "#fef2f2";
  const borderColor = score >= 60 ? "#bbf7d0" : score >= 40 ? "#fef08a" : "#fecaca";

  const distortions = analysis.distortion_analysis?.matches?.length || 0;
  const fallacies = analysis.fallacy_analysis?.fallacy_count || 0;

  overlayEl = document.createElement("div");
  overlayEl.id = "truthtrace-overlay";
  overlayEl.innerHTML = `
    <div style="
      position:fixed; bottom:20px; right:20px; z-index:99999;
      background:${bgColor}; border:2px solid ${borderColor};
      border-radius:12px; padding:16px; max-width:320px;
      font-family:system-ui,sans-serif; font-size:13px;
      box-shadow:0 4px 24px rgba(0,0,0,0.12); transition:all 0.3s;
    ">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <span style="font-weight:700;color:#1a1a2e">🛡️ TruthTrace 2.0</span>
        <button id="truthtrace-close-btn" style="background:none;border:none;cursor:pointer;color:#6b7280;font-size:18px">&times;</button>
      </div>
      <div style="font-size:28px;font-weight:800;color:${scoreColor};margin-bottom:4px">${score}/100</div>
      <div style="font-size:12px;color:#6b7280;margin-bottom:8px">信息可信度评分 · ${verdict}</div>
      <div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px">
        ${distortions > 0 ? '<span style="background:#fef2f2;color:#dc2626;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:600">⚠ ' + distortions + '处失真</span>' : ''}
        ${fallacies > 0 ? '<span style="background:#fef9c3;color:#ca8a04;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:600">🧠 ' + fallacies + '处谬误</span>' : ''}
        ${score < 40 ? '<span style="background:#fef2f2;color:#dc2626;padding:2px 8px;border-radius:6px;font-size:10px">谨慎转发</span>' : ''}
      </div>
      <div style="display:flex;gap:8px">
        <a href="http://localhost:5173/events/${data.eventId || ''}" target="_blank" style="flex:1;text-align:center;background:#2563eb;color:white;border-radius:8px;padding:6px 12px;font-size:11px;text-decoration:none;font-weight:600">查看完整报告</a>
        <button id="truthtrace-recheck-btn" style="flex:1;background:white;border:1px solid #d1d5db;border-radius:8px;padding:6px 12px;font-size:11px;cursor:pointer;font-weight:500">重新检测</button>
      </div>
    </div>
  `;

  document.body.appendChild(overlayEl);

  document.getElementById("truthtrace-close-btn").onclick = () => { overlayEl.remove(); overlayEl = null; };
  document.getElementById("truthtrace-recheck-btn").onclick = () => {
    overlayEl.remove(); overlayEl = null;
    chrome.runtime.sendMessage({ type: "ANALYZE_CURRENT_PAGE", url: window.location.href });
  };
}

// =============================================================================
// 转发前警告
// =============================================================================

function setupShareGuard() {
  const shareSelectors = [
    '[action-type="feed_list_forward"]',
    '[data-type="repost"]',
    'button[aria-label*="转发"]',
    'button[aria-label*="分享"]',
    'button[aria-label*="Share"]',
    'button[aria-label*="Retweet"]',
    '[role="button"][aria-label*="share" i]',
  ];

  shareSelectors.forEach(selector => {
    document.querySelectorAll(selector).forEach(btn => {
      if (btn.dataset.truthtraceGuarded) return;
      btn.dataset.truthtraceGuarded = "1";
      btn.addEventListener("click", (e) => {
        chrome.storage.local.get("lastAnalysis", (data) => {
          const analysis = data.lastAnalysis?.engineAnalysis || data.lastAnalysis?.result;
          if (analysis && analysis.credibility_score < 40) {
            const warning = confirm(
              "⚠️ TruthTrace 警告\n\n" +
              "该页面信息的可信度评分仅为 " + analysis.credibility_score + "/100。\n" +
              "判定: " + (analysis.verdict || "low_credibility") + "\n\n" +
              "建议核实后再转发。是否仍要转发？"
            );
            if (!warning) {
              e.preventDefault();
              e.stopPropagation();
              e.stopImmediatePropagation();
            }
          }
        });
      }, { capture: true });
    });
  });
}

// =============================================================================
// 链接预扫描
// =============================================================================

function setupLinkPreScan() {
  // 收集页面上的外部链接
  const links = document.querySelectorAll('a[href^="http"]');
  const urls = new Set();
  links.forEach(a => {
    const href = a.href;
    if (href && !href.startsWith(window.location.origin)) {
      urls.add(href);
    }
  });

  // 在空闲时预扫描 (最多20个)
  if (urls.size > 0) {
    const urlArray = Array.from(urls).slice(0, 20);
    if ("requestIdleCallback" in window) {
      requestIdleCallback(() => {
        chrome.runtime.sendMessage(
          { type: "PRE_SCAN_LINKS", urls: urlArray },
          (results) => {
            if (results) {
              scannedUrls = results;
              // 给已知低可信度链接添加视觉标记
              markLowCredibilityLinks();
            }
          }
        );
      });
    }
  }
}

function markLowCredibilityLinks() {
  document.querySelectorAll('a[href^="http"]').forEach(a => {
    const info = scannedUrls[a.href];
    if (info && info.known && info.score < 40) {
      // 添加警告图标
      if (!a.querySelector(".truthtrace-link-warning")) {
        const badge = document.createElement("span");
        badge.className = "truthtrace-link-warning";
        badge.style.cssText = "display:inline-block;background:#fef2f2;color:#dc2626;padding:0 4px;border-radius:3px;font-size:10px;margin-left:2px;cursor:help";
        badge.textContent = "⚠" + info.score;
        badge.title = "TruthTrace 可信度: " + info.score + "/100 · " + (info.verdict || "");
        a.appendChild(badge);
      }
    }
  });
}

// =============================================================================
// 划词工具提示
// =============================================================================

function setupSelectionTooltip() {
  document.addEventListener("mouseup", (e) => {
    const selection = window.getSelection();
    const text = selection?.toString().trim();

    // 移除旧工具提示
    if (tooltipEl) {
      tooltipEl.remove();
      tooltipEl = null;
    }

    if (text && text.length > 20) {
      // 显示快捷操作按钮
      tooltipEl = document.createElement("div");
      tooltipEl.id = "truthtrace-selection-tooltip";
      tooltipEl.style.cssText = `
        position:fixed; z-index:100000;
        background:white; border:1px solid #e5e7eb;
        border-radius:8px; padding:6px; box-shadow:0 4px 16px rgba(0,0,0,0.1);
        font-family:system-ui,sans-serif; display:flex; gap:4px;
      `;

      const x = Math.min(e.clientX + 10, window.innerWidth - 200);
      const y = Math.min(e.clientY + 10, window.innerHeight - 40);
      tooltipEl.style.left = x + "px";
      tooltipEl.style.top = y + "px";

      tooltipEl.innerHTML = `
        <button id="tt-analyze-btn" style="background:#2563eb;color:white;border:none;border-radius:6px;padding:4px 10px;font-size:11px;cursor:pointer;font-weight:600;white-space:nowrap">
          🔬 分析选中文字
        </button>
        <button id="tt-dismiss-btn" style="background:#f3f4f6;border:none;border-radius:6px;padding:4px 10px;font-size:11px;cursor:pointer;white-space:nowrap">
          ✕
        </button>
      `;

      document.body.appendChild(tooltipEl);

      document.getElementById("tt-analyze-btn").onclick = () => {
        chrome.runtime.sendMessage(
          { type: "ANALYZE_SELECTION", text: text.slice(0, 2000) },
          (response) => {
            if (response) {
              showSelectionResult(response);
            }
          }
        );
        tooltipEl.remove();
        tooltipEl = null;
      };

      document.getElementById("tt-dismiss-btn").onclick = () => {
        tooltipEl.remove();
        tooltipEl = null;
      };

      // 3秒后自动消失
      setTimeout(() => {
        if (tooltipEl) { tooltipEl.remove(); tooltipEl = null; }
      }, 3000);
    }
  });
}

function showSelectionResult(data) {
  // 移除旧结果弹窗
  const old = document.getElementById("truthtrace-selection-result");
  if (old) old.remove();

  if (data.status === "fallback" || data.status === "error") {
    // 简单提示
    const banner = document.createElement("div");
    banner.id = "truthtrace-selection-result";
    banner.style.cssText = `
      position:fixed; top:10px; right:10px; z-index:99999;
      background:#fef2f2; border:1px solid #fecaca; border-radius:8px;
      padding:10px 16px; font-family:system-ui; font-size:12px;
    `;
    banner.textContent = data.message || data.error || "分析不可用";
    document.body.appendChild(banner);
    setTimeout(() => banner.remove(), 3000);
    return;
  }

  const result = data.result || {};
  const score = result.credibility_score || 50;

  const el = document.createElement("div");
  el.id = "truthtrace-selection-result";
  el.style.cssText = `
    position:fixed; top:20px; right:20px; z-index:99999;
    background:white; border:2px solid ${score < 40 ? '#fecaca' : '#bbf7d0'};
    border-radius:12px; padding:16px; max-width:350px;
    font-family:system-ui,sans-serif; font-size:13px;
    box-shadow:0 8px 32px rgba(0,0,0,0.15);
  `;

  const distortions = result.distortion_analysis?.matches || [];
  const fallacies = result.fallacy_analysis?.matches || [];

  el.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <span style="font-weight:700">🔬 划词分析结果</span>
      <button onclick="this.parentElement.parentElement.remove()" style="background:none;border:none;font-size:18px;cursor:pointer;color:#6b7280">&times;</button>
    </div>
    <div style="font-size:24px;font-weight:800;color:${score < 40 ? '#dc2626' : '#16a34a'};margin-bottom:4px">${score}/100</div>
    <div style="font-size:11px;color:#6b7280;margin-bottom:8px">可信度评分 · 判定: ${result.verdict || 'unknown'}</div>
    ${distortions.length > 0 ? '<div style="margin-bottom:4px"><span style="background:#fef2f2;color:#dc2626;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:600">⚠ ' + distortions.length + '处信息失真</span></div>' : ''}
    ${fallacies.length > 0 ? '<div style="margin-bottom:4px"><span style="background:#fef9c3;color:#ca8a04;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:600">🧠 ' + fallacies.length + '处逻辑谬误</span></div>' : ''}
    <div style="margin-top:8px;padding:8px;background:#f9fafb;border-radius:8px;font-size:11px;color:#6b7280">
      "${data.text_analyzed || (result.text_analyzed || '').slice(0, 150)}"
    </div>
    <div style="margin-top:4px;font-size:10px;color:#9ca3af">${result.disclaimer || 'TruthTrace 自动分析 · 仅供参考'}</div>
  `;

  document.body.appendChild(el);
}

// =============================================================================
// DOM变化监听 (SPA支持)
// =============================================================================

const observer = new MutationObserver(() => {
  setupShareGuard();
  markLowCredibilityLinks();
});
observer.observe(document.body, { childList: true, subtree: true });
