"""
辟谣内容创作工坊 API -- AI辟谣文章/海报/短视频脚本/多平台分发
把10引擎分析结果转化为传播力强的辟谣内容
"""

import os
import uuid
import random
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, field_validator

from app.auth.jwt import get_current_active_user
from app.models.user import User

router = APIRouter()

# =============================================================================
# 数据模型
# =============================================================================

class ArticleGenerateRequest(BaseModel):
    event_id: str
    tone: str = "balanced"  # balanced/firm/educational/empathetic

    @field_validator("tone")
    @classmethod
    def valid_tone(cls, v: str) -> str:
        valid = {"balanced", "firm", "educational", "empathetic"}
        if v not in valid:
            raise ValueError(f"语气必须是: {', '.join(valid)}")
        return v


class PosterRequest(BaseModel):
    event_id: str
    style: str = "minimal"  # minimal/impact/infographic


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
    platform: str  # weibo/xiaohongshu/douyin/twitter
    include_hashtags: bool = True


class PublishTrackRequest(BaseModel):
    event_id: str
    platform: str
    publish_url: str


# =============================================================================
# 模拟引擎分析数据 (用于生成内容)
# =============================================================================

def _get_mock_engine_analysis(event_id: str) -> dict:
    """获取模拟引擎分析结果"""
    seed = hash(event_id) % 100
    rng = random.Random(seed)

    distortions = rng.sample([
        {"type": "source_fabrication", "desc": "来源伪造----引用的研究无法查证", "snippet": "据最新研究...", "confidence": "high"},
        {"type": "context_stripping", "desc": "脱离剂量谈毒性", "snippet": "含致癌物质!", "confidence": "high"},
        {"type": "emotional_manipulation", "desc": "利用紧迫性催促转发", "snippet": "速看!马上被删!", "confidence": "moderate"},
        {"type": "authority_abuse", "desc": "虚假权威背书", "snippet": "获FDA认可", "confidence": "moderate"},
        {"type": "misquotation", "desc": "错误引用研究结论", "snippet": "研究表明...", "confidence": "high"},
    ], rng.randint(1, 3))

    fallacies = rng.sample([
        {"type": "false_cause", "desc": "误将相关当作因果", "correction": "时间先后≠因果关系"},
        {"type": "equivocation", "desc": "天然=安全的概念偷换", "correction": "天然≠安全,毒蘑菇也是天然的"},
        {"type": "slippery_slope", "desc": "滑坡论证", "correction": "每个步骤需要独立验证,不能跳跃推理"},
        {"type": "false_dichotomy", "desc": "虚假二分", "correction": "存在多种中间立场和可能性"},
        {"type": "hasty_generalization", "desc": "以偏概全", "correction": "个案例不能推断整体"},
    ], rng.randint(1, 3))

    return {
        "verdict": rng.choice(["likely_false", "false", "misleading"]),
        "credibility_score": rng.uniform(5, 25),
        "distortion_analysis": {"matches": distortions},
        "fallacy_analysis": {
            "matches": [{"fallacy_type": f["type"], "description": f["desc"], "correction_hint": f["correction"], "evidence_snippet": f"涉及: {f['type']}"} for f in fallacies],
            "fallacy_count": len(fallacies),
        },
        "narrative_analysis": {
            "dominant_narrative": rng.choice(["fear_mongering", "conspiracy_theory", "us_vs_them", "scientism_abuse"]),
            "manipulation_score": rng.uniform(40, 80),
        },
        "summary": "该信息存在多处信息操纵手法。",
    }


# =============================================================================
# Claude API 调用 (如可用)
# =============================================================================

async def _call_claude_if_available(prompt: str, max_tokens: int = 2000) -> Optional[str]:
    """如果 ANTHROPIC_API_KEY 可用则调用 Claude, 否则返回 None"""
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
                data = resp.json()
                return data["content"][0]["text"]
    except Exception:
        pass
    return None


# =============================================================================
# 端点: AI 辟谣文章生成
# =============================================================================

