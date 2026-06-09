"""
意见伪装为事实检测引擎 — 模态梯度漂移追踪

## 核心原理:

信息在传播过程中有一种自然趋势:
- 从 "可能" → "很可能" → "肯定" (可能性→确定性)
- 从 "有人认为" → "有证据表明" → "已证实" (推测→证实)
- 从 "在特定条件下" → "一般情况" → "所有情况" (限定→普适)

这种'模态梯度漂移'(Modality Gradient Drift)是信息失真的基本机制之一。

## 检测的 5 种漂移模式:

1. 推测→确定: "可能"→"肯定", "也许"→"就是", "猜测"→"证实"
2. 意见伪装事实: "我认为"→"事实是", "感觉"→"已经是"
3. 条件→绝对: "在X条件下"→"都", "如果X"→"X是"
4. 可能性梯度: 从 might → likely → certainly 的跳跃追踪
5. 责任稀释: "据说/据报道"被用来发表明确主张 (将自己的主张伪装为转述)
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from app.engine.types import Confidence


# =============================================================================
# 模态词汇体系
# =============================================================================

# 推测/可能 (epistemic possibility)
TENTATIVE_MARKERS = [
    "可能", "也许", "或许", "大概", "似乎", "好像", "仿佛",
    "...的话", "倾向于", "有...的可能", "不排除", "初步",
]

# 确定/断言 (epistemic certainty)
CERTAIN_MARKERS = [
    "肯定", "一定", "必然", "绝对", "毫无疑问", "毋庸置疑",
    "证明", "证实", "确认", "确定无疑", "百分之百", "100%",
    "就是", "说白了", "其实是", "本质是", "客观事实",
]

# 主观评价 (subjective)
SUBJECTIVE_MARKERS = [
    "我认为", "我觉得", "我感觉", "个人认为", "依我看", "在我看来",
    "笔者以为", "某认为", "我的观点是", "笔者觉得",
]

# 客观化包装 (subjective→objective appearance)
OBJECTIFYING_PATTERNS = [
    "事实证明", "客观地说", "实事求是地说", "不吹不黑",
    "事实胜于雄辩", "真相就是", "客观事实是",
]


# =============================================================================
# 检测结果
# =============================================================================

class ModalityDriftType(str):
    TENTATIVE_TO_CERTAIN = "tentative_to_certain"
    OPINION_AS_FACT = "opinion_as_fact"
    CONDITION_TO_ABSOLUTE = "condition_to_absolute"
    RESPONSIBILITY_DILUTION = "responsibility_dilution"
    HEDGING_PATTERN = "hedging_pattern"  # 用模糊词汇伪装确定性


@dataclass
class ModalityDriftMatch:
    drift_type: str
    description: str
    confidence: Confidence
    evidence_snippet: str = ""
    tentative_part: str = ""  # 推测性的部分
    certain_part: str = ""    # 确定性的部分
    drift_reasoning: str = ""  # 为什么这是漂移

    def to_dict(self) -> dict:
        return {
            "drift_type": self.drift_type,
            "description": self.description,
            "confidence": self.confidence.value,
            "evidence_snippet": self.evidence_snippet,
            "tentative_part": self.tentative_part,
            "certain_part": self.certain_part,
            "drift_reasoning": self.drift_reasoning,
        }


@dataclass
class ModalityAnalysis:
    matches: list[ModalityDriftMatch] = field(default_factory=list)
    drift_score: float = 0.0
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "matches": [m.to_dict() for m in self.matches],
            "drift_score": self.drift_score,
            "summary": self.summary,
        }


# =============================================================================
# 1. 推测→确定 漂移
# =============================================================================

TENTATIVE_TO_CERTAIN_PATTERNS = [
    # 同一句话内从"可能"跳到"肯定"
    (r"(?:可能|也许|或许|大概|似乎).{0,50}(?:但|不过|然而|可.{0,5}是).{0,20}(?:肯定|一定|确实|真的|绝对|就是).{0,30}",
     "同一段话中从推测('可能')跳到了确定('肯定')——前半段的谨慎态度在后半段消失了。"),

    # 从"可能"的推测直接过渡到确定的行动建议
    (r"(?:可能|也许|或许|大概).{0,30}(?:所以|因此|大家|你们?|快|赶紧|一定[要该]).{0,30}(?:去|买|不要|别|千万|务必|...)",
     "从'可能'的风险推测直接得出确定的行动建议——推测性前提不能自然导出必须立即行动的结论。"),

    # 对外媒/他源的"可能"报道当作"确定"再引用
    (r"(?:引用|据|...报道|...称).{0,20}(?:可能|也许|或|猜测|推测).{0,40}(?:可见|由此可见|这说明|这就|证实|证明|确认)",
     "从一个使用了'可能/或许'的第三方报道，跳到了'可见/证实'的确定性结论。"
     "\n原始信息中的不确定性在转述中被消除了。"),
]


# =============================================================================
# 2. 意见伪装为事实
# =============================================================================

OPINION_AS_FACT_PATTERNS = [
    # 标题/开头声称是事实，内容却是个人看法
    (r"(?:事实是|真相是|事实证明|客观事实是|本质是|说白了就是|其实就是)(?![\s\S]{0,30}(?:证据|数据|研究|官方|文件|原文|...根据))",
     "以'事实是/真相是/事实证明'开头，但不附带任何可核实的证据来源——这是将个人意见包装为事实的经典手法。"),

    # "不吹不黑/客观地说" 后面跟主观判断
    (r"(?:不吹不黑|客观地?说|平心而论|说句公道话|实事求是地?说|有一说一)(.{0,80})",
     "使用'不吹不黑/客观地说'等客观化词汇，但后面的陈述可能完全是主观判断。"
     "\n'客观'一词并不自动使陈述变得客观。真正的客观需要可核实的证据，而非这个前缀。"),

    # 零证据的主张用肯定句式
    (r"(?:显然|明[显白][地然]|毫无疑问道?|众所周知|不容置疑|不争的事实)(?![\s\S]{0,40}(?:证据|数据|来源|研究|报告|统计))",
     "使用'显然/众所周知/毫无疑问'等词汇来增加确定性，但没有附带任何支撑证据。"
     "\n这些词汇在修辞上起到'跳过论证步骤'的作用——读者被暗示'这不需要证据'。"),

    # 个人感受被当作普遍事实
    (r"(?:我|笔者|我本人)(?:感觉|觉得|认为|...感).{0,30}(?:所以|因此|说明|证明|可见|这是|这就).{0,30}(?:就是|肯定|一定|绝对|显然|必然)",
     "从'我感觉/我觉得'的个人感受出发，得出'这就证明/肯定/必然'的普遍结论。"
     "\n个人感受不能作为普遍事实的证明。"),
]


# =============================================================================
# 3. 条件→绝对 漂移
# =============================================================================

CONDITION_TO_ABSOLUTE_PATTERNS = [
    # 从"在一定条件下"省略到"都"
    (r"(?:在.{0,10}(?:条件下?|环境中?|情况下?|范围.{0,5}内?)).{0,30}(?:可能|可以|会|能).{0,40}(?:但是|不过|然而|...的是).{0,20}(?:所有|全部|都|任何|每个|凡是|一概).{0,30}",
     "前半段有明确的条件限定，但后半段使用了无条件词('所有/全部/都')——条件的限定被忽略了。"),

    # 科学论文的Tentative→媒体的Certain的典型转换
    (r"(?:研究|论文|实验)(?:表明|显示|发现).{0,20}(?:可能|或许|或|提示|暗示|相关).{0,60}(?:所以|因此|可见|这就|...说明).{0,20}(?:会|能|可以|导致|造成|引起)",
     "研究原文使用了'可能/提示/暗示'等tentative语言（这是科学的正确做法），"
     "但在转述中被变成了'会/可以/导致'的确定性表述。科学中的不确定性在传播中消失了。"),

    # "在小鼠实验中" → 直接跳到人类
    (r"(?:在|...的)(?:小鼠|大鼠|动物|体外|...实验)(?:中|里).{0,20}(?:可能|发现|显示|表明).{0,40}(?:所以|因此|这就|想必|...的话).{0,20}(?:人|人类|我们|大家|你|...体)",
     "从'动物实验'的结论跳过物种差异，直接应用到人类。物种间的生理差异巨大，"
     "绝大多数动物实验的阳性结果未能转化为人类有效/有害。"),
]


# =============================================================================
# 4. 责任稀释
# =============================================================================

RESPONSIBILITY_DILUTION_PATTERNS = [
    # "据说/据悉/据悉" — 自己说的，但假装是听别人说的
    (r"(?:据说|据悉|据闻|传闻|有消息称|有说法称|坊间传闻)(?![\s\S]{0,40}(?:具体|来源|出处|何人|来自|根据...报道))",
     "使用'据说/据悉/传闻'等模糊来源来发表自己的主张——将自己的观点包装为转述。"
     "\n这是一种责任稀释: '不是我说的，是我听说的'——但传播时不说信息来源，等于在传自己的话。"),

    # "很多人都说/大家公认" 无法验证的共识
    (r"(?:很多人都|大家都|大家都?在|所有人都在|全国人民都|全社会都)(?:说|认为|觉得|知道|清楚|明白|看到)",
     "'很多人都说/大家都认为'——这是一种不可验证的'共识'宣称。"
     "\n你无法核实'很多人'到底是多少人，也无法核实他们是否真的'都'说。"),

    # "不管怎么说/不管怎么样" — 回避具体论证
    (r"(?:不管怎么说|不管怎么样|无论如何|总而言之|反正|说一千道一万|万变不离其宗)(.{0,60})",
     "'不管怎么说/反正'后面跟的陈述绕过了具体论证——将需要证明的结论当作不需要论证的前提。"),
]


# 汇总
ALL_MODALITY_PATTERNS = [
    (ModalityDriftType.TENTATIVE_TO_CERTAIN, TENTATIVE_TO_CERTAIN_PATTERNS),
    (ModalityDriftType.OPINION_AS_FACT, OPINION_AS_FACT_PATTERNS),
    (ModalityDriftType.CONDITION_TO_ABSOLUTE, CONDITION_TO_ABSOLUTE_PATTERNS),
    (ModalityDriftType.RESPONSIBILITY_DILUTION, RESPONSIBILITY_DILUTION_PATTERNS),
]


# =============================================================================
# 模态梯度分析: 整段文本的语气变化
# =============================================================================

def _analyze_modality_gradient(text: str) -> dict:
    """
    分析整段文本中模态词汇的分布和梯度变化。

    如果文本前半段大量使用推测性词汇，后半段突然转为确定性表述，
    → 可能的模态漂移。
    """
    sentences = re.split(r'[。！!？?\n]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

    if len(sentences) < 2:
        return {"gradient_detected": False}

    first_half = sentences[:len(sentences)//2]
    second_half = sentences[len(sentences)//2:]

    # 计数各半的模态词
    tentative_first = sum(1 for s in first_half for m in TENTATIVE_MARKERS if m in s)
    tentative_second = sum(1 for s in second_half for m in TENTATIVE_MARKERS if m in s)
    certain_first = sum(1 for s in first_half for m in CERTAIN_MARKERS if m in s)
    certain_second = sum(1 for s in second_half for m in CERTAIN_MARKERS if m in s)

    # 如果前半推测多 → 后半确定多 = 梯度漂移
    if tentative_first > 0 and certain_second > certain_first * 2:
        return {
            "gradient_detected": True,
            "pattern": "前半段使用推测性语言(+{}处), 后半段转为确定性断言(+{}处)".format(
                tentative_first, certain_second),
            "tentative_to_certain_ratio": f"{tentative_first}:{certain_second}",
            "risk": "HIGH" if tentative_first >= 2 and certain_second >= 3 else "MODERATE",
        }

    return {"gradient_detected": False}


# =============================================================================
# 主检测
# =============================================================================

def detect_modality_drift(text: str, title: str = "") -> ModalityAnalysis:
    """
    检测信息中的模态梯度漂移——从推测到确定、从意见伪装为事实。
    """
    combined = f"{title}\n{title}\n{text}" if title else text

    all_matches: list[ModalityDriftMatch] = []

    for drift_type, patterns in ALL_MODALITY_PATTERNS:
        for pattern_regex, description in patterns:
            for match in re.finditer(pattern_regex, combined, re.IGNORECASE):
                snippet = _extract_context(combined, match.start(), match.end())

                if not _is_duplicate(all_matches, drift_type, snippet):
                    # 提取推测部分和确定部分
                    tentative_part, certain_part = _split_tentative_certain(snippet)

                    all_matches.append(ModalityDriftMatch(
                        drift_type=drift_type,
                        description=description.split("\n")[0],
                        confidence=_modality_confidence(drift_type, combined),
                        evidence_snippet=snippet,
                        tentative_part=tentative_part,
                        certain_part=certain_part,
                        drift_reasoning=description,
                    ))

    # 梯度分析
    gradient = _analyze_modality_gradient(combined)

    drift_score = len(set(m.abuse_type if hasattr(m, 'abuse_type') else m.drift_type for m in all_matches)) * 15.0
    if gradient.get("gradient_detected"):
        drift_score += 20
    drift_score = min(100.0, drift_score)

    if not all_matches:
        return ModalityAnalysis(matches=[], drift_score=0.0, summary="未检测到模态梯度漂移。")

    summary_parts = [f"检测到 {len(all_matches)} 处模态漂移"]
    if gradient.get("gradient_detected"):
        summary_parts.append(f"整体文本模态梯度异常: {gradient.get('pattern', '')}")
    summary_parts.append(f"漂移评分: {drift_score:.0f}/100")
    summary = "。".join(summary_parts) + "。"

    return ModalityAnalysis(
        matches=all_matches,
        drift_score=drift_score,
        summary=summary,
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


def _split_tentative_certain(text: str) -> tuple[str, str]:
    """尝试从文本中分离推测部分和确定部分"""
    tentative = ""
    certain = ""

    for tm in TENTATIVE_MARKERS:
        if tm in text:
            idx = text.index(tm)
            tentative = text[max(0, idx-10):idx+20]
            break

    for cm in CERTAIN_MARKERS:
        if cm in text:
            idx = text.index(cm)
            certain = text[max(0, idx-10):idx+20]
            break

    return tentative, certain


def _is_duplicate(existing: list, drift_type: str, snippet: str) -> bool:
    for m in existing:
        if m.drift_type == drift_type and m.evidence_snippet == snippet:
            return True
    return False


def _modality_confidence(drift_type: str, text: str) -> Confidence:
    if drift_type == ModalityDriftType.RESPONSIBILITY_DILUTION:
        if re.search(r'(?:据说|据悉|坊间传闻|很多人都说|大家都认为)', text):
            return Confidence.HIGH
        return Confidence.MODERATE

    if drift_type == ModalityDriftType.TENTATIVE_TO_CERTAIN:
        if re.search(r'(?:可能.{0,30}但.{0,20}肯定|也许.{0,30}但.{0,20}一定)', text):
            return Confidence.HIGH
        return Confidence.MODERATE

    return Confidence.MODERATE
