"""
统计素养引擎 — 检测统计主张的常见滥用

这是对抗"利用学术论文/数据制造恐惧"的核心防线。

## 检测的 8 种统计滥用模式:

1. 绝对风险 vs 相对风险 — "风险增加50%"（没说从0.002%升到0.003%）
2. 样本量忽略 — "一项研究发现..."（没说是N=10还是N=10000）
3. 混杂因素忽略 — "喝咖啡的人心脏病更多"（没提他们也更爱抽烟）
4. 数据来源不透明 — "统计显示78.5%..."（谁统计的？怎么抽样的？）
5. 基线率忽略 — 诊断测试在罕见病中的假阳性问题
6. 选择性报告 — 报告阳性结果但不报告阴性/不显著结果
7. 生态学谬误 — 用群体数据推断个体
8. 辛普森悖论 — 聚合数据反转的潜在可能

## 关键原则:

统计滥用比直接编造数据更难识别，因为它常常引用真实的研究。
问题不在于数据本身是假的，而在于对数据的解释方式是有意或无意的误导。

引擎不仅检测模式，更重要的是输出"为什么这种解读可能是误导的"教育性解释。
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from app.engine.types import Confidence


# =============================================================================
# 检测结果类型
# =============================================================================

class StatisticalAbuseType(str):
    """统计滥用类型 (string enum for simplicity)"""
    RELATIVE_WITHOUT_ABSOLUTE = "relative_without_absolute"  # 只报告相对风险
    SAMPLE_SIZE_NEGLECT = "sample_size_neglect"              # 忽略样本量
    CONFOUNDER_OMISSION = "confounder_omission"              # 忽略混杂因素
    DATA_SOURCE_OPACITY = "data_source_opacity"              # 数据来源不透明
    BASE_RATE_NEGLECT = "base_rate_neglect"                  # 基线率忽略
    SELECTIVE_REPORTING = "selective_reporting"              # 选择性报告
    ECOLOGICAL_FALLACY = "ecological_fallacy"                # 生态学谬误
    SPURIOUS_PRECISION = "spurious_precision"                # 虚假精确


@dataclass
class StatisticalAbuseMatch:
    abuse_type: str
    description: str
    confidence: Confidence
    evidence_snippet: str = ""
    reasoning: str = ""
    education: str = ""  # 为什么这种解读可能有问题

    def to_dict(self) -> dict:
        return {
            "abuse_type": self.abuse_type,
            "description": self.description,
            "confidence": self.confidence.value,
            "evidence_snippet": self.evidence_snippet,
            "reasoning": self.reasoning,
            "education": self.education,
        }


@dataclass
class StatisticalAnalysis:
    matches: list[StatisticalAbuseMatch] = field(default_factory=list)
    risk_score: float = 0.0  # 0-100
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "matches": [m.to_dict() for m in self.matches],
            "risk_score": self.risk_score,
            "summary": self.summary,
        }


# =============================================================================
# 1. 相对风险不报告绝对风险
# =============================================================================
# 最常见的数据操纵: "风险增加50%" — 但实际上绝对风险从0.002%升到0.003%
# 相对风险听起来很大，绝对风险几乎可以忽略

RELATIVE_RISK_PATTERNS = [
    # 百分比增加但没有基线率
    (r"(?:风险|概率|几率|可能性)(?:增加|提高|上升|升高|高出)(?:了?)(\d+(?:\.\d+)?)\s*[%％](?![\s\S]{0,60}(?:绝对|基线|基础|原本|原|对照组))",
     "报告了相对风险增加(%），但没有提供绝对风险基线——无法判断这个'增加'实际意味着什么。"
     "\n示例: '风险增加50%' 如果绝对风险是2/10000 (0.02%)，增加50%后是3/10000 (0.03%) — 增加了万分之一。"),

    # N倍增加
    (r"(?:风险|概率|几率|可能性).{0,10}(?:是|高达|提高|增加|高出)(?:了?)?.{0,10}(\d+(?:\.\d+)?)\s*倍(?![\s\S]{0,60}(?:绝对|基线|基础|原本|对照组))",
     "报告了风险倍数但没有绝对基线——'风险是X倍'在不给绝对数字时极易误导。"
     "\n示例: '风险是5倍' — 如果基线风险是1/1000000，5倍后是5/1000000，仍然极低。"),

    # "研究发现X增加Y%风险"但未给上下文
    (r"(?:研究|meta|系统评价|荟萃)(?:发现|显示|表明).{0,40}(?:增加|提高|升高).{0,20}(\d+(?:\.\d+)?)\s*[%％].{0,20}(?:风险|概率)",
     "研究报告中提到风险增加百分比，但信息中缺少该研究的样本量、效应量的置信区间和绝对基线风险。"),
]


# =============================================================================
# 2. 样本量忽略
# =============================================================================
# "一项研究发现..." — 没说N=10, 100, 还是10000
# 样本量越小，结果越不稳定，越可能是偶然

SAMPLE_SIZE_PATTERNS = [
    # 引用"研究"但不给样本量
    (r"(?:一项|某|这份?|该)(?:研究|调查|实验|统计|分析)(?:显示|表明|发现|指出|认为)(?![\s\S]{0,50}(?:N\s*=|n\s*=|样本|sample|...名|...位|...人|...例))",
     "引用'一项研究'的结论但没有报告样本量(N)。样本量决定统计效力和结论的可靠性。"
     "\n小样本(N<100)的研究结果不稳定，可能是偶然；大样本(N>1000)的研究更可靠。"),

    # 基于极少案例的断言
    (r"(?:有|共|共计|只有|仅)\s*(\d{1,2})\s*(?:个|名|位|例|起|次)(?:案例|病例|例子|事件|实验)(?![\s\S]{0,30}(?:样本|总|共))",
     "基于极少案例(N≤20)做出断言——在统计学上，样本量过小意味着结果极不稳定，"
     "一个异常值就可能完全改变结论。单个案例或少量案例不能代表总体。"),

    # 动物实验 → 人类的无样本过渡
    (r"(?:小鼠|大鼠|动物|体外|细胞|果蝇|斑马鱼)(?:实验|研究|测试|试验).{0,20}(?:表明|显示|发现|证实).{0,30}(?:导致|造成|引起|致癌|有毒)",
     "引用动物/体外研究结论直接推到人类——动物实验是人类研究的重要参考，"
     "但物种间存在巨大的生理差异。绝大多数动物实验中的阳性结果未能转化为人类有效/有害。"),
]


# =============================================================================
# 3. 混杂因素忽略
# =============================================================================
# "喝咖啡的人心脏病风险更高" — 是真的，但原因不是咖啡，
# 而是喝咖啡的人整体上更可能抽烟、熬夜、压力大

CONFOUNDER_PATTERNS = [
    # 简单的A→B因果声明
    (r"(?:吃|喝|食用|摄入|饮用).{1,10}(?:会导致?|会造成?|会引起?|会引发?|会增加?|会提高?|致癌|有毒)(?![\s\S]{0,60}(?:混杂|其他因素|同时也?|生活方式|遗传|环境|年龄|性别))",
     "将饮食与疾病之间的关系简单归因，但忽略了成千上万个可能的混杂因素。"
     "\n营养流行病学中最常见的陷阱: 吃X的人通常也有其他共同特征(生活方式、收入、教育)，"
     "这些因素可能才是真正的原因。观察性研究只能找到'相关'，不能证明'因果'。"),

    # 忽略"反向因果"
    (r"(?:使用|服用|...的)\S+的?人.{0,20}(?:更容易|更可能|更多)(?:患|得|出现|发生)(?![\s\S]{0,40}(?:可能因|可能是|不排除|也许|或许|可能另有))",
     "将统计关联简单归因为A导致B，但忽略了反向因果的可能性——可能是B导致了A，"
     "或者C同时导致了A和B。\n例如: '吃保健品的老人更健康'——可能是因为本来就健康的人更注重吃保健品。"),
]


# =============================================================================
# 4. 数据来源不透明
# =============================================================================

DATA_OPACITY_PATTERNS = [
    # 模糊的"调查显示"/"统计显示"
    (r"(?:据|根据|...)(?:调查|统计|数据|抽样|问卷)(?:显示|表明|发现|...)(?![\s\S]{0,60}(?:样本量|抽样方法|误差|置信|统计局|WHO|IMF|...研究))",
     "引用了'调查/统计/数据'但没有说明: 谁做的调查？样本量多大？抽样方法是什么？"
     "\n没有这些基本信息的数据，其可信度和代表性无法评估。"),

    # 精确数字无误差范围
    (r"(?:高达|达到|占比|整整|足足)\s*(\d{2,3}(?:\.\d+)?)\s*[%％](?![\s\S]{0,40}(?:误差|±|置信|范围|区间))",
     "给出了精确的百分比数字但没有提供误差范围/置信区间。"
     "\n所有的统计估计都有不确定性——不给误差范围就是在暗示'精确得不容置疑'的假象。"),

    # "某/有"机构统计
    (r"(?:某|有|根据)(?:机构|组织|部门|单位|公司|平台)(?:统计|调查|数据|报告)(?:显示|表明|发现)",
     "引用了一个模糊的'机构/组织'的数据但不指明具体名称——这样的数据无法独立核实。"),
]


# =============================================================================
# 5. 基线率忽略
# =============================================================================
# 最被忽视的统计陷阱: 检测罕见病的准确率99%，但阳性结果中90%可能是假阳性

BASE_RATE_PATTERNS = [
    # 检测/筛查准确率 但不说基线率
    (r"(?:检测|筛查|诊断|测试|...检查)(?:准确率|准确度|正确率|灵敏度|...的|高达)\s*(\d{2,3}(?:\.\d+)?)\s*[%％](?![\s\S]{0,60}(?:患病率|发病率|流行率|基线|假阳性|假阴性|阳性预测值))",
     "报告了检测的准确率/灵敏度但没有提及基线发病率。"
     "\n在罕见病中(如发病率0.1%)，即使检测准确率99%，阳性结果中绝大多数是假阳性。"
     "\n示例: 发病率0.1%，检测准确率99%，检测1万人 → 约10个真阳性 + 约100个假阳性 → 阳性者中只有~9%是真的患病。"),

    # 筛查=确诊的表述
    (r"(?:筛查|体检|普查|...检测)(?:发现|检出|查出了?).{0,10}(\d+(?:\.\d+)?)\s*[%％].{0,10}(?:异常|问题|阳性|病患)",
     "将筛查阳性结果等同于确诊——筛查不等于确诊。筛查是初步过滤，"
     "阳性后还需要金标准确诊。对于低发病率疾病，筛查阳性极可能是假阳性。"),
]


# =============================================================================
# 6. 选择性报告
# =============================================================================

SELECTIVE_REPORTING_PATTERNS = [
    # 正面结果被强调，负面结果被隐藏
    (r"(?:最新|最新?的?|突破性|开创性)(?:研究|发现|成果).{0,40}(?:有效|成功|显著|确认|证实|支持)(?![\s\S]{0,60}(?:但|然而|不过|也发现|同时发现|局限|不足|需要更多|需要进一步|尚需))",
     "强调'正面/突破'结果但不提及研究的局限性和可能的阴性结果。"
     "\n正宗的科学研究应该陈述研究的局限性。只讲好处不谈局限的是广告，不是科学。"),

    # 发表偏倚 — "confirm 但不 disconfirm"
    (r"(?:多项|大量|众多|无数|海量)(?:研究|证据|数据|实验)(?:证实|支持|证明)(?![\s\S]{0,60}(?:也(?:有|存在)|不一|并非|相反))",
     "'大量研究证实'的表述忽略了发表偏倚——阴性结果的研究更难被发表。"
     "\n你看到的'大量支持研究'可能只是冰山一角，下面埋藏着更多没被发表的阴性结果。"),

    # P值操纵 / P-hacking 的暗示
    (r"(?:显著|统计学意义|统计学上|p\s*[<≤]\s*0?\.?05|显著差异)(?![\s\S]{0,60}(?:多重|校正|Bonferroni|FDR|假发现|多重比较))",
     "提及'显著'/'p<0.05'但没有提及多重比较校正。"
     "\n如果做了20个分析，随机就会有一个'p<0.05'出现——这不是真正的显著，而是多重比较的必然。"),
]


# =============================================================================
# 7. 生态学谬误
# =============================================================================

ECOLOGICAL_PATTERNS = [
    # 用群体数据推断个体
    (r"(?:平均水平?|人均|平均|中位数|绝大多数|普遍).{0,20}(?:所以|因此|意味着|说明|...).{0,20}(?:你|我|每个人|每个|任何人|所有人|大家)(?:都|就|...的)",
     "用群体层面的统计推断个体——生态学谬误。"
     "\n群体的平均特征 ≠ 个体的具体特征。'平均来说中国人每天吃5克盐'不意味着'你每天吃5克盐'。"),

    # 用国家/群体比较推断个体
    (r"(?:某国|某地区|某省|某城市).{0,10}(?:的人|的居民|的老百姓|...).{0,10}(?:比|较).{0,10}(?:更|高|低|多|少).{0,20}(?:所以|因此|说明)",
     "用地域/群体比较统计来推断个体特征，忽略了个体差异和组内方差。"
     "\n两个群体之间的统计差异可能完全是由极少数极端值造成的，不能代表群体中任何具体个体。"),
]


# =============================================================================
# 8. 虚假精确
# =============================================================================

SPURIOUS_PRECISION_PATTERNS = [
    # 精确到小数点后很多位的百分比
    (r"(\d{2,3}\.\d{2,})[%％](?![\s\S]{0,30}(?:误差|±|约|大约|左右))",
     "给出了极高精度的小数(如78.43%)但几乎可以肯定这种精确度是虚假的。"
     "\n真正的统计估计都有置信区间。给出过于精确的数字是制造权威感的常见手段。"),

    # "精确"排名
    (r"(?:排名|位居|位列).{0,10}(?:第\s*[一二三四五六七八九十\d]+|...名)(?![\s\S]{0,40}(?:统计口径|评价标准|方法|...说明))",
     "给出了精确排名但没有说明评价标准和统计口径——'排名第3'在不同的排名体系中可能完全不同。"),
]


# 汇总
ALL_STATISTICAL_PATTERNS = [
    (StatisticalAbuseType.RELATIVE_WITHOUT_ABSOLUTE, RELATIVE_RISK_PATTERNS),
    (StatisticalAbuseType.SAMPLE_SIZE_NEGLECT, SAMPLE_SIZE_PATTERNS),
    (StatisticalAbuseType.CONFOUNDER_OMISSION, CONFOUNDER_PATTERNS),
    (StatisticalAbuseType.DATA_SOURCE_OPACITY, DATA_OPACITY_PATTERNS),
    (StatisticalAbuseType.BASE_RATE_NEGLECT, BASE_RATE_PATTERNS),
    (StatisticalAbuseType.SELECTIVE_REPORTING, SELECTIVE_REPORTING_PATTERNS),
    (StatisticalAbuseType.ECOLOGICAL_FALLACY, ECOLOGICAL_PATTERNS),
    (StatisticalAbuseType.SPURIOUS_PRECISION, SPURIOUS_PRECISION_PATTERNS),
]


# =============================================================================
# 主检测函数
# =============================================================================

def detect_statistical_abuse(text: str, title: str = "") -> StatisticalAnalysis:
    """
    对输入文本进行 8 种统计滥用模式的全面检测。

    返回 StatisticalAnalysis，包含:
    - 每个匹配的详细说明
    - 教育性解释 (为什么这种解读可能有问题)
    - 总体风险评分
    """
    combined = f"{title}\n{title}\n{text}" if title else text

    all_matches: list[StatisticalAbuseMatch] = []

    for abuse_type, patterns in ALL_STATISTICAL_PATTERNS:
        for pattern_regex, description in patterns:
            for match in re.finditer(pattern_regex, combined, re.IGNORECASE):
                snippet = _extract_context(combined, match.start(), match.end())

                if not _is_duplicate(all_matches, abuse_type, snippet):
                    all_matches.append(StatisticalAbuseMatch(
                        abuse_type=abuse_type,
                        description=description.split("\n")[0],
                        confidence=_stat_confidence(abuse_type, combined),
                        evidence_snippet=snippet,
                        reasoning=f"匹配模式 → 触发词: '{match.group()[:60]}'",
                        education=description,  # 完整教育性解释
                    ))

    # 计算风险评分
    if not all_matches:
        return StatisticalAnalysis(
            matches=[],
            risk_score=0.0,
            summary="未检测到明显的统计滥用模式。数据/统计相关主张看起来较为规范。"
        )

    # 每类+10分，高置信度额外+5
    types_seen = set(m.abuse_type for m in all_matches)
    high_conf = sum(1 for m in all_matches if m.confidence == Confidence.HIGH)

    risk = len(types_seen) * 10.0 + high_conf * 5.0
    risk = min(100.0, risk)

    # 汇总
    type_labels = {
        StatisticalAbuseType.RELATIVE_WITHOUT_ABSOLUTE: "相对风险不报绝对基线",
        StatisticalAbuseType.SAMPLE_SIZE_NEGLECT: "忽略样本量",
        StatisticalAbuseType.CONFOUNDER_OMISSION: "忽略混杂因素",
        StatisticalAbuseType.DATA_SOURCE_OPACITY: "数据来源不透明",
        StatisticalAbuseType.BASE_RATE_NEGLECT: "基线率忽略",
        StatisticalAbuseType.SELECTIVE_REPORTING: "选择性报告",
        StatisticalAbuseType.ECOLOGICAL_FALLACY: "生态学谬误",
        StatisticalAbuseType.SPURIOUS_PRECISION: "虚假精确",
    }

    labels_seen = [type_labels.get(t, t) for t in sorted(types_seen)]
    summary = (
        f"检测到 {len(types_seen)} 类统计滥用模式 (共 {len(all_matches)} 处匹配): "
        + "; ".join(labels_seen)
        + f"。风险评分: {risk:.0f}/100。"
        + " 注意: 统计滥用不等于数据造假——问题往往在于解释方式而非数据本身。"
    )

    return StatisticalAnalysis(
        matches=all_matches,
        risk_score=risk,
        summary=summary,
    )


# =============================================================================
# 意图分析: 统计滥用是故意的还是无意的？
# =============================================================================

def assess_intent(text: str, matches: list[StatisticalAbuseMatch]) -> dict:
    """
    评估统计滥用的可能意图——主动操纵 vs 无意的统计错误。

    这不能做出确定判断，但可以提供线索。
    """
    clues_manipulative = 0
    clues_innocent = 0

    if re.search(r'(?:赚钱|暴利|商机|购买|下单|抢购|限时|优惠|点击|关注|订阅)', text):
        clues_manipulative += 1

    if re.search(r'(?:科学研究|学术|客观|公平|中立|实事求是|不偏不倚)', text):
        clues_innocent += 1

    if len(matches) >= 3:
        clues_manipulative += 1

    if len(matches) <= 1:
        clues_innocent += 1

    return {
        "matches_analyzed": len(matches),
        "manipulative_clues": clues_manipulative,
        "innocent_clues": clues_innocent,
        "caveat": "意图分析仅为辅助参考，不能作为确定判断。统计错误可能是有意的操纵也可能是无意的知识不足。",
    }


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


def _is_duplicate(existing: list, abuse_type: str, snippet: str) -> bool:
    for m in existing:
        if m.abuse_type == abuse_type and m.evidence_snippet == snippet:
            return True
    return False


def _stat_confidence(abuse_type: str, text: str) -> Confidence:
    """估算统计滥用的置信度"""
    # 明确的相对风险不报绝对基线 → HIGH
    if abuse_type == StatisticalAbuseType.RELATIVE_WITHOUT_ABSOLUTE:
        if re.search(r'风险.{0,10}(?:增加|提高|升高)\d+[%％]', text):
            return Confidence.HIGH
        return Confidence.MODERATE

    # 精确小数 → HIGH (明显的虚假精确)
    if abuse_type == StatisticalAbuseType.SPURIOUS_PRECISION:
        return Confidence.HIGH

    # 数据来源完全模糊 → HIGH
    if abuse_type == StatisticalAbuseType.DATA_SOURCE_OPACITY:
        if re.search(r'(?:据调查|据统计|数据显示|调查显示)(?![\s\S]{0,40}(?:来源|报告|白皮书))', text):
            return Confidence.HIGH
        return Confidence.MODERATE

    return Confidence.MODERATE
