"""
信息失真检测引擎 — 7 种失真模式的形式化检测

每种失真模式都有明确的检测规则和判定逻辑。
检测结果必须附带证据摘录和推理过程，绝不凭空判断。

核心原则:
- 只检测模式，不做事实判断 (事实判断交给知识验证器)
- 每个匹配附带原文片段作为证据
- 置信度反映了模式匹配的确定性，而非事实确定性
"""

from __future__ import annotations
import re
from typing import Optional
from app.engine.types import (
    DistortionType, DistortionMatch, DistortionAnalysis, Confidence
)


# =============================================================================
# 模式 1: 源头伪造 (SOURCE_FABRICATION)
# =============================================================================
# 特征: 声称来源于某权威来源但无法追溯到原文;
#       使用模糊引用 ("据研究显示"、"有报道称"、"科学家发现" 而不给具体引用);
#       引用不存在的机构或人物

SOURCE_FABRICATION_PATTERNS = [
    # 模糊权威引用 — 没有具体出处
    (r"据(?:相关|有关)?研究(?:表明|显示|发现)(?![\s\S]{0,30}(?:https?://|DOI[：:]|《[^》]+》))",
     "使用模糊的'据研究'但没有给出具体研究名称或链接"),
    (r"有(?:报道|消息)称(?![\s\S]{0,30}(?:https?://|[Nn]ews|[Aa]gency))",
     "使用模糊的'有报道称'但没有指明具体来源"),
    (r"科学家(?:们)?(?:发现|表示|认为)(?![\s\S]{0,40}(?:大学|研究院|DOI|发表于|[Pp]ublish))",
     "使用模糊的'科学家发现'但没有指出具体科学家或研究机构"),
    (r"专家(?:指出|表示|称)(?![\s\S]{0,40}(?:教授|主任|博士|医院|大学|研究))",
     "引用'专家'但没有具体姓名和资质"),
    # 农业伪科普模板检测 — B站视频揭露的标准造谣句式
    (r"我(?:朋友|亲戚|认识.{0,5}(?:人|的)).{0,10}(?:就是|是)(?:种|养|做|搞).{0,10}(?:的.{0,5})?(?:但是|但|可是|却).{0,5}(?:从来|从|绝对|都).{0,5}(?:不吃|不喝|不用|不买)",
     "检测到'我朋友就是种XX的但他从来不吃'模板 — 农业伪科普的标准带货句式，无法验证"),
    (r"(?:顶花带刺|带花).{0,10}(?:黄瓜|水果|蔬菜).{0,10}(?:不好|有毒|有药|打了|喷了)",
     "检测到'顶花带刺的XX不好/有药'模板 — 不符合农业常识的伪科普恐吓"),
    (r"(?:大(?:草莓|葡萄|水果|桃子|苹果)).{0,10}(?:打(?:了)?|喷(?:了)?|用(?:了)?).{0,10}(?:激素|膨大剂|农药|药)",
     "检测到'大XX打了激素'模板 — 将果实大小简单归因于激素，忽略品种/管理/水肥"),
    # 引用不存在/无法查证的来源
    (r"(?:根据|依照|按照)(?:内部文件|内部消息|可靠消息|权威人士|知情人士)(?![\s\S]{0,20}(?:披露|公开))",
     "引用'内部文件/可靠消息'等无法查证的来源"),
    # 数据无出处
    (r"(?:高达|超过|达到|占比)\d+(?:\.\d+)?[%％](?![\s\S]{0,40}(?:来源|数据来源|统计局|[Ss]ource))",
     "给出精确数据但没有标注数据来源"),
    # 引用虚构的专家/机构
    (r"(?:世界|国际|全球|中国|国家).{2,6}(?:组织|协会|学会|机构|中心)(?![\s\S]{0,20}(?:官网|注册|成立))",
     "引用可能的虚构或未被认可的机构名称（需要人工核实）"),
]


# =============================================================================
# 模式 2: 内容篡改 (CONTENT_TAMPERING)
# =============================================================================
# 特征: 提到"剪辑"、"拼接"、"断章取义"等;
#       引用内容与原文不符（需要原文比对，这里只做模式检测）;
#       多个版本间存在矛盾

