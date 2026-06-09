"""
领域知识验证器 — 6 大领域的权威知识校验

这是产品的知识防线。
核心原则:
1. 每个主张都需要可验证的证据
2. 只基于公认的权威来源（国标、法规、同行评审论文、官方数据）
3. 遇到不确定的，明确说"不确定"——绝不编造
4. 知识不是推理出来的，是查出来的

领域覆盖:
- 食品安全: GB2760, ADI, 毒理学基础
- 医药健康: 临床试验阶段, 不良反应, 循证医学
- 经济金融: 统计口径, 宏观指标含义
- 法律法规: 法条原文, 司法解释
- 环境气候: IPCC, 碳排放核算
- 历史事件: 一手史料, 多方记录
"""

from __future__ import annotations
import re
from app.engine.types import (
    DomainType, DomainAnalysis, Confidence,
    Evidence, EvidenceType, EvidenceQuality,
)


# =============================================================================
# 食品安全 — 权威知识基
# =============================================================================

FOOD_SAFETY_KNOWLEDGE = {
    "authoritative_sources": [
        "GB 2760-2024 食品安全国家标准 食品添加剂使用标准",
        "JECFA (WHO/FAO 食品添加剂联合专家委员会)",
        "EFSA (欧洲食品安全局)",
        "国家食品安全风险评估中心 (CFSA)",
        "FDA (美国食品药品监督管理局) GRAS 清单",
    ],
    "key_principles": [
        "毒性取决于剂量 — 所有物质在特定剂量下都可能产生毒性 (Paracelsus原则)",
        "ADI (每日允许摄入量) = NOAEL / 安全系数(通常100)",
        "脱离ADI谈毒性没有意义",
        "'天然'不等于'安全'，'人工合成'不等于'有毒'",
        "GB 2760 规定的添加剂都经过了安全评估，在规定范围内使用是安全的",
    ],
    "common_misinformation_patterns": [
        (r"(?:添加剂|防腐剂|色素|香精|甜味剂).{0,10}(?:致癌|有毒|有害|致命)",
         "脱离剂量声称添加剂有害——需要检查是否提及ADI/使用量/GB2760限量"),
        (r"(?:XX|某某|某|这种|那种)(?:物质|成分|东西).{0,10}(?:在国外|在美国|在欧洲|在日本|发达国家)(?:被禁|禁止|禁用|不允许)",
         "声称'国外禁用'——需要核实: (1)是否真的被禁 (2)禁用原因 (3)是否适用于中国"),
        (r"(?:阿斯巴甜|糖精|甜蜜素|亚硝酸盐|苯甲酸|山梨酸|柠檬黄|日落黄).{0,10}(?:致癌|有毒)",
         "针对具体添加剂的恐惧传播——需要引用JECFA/EFSA的评估结论"),
        (r"(?:干净配料表|零添加|无添加|清洁标签).{0,20}(?:更健康|更安全|更好)",
         "零添加营销——'添加'不等于有害，'零添加'不一定更安全"),
    ],
    # 常见错误主张及正确信息
    "fact_checks": {
        "阿斯巴甜致癌": "IARC将阿斯巴甜列为2B类致癌物（证据有限），但JECFA维持其ADI为40mg/kg。一个60kg的成年人每天要喝12-36罐无糖可乐才可能超标。",
        "味精有害": "多个meta分析和FDA/EFSA评估均未发现正常食用味精与不良反应之间存在因果关联。MSG的负面声誉来自于一封信而非科学研究。",
        "零添加更安全": "食品添加剂的作用包括防腐（防止肉毒杆菌等致命细菌）、抗氧化（防止油脂酸败）等。不加防腐剂的食品反而可能更不安全。",
        "所有添加剂都是化工产品": "许多食品添加剂天然存在，如维生素C（抗坏血酸）、柠檬酸等。'化工'不等于有毒。",
        "欧盟/美国/日本都禁了": "不同国家的食品法规体系不同，某物质在A国被禁不等于是有害的——可能是使用习惯/工艺需求/法规体系差异。具体需要查各法规原文。",
    },
    "uncertainty_threshold": "当无法获取以下信息时，应明确说'不确定': (1) 该物质的ADI或NOAEL值 (2) 目标食品中的实际添加量 (3) 消费者的实际摄入量"
}