@router.post("/studio/generate-article")
async def generate_article(
    req: ArticleGenerateRequest,
    current_user: User = Depends(get_current_active_user),
):
    """生成AI辟谣文章草稿"""
    analysis = _get_mock_engine_analysis(req.event_id)

    # 构建prompt
    distortions_text = "\n".join(
        f"- {d['desc']} (置信度: {d['confidence']})"
        for d in analysis.get("distortion_analysis", {}).get("matches", [])
    )
    fallacies_text = "\n".join(
        f"- {f['description']} → 纠偏: {f['correction_hint']}"
        for f in analysis.get("fallacy_analysis", {}).get("matches", [])
    )

    tone_instructions = {
        "balanced": "以中立、客观的语气写作,先呈现原始说法再提供事实核查结果。",
        "firm": "以坚定但不攻击性的语气写作,明确指出错误但避免妖魔化传播者。",
        "educational": "以教育性的语气写作,把读者当作学习者,解释为什么这种说法有问题以及如何识别。",
        "empathetic": "以同理心的语气写作,理解读者为什么会相信这些信息,同时温和地提供正确信息。",
    }

    prompt = f"""你是一个专业的事实核查和辟谣内容创作者。请根据以下引擎分析结果撰写一篇辟谣文章。

【原始信息问题】
可信度评分: {analysis['credibility_score']:.0f}/100
综合判定: {analysis['verdict']}
主导叙事框架: {analysis.get('narrative_analysis', {}).get('dominant_narrative', '未知')}
操纵性评分: {analysis.get('narrative_analysis', {}).get('manipulation_score', 0):.0f}/100

【检测到的信息失真】
{distortions_text if distortions_text else '未检测到明显失真'}

【检测到的逻辑谬误】
{fallacies_text if fallacies_text else '未检测到明显谬误'}

【写作要求】
语气: {tone_instructions.get(req.tone, tone_instructions['balanced'])}
标题: 10-20字,吸引人但不标题党
结构: 谣言原文引用 → 逐条分析 → 事实核查结论 → 如何识别类似信息
字数: 800-1200字
每一条反驳都要有证据支撑
不确定的地方明确说"目前无法确认"

请输出格式化的辟谣文章。"""

    # 尝试调用 Claude
    ai_text = await _call_claude_if_available(prompt, max_tokens=2000)

    if ai_text:
        lines = ai_text.strip().split("\n")
        title = lines[0].replace("#", "").strip() if lines else "辟谣报告"
        body = "\n".join(lines[1:]) if len(lines) > 1 else ai_text
    else:
        # 模拟生成
        title = f"辟谣: {analysis.get('verdict', '可疑信息')}的真相"
        body = _generate_mock_article(analysis, req.tone)

    sections = _parse_article_sections(body)

    return {
        "event_id": req.event_id,
        "title": title,
        "sections": sections,
        "tone": req.tone,
        "word_count": len(body),
        "engine_verdict": analysis["verdict"],
        "credibility_score": analysis["credibility_score"],
        "generated_by": "claude-api" if ai_text else "template-engine",
        "disclaimer": "本文由AI辅助生成,基于TruthTrace引擎分析结果。请人工审核后发布。",
    }


def _generate_mock_article(analysis: dict, tone: str) -> str:
    """生成模拟辟谣文章"""
    verdict = analysis.get("verdict", "可疑信息")
    score = analysis.get("credibility_score", 20)

    return f"""## 事件概述
该信息经TruthTrace引擎分析,可信度评分为{score:.0f}/100,综合判定为"{verdict}"。

## 主要问题
{analysis.get('summary', '该信息存在多处信息操纵。')}

## 信息失真分析
该信息使用了多种信息操纵手法。建议读者在转发前先核实信息来源和科学依据。

## 如何识别类似信息
1. 检查信息来源: 是否有具体的机构名称、研究报告链接？
2. 注意情绪操纵: 是否使用了"速看""马上被删""不转不是XX"等催促性语言？
3. 查阅权威渠道: 涉及健康信息可查WHO/国家卫健委官网。

## 结论
基于目前可获得的证据,该信息的可信度{score:.1f}分为"{verdict}"。建议以权威部门发布的信息为准。

*本文由TruthTrace辟谣工坊生成,事实核查结果基于10引擎推理管线。*"""


def _parse_article_sections(text: str) -> list[dict]:
    """解析文章为章节"""
    sections = []
    current_heading = ""
    current_content = []

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            if current_heading and current_content:
                sections.append({
                    "heading": current_heading,
                    "content": "\n".join(current_content),
                })
                current_content = []
            continue
        if line.startswith("##"):
            if current_heading and current_content:
                sections.append({
                    "heading": current_heading,
                    "content": "\n".join(current_content),
                })
                current_content = []
            current_heading = line.replace("##", "").strip()
        else:
            current_content.append(line)

    if current_heading or current_content:
        sections.append({
            "heading": current_heading or "正文",
            "content": "\n".join(current_content),
        })

    return sections if sections else [{"heading": "正文", "content": text}]


