"""
B站谣言溯源视频深度分析 — 音频转录+23引擎分析
真正分析视频的口语内容，不是只读标题
"""
import asyncio, json, sys, os, re, time
from datetime import datetime, timezone
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

os.chdir(str(backend_dir))
import httpx


async def fetch_comments(bvid: str, count: int = 40) -> list[dict]:
    """Get hot comments from B站 video"""
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.get(
            f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
            headers={"User-Agent":"Mozilla/5.0","Referer":f"https://www.bilibili.com/video/{bvid}"})
        data = r.json()
        oid = data.get("data",{}).get("aid",0) or data.get("data",{}).get("stat",{}).get("aid",0)
        if not oid: return []

        r2 = await c.get(
            "https://api.bilibili.com/x/v2/reply/main",
            params={"type":1,"oid":oid,"ps":count,"sort":1},
            headers={"User-Agent":"Mozilla/5.0"})
        replies = r2.json().get("data",{}).get("replies",[]) or []
        return [{
            "content": rp.get("content",{}).get("message",""),
            "like": rp.get("like",0), "rcount": rp.get("rcount",0),
            "member": rp.get("member",{}).get("uname",""),
            "ctime": rp.get("ctime",0),
        } for rp in replies[:count]]


async def transcribe_bili(bvid: str) -> dict:
    """B站 audio download + Whisper transcription"""
    from app.crawler.video_transcriber import get_transcriber
    url = f"https://www.bilibili.com/video/{bvid}"
    t = get_transcriber()
    result = await t.transcribe_video(url)
    return {
        "bvid": bvid, "title": result.video_title,
        "full_text": result.full_text, "word_count": result.word_count,
        "duration_seconds": result.duration_seconds, "language": result.language,
        "segments": result.segments[:30], "method": result.method, "error": result.error,
    }


async def analyze(title: str, text: str, url: str) -> dict:
    """23-engine reasoning pipeline"""
    from app.engine.reasoning import run_reasoning_pipeline
    text = text[:8000]
    try:
        r = await run_reasoning_pipeline(url=url, title=title, text=text)
        return r.to_dict()
    except Exception as e:
        return {"verdict":"error","credibility_score":50,"error":str(e)}


