"""
逻辑谬误检测引擎 — 12 种常见逻辑谬误的形式化检测

检测原则:
- 每种谬误都有形式化定义和检测规则
- 返回原文片段作为证据
- 每个检测附带纠偏提示——帮助读者理解为什么这是谬误
- 注意区分"模式匹配"和"事实判定"——引擎只提示潜在谬误，不做最终定论
"""

from __future__ import annotations
import re
from app.engine.types import (
    FallacyType, FallacyMatch, FallacyAnalysis, Confidence
)


# =============================================================================
# 1. 因果倒置 / 虚假因果 (FALSE_CAUSE)
# =============================================================================
# post hoc ergo propter hoc — 仅仅因为B发生在A之后就认为是A导致B
# cum hoc ergo propter hoc — 将相关性当作因果性

FALSE_CAUSE_PATTERNS = [
    (r"(?:自从|自从有了?|从|打从).{0,20}(?:以后|之后|后|以来).{0,20}(?:就|便|于是|开始|出现|发生)",
     "将先后关系表述为因果关系 (post hoc ergo propter hoc)"),
    (r"(?:因为|由于|正因为).{0,30}(?:所以|因此|于是|导致|造成|引起|引发了?)",
     "直接的因果声明——需要检查A是否真的是B的充分原因"),
    (r"(?:数据|统计|调查|研究).{0,15}(?:显示|表明).{0,15}(?:相关|关联|correlation).{0,20}(?:所以|因此|说明|证明|意味着)",
     "将相关关系升级为因果关系 (correlation ≠ causation)"),
    (r"(?:就是|肯定?是|绝对|一定)(?:因为|由于|...的原因|造成的|导致的)",
     "绝对化的因果归因——复杂现象通常有多重原因"),
    (r"(?:XX|某某|某).{0,5}事件.{0,10}(?:之后|以后).{0,15}(?:经济|股市|房价|汇率|物价).{0,10}(?:\w+了)",
     "将宏观事件简单归因于单一事件——忽略了多重因素"),
]


# =============================================================================
# 2. 滑坡论证 (SLIPPERY_SLOPE)
# =============================================================================
# 如果允许A发生，那么B就会发生，然后C就会发生......最终导致灾难Z
# 问题: 每一步的概率都不是100%，链条越长概率越低

SLIPPERY_SLOPE_PATTERNS = [
    (r"(?:如果|一旦|只要).{0,20}(?:允许|放任|不管|开了?这个).{0,20}(?:那么|就会|就).{0,20}(?:接着|然后|之后|进而|更进一步|最终)",
     "滑坡论证: 从一件小事推导出一连串越来越严重的后果，但每步的概率并未论证"),
    (r"(?:今天.{0,10}).{0,5}(?:明天|下次|回头).{0,5}.{0,10}(?:后天|最后|最终).{0,5}",
     "典型滑坡叙事: 今天...明天...后天... 步步升级"),
    (r"(?:先.{0,5}).{0,5}(?:然后|接着|之后).{0,5}.{0,5}(?:最后|最终|到头来).{0,5}",
     "逐步升级的后果链——每步需要独立证明"),
    (r"(?:第一步|首先).{0,30}(?:第二步|其次|接着|然后).{0,30}(?:最后|最终|结果|结局)",
     "明确列出了步骤链条——需要证实每步的必然性"),
]


# =============================================================================
# 3. 虚假二分 (FALSE_DICHOTOMY)
# =============================================================================
# 将复杂问题简化为两个对立选项，忽略了中间地带和第三种可能

FALSE_DICHOTOMY_PATTERNS = [
    (r"(?:要么|不是).{0,20}(?:要么|就是).{0,20}(?![\s\S]{0,20}(?:或者|还有|此外|另外|也))",
     "非此即彼的二分法——忽略了其他可能性"),
    (r"(?:不.{0,3})?支持.{0,5}(?:就是|等于是|意味着).{0,10}反对",
     "'不支持=反对'的虚假二分"),
    (r"(?:\S+和\S+)(?:只能|必须|一定要)(?:选|选择|...的)(?:一个|一种|一)个",
     "迫使在两者之间做选择的虚假二分"),
    (r"(?:如果你?不).{0,20}(?:那你?就是|就说明你是|就等于|意味着你是)",
     "'你不做A=你是B'的虚假二分"),
    (r"(?:只有).{0,15}(?:才能|才可以).{0,20}(?:否则|不然).{0,10}(?:就会|就是|只能)",
     "'只有A才能B，否则就C'——排除了其他途径"),
]


