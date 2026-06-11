const API = "http://localhost:8000/api";
const inp = document.getElementById("inp");
const chk = document.getElementById("chk");
const ld = document.getElementById("ld");
const err = document.getElementById("err");
const res = document.getElementById("res");

chk.onclick = async () => {
  const text = inp.value.trim();
  if (text.length < 10) { showErr("Text must be at least 10 characters"); return; }
  ld.style.display = "block"; err.style.display = "none"; res.classList.remove("s"); chk.disabled = true;
  try {
    const r = await fetch(API + "/quick-check/text", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text.slice(0, 5000), title: "" })
    });
    if (!r.ok) throw new Error((await r.json().catch(()=>({detail:"Error"}))).detail || "HTTP " + r.status);
    showRes(await r.json());
  } catch(e) { showErr(e.message || "Connection failed"); }
  ld.style.display = "none"; chk.disabled = false;
};

function showRes(r) {
  const cs = r.credibility_score;
  const vc = cs >= 60 ? "#16a34a" : cs >= 40 ? "#ca8a04" : "#dc2626";
  const vl = { likely_true:"Likely True",unverifiable:"Unverifiable",misleading:"Misleading",likely_false:"Likely False",false:"False",true:"True" }[r.verdict] || r.verdict;
  document.getElementById("ring").style.borderColor = vc;
  document.getElementById("sn").textContent = cs; document.getElementById("sn").style.color = vc;
  document.getElementById("vt").textContent = vl; document.getElementById("vt").style.color = vc;
  document.getElementById("sum").textContent = r.summary || "";
  let fh = "";
  (r.analysis?.distortion?.matches||[]).slice(0,2).forEach(m=>{fh+="<div class=fl fd>"+esc(m.description)+"</div>"});
  (r.analysis?.fallacy?.matches||[]).slice(0,2).forEach(m=>{fh+="<div class=fl ff>"+esc(m.description)+"</div>"});
  (r.analysis?.causal?.fallacies||[]).slice(0,1).forEach(m=>{fh+="<div class=fl fc>"+esc(m.description)+"</div>"});
  document.getElementById("fnd").innerHTML = fh;
  res.classList.add("s");
}

function showErr(msg) { err.textContent = msg; err.style.display = "block"; }
function esc(s) { const d=document.createElement("div");d.textContent=s||"";return d.innerHTML; }
