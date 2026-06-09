/**
 * TruthTrace 浏览器扩展 — 后台脚本
 *
 * 功能:
 * 1. 右键菜单 → "用 TruthTrace 分析此链接"
 * 2. 接受 popup/content script 的分析请求
 * 3. 调用本地 TruthTrace API
 */

const API_BASE = "http://localhost:8000/api";

// =============================================================================
// 右键菜单
// =============================================================================

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "truthtrace-analyze-link",
    title: "🔍 用 TruthTrace 溯源分析",
    contexts: ["link", "page", "selection"],
  });

  chrome.contextMenus.create({
    id: "truthtrace-analyze-page",
    title: "📋 分析当前页面可信度",
    contexts: ["page"],
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  let url = "";

  if (info.menuItemId === "truthtrace-analyze-link") {
    url = info.linkUrl || info.pageUrl;
  } else if (info.menuItemId === "truthtrace-analyze-page") {
    url = info.pageUrl;
  }

  if (url) {
    analyzeAndShowResult(url, tab.id);
  }
});

// =============================================================================
// 消息处理
// =============================================================================

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "ANALYZE_URL") {
    analyzeUrl(message.url).then(sendResponse);
    return true;  // 异步响应
  }

  if (message.type === "ANALYZE_CURRENT_PAGE") {
    const url = message.url || (sender.tab && sender.tab.url);
    if (url) {
      analyzeUrl(url).then(sendResponse);
      return true;
    }
  }

  if (message.type === "GET_CREDIBILITY_OVERLAY") {
    const url = message.url || (sender.tab && sender.tab.url);
    if (url) {
      quickCheck(url).then(sendResponse);
      return true;
    }
  }
});

// =============================================================================
// API 调用
// =============================================================================

async function analyzeUrl(url) {
  try {
    // 1. 先搜索是否已有分析结果
    const searchResp = await fetch(`${API_BASE}/search/url?url=${encodeURIComponent(url)}`);
    const searchData = await searchResp.json();

    if (searchData.found && !searchData.is_new) {
      // 已有结果 — 获取完整分析
      const eventId = searchData.event?.id || searchData.events?.[0]?.id;
      if (eventId) {
        const analysisResp = await fetch(`${API_BASE}/events/${eventId}/analysis`);
        const analysisData = await analysisResp.json();
        return {
          status: "found",
          eventId,
          analysis: analysisData.analysis || null,
          message: "找到已有分析结果",
          summary: searchData.event || searchData.events?.[0],
        };
      }
      return { status: "found", message: "找到已有分析结果", summary: searchData };
    }

    // 2. 提交新的溯源任务
    const traceResp = await fetch(`${API_BASE}/trace`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, deep_trace: false }),
    });
    const traceData = await traceResp.json();

    // 3. 轮询结果
    const taskId = traceData.task_id;
    let attempts = 0;
    while (attempts < 60) {
      await sleep(1000);
      const taskResp = await fetch(`${API_BASE}/tasks/${taskId}`);
      const taskData = await taskResp.json();

      if (taskData.status === "SUCCESS") {
        const eventId = taskData.result?.event_id;
        return {
          status: "analyzed",
          taskId,
          eventId,
          engineAnalysis: taskData.result?.engine_analysis || null,
          result: taskData.result,
        };
      }
      if (taskData.status === "FAILURE") {
        return { status: "error", error: taskData.error || "分析失败" };
      }
      attempts++;
    }
    return { status: "timeout", message: "分析超时，请在 TruthTrace 网页中查看结果" };

  } catch (err) {
    return { status: "error", error: `无法连接到 TruthTrace 服务 (${API_BASE})。请确保服务已启动。` };
  }
}

async function quickCheck(url) {
  try {
    const resp = await fetch(`${API_BASE}/search/url?url=${encodeURIComponent(url)}`);
    const data = await resp.json();
    return {
      found: data.found,
      credibility_score: data.event?.credibility_score || (data.events?.[0]?.credibility_score),
      verdict: data.event?.rumor_verdict || null,
      message: data.message,
    };
  } catch {
    return { found: false, error: "无法连接" };
  }
}

// =============================================================================
// 弹窗展示分析结果
// =============================================================================

async function analyzeAndShowResult(url, tabId) {
  const result = await analyzeUrl(url);

  // 存储结果并打开 popup
  await chrome.storage.local.set({ lastAnalysis: result });

  // 向 content script 发送结果
  if (tabId) {
    chrome.tabs.sendMessage(tabId, {
      type: "SHOW_CREDIBILITY_OVERLAY",
      data: result,
    }).catch(() => {});  // content script 可能未加载
  }
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