# =============================================================================
# 4. 偷换概念 (EQUIVOCATION)
# =============================================================================
# 在论证中变换词语的含义或将不同概念混为一谈

EQUIVOCATION_PATTERNS = [
    (r"(?:就是|等于|相当于|本质上是|其实就?是)(?![\s\S]{0,15}(?:定义|界定的?|共识))",
     "将一个概念等同于另一个概念——可能发生了概念漂移"),
    (r"(?:自然|天然)(?:的|地|地).{0,10}(?:所以|因此|就|意味着|等于|说明).{0,10}(?:安全|无害|健康|好)",
     "'天然=安全'的概念偷换——天然物质同样可能有毒"),
    (r"(?:传统|老祖宗|千年|自古).{0,10}(?:所以|因此|说明|证明|肯定|就是).{0,10}(?:好|对|安全|有效|正确)",
     "'传统=正确'的概念偷换——诉诸传统的谬误"),
    (r"(?:化学|人工|合成|添加剂|转基因).{0,5}(?:的|...).{0,10}(?:全是|都是|肯定|一定|就是).{0,10}(?:有害|有毒|不好|坏的?)",
     "'化学/人工=有害'的概念偷换——天然≠安全，化学≠有毒"),
]


# =============================================================================
# 5. 诉诸情感 (APPEAL_TO_EMOTION)
# =============================================================================
# 用情感代替理性论证

APPEAL_TO_EMOTION_PATTERNS = [
    (r"(?:想想|考虑一下|如果.{0,5}是)(?:你的?|你们的?)(?:孩子|父母|家人|亲人|爱人)",
     "诉诸对家人的保护情感——替换了理性论证"),
    (r"(?:忍心|忍心看到|忍心让|忍心看着).{0,15}(?:受苦|遭罪|受难)",
     "诉诸不忍/同情——替代了事实判断"),
    (r"(?:让人|令人|使人)(?:愤怒|气愤|恶心|恐怖|恐惧|可怕|害怕|震惊|发指)",
     "通过引发强烈情绪来替代理性讨论"),
    (r"(?:看到|看完|读).{0,5}(?:我|笔者|我).{0,5}(?:哭了|流泪|泪目|心碎|心寒|心酸|心凉)",
     "以个人情绪体验替代客观论证"),
]


# =============================================================================
# 6. 诉诸虚假权威 (APPEAL_TO_AUTHORITY)
# =============================================================================

APPEAL_TO_AUTHORITY_PATTERNS = [
    (r"(?:一个|有位?|某)(?:老中医|老农民|老人家|前辈|过来人|内行)(?:说|过|的?话)",
     "引用'老中医/老农民'等非特定权威——无法验证"),
    (r"(?:诺贝尔奖|院士|教授|博士|专家).{0,10}(?:说|认为|指出).{0,30}(?![\s\S]{0,30}(?:研究领域|专业领域|本专业))",
     "引用权威人物但不说明其是否在相关领域有资质"),
    (r"(?:据说|听说|传说|坊间传闻|民间说法)(?![\s\S]{0,20}(?:考证|核实|查证|验证))",
     "以'据说/听说'作为信息来源"),
]


# =============================================================================
# 7. 以偏概全 (HASTY_GENERALIZATION)
# =============================================================================

HASTY_GENERALIZATION_PATTERNS = [
    (r"(?:一个|某个|有个|见过?|遇到过?|经历.{0,3})(?:案例|例子|人|事|情况|现象).{0,20}(?:所以|说明|证明|意味着|可见).{0,10}(?:所有|全部|都|每个|任何|整个|凡是)",
     "从个别案例跳跃到普遍结论——样本量不足"),
    (r"(?:我|我们?|本人|笔者)(?:身边|周围|附近|认识的?|看到的?).{0,15}(?:都是|都没有?|全都|从来都?没)\w",
     "以个人观察/身边经验代表整体情况——存在严重的样本偏差"),
    (r"(?:外国|国外|人家|发达国家).{0,10}(?:都|全都|从来都?|全部).{0,30}(?:中国|我们|我国|国内)(?:却|没有|不|做不到)",
     "以国外的部分情况概括全部，并与国内做不当对比"),
]