# =============================================================================
# 医药健康 — 权威知识基
# =============================================================================

MEDICINE_KNOWLEDGE = {
    "authoritative_sources": [
        "国家药品监督管理局 (NMPA)",
        "WHO 基本药物清单",
        "Cochrane 系统评价",
        "NIH PubMed/MEDLINE",
        "药品说明书 (具有法律效力)",
        "中国药典",
    ],
    "key_principles": [
        "随机对照试验 (RCT) 是评估疗效的金标准",
        "相关 ≠ 因果 — 不良事件 ≠ 不良反应",
        "样本量、效应量、p值、置信区间是评估研究的基本指标",
        "药品审批经过严格的Ⅰ-Ⅲ期临床试验",
        "疫苗不良反应监测系统 (AEFI/VAERS) 的存在不等于疫苗不安全",
    ],
    "common_misinformation_patterns": [
        (r"(?:疫苗|接种).{0,15}(?:导致|引起|造成).{0,15}(?:自闭症|死亡|瘫痪|残疾|脑损伤)",
         "声称疫苗导致严重疾病——Andrew Wakefield论文已被撤回，大规模研究已证实MMR疫苗与自闭症无关"),
        (r"(?:中药|西药).{0,5}(?:全是|都是).{0,5}(?:骗人|没用|有害|有毒)",
         "全盘否定某类药物——需要具体药物具体分析"),
        (r"(?:治愈|治好|根治|根除|痊愈).{0,10}(?:癌症|糖尿病|高血压|艾滋病|乙肝)",
         "声称可以'治愈/根治'慢性病——目前医学上极少有慢性病能被根治"),
        (r"(?:医院|医生|大夫).{0,5}(?:故意|存心|为了).{0,5}(?:害|骗|坑|赚钱)",
         "声称医疗机构故意害人——属于阴谋论，需要极高标准的证据"),
        (r"(?:某某|XX|某).{0,5}(?:偏方|秘方|祖传|神药|特效药)",
         "未经验证的疗法——需要临床试验证据"),
    ],
    "fact_checks": {
        "疫苗导致自闭症": "该说法的原始论文(Andrew Wakefield, 1998)已被《柳叶刀》撤回，作者因学术不端被英国医学总会除名。此后数十项研究(n>100万)一致未发现MMR疫苗与自闭症之间的关联。",
        "中药都是安慰剂": "部分中药/天然产物如青蒿素(屠呦呦,诺贝尔奖)、三氧化二砷(砒霜)治疗APL白血病等已有RCT证据。但许多中成药的疗效确实需要更多高质量RCT来评估。需要具体分析。",
        "医院故意让你多检查": "中国的医保DRG/DIP付费改革正在从'按项目付费'转向'按病种付费'，医院的经济激励正在从多开检查转向控制成本。同时，防御性医疗(为避免漏诊而多做检查)是一个复杂的系统性问题。",
    },
    "uncertainty_threshold": "以下情况应明确说'不确定': (1) 治疗方法未经足够规模的RCT验证 (2) 药物相互作用的个案 (3) 罕见病的治疗方案 (4) 尚在临床试验阶段的新药"
}


# =============================================================================
# 经济金融 — 权威知识基
# =============================================================================

