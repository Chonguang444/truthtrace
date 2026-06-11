"""
辟谣视频脚本生成器

基于中国食品报融媒体的辟谣模式分析，自动生成可直接录制的辟谣视频脚本。
包含: 前3秒身份声明→谣言陈述→事实楔子→证据展示→成本逻辑→呼吁行动
"""

from datetime import datetime, timezone


def generate_debunk_script(
    rumor_claim: str = "",
    verified_facts: list[str] | None = None,
    evidence_sources: list[str] | None = None,
    cost_reasoning: dict | None = None,
    tone: str = "authoritative",
    duration_sec: int = 60,
) -> dict:
    """
    生成辟谣视频脚本。

    Args:
        rumor_claim: 原始谣言主张
        verified_facts: 验证后的事实列表
        evidence_sources: 证据来源 URL 列表
        cost_reasoning: 成本推演结果 (来自 correction_agent.generate_cost_reasoning)
        tone: 语气 (authoritative/expert/casual)
        duration_sec: 目标时长 (30/60/90秒)

    Returns:
        结构化的视频脚本
    """
    verified_facts = verified_facts or []
    evidence_sources = evidence_sources or []

    rumor_short = rumor_claim[:120] if rumor_claim else "该信息"

    # === Scene 1: Hook — 前3秒身份声明 ===
    hook_options = {
        "authoritative": f"辟谣声明：关于「{rumor_short}」的说法——不属实。我是{get_title(tone)}，今天用{len(verified_facts) + (1 if cost_reasoning and cost_reasoning.get('matched') else 0)}个事实拆解这条谣言。",
        "expert": f"作为{get_title(tone)}，我看到「{rumor_short}」这条内容时，发现了一个关键问题。今天用专业视角帮你拆解。",
        "casual": f"你是不是也看到过「{rumor_short}」？今天告诉你为什么它是错的——而且只用1分钟。",
    }
    hook = hook_options.get(tone, hook_options["authoritative"])

    # === Scene 2: Rumor statement — 公正呈现谣言 ===
    rumor_statement = f"先说这条信息说了什么：{rumor_short}"

    # === Scene 3: Fact wedge — 用一个无可辩驳的事实击穿 ===
    fact_wedge = ""
    if verified_facts:
        fact_wedge = f"事实是：{verified_facts[0]}"

    # === Scene 4: Evidence — 具体证据展示 ===
    evidence_scenes = []
    for i, fact in enumerate(verified_facts[:3]):
        source = evidence_sources[i] if i < len(evidence_sources) else ""
        scene = {
            "scene": i + 1,
            "narration": fact,
            "on_screen": f"来源: {source[:80]}" if source else "来源: 权威数据",
            "visual": "展示原文截图/数据图表/工艺流程图" if i == 0 else "对比展示谣言vs事实",
        }
        evidence_scenes.append(scene)

    # === Scene 5: Cost logic — 成本推演 (如果有) ===
    cost_scene = None
    if cost_reasoning and cost_reasoning.get("matched"):
        cost_scene = {
            "narration": cost_reasoning.get("logic", ""),
            "on_screen": cost_reasoning.get("breakdown", ""),
            "visual": "价格对比图表/成本数字跳动动画",
        }

    # === Scene 6: Call to action ===
    cta_options = {
        "authoritative": "不造谣、不信谣、不传谣。遇到不确定的信息，先用搜索引擎查证来源。",
        "expert": "如果你对这类信息有疑问，欢迎在评论区提问——我会用专业知识帮你解答。",
        "casual": "下次看到类似的信息，记得想一想：这是真的吗？有什么证据？别急着转。",
    }
    cta = cta_options.get(tone, cta_options["authoritative"])

    # === Assemble script ===
    scenes = [{
        "scene": 1, "duration_sec": 5,
        "type": "hook", "narration": hook,
        "on_screen_text": f"辟谣: {rumor_short[:50]}",
        "visual_suggestion": "出镜+大字标题+身份标识",
    }, {
        "scene": 2, "duration_sec": 8,
        "type": "rumor_statement", "narration": rumor_statement,
        "on_screen_text": rumor_short[:80],
        "visual_suggestion": "引用原文截图(带模糊效果)+红色方框标注",
    }]

    if fact_wedge:
        scenes.append({
            "scene": 3, "duration_sec": 10,
            "type": "fact_wedge", "narration": fact_wedge,
            "on_screen_text": verified_facts[0][:80] if verified_facts else "",
            "visual_suggestion": "权威来源截图/绿色对勾动画",
        })

    for escene in evidence_scenes:
        scenes.append({
            "scene": len(scenes) + 1,
            "duration_sec": 10,
            "type": "evidence",
            "narration": escene["narration"],
            "on_screen_text": escene["on_screen"][:80],
            "visual_suggestion": escene["visual"],
        })

    if cost_scene:
        scenes.append({
            "scene": len(scenes) + 1, "duration_sec": 8,
            "type": "cost_logic",
            "narration": cost_scene["narration"],
            "on_screen_text": cost_scene["on_screen"][:80],
            "visual_suggestion": cost_scene["visual"],
        })

    scenes.append({
        "scene": len(scenes) + 1, "duration_sec": 8,
        "type": "call_to_action", "narration": cta,
        "on_screen_text": "不造谣 不信谣 不传谣",
        "visual_suggestion": "出镜+总结要点列表",
    })

    total_dur = sum(s["duration_sec"] for s in scenes)
    hashtags = ["辟谣", "真相", "事实核查", rumor_short[:10]]

    return {
        "title": f"辟谣: {rumor_short[:50]}",
        "duration_sec": total_dur,
        "tone": tone,
        "total_scenes": len(scenes),
        "scenes": scenes,
        "hashtags": hashtags,
        "production_tips": [
            "前3秒必须出镜+身份声明建立信任",
            "用大号字体在屏幕上展示关键数据",
            "谣言原文要用红色框/模糊效果区分——避免被误读为你在传播谣言",
            "引用来源时截图要清晰可读",
            "结尾加上你的频道Logo和水印——好的辟谣内容会被二次传播",
        ],
    }


def get_title(tone: str) -> str:
    return {
        "authoritative": "TruthTrace 事实核查员",
        "expert": "本领域研究员",
        "casual": "你的信息可信度助手",
    }.get(tone, "信息核查员")