CONTENT_TAMPERING_PATTERNS = [
    # 截取/裁剪暗示
    (r"(?:视频|音频|文章|内容|画面)(?:被)?(?:剪辑|截取|拼接|合成|修改|篡改)",
     "内容明确提及或被指控存在剪辑/篡改"),
    # 选择性引用 — 引号内内容极短
    (r"[''""][^''""]{1,15}[''""](?![\s\S]{0,30}(?:原文|出处|参见))",
     "极短的引用片段(≤15字)，可能是选择性摘录，需要比对原文"),
    # 掐头去尾
    (r"(?:只说|只截取|只看到|只放了?)(?:了?)(?:一[半部分段句]|前面|后面|开头)",
     "可能的断章取义——只呈现了信息的一部分"),
    # PS/深度伪造
    (r"(?:PS|P图|修图|AI换脸|deepfake|深度伪造|deep.?fake)",
     "涉及图片/视频伪造技术"),
    # 翻译歪曲
    (r"(?:翻译|机翻|误译|错译)(?![\s\S]{0,30}(?:正确|准确|忠实|原文))",
     "可能的翻译歪曲——翻译可能偏离原意"),
]


# =============================================================================
# 模式 3: 错误引用 (MISQUOTATION)
# =============================================================================
# 特征: 引用论文/研究但结论与原研究不符;
#       把相关性说成因果性;
#       使用学术语言但逻辑不成立

MISQUOTATION_PATTERNS = [
    # 相关性→因果性 转换 (最常见的学术滥用)
    (r"(?:研究|数据|统计)(?:表明|显示|发现|证实|证明)(?![\s\S]{0,20}(?:相关|关联|correlation))",
     "将研究结果表述为'证明'——可能将相关性当成因果性（研究通常只显示相关性）"),
    # 直接声称因果关系但无实验支撑
    (r"(?:导致|造成|引起|诱发).{0,15}(?:癌症|疾病|死亡|病变|中毒|不孕|畸形)(?![\s\S]{0,50}(?:随机对照|双盲|临床试验|RCT|cohort|动物实验))",
     "声称因果关系（XX导致YY）但没有提及实验证据类型"),
    # 绝对化表述 + 学术引用
    (r"(?:100\%|百分之百|绝对|肯定|必然|一定)(?:有效|安全|无害|有毒|有害|致癌)",
     "使用绝对化表述修饰安全性/有效性声明——科学中极少有100%的结论"),
    # 引用过时或被撤回的研究
    (r"(?:研究|论文)(?:发表)?.{0,20}(?:19\d{2}|20[01]\d)",
     "引用的研究年代久远——可能已被更新的研究推翻"),
    # 把建议/推测说成结论
    (r"(?:可能|也许|或许|推测|猜测|估计)(?![\s\S]{0,30}(?:可能|也许|不一定|不确定))",
     "使用了推测性语言但被当作确定结论传播（需要检查是否在传播中被强化为确定结论）"),
]


# =============================================================================
# 模式 4: 忽略语境 (CONTEXT_STRIPPING)
# =============================================================================
# 特征: 去掉限定条件 (如 "在一定条件下" "大剂量" "动物实验" 被省略);
#       数据不带统计口径说明;
#       法律条文去掉适用范围

CONTEXT_STRIPPING_PATTERNS = [
    # 去掉剂量谈毒性 (食品安全领域极常见)
    (r"(?:有毒|致癌|有害|致命|剧毒)(?![\s\S]{0,50}(?:剂量|摄入量|ADI|mg/kg|LD50|ppm))",
     "声称'有毒/致癌'但没有提及剂量——脱离剂量谈毒性是典型的误导"),
    # 去掉实验对象
    (r"(?:研究|实验)(?:表明|证实|发现)(?![\s\S]{0,40}(?:动物|小鼠|大鼠|体外|细胞|人类|临床|人体))",
     "引用研究结论但没有说明实验是在什么对象上做的（体外？动物？人体？）"),
    # 法律条文掐头去尾
    (r"(?:根据|依照|按照)(?:《[^》]+》|第[一二三四五六七八九十\d]+条)(?![\s\S]{0,50}(?:适用|范围|除外|但|除非))",
     "引用法律条文但没有说明适用范围和例外条款"),
    # 统计口径缺失
    (r"(?:人均|平均|增长率|增长率|下降|上升)(?:\d+(?:\.\d+)?[%％]?)(?![\s\S]{0,40}(?:同比|环比|名义|实际|口径))",
     "引用统计数据但没有说明统计口径（同比/环比/名义/实际）"),
    # 实验条件被忽略
    (r"(?:实验|测试|检测)(?:结果|表明)(?![\s\S]{0,40}(?:条件下?|环境中?|温度|压力|浓度|时间))",
     "引用实验结果但没有说明实验条件"),
]