ECONOMICS_KNOWLEDGE = {
    "authoritative_sources": [
        "国家统计局 (NBS)",
        "中国人民银行 (PBoC)",
        "国家外汇管理局 (SAFE)",
        "IMF 世界经济展望",
        "World Bank Open Data",
        "BIS 国际清算银行",
    ],
    "key_principles": [
        "GDP、CPI、PMI、失业率等指标各有一套标准统计方法和口径",
        "同比 vs 环比 vs 累计 — 同一指标的不同计算方式解释不同的经济现象",
        "'名义' vs '实际'增速 — 是否扣除通胀/汇率因素",
        "M0/M1/M2 的定义和包含范围",
        "基尼系数 vs 人均收入 — 分布和均值是不同的信息",
    ],
    "common_misinformation_patterns": [
        (r"(?:经济|GDP|失业|通胀|房价|股市|汇率).{0,10}(?:崩溃|完蛋|崩盘|末日|危机|完了)",
         "经济末日论——经济指标的波动不等于崩溃"),
        (r"(?:数据|统计|数字).{0,5}(?:造假|作假|灌水|注水|水分)",
         "声称经济数据全面造假——需要具体指出哪个指标、什么口径、如何验证"),
        (r"(?:人均|平均).{0,10}(?:被|拖|拉).{0,5}(?:平均|后腿|高了|低了)",
         "'被平均'的吐槽——忽略了中位数、分位数等其他统计指标"),
        (r"(?:房价|物价|工资).{0,10}(?:永远|一直|肯定|绝对).{0,10}(?:涨|跌|不涨|不跌)",
         "绝对化的经济预测——经济变量受太多因素影响，无法绝对预测"),
    ],
    "fact_checks": {
        "中国GDP数据造假": "部分研究(如Clark, Pinkovskiy, Sala-i-Martin等)用夜间灯光数据等方法交叉验证中国GDP数据，发现与官方数据大致一致。局部地区统计注水问题确实存在，但不能以此否定整体数据。",
        "通货膨胀比官方数据高很多": "CPI篮子权重可以质疑（住房权重等），但这是方法论层面的讨论。各国有独立的学术机构进行CPI替代测算。这不是'造假'，而是'用什么口径更准确'的合理讨论。",
    },
}


# =============================================================================
# 法律法规 — 权威知识基
# =============================================================================

LAW_KNOWLEDGE = {
    "authoritative_sources": [
        "全国人大/全国人大网 — 法律全文",
        "国务院/国务院公报 — 行政法规",
        "最高人民法院/最高人民检察院 — 司法解释",
        "全国人大常委会法工委 — 立法解释",
        "中国裁判文书网 — 判例",
    ],
    "key_principles": [
        "法条的适用有明确的主体、客体、范围、条件和例外",
        "司法解释是法律适用的重要组成部分",
        "法律草案≠法律——草案在审议过程中可能大幅修改",
        "法律的'解读'需要结合立法原意、上下文和司法实践",
    ],
    "common_misinformation_patterns": [
        (r"(?:新法|新规|新政|草案|条例).{0,15}(?:意味着|表示|说明|等于).{0,15}(?:以后|从此|再也|不再|不能再?)",
         "对法律/政策的解读脱离了原文和官方解释"),
        (r"(?:第[一二三四五六七八九十\d]+条).{0,20}(?:规定|明确).{0,50}(?![\s\S]{0,30}(?:但书|除外|例外|适用范围))",
         "引用法条但忽略了但书/例外条款"),
        (r"(?:违法|犯法|犯罪).{0,10}(?:就是|肯定|一定|必然)(?![\s\S]{0,20}(?:根据|依照|按照|法|条))",
         "未经法律论证就断定违法——法律判断需要构成要件的分析"),
    ],
    "fact_checks": {
        "法律草案被当成已生效法律": "法律草案在征求意见阶段经常被媒体当作'新规'报道。草案不等于法律，最终通过的版本可能有重大变化。",
        "法条断章取义": "许多法条有'但书'（但...除外）和例外条款。引用前半段而忽略后半段是常见的法律误导手段。",
    },
}


# =============================================================================
# 环境气候 — 权威知识基
# =============================================================================

