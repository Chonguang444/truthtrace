const API_BASE = "http://localhost:8000/api";
const WEB_BASE = "http://localhost:5173";

// =============================================================================
// Popup Logic
// =============================================================================

const urlInput = document.getElementById("urlInput");
const analyzeBtn = document.getElementById("analyzeBtn");
const analyzePageBtn = document.getElementById("analyzePageBtn");
const resultDiv = document.getElementById("result");

// 自动填充当前页面 URL
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  if (tabs[0] && tabs[0].url && !tabs[0].url.startsWith("chrome://")) {
    urlInput.value = tabs[0].url;
  }
});

// 加载上次分析结果
chrome.storage.local.get("lastAnalysis", (data) => {
  if (data.lastAnalysis && data.lastAnalysis.status === "analyzed") {
    renderResult(data.lastAnalysis);
  }
});

// =============================================================================
// 事件处理
// =============================================================================

analyzeBtn.addEventListener("click", () => {
  const url = urlInput.value.trim();
  if (!url) return;
  analyzeUrl(url);
});

analyzePageBtn.addEventListener("click", () => {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0] && tabs[0].url) {
      urlInput.value = tabs[0].url;
      analyzeUrl(tabs[0].url);
    }
  });
});

urlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    analyzeBtn.click();
  }
});

// =============================================================================
// 核心
// =============================================================================

async function analyzeUrl(url) {
  resultDiv.innerHTML = `<div class="loading"><span class="spinner"></span> 正在分析中...<br><small>10维度引擎分析进行中</small></div>`;
  analyzeBtn.disabled = true;

  chrome.runtime.sendMessage({ type: "ANALYZE_URL", url }, (response) => {
    analyzeBtn.disabled = false;
    if (chrome.runtime.lastError) {
      // 直接调用 API
      directAnalyze(url);
      return;
    }
    if (response) {
      chrome.storage.local.set({ lastAnalysis: response });
      renderResult(response);
    }
  });
}

async function directAnalyze(url) {
  try {
    // 提交溯源
    const traceResp = await fetch(`${API_BASE}/trace`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const traceData = await traceResp.json();

    // 轮询
    let attempts = 0;
    while (attempts < 90) {
      await sleep(1500);
      const taskResp = await fetch(`${API_BASE}/tasks/${traceData.task_id}`);
      const taskData = await taskResp.json();

      if (taskData.status === "SUCCESS") {
        const result = {
          status: "analyzed",
          taskId: traceData.task_id,
          eventId: taskData.result?.event_id,
          engineAnalysis: taskData.result?.engine_analysis || null,
          result: taskData.result,
        };
        chrome.storage.local.set({ lastAnalysis: result });
        renderResult(result);
        return;
      }
      if (taskData.status === "FAILURE") {
        resultDiv.innerHTML = `<div class="error">${taskData.error || "分析失败"}</div>`;
        return;
      }
      attempts++;
    }
    resultDiv.innerHTML = `<div class="error">分析超时。请<a href="${WEB_BASE}" target="_blank">打开 TruthTrace</a>查看完整结果。</div>`;
  } catch (err) {
    resultDiv.innerHTML = `<div class="error">无法连接 TruthTrace 服务。请确保已启动: <code>docker-compose up -d</code></div>`;
  }
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

// =============================================================================
// 渲染结果
// =============================================================================

function renderResult(data) {
  const analysis = data.engineAnalysis;
  const result = data.result;

  if (!analysis) {
    resultDiv.innerHTML = `<div class="result">
      <p style="color:#6b7280;font-size:12px">${data.message || "分析中..."}</p>
      ${data.eventId ? `<a href="${WEB_BASE}/events/${data.eventId}" target="_blank">查看事件详情 →</a>` : ""}
    </div>`;
    return;
  }

  const verdict = analysis.verdict || "unknown";
  const score = analysis.credibility_score || 50;
  const distortionCount = analysis.distortion_analysis?.matches?.length || 0;
  const fallacyCount = analysis.fallacy_analysis?.fallacy_count || 0;
  const statRisk = analysis.statistical_analysis?.risk_score || 0;
  const narrativeScore = analysis.narrative_analysis?.manipulation_score || 0;

  const verdictLabel = {
    false: "🚫 虚假信息", likely_false: "🚫 可能虚假",
    misleading: "⚠️ 误导性", likely_true: "✅ 可能真实",
    true: "✅ 真实信息", unverifiable: "❓ 无法验证",
  };

  const scoreColor = score >= 60 ? "#16a34a" : score >= 40 ? "#ca8a04" : "#dc2626";

  resultDiv.innerHTML = `
    <div class="result">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
        <div>
          <div class="score" style="color:${scoreColor}">${score}<span style="font-size:14px;font-weight:400">/100</span></div>
          <span class="verdict-badge" style="background:${score >= 60 ? '#dcfce7' : score >= 40 ? '#fef9c3' : '#fef2f2'};color:${scoreColor}">
            ${verdictLabel[verdict] || verdict}
          </span>
        </div>
        <div style="text-align:right">
          <div style="display:flex;flex-wrap:wrap;gap:3px;justify-content:flex-end">
            ${distortionCount > 0 ? `<span class="tag" style="background:#fef2f2;color:#dc2626">⚠️ ${distortionCount}处失真</span>` : ""}
            ${fallacyCount > 0 ? `<span class="tag" style="background:#fef9c3;color:#ca8a04">🧠 ${fallacyCount}处谬误</span>` : ""}
            ${statRisk > 30 ? `<span class="tag" style="background:#fff7ed;color:#ea580c">📊 统计滥用</span>` : ""}
            ${narrativeScore > 40 ? `<span class="tag" style="background:#f3e8ff;color:#7c3aed">👁️ 叙事操纵</span>` : ""}
          </div>
        </div>
      </div>
      ${result?.sources_found ? `<p style="font-size:11px;color:#6b7280">发现 ${result.sources_found} 个信息来源 | ${result.original_sources?.length || 0} 个原始来源</p>` : ""}
      <div style="margin-top:8px">
        <a href="${WEB_BASE}/events/${data.eventId}" target="_blank">查看完整分析报告 →</a>
        ${data.eventId ? `<a href="${WEB_BASE}/events/${data.eventId}/report" target="_blank" style="margin-left:12px">📋 溯源报告 →</a>` : ""}
      </div>
    </div>
  `;
}