# =============================================================================
# 模式 5: 情感操纵 (EMOTIONAL_MANIPULATION)
# =============================================================================
# 特征: 大量使用情感化词汇；唤起恐惧/愤怒/焦虑；
#       使用儿童/老人等弱势群体唤起保护欲；
#       "再不看就晚了"、"速转"、"紧急通知"等

EMOTIONAL_MANIPULATION_PATTERNS = [
    # 恐惧诉求
    (r"(?:速看|紧急|赶快|马上|立刻|立即)(?:扩散|转发|分享|通知|告诉)(?![\s\S]{0,20}(?:官方|核实|确认))",
     "使用'速转/紧急'等紧迫性词汇催促传播——不给你核实的时间"),
    # 恐惧-儿童/老人
    (r"(?:为了|救救|保护|为了).{0,10}(?:孩子|宝宝|幼儿|儿童|老人|父母|家人)(?:的)?(?:健康|安全|生命|未来)",
     "利用对儿童/老人/家人的保护欲进行情感动员"),
    # 愤怒动员
    (r"(?:还有天理吗|令人发指|丧心病狂|天理难容|忍无可忍|欺人太甚)",
     "使用极端愤怒词汇进行情绪动员"),
    # 虚假紧迫感
    (r"(?:再不看?就)?(?:晚了|来不及了|删前速看|马上就被?删|限时|最后机会)",
     "制造虚假紧迫感——'删前速看'、'再不看就晚了'"),
    # 群体对立
    (r"(?:他们|这帮人|那群人)(?:就是|都是|肯定是|故意|存心|想|要).{0,20}(?:害|骗|坑|整|弄|搞)",
     "构建'他们要害你'的对立叙事，激发敌意和恐惧"),
    # 爱国/民族情绪绑架
    (r"(?:是中国人就|不转不是中国人|炎黄子孙|中华民族到了|国难当头|亡国灭种|汉奸|卖国)",
     "以爱国/民族情绪进行道德绑架，制造'不转发=不爱国'的虚假二分"),
]


# =============================================================================
# 模式 6: 权威绑架 (AUTHORITY_ABUSE)
# =============================================================================
# 特征: 冒用不存在或不相干的权威;
#       "XX机构认证"但机构无认证资质;
#       利用学历/头衔进行不相干领域的背书;
#       "诺贝尔奖得主说..."但与得主的领域完全无关

AUTHORITY_ABUSE_PATTERNS = [
    # 虚假认证
    (r"(?:经|通过|获得)(?:国家|国际|全球|美国|欧盟|FDA|WHO|ISO)(?:认证|认可|批准|推荐)(?![\s\S]{0,30}(?:编号|证书|查询|官网))",
     "声称获得权威认证但没有给出认证编号/可查证信息"),
    # 不相干领域的专家背书
    (r"(?:诺贝尔奖得主|院士|教授|博士|专家).{0,20}(?:说|表示|认为|推荐|建议)(?![\s\S]{0,40}(?:研究领域|专业|论文|发表))",
     "使用权威人物的头衔背书但没有说明该人物是否在被引用领域具有专业资质"),
    # 机构名称误导
    (r"(?:XX|某某|某).{0,5}(?:医院|大学|研究所|科学院)(?:专家|教授|医生|主任)(?:说|称|表示)",
     "使用模糊的机构名称（'某医院专家'），无法验证是否真实存在"),
    # "科学研究表明" 但非科学
    (r"科学(?:研究)?(?:表明|发现|证实|已经证实|早已证实)(?![\s\S]{0,40}(?:论文|期刊|发表|DOI|peer.?review))",
     "使用'科学证实'的权威语气但未提供可查证的学术引用"),
    # 利用名人效应
    (r"(?:明星|网红|名人|大V|主播|博主).{0,10}(?:推荐|代言|说|表示|使用|亲测)(?![\s\S]{0,30}(?:广告|合作|商业))",
     "名人/网红推荐但未披露是否为商业合作"),
]


# =============================================================================
# 模式 7: 语境剥离 (DECONTEXTUALIZATION)
# =============================================================================
# 特征: 将旧事件当作新事件传播;
#       将A国语境下的信息套用到B国;
#       将特定条件下的结论推广为普适结论;
#       将历史上特定时期的信息当作当下信息传播