ENVIRONMENT_KNOWLEDGE = {
    "authoritative_sources": [
        "IPCC (政府间气候变化专门委员会)",
        "WMO (世界气象组织)",
        "中国气象局",
        "生态环境部",
        "NASA GISS / NOAA 全球温度记录",
    ],
    "key_principles": [
        "全球变暖是科学共识 (>97%气候科学家的共识)",
        "天气≠气候 — 某地某天的降温不能反驳全球变暖趋势",
        "碳排放核算有标准方法 (如 GHG Protocol)",
        "气候模型存在不确定性，但趋势方向是稳定的",
    ],
    "common_misinformation_patterns": [
        (r"(?:全球变暖|气候变暖|温室效应).{0,10}(?:骗局|谎言|忽悠|假的|瞎说)",
         "声称全球变暖是骗局——与压倒性的科学共识相悖"),
        (r"(?:今年|今天|这几天|某地).{0,5}(?:这么冷|暴雪|降温).{0,10}(?:还|哪).{0,5}(?:全球变暖|变暖|升温)",
         "用局部寒冷天气反驳全球变暖——混淆了天气和气候"),
        (r"(?:碳排放|碳中和|碳达峰|减排).{0,10}(?:阴谋|骗局|陷阱|忽悠)",
         "声称气候行动是阴谋——需要检查背后的利益关联"),
    ],
    "fact_checks": {
        "全球变暖是骗局": "IPCC第六次评估报告(AR6)基于14,000+篇同行评审研究，明确结论：人类活动导致的温室气体排放在过去一个多世纪的全球升温中扮演了主导角色。此结论获得全球195个国家的政府认可。",
        "冬天这么冷还全球变暖？": "全球变暖指的是全球平均气温的长期上升趋势，不等同于每个地方的每个冬天都更暖和。全球变暖甚至可能导致某些地区出现极端寒潮（如极地涡旋减弱南移）。天气是短期局部现象，气候是长期全球趋势。",
    },
}


# =============================================================================
# 历史事件 — 权威知识基
# =============================================================================

HISTORY_KNOWLEDGE = {
    "authoritative_sources": [
        "国家档案局/档案馆档案",
        "一手史料 (同时期记录)",
        "多国交叉历史记录",
        "同行评审的历史学术论文",
    ],
    "key_principles": [
        "孤证不立 — 单一来源不能单独作为历史事实的证据",
        "一手史料 > 二手转述 > 三手评论",
        "同时期记录 > 事后回忆",
        "多方独立记录的一致性增强可信度",
        "历史解释可以有不同视角，但基本事实需要核实",
    ],
    "common_misinformation_patterns": [
        (r"(?:历史|真相|事实|内幕|秘闻|不为人知).{0,10}(?:其实|竟然|居然是|原来是|原?来如此)",
         "'揭秘历史真相'的路数——通常伴随着大量无法验证的声称"),
        (r"(?:据说|据传|传说|坊间).{0,30}(?:其实|真正|真相|真实)",
         "以'据说/据传'之类的模糊来源来重新解释历史"),
    ],
    "fact_checks": {},
}

# 领域知识库索引
DOMAIN_KNOWLEDGE = {
    DomainType.FOOD_SAFETY: FOOD_SAFETY_KNOWLEDGE,
    DomainType.MEDICINE_HEALTH: MEDICINE_KNOWLEDGE,
    DomainType.ECONOMICS_FINANCE: ECONOMICS_KNOWLEDGE,
    DomainType.LAW_REGULATION: LAW_KNOWLEDGE,
    DomainType.ENVIRONMENT_CLIMATE: ENVIRONMENT_KNOWLEDGE,
    DomainType.HISTORY: HISTORY_KNOWLEDGE,
}


# =============================================================================
# 领域识别 — 从文本判断属于哪个领域
# =============================================================================

