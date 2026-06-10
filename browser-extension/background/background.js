/**
 * TruthTrace 2.0 浏览器扩展 — 后台脚本
 *
 * 新增功能:
 * 1. 划词即查 — 选中文字右键 → 即时分析
 * 2. 链接预扫描 — 悬停链接显示可信度
 * 3. 实时叠加层 — 浏览任何页面均可触发
 * 4. 快速分析API — 无需等待完整溯源
 */

const API_BASE = "http://localhost:8000/api";

// =============================================================================
// 安装 & 右键菜单
// =============================================================================

chrome.runtime.onInstalled.addListener(() => {
  // 原有菜单
  chrome.contextMenus.create({
    id: "truthtrace-analyze-link",
    title: "🔍 用 TruthTrace 溯源分析此链接",
    contexts: ["link"],
  });
  chrome.contextMenus.create({
    id: "truthtrace-analyze-page",
    title: "📋 分析当前页面可信度",
    contexts: ["page"],
  });
  // 新: 划词即查
  chrome.contextMenus.create({
    id: "truthtrace-analyze-selection",
    title: "🔬 TruthTrace 分析选中文字",
    contexts: ["selection"],
  });
  // 新: 快速查证
  chrome.contextMenus.create({
    id: "truthtrace-quick-fact",
    title: "⚡ 快速事实核查",
    contexts: ["selection"],
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  const menuId = info.menuItemId;

  if (menuId === "truthtrace-analyze-selection" && info.selectionText) {
    // 划词分析 — 发送选中文字到API
    analyzeSelectedText(info.selectionText, tab.id);
  } else if (menuId === "truthtrace-quick-fact" && info.selectionText) {
    quickFactCheck(info.selectionText, tab.id);
  } else if (menuId === "truthtrace-analyze-link" && info.linkUrl) {
    analyzeUrl(info.linkUrl).then(result => showResult(result, tab.id));
  } else if (menuId === "truthtrace-analyze-page") {
    const url = info.pageUrl;
    if (url) analyzeUrl(url).then(result => showResult(result, tab.id));
  }
});

// =============================================================================
// 消息处理 (扩展版)
// =============================================================================

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.type) {
    case "ANALYZE_URL":
      analyzeUrl(message.url).then(sendResponse);
      return true;

    case "ANALYZE_SELECTION":
      analyzeSelectedText(message.text, sender.tab?.id).then(sendResponse);
      return true;

    case "ANALYZE_CURRENT_PAGE":
      analyzeUrl(message.url || sender.tab?.url).then(sendResponse);
      return true;

    case "GET_CREDIBILITY_OVERLAY":
      quickCheckUrl(message.url || sender.tab?.url).then(sendResponse);
      return true;

    case "QUICK_CHECK_TEXT":
      quickFactCheck(message.text).then(sendResponse);
      return true;

    case "PRE_SCAN_LINKS":
      preScanLinks(message.urls || []).then(sendResponse);
      return true;
  }
});

// =============================================================================
// API 调用
// =============================================================================

async function analyzeUrl(url) {
  try {
    // 先搜索已有结果
    const searchResp = await fetch(`${API_BASE}/search?q=${encodeURIComponent(url)}&limit=1`);
    const searchData = await searchResp.json();

    if (searchData.events?.length > 0) {
      const eventId = searchData.events[0].id;
      const analysisResp = await fetch(`${API_BASE}/events/${eventId}/analysis`);
      const analysisData = await analysisResp.json();
      return {
        status: "found",
        eventId,
        credibility_score: searchData.events[0].credibility_score,
        engine_verdict: searchData.events[0].engine_verdict,
        analysis: analysisData.analysis || null,
        summary: searchData.events[0],
      };
    }

    // 提交溯源
    const traceResp = await fetch(`${API_BASE}/trace`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, deep_trace: false }),
    });
    const traceData = await traceResp.json();
    const taskId = traceData.task_id;

    // 轮询 (最多30秒)
    for (let i = 0; i < 30; i++) {
      await sleep(1000);
      const taskResp = await fetch(`${API_BASE}/tasks/${taskId}`);
      const taskData = await taskResp.json();
      if (taskData.status === "SUCCESS") {
        return {
          status: "analyzed",
          taskId,
          eventId: taskData.result?.event_id,
          engineAnalysis: taskData.result?.engine_analysis || null,
          result: taskData.result,
        };
      }
      if (taskData.status === "FAILURE") {
        return { status: "error", error: taskData.error || "分析失败" };
      }
    }
    return { status: "timeout", message: "分析超时，请在 TruthTrace 网页中查看结果" };

  } catch (err) {
    return { status: "error", error: `无法连接 TruthTrace 服务 (${API_BASE})。请确保服务已启动。` };
  }
}