DECONTEXTUALIZATION_PATTERNS = [
    # 时空错位 — 旧闻当新闻
    (r"(?:刚刚|最新|突发|今天|昨日|近日).{0,30}(?:发生|发现|曝光|出现)(?![\s\S]{0,20}(?:年|月|日))",
     "使用'刚刚/突发'等时效性词汇但信息可能来自过去——需查证发布时间"),
    # 跨文化误用
    (r"(?:国外|外国|美国|日本|欧洲|西方).{0,10}(?:都|全是|从来|从来都).{0,20}(?:中国|我国|国内|我们)",
     "将国外特定情况直接套用到中国语境——忽略了制度/文化/法律的差异"),
    # 特殊→一般 过度推广
    (r"(?:一个|某|个别|偶发|极少数).{0,20}(?:案例|事件|情况|现象).{0,20}(?:说明|证明|意味着|可见|由此).{0,10}(?:所有|全部|都|整个|普遍)",
     "从个别案例跳跃到普遍结论——以偏概全"),
    # 截图/录屏脱离上下文
    (r"(?:截图|录屏|聊天记录)(?:显示|曝光|流出)(?![\s\S]{0,30}(?:上下文|前后文|完整对话|完整视频))",
     "以截图/录屏作为证据但缺乏完整上下文——无法确认是否断章取义"),
    # 政策本身的语境错位
    (r"(?:新政|新规|新法|政策).{0,30}(?:解读|分析|意味着)(?![\s\S]{0,40}(?:原文|全文|官方|细则|试行))",
     "对政策/法规的'解读'但未引用原文或官方解释——可能有主观曲解"),
]


# 所有检测模式的汇总表
ALL_DISTORTION_PATTERNS = [
    (DistortionType.SOURCE_FABRICATION, SOURCE_FABRICATION_PATTERNS),
    (DistortionType.CONTENT_TAMPERING, CONTENT_TAMPERING_PATTERNS),
    (DistortionType.MISQUOTATION, MISQUOTATION_PATTERNS),
    (DistortionType.CONTEXT_STRIPPING, CONTEXT_STRIPPING_PATTERNS),
    (DistortionType.EMOTIONAL_MANIPULATION, EMOTIONAL_MANIPULATION_PATTERNS),
    (DistortionType.AUTHORITY_ABUSE, AUTHORITY_ABUSE_PATTERNS),
    (DistortionType.DECONTEXTUALIZATION, DECONTEXTUALIZATION_PATTERNS),
]