# =============================================================================
# 端点: 辟谣海报生成
# =============================================================================

@router.post("/studio/generate-poster")
async def generate_poster(
    req: PosterRequest,
    current_user: User = Depends(get_current_active_user),
):
    """生成辟谣海报数据(前端Canvas渲染)"""
    analysis = _get_mock_engine_analysis(req.event_id)

    # 提取核心事实
    rumor_texts = []
    for d in analysis.get("distortion_analysis", {}).get("matches", []):
        rumor_texts.append(d.get("snippet", ""))

    main_fact = f"经TruthTrace {10}引擎分析,该信息可信度仅{analysis['credibility_score']:.0f}/100分"

    return {
        "event_id": req.event_id,
        "style": req.style,
        "truth_card": {
            "title": "事实核查",
            "rumor_label": "网络说法",
            "rumor_text": "; ".join(rumor_texts[:2]) if rumor_texts else "该信息包含未经验证的说法",
            "fact_label": "核查结果",
            "fact_text": main_fact,
            "credibility_badge": {
                "score": round(analysis["credibility_score"]),
                "label": analysis["verdict"],
                "color": "#ef4444" if analysis["credibility_score"] < 30 else "#f59e0b",
            },
            "key_findings": [
                {"icon": "magnifier", "text": f"检测到 {len(analysis.get('distortion_analysis', {}).get('matches', []))} 种信息失真"},
                {"icon": "brain", "text": f"检测到 {analysis.get('fallacy_analysis', {}).get('fallacy_count', 0)} 个逻辑谬误"},
                {"icon": "chart", "text": f"操纵性评分: {analysis.get('narrative_analysis', {}).get('manipulation_score', 0):.0f}/100"},
            ],
            "share_text": f"【事实核查】{main_fact}。查看完整分析: https://truthtrace.app/events/{req.event_id}",
        },
        "colors": {
            "minimal": {"bg": "#ffffff", "text": "#1a1a2e", "accent": "#2563eb", "danger": "#ef4444"},
            "impact": {"bg": "#1a1a2e", "text": "#ffffff", "accent": "#f59e0b", "danger": "#ef4444"},
            "infographic": {"bg": "#f8fafc", "text": "#0f172a", "accent": "#0891b2", "danger": "#dc2626"},
        }.get(req.style, {}),
    }


# =============================================================================
# 端点: 短视频脚本
# =============================================================================

@router.post("/studio/generate-script")
async def generate_script(
    req: ScriptRequest,
    current_user: User = Depends(get_current_active_user),
):
    """生成辟谣短视频脚本"""
    analysis = _get_mock_engine_analysis(req.event_id)
    duration = req.duration_sec
    num_scenes = duration // 15  # 每15秒一个场景

    scene_templates = [
        {
            "narration": "最近,一条关于[X]的信息在网上广泛传播。",
            "on_screen_text": "⚠️ 网络热传信息",
            "visual_suggestion": "手机屏幕滚动展示原始谣言的截图和转发数",
        },
        {
            "narration": f"经TruthTrace系统分析,该信息可信度仅{analysis['credibility_score']:.0f}分。",
            "on_screen_text": f"可信度: {analysis['credibility_score']:.0f}/100",
            "visual_suggestion": "大号可信度仪表盘指针转动到红色区域",
        },
        {
            "narration": "我们检测到了信息失真和逻辑谬误。比如,它将相关关系当作因果关系。",
            "on_screen_text": "❌ 相关 ≠ 因果",
            "visual_suggestion": "并排显示两个图表,标注\"这只是相关,不是因果\"",
        },
        {
            "narration": "那么事实是什么？根据权威机构的数据,实际的情况是...",
            "on_screen_text": "✅ 事实核查",
            "visual_suggestion": "翻转卡片效果,从谣言翻到事实",
        },
    ]

    scenes = []
    for i in range(min(num_scenes, len(scene_templates))):
        t = scene_templates[i]
        scenes.append({
            "scene": i + 1,
            "duration_sec": 15,
            "narration": t["narration"],
            "on_screen_text": t["on_screen_text"],
            "visual_suggestion": t["visual_suggestion"],
            "transition": "fade" if i < num_scenes - 1 else "end_card",
        })

    # 如果场景不够,补充
    while len(scenes) < num_scenes:
        scenes.append({
            "scene": len(scenes) + 1,
            "duration_sec": 15,
            "narration": "学会识别信息操纵,从今天开始做聪明的信息消费者。",
            "on_screen_text": "🔍 批判性思维",
            "visual_suggestion": "TruthTrace Logo + 下载二维码",
            "transition": "end_card",
        })

    return {
        "event_id": req.event_id,
        "duration_sec": duration,
        "scenes": scenes,
        "total_scenes": len(scenes),
        "hashtags": ["#事实核查", "#辟谣", "#信息素养", "#CriticalThinking"],
        "end_card": {
            "text": "下载TruthTrace,获取实时事实核查",
            "qr_url": "https://truthtrace.app/download",
        },
        "production_tips": [
            "每个场景建议配上简洁的图标或文字动画",
            "旁白语速建议每分钟180-200字",
            "背景音乐推荐轻快的科技风格(如Upbeat Technology)",
            "关键数据可添加音效强调",
        ],
    }