# =============================================================================
# 8. 稻草人谬误 (STRAW_MAN)
# =============================================================================

STRAW_MAN_PATTERNS = [
    (r"(?:\S+们?|有些人?|某些人)(?:不就是|不就是?说|无非是|说白了就是|其实就是).{0,30}(?:吗|嘛|吧|而已)",
     "将对方观点简单化/极端化后进行攻击——稻草人谬误"),
    (r"(?:按\S+们?的说法|照\S+们?的意思|如果按\S+们?的逻辑).{0,40}(?:那|那么|岂不是|是不是).{0,20}(?:也|都|就)",
     "将对方观点延伸至荒谬境地——稻草人谬误"),
    (r"(?:难道|莫非).{0,20}(?:就|才是).{0,10}(?:对|正确|合理|可以)(?:吗|\?)",
     "反问形式构建稻草人——歪曲对方立场后攻击"),
]


# =============================================================================
# 9. 转移话题 (RED_HERRING)
# =============================================================================

RED_HERRING_PATTERNS = [
    (r"(?:那|那么|那你?怎么|那你?为什么)(?:不说|不看|不管|不提).{0,20}(?:呢|\?)",
     "用'那XX又怎么说'转移焦点——whataboutism"),
    (r"(?:先不说|先不管|且不提|暂且不论|咱先不说).{0,30}(?:就说|就说这?|你?看看).{0,20}",
     "先承认A但立即转移话题到B"),
    (r"(?:重要的?不是).{0,20}(?:而是|重要的是?|关键的是?|问题是)",
     "转移焦点——从可讨论的事实转向另一个话题"),
]


# =============================================================================
# 10. 循环论证 (BEGGING_THE_QUESTION)
# =============================================================================

BEGGING_THE_QUESTION_PATTERNS = [
    (r"(?:因为|由于).{0,20}(?:所以|因此).{0,20}(?:因为|由于).{0,20}(?:所以|因此)",
     "明显的循环论证——用结论证明前提"),
    (r"(?:.{2,10})就是.{2,10}(?:因为.{2,10})就是.{2,10}",
     "定义循环——用自身定义自身"),
]


# =============================================================================
# 11. 错误类比 (FALSE_ANALOGY)
# =============================================================================

FALSE_ANALOGY_PATTERNS = [
    (r"(?:就(?:像|好比|如同|相当于|跟.{0,3}一样|好像)).{0,40}(?:一样|似的|一般|那样)(?![\s\S]{0,20}(?:在.{0,5}方面|从.{0,5}角度|就.{0,5}而言))",
     "使用类比进行论证——需要检查类比是否在关键性质上相似"),
    (r"(?:如果.{0,10}可以).{0,10}(?:那.{0,10}也可以|那.{0,10}为什么不行)",
     "将不同性质的事物进行不当类比"),
]


# =============================================================================
# 12. 选择性证据 (CHERRY_PICKING)
# =============================================================================

CHERRY_PICKING_PATTERNS = [
    (r"(?:你看|看吧|我就说|早就说过?|果然).{0,20}(?:了吧|是不是|对不对|没错吧)",
     "选择性呈现符合预设结论的证据——confirmation bias"),
    (r"(?:根据|据|按照|数据显示|数据表明)(?![\s\S]{0,60}(?:也|同时|另一方[面]|但|然而|不过|尽管如此))",
     "引用单一数据/来源支持结论，未提及相反证据"),
    (r"(?:这份?|这篇?|这?个|这些?)(?:报告|研究|数据|统计|实验).{0,10}(?:清楚地?|明确地?|毫无疑问|充分).{0,10}(?:表明|说明|证明|证实)",
     "声称某单一研究'明确证明'了某结论——科学研究很少由单一论文'证明'"),
]


