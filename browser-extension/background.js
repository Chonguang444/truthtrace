// Truth Lens Background Service Worker
const API_BASE = "http://localhost:8000/api";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "truthlens-check",
    title: "Truth Lens - Check credibility",
    contexts: ["selection"]
  });
  chrome.contextMenus.create({
    id: "truthlens-check-url",
    title: "Truth Lens - Check this link",
    contexts: ["link"]
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === "truthlens-check" && info.selectionText) {
    await checkAndShow(tab.id, { type: "text", text: info.selectionText.trim().slice(0, 5000) });
  }
  if (info.menuItemId === "truthlens-check-url" && info.linkUrl) {
    await checkAndShow(tab.id, { type: "url", url: info.linkUrl });
  }
});

async function checkAndShow(tabId, payload) {
  try {
    const endpoint = payload.type === "url"
      ? API_BASE + "/quick-check/url"
      : API_BASE + "/quick-check/text";
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload.type === "url" ? { url: payload.url } : { text: payload.text, title: "" })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "API error" }));
      throw new Error(err.detail || "HTTP " + res.status);
    }
    const result = await res.json();
    await chrome.scripting.executeScript({
      target: { tabId },
      func: showResultPanel,
      args: [result]
    });
  } catch (e) {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: showErrorPanel,
      args: [e.message || "Detection failed"]
    });
  }
}

function showErrorPanel(msg) {
  const old = document.getElementById("truthlens-panel");
  if (old) old.remove();
  const div = document.createElement("div");
  div.id = "truthlens-panel";
  div.innerHTML = "<div style="position:fixed;top:20px;right:20px;z-index:2147483647;width:360px;background:#fef2f2;border:1px solid #fecaca;border-radius:12px;padding:16px;font-family:system-ui;font-size:13px;box-shadow:0 8px 32px rgba(0,0,0,0.2)"><div style="display:flex;justify-content:space-between;margin-bottom:8px"><b>Truth Lens</b><button onclick="this.closest('#truthlens-panel').remove()" style="background:none;border:none;cursor:pointer;font-size:16px">X</button></div><p style="color:#991b1b;margin:0">" + msg + "</p><p style="color:#6b7280;font-size:11px;margin-top:8px">Ensure TruthTrace backend is running on port 8000.</p></div>";
  document.body.appendChild(div);
  setTimeout(() => { if (div.parentNode) div.remove(); }, 10000);
}

function showResultPanel(result) {
  const old = document.getElementById("truthlens-panel");
  if (old) old.remove();
  const cs = result.credibility_score;
  const labels = { likely_true:"Likely True", unverifiable:"Unverifiable", misleading:"Misleading", likely_false:"Likely False", false:"False", true:"True" };
  const vLabel = labels[result.verdict] || result.verdict;
  const vColor = cs >= 60 ? "#16a34a" : cs >= 40 ? "#ca8a04" : "#dc2626";
  const dists = (result.analysis?.distortion?.matches || []).slice(0, 3);
  const falls = (result.analysis?.fallacy?.matches || []).slice(0, 3);
  const causals = (result.analysis?.causal?.fallacies || []).slice(0, 2);
  let fh = "";
  dists.forEach(m => { fh += "<div class=tl-f style=background:#fef2f2;color:#991b1b>" + esc(m.description) + "</div>"; });
  falls.forEach(m => { fh += "<div class=tl-f style=background:#fef3c7;color:#92400e>" + esc(m.description) + "</div>"; });
  causals.forEach(m => { fh += "<div class=tl-f style=background:#f3e8ff;color:#6b21a8>" + esc(m.description) + "</div>"; });
  let sh = "";
  if (result.risk_signals?.length) {
    sh = "<div style=display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px>" + result.risk_signals.map(s => "<span style=font-size:11px;padding:2px 8px;border-radius:12px;background:#fef3c7;color:#92400e>" + esc(s[0]) + ": " + s[1] + "</span>").join("") + "</div>";
  }
  const panel = document.createElement("div");
  panel.id = "truthlens-panel";
  panel.innerHTML = "<div style=position:fixed;top:20px;right:20px;z-index:2147483647;width:380px;max-height:80vh;overflow-y:auto;background:#fff;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,0.2);font-family:system-ui;font-size:13px;line-height:1.5>" +
    "<div style=display:flex;justify-content:space-between;align-items:center;padding:12px 16px;border-bottom:1px solid #e5e7eb;background:#f9fafb;border-radius:12px 12px 0 0>" +
      "<b>Truth Lens</b>" +
      "<div>" +
        "<button id=tl-copy style=background:none;border:1px solid #e5e7eb;cursor:pointer;font-size:12px;padding:3px 8px;border-radius:6px;margin-right:4px>Copy</button>" +
        "<button id=tl-close style=background:none;border:1px solid #e5e7eb;cursor:pointer;font-size:12px;padding:3px 8px;border-radius:6px>X</button>" +
      "</div>" +
    "</div>" +
    "<div style=padding:16px>" +
      "<div style=display:flex;align-items:center;gap:16px;margin-bottom:12px>" +
        "<div style=width:72px;height:72px;border-radius:50%;border:6px solid " + vColor + ";display:flex;flex-direction:column;align-items:center;justify-content:center>" +
          "<span style=font-size:24px;font-weight:800;color:" + vColor + ">" + cs + "</span>" +
          "<span style=font-size:9px;color:#6b7280>credibility</span>" +
        "</div>" +
        "<span style=font-size:16px;font-weight:700;color:" + vColor + ">" + vLabel + "</span>" +
      "</div>" +
      "<div style=font-size:13px;color:#374151;margin-bottom:12px;padding:10px;background:#f0f9ff;border-radius:8px;line-height:1.6>" + esc(result.summary || "") + "</div>" +
      sh +
      (fh ? "<div style=margin-bottom:10px>" + fh + "</div>" : "") +
      "<div style=margin-top:10px;padding-top:8px;border-top:1px solid #e5e7eb>" +
        "<span style=font-size:10px;color:#9ca3af>" + esc(result.method || "Quick-Check") + "</span>" +
        "<span style=display:block;font-size:10px;color:#9ca3af;margin-top:4px>" + esc((result.disclaimer || "").slice(0, 100)) + "</span>" +
      "</div>" +
    "</div></div>";
  document.body.appendChild(panel);
  panel.querySelector("#tl-close").onclick = () => panel.remove();
  panel.querySelector("#tl-copy").onclick = () => {
    navigator.clipboard.writeText("Truth Lens: " + cs + "/100 - " + vLabel + "
" + (result.summary || ""));
  };
  setTimeout(() => { if (panel.parentNode) panel.remove(); }, 60000);
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s || "";
  return d.innerHTML;
}