# =============================================================================
# 端点: 多平台分发格式化
# =============================================================================

@router.post("/studio/format-for-platform")
async def format_for_platform(
    req: PlatformFormatRequest,
    current_user: User = Depends(get_current_active_user),
):
    """将辟谣内容格式化为各平台适用格式"""
    content = req.content
    platform = req.platform
    hashtags = "#事实核查 #辟谣 #TruthTrace" if req.include_hashtags else ""

    formatters = {
        "weibo": lambda c: {
            "platform": "微博",
            "max_length": 140,
            "formatted": f"{c[:120]}...{hashtags}" if len(c) > 120 else f"{c} {hashtags}",
            "tips": ["使用短链接(如t.cn)指向完整报告", "配图比纯文字传播力强3倍", "黄金发布时段: 12:00-14:00, 20:00-22:00"],
        },
        "xiaohongshu": lambda c: {
            "platform": "小红书",
            "formatted": f"📋 事实核查报告\n\n{c[:300]}\n\n---\n🔍 以上分析由TruthTrace引擎自动生成\n💡 学会识别信息操纵,做聪明的信息消费者\n\n{hashtags}",
            "tips": ["封面图要突出核心数据(如: 可信度12/100)", "正文前3行决定阅读率,要抓眼球", "使用小红书的\"合辑\"功能做系列辟谣"],
        },
        "douyin": lambda c: {
            "platform": "抖音",
            "formatted": f"{c[:200]}\n\n{hashtags}",
            "tips": ["视频前3秒必须抛出悬念(如: 这条信息可信度只有12分?)", "使用热门BGM增加推荐概率", "评论区置顶完整报告链接"],
        },
        "twitter": lambda c: {
            "platform": "Twitter/X",
            "formatted": f"Fact check: {c[:200]}\n\nSource: TruthTrace AI Analysis\n{hashtags}" if len(c) > 200 else f"{c}\n\nSource: TruthTrace\n{hashtags}",
            "tips": ["使用Thread功能发布长文分析", "配数据可视化截图", "标记相关权威机构账号"],
        },
    }

    fn = formatters.get(platform)
    if not fn:
        raise HTTPException(400, f"不支持的平台: {platform}。支持: {', '.join(formatters.keys())}")

    result = fn(content)
    return {
        "original_length": len(content),
        **result,
        "original_content": content,
    }


# =============================================================================
# 端点: 发布追踪
# =============================================================================

_publish_records: list[dict] = []


@router.post("/studio/track-publish")
async def track_publish(
    req: PublishTrackRequest,
    current_user: User = Depends(get_current_active_user),
):
    """记录用户发布的辟谣链接"""
    record = {
        "id": str(uuid.uuid4())[:8],
        "user_id": str(current_user.id),
        "username": current_user.username,
        "event_id": req.event_id,
        "platform": req.platform,
        "publish_url": req.publish_url,
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    _publish_records.append(record)
    return {"status": "tracked", "record": record}


@router.get("/studio/publish-stats/{event_id}")
async def publish_stats(event_id: str):
    """辟谣效果统计"""
    records = [r for r in _publish_records if r["event_id"] == event_id]

    platform_counts = {}
    for r in records:
        platform_counts[r["platform"]] = platform_counts.get(r["platform"], 0) + 1

    return {
        "event_id": event_id,
        "total_publishes": len(records),
        "by_platform": platform_counts,
        "publishers": [r["username"] for r in records],
        "message": (
            f"已有 {len(records)} 位用户发布了针对此事件的辟谣内容"
            if records else "此事件还没有辟谣内容发布,来做第一个辟谣者吧!"
        ),
    }
