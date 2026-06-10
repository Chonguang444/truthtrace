"""
辟谣内容创作工坊 API -- AI辟谣文章/海报/短视频脚本/多平台分发
从数据库提取真实引擎分析结果，不再生成虚假模拟数据。
"""

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.base import get_db
from app.models.event import Event
from app.auth.jwt import get_current_active_user
from app.models.user import User

router = APIRouter()


# =============================================================================
# 数据模型
# =============================================================================

class ArticleGenerateRequest(BaseModel):
    event_id: str
    tone: str = "balanced"

    @field_validator("tone")
    @classmethod
    def valid_tone(cls, v: str) -> str:
        if v not in {"balanced", "firm", "educational", "empathetic"}:
            raise ValueError(f"语气必须是: balanced/firm/educational/empathetic")
        return v


class PosterRequest(BaseModel):
    event_id: str
    style: str = "minimal"


class ScriptRequest(BaseModel):
    event_id: str
    duration_sec: int = 60

    @field_validator("duration_sec")
    @classmethod
    def valid_duration(cls, v: int) -> int:
        if v not in (30, 60, 90):
            raise ValueError("时长支持: 30秒/60秒/90秒")
        return v


class PlatformFormatRequest(BaseModel):
    content: str
    platform: str
    include_hashtags: bool = True


class PublishTrackRequest(BaseModel):
    event_id: str
    platform: str
    publish_url: str


# =============================================================================
# 真实数据获取
# =============================================================================

async def _get_real_analysis(event_id: str, db: AsyncSession) -> dict | None:
    """从数据库获取真实引擎分析结果"""
    try:
        eid = uuid.UUID(event_id)
    except ValueError:
        return None
    event = await db.get(Event, eid)
    if not event or not event.engine_analysis:
        return None
    return {
        "verdict": event.engine_analysis.get("verdict", "unverifiable"),
        "credibility_score": event.credibility_score,
        "distortion_analysis": event.engine_analysis.get("distortion_analysis", {}),
        "fallacy_analysis": event.engine_analysis.get("fallacy_analysis", {}),
        "narrative_analysis": event.engine_analysis.get("narrative_analysis", {}),
        "statistical_analysis": event.engine_analysis.get("statistical_analysis", {}),
        "correction": event.engine_analysis.get("correction", ""),
        "summary": event.summary or "",
        "title": event.title,
    }


# =============================================================================
# Claude API
# =============================================================================

async def _call_claude(prompt: str, max_tokens: int = 2000) -> Optional[str]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            if resp.status_code == 200:
                return resp.json()["content"][0]["text"]
    except Exception:
        pass
    return None


def _build_fallback_article(analysis: dict, tone: str) -> str:
    """当Claude不可用时，基于真实分析数据生成模板化辟谣文章"""
    score = analysis.get("credibility_score", 50)
    verdict_cn = {"false": "虚假信息", "likely_false": "可能虚假", "misleading": "误导性",
                  "likely_true": "可能真实", "true": "真实", "unverifiable": "无法验证"}
    verdict = verdict_cn.get(analysis.get("verdict", ""), "待验证")

    dist_matches = analysis.get("distortion_analysis", {}).get("matches", [])
    fal_count = analysis.get("fallacy_analysis", {}).get("fallacy_count", 0)
    narrative = analysis.get("narrative_analysis", {})
    dominant = narrative.get("dominant_narrative", "无") if isinstance(narrative, dict) else "无"
    manipulation = narrative.get("manipulation_score", 0) if isinstance(narrative, dict) else 0
    correction = analysis.get("correction", "")

    parts = ["## 事件概述\n经TruthTrace 10引擎推理管线分析，该信息可信度评分为 {:.0f}/100，综合判定为“{}”。".format(score, verdict)]
    parts.append(f"\n## 分析结果")

    if dist_matches:
        parts.append(f"\n### 信息失真 ({len(dist_matches)} 处)")
        for d in dist_matches[:5]:
            desc = d.get("description", d.get("desc", str(d)))
            parts.append(f"- {desc}")

    if fal_count > 0:
        parts.append(f"\n### 逻辑谬误 ({fal_count} 处)")
        for f in analysis.get("fallacy_analysis", {}).get("matches", [])[:5]:
            parts.append(f"- {f.get('description', str(f))}")

    parts.append(f"\n### 叙事框架\n主导叙事: {dominant} · 操纵性评分: {manipulation:.0f}/100")

    if correction:
        parts.append(f"\n## 纠偏建议\n{correction}")

    parts.append(f"\n## 如何识别类似信息")
    parts.append("1. 检查信息来源：是否有具体的机构名称、研究报告链接？")
    parts.append("2. 注意情绪操纵：是否使用了\"速看\"\"马上被删\"\"不转不是XX\"等催促性语言？")
    parts.append("3. 查阅权威渠道：涉及健康信息可查WHO/国家卫健委官网；涉及政策可查政府公报。")
    parts.append(f"\n## 结论\n基于目前可获得的证据,该信息的可信度为 {score:.0f}/100 分。建议以权威部门发布的信息为准。")
    parts.append(f"\n*本文由TruthTrace辟谣工坊基于10引擎真实分析结果生成。*")

    return "\n".join(parts)