# 汇总
ALL_FALLACY_PATTERNS = [
    (FallacyType.FALSE_CAUSE, FALSE_CAUSE_PATTERNS),
    (FallacyType.SLIPPERY_SLOPE, SLIPPERY_SLOPE_PATTERNS),
    (FallacyType.FALSE_DICHOTOMY, FALSE_DICHOTOMY_PATTERNS),
    (FallacyType.EQUIVOCATION, EQUIVOCATION_PATTERNS),
    (FallacyType.APPEAL_TO_EMOTION, APPEAL_TO_EMOTION_PATTERNS),
    (FallacyType.APPEAL_TO_AUTHORITY, APPEAL_TO_AUTHORITY_PATTERNS),
    (FallacyType.HASTY_GENERALIZATION, HASTY_GENERALIZATION_PATTERNS),
    (FallacyType.STRAW_MAN, STRAW_MAN_PATTERNS),
    (FallacyType.RED_HERRING, RED_HERRING_PATTERNS),
    (FallacyType.BEGGING_THE_QUESTION, BEGGING_THE_QUESTION_PATTERNS),
    (FallacyType.FALSE_ANALOGY, FALSE_ANALOGY_PATTERNS),
    (FallacyType.CHERRY_PICKING, CHERRY_PICKING_PATTERNS),
]

# 每个谬误的纠偏提示
CORRECTION_HINTS = {
    FallacyType.FALSE_CAUSE:
        "两个事件先后发生或同时发生，并不等于其中一个导致了另一个。请寻找直接因果证据（如随机对照实验），而非仅凭时间先后或统计相关性推断因果。",
    FallacyType.SLIPPERY_SLOPE:
        "一连串的'如果...就会...'需要每一步都独立证明。现实中很少有事情会按直线逻辑极端发展，每步都需要提供概率或机制证据。",
    FallacyType.FALSE_DICHOTOMY:
        "世界不是非黑即白的。在'支持'和'反对'之间有大量中间地带——可以部分同意、可以持保留态度、可以认为问题本身需要重新定义。",
    FallacyType.EQUIVOCATION:
        "同一个词在不同语境下可能有完全不同的含义。'天然'不等于'安全'，'化学'不等于'有毒'。请关注物质本身的性质而非其标签。",
    FallacyType.APPEAL_TO_EMOTION:
        "强烈的情感反应不能替代事实判断。一个让人愤怒的故事可能是虚假的，一个让人感动的叙述可能隐藏了关键事实。请回归证据。",
    FallacyType.APPEAL_TO_AUTHORITY:
        "权威人物的意见在其专业领域内值得参考，但不能替代直接证据。而且要注意权威人物是否在被引用的话题上具有专业资质。",
    FallacyType.HASTY_GENERALIZATION:
        "从个案推断整体需要足够的样本量和随机抽样。'我认识的XX都YY'不能代表'所有XX都YY'，因为你的社交圈不是随机样本。",
    FallacyType.STRAW_MAN:
        "歪曲对方观点然后攻击这个被歪曲的版本，并没有真正回应对方的实际论证。请先准确理解对方的真实立场再回应。",
    FallacyType.RED_HERRING:
        "用另一个话题转移注意力并不能回答当前的问题。'XX又怎么说'不能证明或否定当前讨论的事情。请就事论事。",
    FallacyType.BEGGING_THE_QUESTION:
        "前提中已经包含了结论，这样的论证在逻辑上没有提供任何新信息。请用独立于结论之外的证据来支撑论证。",
    FallacyType.FALSE_ANALOGY:
        "类比只在两个事物在关键性质上相似时才有效。'如果A可以，那B也可以'——需要先证明A和B在相关方面确实可类比。",
    FallacyType.CHERRY_PICKING:
        "只选择支持自己观点的证据而忽略反对证据，不是客观分析。完整的论证应该呈现正反两方面的证据并说明为什么一方的权重更高。",
}


# =============================================================================
# 主检测函数
# =============================================================================