# =============================================================================
# English-language patterns (parallel detection for non-Chinese text)
# =============================================================================
ENGLISH_PATTERNS = {
    DistortionType.SOURCE_FABRICATION: [
        (r"(?i)(stud(?:y|ies)\s+(?:show|suggest|find|reveal|indicate|confirm|prove))(?!.{0,30}(?:DOI|doi|https?://|published\s+in|journal))",
         "Claims 'studies show X' without citing a specific study. Vague authority reference."),
        (r"(?i)(scientists?\s+(?:say|warn|discover|find|reveal|confirm))(?!.{0,40}(?:university|institute|journal|published|DOI))",
         "Vague reference to unnamed 'scientists'. Legitimate science reporting names specific researchers and institutions."),
        (r"(?i)according\s+to\s+(?:research|researchers|experts|scientists)(?!.{0,30}(?:at\s|from\s|published|journal|university))",
         "Vague 'according to research' without naming the research. Unverifiable claim."),
        (r"\d{2,3}\.\d+\s*[%](?!.{0,40}(?:source|according|published|survey\s+of))",
         "Precise percentage given without citing data source. Where does this number come from?"),
    ],
    DistortionType.CONTEXT_STRIPPING: [
        (r"(?i)(toxic|poisonous|deadly|lethal|hazardous|causes?\s+cancer|carcinogenic)(?!.{0,50}(?:dose|dosage|concentration|level|amount|exposure|mg|ppm|ppb|ADI|animal\s+stud))",
         "Claims toxicity/harm without mentioning dosage. The dose makes the poison (Paracelsus principle)."),
        (r"(?i)(banned\s+in\s+(?:Europe|Japan|America|other\s+countries))(?!.{0,30}(?:context|difference|reason|regulation|standard))",
         "Claims something is 'banned abroad' without explaining the regulatory context. Different countries have different regulatory frameworks."),
    ],
    DistortionType.MISQUOTATION: [
        (r"(?i)(proves?|confirms?|conclusively\s+shows?)(?!.{0,30}(?:controlled\s+trial|RCT|randomized|peer.?review|meta.analysis))",
         "Uses 'proves/confirms' for what is likely a correlational study. Scientific studies rarely 'prove' anything."),
    ],
    DistortionType.EMOTIONAL_MANIPULATION: [
        (r"(?i)(share\s+(?:this|now|before|immediately)|forward\s+(?:this|now|to\s+everyone)|delete\s+(?:this|before)|spread\s+the\s+word)(?!.{0,20}(?:verify|check|fact.?check))",
         "Urgency-driven sharing demand. 'Share before deleted' etc. Designed to bypass verification."),
        (r"(?i)(your\s+(?:children|kids|family|loved\s+ones)\s+(?:are|will|being)\s+(?:poisoned|harmed|killed|destroyed|in\s+danger))",
         "Exploiting fear for children/family safety to drive engagement. Emotional manipulation."),
        (r"(?i)(if\s+you\s+(?:love|care\s+about)\s+your\s+(?:country|children|family))(?!.{0,20}(?:evidence|fact|verify))",
         "Moral coercion: 'if you care about X, you must share this'. Emotional blackmail."),
        (r"(?i)(they\s+(?:dont|do\s+not)\s+want\s+you\s+to\s+know|they\s+are\s+hiding|what\s+they\s+are\s+hiding)",
         "Conspiracy framing: 'they don't want you to know the truth'. Emotional manipulation through distrust."),
    ],
    DistortionType.AUTHORITY_ABUSE: [
        (r"(?i)(a\s+(?:doctor|scientist|professor|expert|researcher)\s+(?:reveals?|admits?|confesses?|says?))(?!.{0,30}(?:name|identified|from|at\s|university|credentials))",
         "References an unnamed 'doctor/expert'. Legitimate references name the specific expert and their qualifications."),
        (r"(?i)(Nobel\s+(?:prize|laureate).{0,30}(?:says?|recommends?|endorses?))(?!.{0,30}(?:field|expertise|qualification|relevant))",
         "Appeals to Nobel laureate authority outside their field of expertise."),
    ],
    DistortionType.DECONTEXTUALIZATION: [
        (r"(?i)(BREAKING|JUST\s+IN|URGENT|EMERGENCY|ALERT)(?!.{0,20}(?:official|source|verified))",
         "All-caps urgency markers. Breaking news framing for potentially old or unverified information."),
    ],
}


# =============================================================================
# 主检测函数
# =============================================================================

def detect_distortions(text: str, title: str = "", metadata: dict | None = None) -> DistortionAnalysis:
    """
    对输入文本进行 7 种失真模式的全面检测。

    Args:
        text: 信息正文内容
        title: 信息标题
        metadata: 额外元数据 (如发布时间、平台、作者等)

    Returns:
        DistortionAnalysis — 包含所有匹配的失真类型及详细推理
    """
    if metadata is None:
        metadata = {}

    # 合并标题和正文进行检测 (标题权重更高)
    combined_text = f"{title}\n{title}\n{text}" if title else text

    all_matches: list[DistortionMatch] = []

    for distortion_type, patterns in ALL_DISTORTION_PATTERNS:
        for pattern_regex, description in patterns:
            matches = re.finditer(pattern_regex, combined_text, re.IGNORECASE)
            for match in matches:
                snippet = _extract_snippet(combined_text, match.start(), match.end())
                if not _is_duplicate(all_matches, distortion_type, snippet):
                    all_matches.append(DistortionMatch(
                        distortion_type=distortion_type,
                        description=description,
                        confidence=_estimate_confidence(distortion_type, pattern_regex, combined_text),
                        evidence_snippet=snippet,
                        reasoning=f"Pattern: {pattern_regex[:60]}... -> matched: '{match.group()[:50]}'"
                    ))

    # English-language patterns (parallel detection)
    for distortion_type, patterns in ENGLISH_PATTERNS.items():
        for pattern_regex, description in patterns:
            matches = re.finditer(pattern_regex, combined_text, re.IGNORECASE)
            for match in matches:
                snippet = _extract_snippet(combined_text, match.start(), match.end())
                if not _is_duplicate(all_matches, distortion_type, snippet):
                    all_matches.append(DistortionMatch(
                        distortion_type=distortion_type,
                        description=description,
                        confidence=Confidence.HIGH if distortion_type == DistortionType.EMOTIONAL_MANIPULATION else Confidence.MODERATE,
                        evidence_snippet=snippet,
                        reasoning=f"EN pattern: {pattern_regex[:60]}... -> matched: '{match.group()[:60]}'"
                    ))

    # 计算总体风险等级
    if not all_matches:
        return DistortionAnalysis(
            matches=[],
            overall_risk=Confidence.LOW,
            summary="未检测到明显的信息失真模式。"
        )

    # 按置信度加权
    high_risk_count = sum(1 for m in all_matches if m.confidence in (Confidence.CERTAIN, Confidence.HIGH))
    mid_risk_count = sum(1 for m in all_matches if m.confidence == Confidence.MODERATE)

    if high_risk_count >= 3 or (high_risk_count >= 1 and mid_risk_count >= 3):
        overall = Confidence.HIGH
    elif high_risk_count >= 1 or mid_risk_count >= 2:
        overall = Confidence.MODERATE
    else:
        overall = Confidence.LOW

    # 按失真类型分组汇总
    type_summary: dict[DistortionType, int] = {}
    for m in all_matches:
        type_summary[m.distortion_type] = type_summary.get(m.distortion_type, 0) + 1

    summary_parts = []
    for dt, count in sorted(type_summary.items(), key=lambda x: -x[1]):
        label = _distortion_label(dt)
        summary_parts.append(f"{label} ({count}处)")

    summary = "检测到以下信息失真模式: " + "; ".join(summary_parts) + \
              "。注意: 模式检测仅提示潜在风险，需要人工结合上下文进行最终判断。"

    return DistortionAnalysis(
        matches=all_matches,
        overall_risk=overall,
        summary=summary,
    )