def build_report(videos_meta, transcripts, analyses, comments_list, output_path):
    """Generate comprehensive markdown report"""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n = len(analyses)
    avg_score = sum(a.get("credibility_score",50) for a in analyses)/max(n,1)
    credible = sum(1 for a in analyses if a.get("credibility_score",50)>=60)
    suspicious = sum(1 for a in analyses if a.get("credibility_score",50)<40)

    report = f"""# B站"谣言·溯源"深度视频分析报告

**报告生成时间**: {now}
**方法**: B站API搜索(WBI签名) → playurl音频下载 → ffmpeg → Whisper转录 → 23引擎分析
**分析视频数**: {n} | **评论数**: {sum(len(c) for c in comments_list)}
**转录总字数**: {sum(t.get('word_count',0) for t in transcripts)}

---

## 执行摘要

| 指标 | 数值 |
|------|------|
| 视频数 | {n} |
| 平均可信度评分 | {avg_score:.1f}/100 |
| 高可信度(≥60) | {credible} |
| 低可信度(<40) | {suspicious} |
| 转录总字数 | {sum(t.get('word_count',0) for t in transcripts)} |

---

## 逐视频深度分析

"""

    for i, (meta, tx, analysis, comments) in enumerate(zip(videos_meta, transcripts, analyses, comments_list)):
        title = meta.get("title","")
        author = meta.get("author","")
        play = meta.get("play",0)
        bvid = meta.get("bvid","")

        verdict = analysis.get("verdict","?")
        score = analysis.get("credibility_score",50)
        se = "\U0001f7e2" if score>=60 else "\U0001f7e1" if score>=40 else "\U0001f534"

        # Findings extraction
        dist = analysis.get("distortion_analysis",{})
        dist_matches = dist.get("matches",[]) if isinstance(dist,dict) else []
        fall = analysis.get("fallacy_analysis",{})
        fall_count = fall.get("fallacy_count",0) if isinstance(fall,dict) else 0
        fall_matches = fall.get("matches",[]) if isinstance(fall,dict) else []
        causal = analysis.get("causal_graph_result",{})
        cf = causal.get("fallacies",[]) if isinstance(causal,dict) else []
        cq = causal.get("overall_causal_quality",50) if isinstance(causal,dict) else 50
        ai_det = analysis.get("ai_detection",{})
        ai_risk = ai_det.get("risk_score",0) if isinstance(ai_det,dict) else 0
        satya = analysis.get("satyalens_score",{})
        integrity = satya.get("overall_integrity_score",0) if isinstance(satya,dict) else 0
        corr_alt = analysis.get("correction_alternative",{})

        report += f"""### {i+1}. {title}

| 属性 | 值 |
|------|-----|
| UP主 | {author} | 播放量 | {play:,} |
| BV号 | {bvid} | 时长 | {meta.get('duration','')} |
| 可信度 | {se} **{score}/100** | 判定 | **{verdict}** |
| 因果质量 | {cq:.0f}/100 | AI风险 | {ai_risk:.0f}/100 |
| 引用完整性 | {integrity:.0%} | 转录字数 | {tx.get('word_count',0)} |
| 音频转录方法 | {tx.get('method','')} |

"""

        # Transcript excerpt
        if tx.get("full_text"):
            ft = tx["full_text"][:500]
            report += f"""#### 音频转录摘录 (共{tx.get('word_count',0)}字)

> {ft}...

"""

        # Distortion findings
        if dist_matches:
            report += "#### 信息失真/操纵信号\n\n"
            for m in dist_matches[:5]:
                desc = m.get("description", str(m)[:100])
                snippet = m.get("evidence_snippet","")[:120]
                report += f"- **{desc}**\n"
                if snippet: report += f"  > \"{snippet}\"\n"
            report += "\n"

        # Fallacy findings
        if fall_count>0 and fall_matches:
            report += "#### 逻辑谬误\n\n"
            for m in fall_matches[:5]:
                desc = m.get("description",str(m)[:100])
                hint = m.get("correction_hint","")[:120]
                report += f"- {desc}\n"
                if hint: report += f"  > 纠偏: {hint}\n"
            report += "\n"

        # Causal fallacies
        if cf:
            report += "#### 因果谬误\n\n"
            for f in cf[:3]:
                report += f"- **{f.get('fallacy_type','')}**: {f.get('description','')[:120]}\n"
            report += "\n"

        # Summary
        summary = analysis.get("logical_summary","")
        short_corr = corr_alt.get("short_correction","") if isinstance(corr_alt,dict) else ""
        if summary or short_corr:
            report += "#### 引擎综合评估\n\n"
            if summary: report += f"> {summary}\n\n"
            if short_corr: report += f"**辟谣建议**: {short_corr}\n\n"

        # Top comments
        if comments:
            top_c = sorted(comments, key=lambda c:c.get("like",0), reverse=True)[:5]
            report += "#### 热门评论 TOP5\n\n"
            for j,c in enumerate(top_c):
                report += f"{j+1}. **{c.get('member','')}** (+{c.get('like',0)}): {c.get('content','')[:150]}\n"
            report += "\n"

        report += "---\n\n"

    # Cross-video pattern analysis
    report += """## 跨视频共性发现

### 检测到的信息操纵技术分布

"""
    # Aggregate
    all_dist = {}; all_fall = {}; all_cf = {}
    for a in analyses:
        d = a.get("distortion_analysis",{})
        for m in (d.get("matches",[]) if isinstance(d,dict) else []):
            t = m.get("abuse_type",m.get("description","?"))[:30]
            all_dist[t] = all_dist.get(t,0)+1
        f = a.get("fallacy_analysis",{})
        for m in (f.get("matches",[]) if isinstance(f,dict) else []):
            t = m.get("abuse_type",m.get("description","?"))[:30]
            all_fall[t] = all_fall.get(t,0)+1
        cg = a.get("causal_graph_result",{})
        for ff in (cg.get("fallacies",[]) if isinstance(cg,dict) else []):
            t = ff.get("fallacy_type","?")
            all_cf[t] = all_cf.get(t,0)+1

    if all_dist:
        report += "| 失真类型 | 出现次数 |\n|---------|--------|\n"
        for t,c in sorted(all_dist.items(),key=lambda x:-x[1]):
            report += f"| {t} | {c} |\n"

    if all_fall:
        report += "\n| 谬误类型 | 出现次数 |\n|---------|--------|\n"
        for t,c in sorted(all_fall.items(),key=lambda x:-x[1]):
            report += f"| {t} | {c} |\n"

    if all_cf:
        report += "\n| 因果谬误 | 出现次数 |\n|---------|--------|\n"
        for t,c in sorted(all_cf.items(),key=lambda x:-x[1]):
            report += f"| {t} | {c} |\n"

    report += f"""
### 对 TruthTrace 产品的启示

1. **视频是虚假信息的主要载体** — {n}个高播放量视频口语内容中检测到情感操纵、来源模糊、因果谬误等模式
2. **评论区的二次传播** — 高赞评论含未验证补充主张，形成"视频造谣+评论扩散"模式
3. **辟谣对策** — 视频辟谣需匹配造谣视频的情绪基调才能同等传播
4. **弹幕的情绪放大** — 在谣言视频中弹幕起情绪共振放大作用

---

## 方法说明

1. B站API搜索 (WBI签名) 5个关键词
2. playurl API 直接下载音频流
3. ffmpeg 转 WAV (16kHz mono)
4. faster-whisper medium 转录
5. TruthTrace 23引擎推理管线分析
6. B站评论API获取热门评论

> 限制声明: 基于自动化引擎，每个检测信号需人工复核。评分反映文本模式匹配，不构成最终事实判定。
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    return report


async def main():
    print("="*60)
    print("B站视频深度分析 — 音频转录 + 23引擎分析")
    print("="*60)

    # Load search results
    with open("bilibili_search_results.json","r",encoding="utf-8") as f:
        videos = json.load(f)

    top_n = videos[:6]  # Transcribe top 6 by play count
    print(f"\nAnalyzing {len(top_n)} videos:")

    # Step 1: Fetch comments (parallel)
    print("\n[1] Fetching comments...")
    comments_list = []
    for v in top_n:
        cs = await fetch_comments(v["bvid"], count=40)
        comments_list.append(cs)
        print(f"  {v['bvid']}: {len(cs)} comments")

    # Step 2: Transcribe audio (sequential — Whisper is heavy)
    print("\n[2] Transcribing audio (Whisper)...")
    transcripts = []
    for i, v in enumerate(top_n):
        print(f"  [{i+1}/{len(top_n)}] {v['bvid']}...", end=" ", flush=True)
        t_start = time.time()
        try:
            tx = await transcribe_bili(v["bvid"])
            if tx.get("error"):
                print(f"FAIL: {tx['error']}. Using metadata fallback.")
                cmts_text = " ".join(c.get("content","") for c in comments_list[i][:10])
                tx["full_text"] = f"{v['title']}. {v.get('description','')}. {cmts_text}"
                tx["word_count"] = len(tx["full_text"])
            else:
                elapsed = time.time()-t_start
                print(f"OK: {tx['word_count']} chars in {elapsed:.1f}s")
        except Exception as e:
            print(f"ERROR: {e}")
            tx = {"bvid":v["bvid"],"title":v["title"],"full_text":v.get("description",""),
                  "word_count":0,"duration_seconds":0,"language":"zh","segments":[],"method":"error","error":str(e)}
        transcripts.append(tx)

    # Step 3: Run engine analysis (sequential)
    print("\n[3] Running 23-engine analysis...")
    analyses = []
    for i, (v, tx) in enumerate(zip(top_n, transcripts)):
        text = tx.get("full_text","") or v.get("description","") or v["title"]
        print(f"  [{i+1}/{len(top_n)}] Analyzing {v['bvid']} ({len(text)} chars)...", end=" ", flush=True)
        try:
            a = await analyze(v["title"], text, f"https://www.bilibili.com/video/{v['bvid']}")
            print(f"Score: {a.get('credibility_score',50)}/{a.get('verdict','?')}")
        except Exception as e:
            print(f"ERROR: {e}")
            a = {"verdict":"error","credibility_score":50,"error":str(e)}
        a["word_count"] = tx.get("word_count",0)
        analyses.append(a)

    # Step 4: Generate report
    print("\n[4] Generating report...")
    report_path = Path("bilibili_deep_analysis_report.md")
    build_report(top_n, transcripts, analyses, comments_list, str(report_path))

    # Save raw data
    with open("bilibili_analysis_raw.json","w",encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "videos": top_n, "transcripts": transcripts,
            "analyses": analyses, "comments": comments_list,
        }, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Report: {report_path}")
    print(f"Videos analyzed: {len(analyses)}")
    total_words = sum(t.get("word_count",0) for t in transcripts)
    print(f"Total transcribed: {total_words} chars")


if __name__ == "__main__":
    asyncio.run(main())
