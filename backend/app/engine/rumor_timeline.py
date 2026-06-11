"""
谣言制造过程时间线生成器

基于落九川视频的启示: 最有效的辟谣不是"告诉你什么是对的"，
而是"让你看到谣言是怎么被造出来的"。

生成: 造谣步骤时间线 + 每步被歪曲的标注 + 被忽略的上下文
"""
import re
from dataclasses import dataclass, field


@dataclass
class TimelineStep:
    step: int
    phase: str           # "search" | "extract" | "distort" | "amplify"
    description: str     # 这一步骤做了什么
    original_text: str   # 原始被引用的内容
    distorted_text: str  # 被歪曲后的版本
    distortion_type: str # 歪曲类型
    evidence: str        # 如何证明被歪曲


@dataclass
class RumorTimeline:
    """完整的谣言制造过程"""
    rumor_title: str = ""
    rumor_summary: str = ""
    steps: list[TimelineStep] = field(default_factory=list)
    verdict: str = ""
    reveals: list[str] = field(default_factory=list)  # 这条时间线揭示的关键教训

    def to_dict(self) -> dict:
        return {
            "rumor_title": self.rumor_title,
            "rumor_summary": self.rumor_summary,
            "steps": [
                {
                    "step": s.step, "phase": s.phase,
                    "description": s.description,
                    "original_text": s.original_text[:200],
                    "distorted_text": s.distorted_text[:200],
                    "distortion_type": s.distortion_type,
                    "evidence": s.evidence[:200],
                }
                for s in self.steps
            ],
            "verdict": self.verdict,
            "reveals": self.reveals,
        }


# =============================================================================
# 已识别的标准造谣模式
# =============================================================================

KNOWN_RUMOR_TEMPLATES = {
    "context_stripping": {
        "pattern": "把结论从上下文中剥离",
        "steps": [
            ("search", "找到一篇包含特定数据的论文/报道"),
            ("extract", "只截取结论句，去掉所有限定条件（如'在特定条件下''高剂量''动物实验'等）"),
            ("distort", "将限定条件下的结论转化为绝对陈述：'XX会导致YY'"),
            ("amplify", "配以情绪化标题和图片在社交媒体传播"),
        ],
        "example": "IARC将阿斯巴甜列为2B类致癌物 → 自媒体提取'致癌' → 去掉'2B类（证据有限）'和ADI背景 → 变为'阿斯巴甜致癌！'",
    },
    "quote_fabrication": {
        "pattern": "伪造专家引述",
        "steps": [
            ("search", "找到一个权威机构或专家的名字"),
            ("extract", "完全不引用实际原文——直接编造一句'专家说'"),
            ("distort", "将科学界共识反着说"),
            ("amplify", "用'XX专家揭露''内部人士曝料'等标题发布"),
        ],
        "example": "WHO从未说过疫苗导致自闭症 → 自媒体：'WHO专家揭露：疫苗与自闭症有关联'",
    },
    "timeline_manipulation": {
        "pattern": "时间线压缩嫁接",
        "steps": [
            ("search", "找到A事件（旧）和B事件（新）"),
            ("extract", "只显示B事件发生后的结果"),
            ("distort", "暗示B是A的原因——但A实际上发生在B之后"),
            ("amplify", "用'自从XX以来YY就…'句式传播"),
        ],
        "example": "新疫苗2023年获批 → 2020年的自闭症数据上升 → '自从新疫苗接种以来，自闭症激增'（但实际上趋势在疫苗前就存在）",
    },
}


def generate_rumor_timeline(
    rumor_text: str = "",
    detected_distortions: list[str] | None = None,
    detected_fallacies: list[str] | None = None,
) -> RumorTimeline:
    """
    为一条谣言自动生成"它是怎么被造出来的"时间线。

    基于检测到的失真/谬误类型，匹配已知的造谣模板，还原造谣者的操作步骤。
    """
    timeline = RumorTimeline(
        rumor_title=rumor_text[:120] if rumor_text else "未知谣言",
        rumor_summary=rumor_text[:300] if rumor_text else "",
        verdict="该谣言的制造过程被还原如下",
    )

    detected_distortions = detected_distortions or []
    detected_fallacies = detected_fallacies or []

    # 匹配已知模板
    matched_template = None
    if "context_stripping" in str(detected_distortions).lower() or "语境剥离" in str(detected_distortions):
        matched_template = "context_stripping"
    elif "source_fabrication" in str(detected_distortions).lower() or "源头伪造" in str(detected_distortions):
        matched_template = "quote_fabrication"
    elif "post_hoc" in str(detected_fallacies).lower() or "后此" in str(detected_fallacies):
        matched_template = "timeline_manipulation"

    # 生成步骤
    if matched_template and matched_template in KNOWN_RUMOR_TEMPLATES:
        template = KNOWN_RUMOR_TEMPLATES[matched_template]
        for i, (phase, desc) in enumerate(template["steps"]):
            timeline.steps.append(TimelineStep(
                step=i + 1,
                phase=phase,
                description=desc,
                original_text=f"[还原] {template['example']}",
                distorted_text=f"[造谣者版本] {template['example']}",
                distortion_type=template["pattern"],
                evidence=f"可查证原始来源/限制条件验证",
            ))

    # 通用步骤 (如果没有匹配到特定模板)
    if not timeline.steps:
        generic_steps = [
            ("search", "造谣者搜索相关主题的真实信息"),
            ("extract", "从真实信息中提取部分内容——选择性忽略关键限定条件"),
            ("distort", "将内容重新包装：添加情绪化词汇、去除不确定性、添加虚假权威"),
            ("amplify", "在社交平台发布，利用算法推荐和情绪驱动获得传播"),
        ]
        for i, (phase, desc) in enumerate(generic_steps):
            timeline.steps.append(TimelineStep(
                step=i + 1,
                phase=phase,
                description=desc,
                original_text="[需人工提供原始来源]",
                distorted_text="[检测到的失真片段]",
                distortion_type="通用造谣模式",
                evidence="正在分析中",
            ))

    # 揭示的教训
    timeline.reveals = [
        "谣言制造的核心不是'编造全新信息'，而是'对真实信息的歪曲重组'",
        "每一个谣言背后都有一条可追溯的真实信息——只是被歪曲了",
        "学会'溯源'比学会'记正确答案'更重要——真相可能被重新包装但不会消失",
        "当你看到一条让你愤怒/恐惧的消息时，先问：这个结论的原始出处是什么？限定条件被保留了吗？",
    ]

    return timeline