# =============================================================================
# Helper 函数
# =============================================================================

def _extract_snippet(text: str, start: int, end: int, context_chars: int = 80) -> str:
    """提取匹配位置周围的上下文片段"""
    snippet_start = max(0, start - context_chars // 2)
    snippet_end = min(len(text), end + context_chars // 2)
    snippet = text[snippet_start:snippet_end].replace("\n", " ").strip()
    if snippet_start > 0:
        snippet = "..." + snippet
    if snippet_end < len(text):
        snippet = snippet + "..."
    return snippet


def _is_duplicate(existing: list[DistortionMatch], new_type: DistortionType, new_snippet: str) -> bool:
    """检查是否与已有匹配高度重复"""
    for m in existing:
        if m.distortion_type == new_type and m.evidence_snippet == new_snippet:
            return True
    return False


def _estimate_confidence(dt: DistortionType, pattern: str, text: str) -> Confidence:
    """
    根据模式的特征强度和上下文估算置信度。

    规则:
    - 情感操纵类的强情绪词 → HIGH
    - 有具体数据但无来源 → HIGH
    - 一般模式匹配 → MODERATE
    - 弱信号 → LOW
    """
    # 强信号: 明确的情感操纵词汇
    strong_emotional = ["删前速看", "不转不是中国人", "速看", "马上被删", "令人发指"]
    for kw in strong_emotional:
        if kw in text:
            return Confidence.HIGH

    # 强信号: 精确数据无来源
    if dt == DistortionType.SOURCE_FABRICATION and re.search(r'\d+\.?\d*[%％]', text):
        return Confidence.HIGH

    # 强信号: 脱离剂量谈毒性
    if dt == DistortionType.CONTEXT_STRIPPING and re.search(r'有毒|致癌|有害', text):
        if not re.search(r'剂量|摄入量|ADI|mg/kg|LD50', text):
            return Confidence.HIGH

    # 中性信号
    if dt in (DistortionType.EMOTIONAL_MANIPULATION, DistortionType.AUTHORITY_ABUSE):
        return Confidence.MODERATE

    # 弱信号
    return Confidence.MODERATE


def _distortion_label(dt: DistortionType) -> str:
    labels = {
        DistortionType.SOURCE_FABRICATION: "源头伪造",
        DistortionType.CONTENT_TAMPERING: "内容篡改",
        DistortionType.MISQUOTATION: "错误引用",
        DistortionType.CONTEXT_STRIPPING: "忽略语境",
        DistortionType.EMOTIONAL_MANIPULATION: "情感操纵",
        DistortionType.AUTHORITY_ABUSE: "权威绑架",
        DistortionType.DECONTEXTUALIZATION: "语境剥离",
    }
    return labels.get(dt, str(dt.value))