async function quickCheckUrl(url) {
  try {
    const resp = await fetch(`${API_BASE}/search?q=${encodeURIComponent(url)}&limit=1`);
    const data = await resp.json();
    const event = data.events?.[0];
    return {
      found: data.total > 0,
      credibility_score: event?.credibility_score,
      verdict: event?.engine_verdict,
      has_engine_analysis: event?.has_engine_analysis,
      title: event?.title,
    };
  } catch {
    return { found: false, error: "无法连接" };
  }
}

async function analyzeSelectedText(text, tabId) {
  try {
    const resp = await fetch(`${API_BASE}/v1/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });

    if (!resp.ok) {
      // v1 API 不可用时回退
      return { status: "fallback", message: "V1 API 不可用。请使用 TruthTrace 网页版。" };
    }

    const data = await resp.json();
    return {
      status: "analyzed",
      taskId: data.task_id,
      result: data.result,
      text_analyzed: text.slice(0, 200),
    };
  } catch {
    return { status: "error", error: "API 不可用。请确保 TruthTrace 服务已启动。" };
  }
}

async function quickFactCheck(text) {
  // 快速模式: 5秒超时, 基础文本分析
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    const resp = await fetch(`${API_BASE}/v1/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text.slice(0, 2000) }),
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (resp.ok) {
      const data = await resp.json();
      return { status: "ok", result: data.result };
    }
    return { status: "error", error: "API 返回错误" };
  } catch {
    return { status: "error", error: "请求超时或网络错误" };
  }
}

async function preScanLinks(urls) {
  // 批量预扫描链接 — 返回已知可信度
  const results = {};
  for (const url of urls.slice(0, 10)) {
    try {
      const resp = await fetch(`${API_BASE}/search?q=${encodeURIComponent(url)}&limit=1`);
      const data = await resp.json();
      const event = data.events?.[0];
      results[url] = {
        known: data.total > 0,
        score: event?.credibility_score || null,
        verdict: event?.engine_verdict || null,
      };
    } catch {
      results[url] = { known: false };
    }
  }
  return results;
}

// =============================================================================
// 结果展示
// =============================================================================

async function showResult(result, tabId) {
  // 存储结果到本地
  await chrome.storage.local.set({ lastAnalysis: result });

  // 向 content script 发送叠加层更新
  if (tabId) {
    chrome.tabs.sendMessage(tabId, {
      type: "SHOW_CREDIBILITY_OVERLAY",
      data: result,
    }).catch(() => {});
  }
}

// =============================================================================
// 定时任务: 每小时清理缓存
// =============================================================================

chrome.alarms.create("cleanup-cache", { periodInMinutes: 60 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "cleanup-cache") {
    chrome.storage.local.get("scanCache", (data) => {
      const cache = data.scanCache || {};
      const now = Date.now();
      // 清除1小时前的缓存
      for (const key of Object.keys(cache)) {
        if (now - cache[key].timestamp > 3600000) {
          delete cache[key];
        }
      }
      chrome.storage.local.set({ scanCache: cache });
    });
  }
});

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