def detect_fallacies(text: str, title: str = "") -> FallacyAnalysis:
    """
    对输入文本进行 12 种逻辑谬误的全面检测。

    Args:
        text: 信息正文内容
        title: 信息标题

    Returns:
        FallacyAnalysis — 包含所有匹配的谬误及纠偏提示
    """
    combined_text = f"{title}\n{title}\n{text}" if title else text

    all_matches: list[FallacyMatch] = []

    for fallacy_type, patterns in ALL_FALLACY_PATTERNS:
        for pattern_regex, description in patterns:
            for match in re.finditer(pattern_regex, combined_text, re.IGNORECASE):
                snippet = _extract_context(combined_text, match.start(), match.end())

                if not _is_duplicate(all_matches, fallacy_type, snippet):
                    all_matches.append(FallacyMatch(
                        fallacy_type=fallacy_type,
                        description=description,
                        confidence=_confidence_for_fallacy(fallacy_type, pattern_regex, combined_text),
                        evidence_snippet=snippet,
                        reasoning=f"检测到模式: '{match.group()[:60]}'",
                        correction_hint=CORRECTION_HINTS.get(fallacy_type, ""),
                    ))

    # 汇总
    if not all_matches:
        return FallacyAnalysis(
            matches=[],
            fallacy_count=0,
            summary="未检测到明显的逻辑谬误。"
        )

    # 按谬误类型统计
    type_count: dict[FallacyType, int] = {}
    for m in all_matches:
        type_count[m.fallacy_type] = type_count.get(m.fallacy_type, 0) + 1

    summary_parts = []
    for ft, cnt in sorted(type_count.items(), key=lambda x: -x[1]):
        label = _fallacy_label(ft)
        summary_parts.append(f"{label} ({cnt}处)")

    return FallacyAnalysis(
        matches=all_matches,
        fallacy_count=len(all_matches),
        summary="检测到以下潜在逻辑谬误: " + "; ".join(summary_parts) +
                "。注意: 自动检测存在误报可能，请结合上下文进行最终判断。"
    )


# =============================================================================
# Helpers
# =============================================================================

def _extract_context(text: str, start: int, end: int, margin: int = 60) -> str:
    s = max(0, start - margin)
    e = min(len(text), end + margin)
    snippet = text[s:e].replace("\n", " ").strip()
    if s > 0:
        snippet = "…" + snippet
    if e < len(text):
        snippet += "…"
    return snippet


def _is_duplicate(existing: list[FallacyMatch], new_type: FallacyType, snippet: str) -> bool:
    for m in existing:
        if m.fallacy_type == new_type and m.evidence_snippet == snippet:
            return True
    return False


def _confidence_for_fallacy(ft: FallacyType, pattern: str, text: str) -> Confidence:
    # 强信号: 明显的模板匹配
    strong_templates = [
        FallacyType.SLIPPERY_SLOPE,
        FallacyType.BEGGING_THE_QUESTION,
    ]
    if ft in strong_templates:
        return Confidence.HIGH

    # 较强信号: 明确的情感操纵/虚假二分
    if ft in (FallacyType.APPEAL_TO_EMOTION, FallacyType.FALSE_DICHOTOMY):
        if re.search(r'不转不是|是中国人就|删前速看|令人发指', text):
            return Confidence.HIGH
        return Confidence.MODERATE

    return Confidence.MODERATE


def _fallacy_label(ft: FallacyType) -> str:
    labels = {
        FallacyType.FALSE_CAUSE: "因果倒置/虚假因果",
        FallacyType.SLIPPERY_SLOPE: "滑坡论证",
        FallacyType.FALSE_DICHOTOMY: "虚假二分",
        FallacyType.EQUIVOCATION: "偷换概念",
        FallacyType.APPEAL_TO_EMOTION: "诉诸情感",
        FallacyType.APPEAL_TO_AUTHORITY: "诉诸虚假权威",
        FallacyType.HASTY_GENERALIZATION: "以偏概全",
        FallacyType.STRAW_MAN: "稻草人谬误",
        FallacyType.RED_HERRING: "转移话题",
        FallacyType.BEGGING_THE_QUESTION: "循环论证",
        FallacyType.FALSE_ANALOGY: "错误类比",
        FallacyType.CHERRY_PICKING: "选择性证据",
    }
    return labels.get(ft, str(ft.value))