DOMAIN_KEYWORDS = {
    DomainType.FOOD_SAFETY: [
        "食品", "添加剂", "防腐剂", "色素", "甜味剂", "食品安全", "GB2760",
        "有毒", "致癌", "无毒", "剂量", "配料表", "成分表", "转基因",
        "保质期", "过期", "餐饮", "外卖", "地沟油", "瘦肉精",
        "阿斯巴甜", "亚硝酸盐", "苯甲酸", "山梨酸", "甜蜜素",
    ],
    DomainType.MEDICINE_HEALTH: [
        "疫苗", "药", "治疗", "药品", "副作用", "不良反应", "临床试验",
        "医院", "医生", "诊断", "检查", "手术", "中药", "西药", "偏方",
        "癌症", "糖尿病", "高血压", "新冠", "病毒", "细菌", "感染",
        "自闭症", "免疫", "抗体", "基因", "DNA", "RNA", "mRNA",
        "FDA", "NMPA", "RCT", "双盲", "安慰剂",
    ],
    DomainType.ECONOMICS_FINANCE: [
        "GDP", "CPI", "PMI", "通胀", "物价", "房价", "股市", "A股",
        "利率", "汇率", "人民币", "美元", "货币", "央行", "银行",
        "经济", "失业", "就业", "收入", "消费", "投资", "债务",
        "数据造假", "统计", "造假", "M0", "M1", "M2",
    ],
    DomainType.LAW_REGULATION: [
        "法律", "法规", "规定", "违法", "合法", "法条", "第X条",
        "宪法", "刑法", "民法", "行政", "法院", "法官", "判决",
        "审批", "批准", "许可", "资质", "权利", "义务",
        "人大", "国务院", "部委", "监管", "政策", "新规",
    ],
    DomainType.ENVIRONMENT_CLIMATE: [
        "气候", "变暖", "碳排放", "碳中和", "碳达峰", "温室",
        "污染", "雾霾", "PM2.5", "空气质量", "核废水", "核污染",
        "IPCC", "环保", "生态", "减排", "新能源", "可再生",
        "极端天气", "干旱", "洪水", "台风", "冰川", "海平面",
    ],
    DomainType.HISTORY: [
        "历史", "古代", "近代", "XX年", "世纪", "朝代",
        "战争", "革命", "建国", "建国以来", "千年",
        "真相", "不为人知", "历史上", "原来", "其实",
    ],
}


def identify_domain(text: str) -> DomainType:
    """根据文本关键词识别所属领域"""
    scores: dict[DomainType, int] = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = 0
        text_lower = text.lower()
        for kw in keywords:
            if kw.lower() in text_lower:
                score += 1
        scores[domain] = score

    best = max(scores, key=scores.get)
    if scores[best] >= 2:
        return best
    return DomainType.GENERAL


# =============================================================================
# 主张提取 — 从文本中提取可验证的知识主张
# =============================================================================

CLAIM_PATTERNS = [
    # 因果主张
    (r"(?P<claim>(?:因为|由于).{5,80}(?:所以|因此|导致|造成|引起|引发).{5,80})", "causal"),
    # 事实主张
    (r"(?P<claim>(?:根据|据|研究|数据|实验|调查|统计)(?:表明|显示|发现|证实|证明).{10,100})", "factual"),
    # 分类/属性主张
    (r"(?P<claim>(?:是|属于|等同于|相当于|就是).{5,60}(?:致癌物|有毒|有害|安全|无毒|健康|危险|骗局|谎言))", "classification"),
    # 数量主张
    (r"(?P<claim>(?:超过|达到|占比|高达|约|大约|左右|至少|最多|超过?)\s*\d+(?:\.\d+)?\s*(?:%|亿|万|千|倍|人|元|美元|吨|千克|克|毫克).{0,30})", "quantitative"),
    # 比较主张
    (r"(?P<claim>(?:比|较|高于|低于|大于|小于|相当于).{5,60}(?:倍|%|多|少|高|低))", "comparative"),
]