def _parse_sections(text: str) -> list[dict]:
    sections = []
    current_heading = ""
    current_lines = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            if current_heading and current_lines:
                sections.append({"heading": current_heading, "content": "\n".join(current_lines)})
                current_lines = []
            continue
        if line.startswith("##"):
            if current_heading and current_lines:
                sections.append({"heading": current_heading, "content": "\n".join(current_lines)})
                current_lines = []
            current_heading = line.replace("##", "").strip()
        else:
            current_lines.append(line)
    if current_heading or current_lines:
        sections.append({"heading": current_heading or "正文", "content": "\n".join(current_lines)})
    return sections if sections else [{"heading": "正文", "content": text}]


# =============================================================================
# 端点
# =============================================================================

@router.post("/studio/generate-article")
async def generate_article(
    req: ArticleGenerateRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """生成AI辟谣文章 -- 基于数据库真实引擎分析"""
    analysis = await _get_real_analysis(req.event_id, db)
    if not analysis:
        raise HTTPException(404, "事件不存在或无引擎分析结果。请先运行溯源分析。")

    tone_map = {
        "balanced": "以中立、客观的语气写作,先呈现原始说法再提供事实核查结果。",
        "firm": "以坚定但不攻击性的语气写作,明确指出错误但避免妖魔化传播者。",
        "educational": "以教育性的语气写作,把读者当作学习者,解释为什么这种说法有问题以及如何识别。",
        "empathetic": "以同理心的语气写作,理解读者为什么会相信这些信息,同时温和地提供正确信息。",
    }

    dist_text = "\n".join(
        f"- {d.get('description', str(d))}" for d in
        analysis.get("distortion_analysis", {}).get("matches", [])[:5]
    )

    prompt = f"""你是专业的事实核查和辟谣内容创作者。根据以下引擎分析结果撰写一篇辟谣文章。

【事件】{analysis.get('title', '')}
【可信度评分】{analysis['credibility_score']:.0f}/100
【综合判定】{analysis.get('verdict', '')}
【信息失真】{dist_text if dist_text else '未检测到明显失真'}
【逻辑谬误数】{analysis.get('fallacy_analysis', {}).get('fallacy_count', 0)} 处
【主导叙事】{analysis.get('narrative_analysis', {}).get('dominant_narrative', '') if isinstance(analysis.get('narrative_analysis'), dict) else '无'}
【纠偏建议】{analysis.get('correction', '')}

【写作要求】语气: {tone_map.get(req.tone, tone_map['balanced'])}
标题: 10-20字,吸引人但不标题党。结构: 原文说法 → 逐条分析 → 结论。字数: 500-800字。不确定处明确说"目前无法确认"。"""

    ai_text = await _call_claude(prompt, max_tokens=2000)
    if ai_text:
        lines = ai_text.strip().split("\n")
        title = lines[0].replace("#", "").strip() if lines else "辟谣报告"
        body = "\n".join(lines[1:]) if len(lines) > 1 else ai_text
        source = "claude-api"
    else:
        title = f"辟谣分析: {analysis.get('title', '事件')[:30]}"
        body = _build_fallback_article(analysis, req.tone)
        source = "template-engine (真实分析数据, 模板化排版)"

    return {
        "event_id": req.event_id,
        "title": title,
        "sections": _parse_sections(body),
        "tone": req.tone,
        "word_count": len(body),
        "engine_verdict": analysis["verdict"],
        "credibility_score": analysis["credibility_score"],
        "generated_by": source,
        "disclaimer": "本文基于TruthTrace引擎真实分析结果生成。请人工审核后发布。",
    }


@router.post("/studio/generate-poster")
async def generate_poster(
    req: PosterRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """生成辟谣海报数据 -- 基于数据库真实分析"""
    analysis = await _get_real_analysis(req.event_id, db)
    if not analysis:
        raise HTTPException(404, "事件不存在或无引擎分析结果")

    dist_matches = analysis.get("distortion_analysis", {}).get("matches", [])
    rumor_snippets = [d.get("evidence_snippet", d.get("snippet", "")) for d in dist_matches if d.get("evidence_snippet") or d.get("snippet")]

    score = analysis["credibility_score"]
    score_color = "#16a34a" if score >= 60 else ("#ca8a04" if score >= 40 else "#ef4444")

    return {
        "event_id": req.event_id,
        "style": req.style,
        "truth_card": {
            "title": "事实核查",
            "rumor_label": "网络说法",
            "rumor_text": "; ".join(rumor_snippets[:2]) if rumor_snippets else "该信息包含未经验证的说法",
            "fact_label": "核查结果",
            "fact_text": f"经TruthTrace 10引擎分析,该信息可信度 {score:.0f}/100 分, 判定为 {analysis['verdict']}",
            "credibility_badge": {"score": round(score), "label": analysis["verdict"], "color": score_color},
            "key_findings": [
                {"icon": "magnifier", "text": f"检测到 {len(dist_matches)} 种信息失真"},
                {"icon": "brain", "text": f"检测到 {analysis.get('fallacy_analysis', {}).get('fallacy_count', 0)} 个逻辑谬误"},
                {"icon": "chart", "text": f"操纵性评分: {analysis.get('narrative_analysis', {}).get('manipulation_score', 0):.0f}/100" if isinstance(analysis.get('narrative_analysis'), dict) else ""},
            ],
            "share_text": f"【事实核查】可信度 {score:.0f}/100。查看完整分析: https://truthtrace.app/events/{req.event_id}",
        },
        "colors": {
            "minimal": {"bg": "#ffffff", "text": "#1a1a2e", "accent": "#2563eb", "danger": "#ef4444"},
            "impact": {"bg": "#1a1a2e", "text": "#ffffff", "accent": "#f59e0b", "danger": "#ef4444"},
            "infographic": {"bg": "#f8fafc", "text": "#0f172a", "accent": "#0891b2", "danger": "#dc2626"},
        }.get(req.style, {}),
    }


@router.post("/studio/generate-script")
async def generate_script(
    req: ScriptRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """生成辟谣短视频脚本 -- 基于数据库真实分析"""
    analysis = await _get_real_analysis(req.event_id, db)
    if not analysis:
        raise HTTPException(404, "事件不存在或无引擎分析结果")

    duration = req.duration_sec
    num_scenes = duration // 15
    score = analysis["credibility_score"]
    verdict_cn = {"false": "虚假信息", "likely_false": "可能虚假", "misleading": "误导性",
                  "likely_true": "可能真实", "true": "真实", "unverifiable": "无法验证"}
    verdict = verdict_cn.get(analysis.get("verdict", ""), "待验证")

    dist_count = len(analysis.get("distortion_analysis", {}).get("matches", []))
    fal_count = analysis.get("fallacy_analysis", {}).get("fallacy_count", 0)
    narrative = analysis.get("narrative_analysis", {})
    dominant = narrative.get("dominant_narrative", "未知") if isinstance(narrative, dict) else "未知"
    manipulation = narrative.get("manipulation_score", 0) if isinstance(narrative, dict) else 0

    scenes = []
    templates = [
        {"narration": f"最近,一条关于'{analysis.get('title','事件')[:30]}'的信息在网上广泛传播。",
         "on_screen_text": "网络热传信息", "visual": "手机屏幕滚动展示原始信息截图"},
        {"narration": f"经TruthTrace系统分析,该信息可信度仅{score:.0f}分,判定为{verdict}。",
         "on_screen_text": f"可信度: {score:.0f}/100", "visual": "大号仪表盘指针转到红色区域"},
        {"narration": f"我们检测到了{dist_count}处信息失真和{fal_count}个逻辑谬误。主导叙事框架为'{dominant}'。",
         "on_screen_text": f"失真{dist_count}处 · 谬误{fal_count}处 · 操纵评分{manipulation:.0f}",
         "visual": "并排显示检测结果清单"},
        {"narration": "那么事实是什么？根据权威来源的数据,实际情况与网络流传的说法不符。",
         "on_screen_text": "事实核查", "visual": "翻转卡片,从谣言翻到事实"},
        {"narration": "学会识别信息操纵,从今天开始做聪明的信息消费者。下载TruthTrace获取实时事实核查。",
         "on_screen_text": "批判性思维", "visual": "TruthTrace Logo + 下载二维码"},
    ]

    for i in range(min(num_scenes, len(templates))):
        t = templates[i]
        scenes.append({"scene": i + 1, "duration_sec": 15, "narration": t["narration"],
                        "on_screen_text": t["on_screen_text"], "visual_suggestion": t["visual"],
                        "transition": "fade" if i < num_scenes - 1 else "end_card"})

    return {
        "event_id": req.event_id, "duration_sec": duration, "scenes": scenes,
        "total_scenes": len(scenes), "hashtags": ["#事实核查", "#辟谣", "#信息素养"],
        "end_card": {"text": "下载TruthTrace,获取实时事实核查", "qr_url": "https://truthtrace.app/download"},
        "production_tips": ["每个场景建议配上简洁的图标或文字动画",
                           "旁白语速建议每分钟180-200字", "关键数据可添加音效强调"],
    }


# =============================================================================
# 多平台分发
# =============================================================================

@router.post("/studio/format-for-platform")
async def format_for_platform(
    req: PlatformFormatRequest,
    current_user: User = Depends(get_current_active_user),
):
    """将辟谣内容格式化为各平台适用格式"""
    content = req.content
    hashtags = "#事实核查 #辟谣 #TruthTrace" if req.include_hashtags else ""

    formatters = {
        "weibo": lambda c: {
            "platform": "微博", "max_length": 140,
            "formatted": f"{c[:120]}...{hashtags}" if len(c) > 120 else f"{c} {hashtags}",
            "tips": ["使用短链接指向完整报告", "配图比纯文字传播力强3倍", "黄金发布时段: 12:00-14:00, 20:00-22:00"],
        },
        "xiaohongshu": lambda c: {
            "platform": "小红书",
            "formatted": f"📋 事实核查报告\n\n{c[:300]}\n\n---\n🔍 以上分析由TruthTrace引擎生成\n\n{hashtags}",
            "tips": ["封面图要突出核心数据", "正文前3行决定阅读率"],
        },
        "douyin": lambda c: {
            "platform": "抖音",
            "formatted": f"{c[:200]}\n\n{hashtags}",
            "tips": ["视频前3秒必须抛出悬念", "评论区置顶完整报告链接"],
        },
        "twitter": lambda c: {
            "platform": "Twitter/X",
            "formatted": f"Fact check: {c[:200]}\n\nSource: TruthTrace\n{hashtags}",
            "tips": ["使用Thread功能发布长文分析", "配数据可视化截图"],
        },
    }

    fn = formatters.get(req.platform)
    if not fn:
        raise HTTPException(400, f"不支持的平台: {req.platform}。支持: {', '.join(formatters.keys())}")
    return {"original_length": len(content), **fn(content), "original_content": content}


# =============================================================================
# 发布追踪
# =============================================================================

_publish_records: list[dict] = []


@router.post("/studio/track-publish")
async def track_publish(req: PublishTrackRequest, current_user: User = Depends(get_current_active_user)):
    record = {
        "id": str(uuid.uuid4())[:8], "user_id": str(current_user.id),
        "username": current_user.username, "event_id": req.event_id,
        "platform": req.platform, "publish_url": req.publish_url,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    _publish_records.append(record)
    return {"status": "tracked", "record": record}


@router.get("/studio/publish-stats/{event_id}")
async def publish_stats(event_id: str):
    records = [r for r in _publish_records if r["event_id"] == event_id]
    platform_counts = {}
    for r in records:
        platform_counts[r["platform"]] = platform_counts.get(r["platform"], 0) + 1
    return {
        "event_id": event_id, "total_publishes": len(records),
        "by_platform": platform_counts, "publishers": [r["username"] for r in records],
        "message": f"已有 {len(records)} 位用户发布了辟谣内容" if records else "此事件还没有辟谣内容发布,来做第一个辟谣者吧!",
    }