def extract_claims(text: str) -> list[dict]:
    """从文本中提取可验证的知识主张"""
    claims = []
    for pattern, claim_type in CLAIM_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            claim_text = match.group("claim") if "claim" in match.groupdict() else match.group()
            if len(claim_text) >= 10:
                claims.append({
                    "text": claim_text.strip(),
                    "type": claim_type,
                    "verifiable": claim_type in ("factual", "quantitative", "classification"),
                })
    # 去重
    seen = set()
    unique = []
    for c in claims:
        if c["text"] not in seen:
            seen.add(c["text"])
            unique.append(c)
    return unique[:20]  # 最多提取20条主张


# =============================================================================
# 知识验证 — 检查主张是否与已知事实一致
# =============================================================================

def verify_claim(claim: str, domain: DomainType) -> dict:
    """
    验证单一主张是否符合已知知识。

    重要: 这个函数只做模式匹配和已知知识比对。
    它不能替代真正的专家判断。
    遇到不在知识库中的主张，返回 uncertain。
    """
    result = {
        "claim": claim,
        "verdict": "unverified",  # verified / refuted / unverified / uncertain
        "explanation": "",
        "references": [],
    }

    knowledge = DOMAIN_KNOWLEDGE.get(domain)
    if not knowledge:
        result["verdict"] = "uncertain"
        result["explanation"] = f"当前领域({domain.value})的知识库尚未充分构建，无法对这条主张进行自动验证"
        return result

    # 检查是否匹配已知的常见错误信息
    for pattern, correct_info in knowledge.get("common_misinformation_patterns", []):
        if re.search(pattern, claim, re.IGNORECASE):
            result["verdict"] = "potential_misinfo"
            result["explanation"] = correct_info
            return result

    # 检查是否匹配已知的 fact_check
    for keyword, refutation in knowledge.get("fact_checks", {}).items():
        if keyword in claim:
            result["verdict"] = "refuted"
            result["explanation"] = refutation
            result["references"] = knowledge.get("authoritative_sources", [])[:3]
            return result

    # 未匹配 — 不确定
    result["verdict"] = "uncertain"
    result["explanation"] = (
        "该主张未匹配已知知识库。这不意味着它必然错误，"
        "而是说当前系统的知识库不足以对其进行自动验证。"
        "建议查阅以下权威来源进行人工核实。"
    )
    result["references"] = knowledge.get("authoritative_sources", [])[:3]

    return result


# =============================================================================
# 主入口
# =============================================================================

def analyze_domain(text: str, title: str = "") -> DomainAnalysis:
    """
    分析文本中涉及的知识领域，提取主张，并尝试验证。

    Returns:
        DomainAnalysis — 包含领域识别、提取的主张和验证结果
    """
    combined = f"{title}\n{text}" if title else text
    domain = identify_domain(combined)

    claims = extract_claims(combined)

    verified = []
    unverified = []
    refuted = []
    knowledge_gaps = []

    for claim in claims:
        result = verify_claim(claim["text"], domain)
        claim["verification"] = result
        if result["verdict"] == "refuted":
            refuted.append(claim)
        elif result["verdict"] == "potential_misinfo":
            refuted.append(claim)
        elif result["verdict"] == "verified":
            verified.append(claim)
        else:
            unverified.append(claim)

    # 知识缺口: 列出本领域的关键原则，帮助读者自我验证
    knowledge = DOMAIN_KNOWLEDGE.get(domain, {})
    if knowledge:
        knowledge_gaps = [
            f"本领域关键原则: {p}" for p in knowledge.get("key_principles", [])
        ]
        uncertainty = knowledge.get("uncertainty_threshold", "")
        if uncertainty:
            knowledge_gaps.append(f"不确定声明: {uncertainty}")

    return DomainAnalysis(
        domain=domain,
        claims=claims,
        verified_claims=verified,
        unverified_claims=unverified,
        refuted_claims=refuted,
        knowledge_gaps=knowledge_gaps,
    )
