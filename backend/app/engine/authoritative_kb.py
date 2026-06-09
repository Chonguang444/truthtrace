"""
权威知识库 — 8大领域可引用来源 + 常见事实核查

每条知识附带:
- 完整引用格式 (类似学术论文参考文献)
- 来源 URL
- 证据质量等级
- 最后验证日期

原则: 不创造知识，只整理已有权威来源。不确定就说"不确定"。

覆盖领域: 食品安全, 医药健康, 经济金融, 法律法规, 环境气候, 历史, 科技, 教育
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

# =============================================================================
# 知识条目
# =============================================================================

@dataclass
class KnowledgeEntry:
    """一条可引用的知识"""
    id: str
    claim: str                          # 知识主张
    source_title: str                   # 来源名称
    source_url: str                     # 来源 URL
    source_type: str                    # national_standard / government / academic_paper / international_consensus
    citation: str                       # 完整引用格式
    evidence_level: str                 # strong / moderate / weak
    verified_date: str = "2026-06"      # 最后验证时间
    limitations: str = ""               # 该知识的适用范围/局限性
    counter_claim: str = ""             # 反面观点(如果有)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "claim": self.claim,
            "source_title": self.source_title,
            "source_url": self.source_url,
            "source_type": self.source_type,
            "citation": self.citation,
            "evidence_level": self.evidence_level,
            "verified_date": self.verified_date,
            "limitations": self.limitations,
            "counter_claim": self.counter_claim,
        }


# =============================================================================
# 食品安全
# =============================================================================

FOOD_SAFETY_KB = [
    KnowledgeEntry(
        id="fs-001",
        claim="阿斯巴甜的每日允许摄入量(ADI)为0-40 mg/kg体重，正常摄入安全",
        source_title="JECFA (WHO/FAO) 食品添加剂联合专家委员会评估报告",
        source_url="https://www.who.int/teams/nutrition-and-food-safety/databases/jecfa",
        source_type="international_consensus",
        citation="JECFA. (2023). Evaluation of certain food additives (TRS 1065). WHO Technical Report Series.",
        evidence_level="strong",
        limitations="仅适用于一般人群。苯丙酮尿症(PKU)患者因无法代谢苯丙氨酸应避免摄入阿斯巴甜。",
        counter_claim="IARC将阿斯巴甜列为2B类致癌物(证据有限)，与JECFA的ADI评估并行。2B类意味着证据有限且不充分。",
    ),
    KnowledgeEntry(
        id="fs-002",
        claim="食品添加剂在GB 2760规定范围内使用是安全的，经过系统毒性评估",
        source_title="GB 2760-2024 食品安全国家标准 食品添加剂使用标准",
        source_url="https://std.samr.gov.cn/gb/search/gbDetailed?id=GB%202760",
        source_type="national_standard",
        citation="中华人民共和国国家卫生健康委员会. (2024). GB 2760-2024 食品添加剂使用标准.",
        evidence_level="strong",
        limitations="标准本身不断更新。个别消费者可能对特定添加剂有过敏反应(如亚硫酸盐)。",
    ),
    KnowledgeEntry(
        id="fs-003",
        claim="毒性取决于剂量。所有物质在特定剂量下都可能产生毒性(Paracelsus原则)",
        source_title="毒理学基本原理 (基础毒理学教科书共识)",
        source_url="https://www.who.int/health-topics/chemical-safety",
        source_type="international_consensus",
        citation="毒理学基础共识: 'the dose makes the poison' — Paracelsus (1493-1541). 现代毒理学教材通用原则。",
        evidence_level="strong",
    ),
    KnowledgeEntry(
        id="fs-004",
        claim="声称'国外禁用的添加剂'需要具体核实。不同国家的食品法规体系存在差异，禁用原因可能是工艺需求、使用习惯或法规框架不同，不一定等于安全性问题。",
        source_title="多家国际权威机构数据库 (JECFA, EFSA, FDA)",
        source_url="https://www.who.int/teams/nutrition-and-food-safety/databases/jecfa",
        source_type="international_consensus",
        citation="JECFA安全评估数据库; EFSA食品添加剂重新评估计划; FDA GRAS物质清单。",
        evidence_level="moderate",
        limitations="需要针对具体的物质和国家进行逐一核实。笼统的'国外都禁了'不应采信。",
    ),
    KnowledgeEntry(
        id="fs-005",
        claim="经过安全评估的转基因作物与常规作物同样安全，不存在独特的健康风险",
        source_title="美国国家科学院 (NASEM) 转基因作物全面评估报告",
        source_url="https://nap.nationalacademies.org/catalog/23395",
        source_type="international_consensus",
        citation="National Academies of Sciences, Engineering, and Medicine. (2016). Genetically Engineered Crops: Experiences and Prospects. Washington, DC: The National Academies Press. doi:10.17226/23395.",
        evidence_level="strong",
        limitations="报告比较的是'已批准的转基因作物'与'常规作物'的安全性。不能推断为'所有转基因作物绝对安全'——每个新的转基因品种仍需独立评估。",
    ),
]

# =============================================================================
# 医药健康
# =============================================================================

MEDICINE_KB = [
    KnowledgeEntry(
        id="med-001",
        claim="MMR疫苗与自闭症之间不存在因果关系。原始论文已被撤回，后续大规模研究一致否定了该关联。",
        source_title="Taylor et al. (2014) 系统综述, n=1,266,327; Cochrane系统评价",
        source_url="https://pubmed.ncbi.nlm.nih.gov/24814559/",
        source_type="academic_paper",
        citation="Taylor LE, Swerdfeger AL, Eslick GD. (2014). Vaccines are not associated with autism: an evidence-based meta-analysis of case-control and cohort studies. Vaccine, 32(29), 3623-3629.",
        evidence_level="strong",
        limitations="科学研究不能'证明不存在关联'——只能证明在现有证据条件下未发现关联。",
        counter_claim="Wakefield et al. (1998) 原始论文已被《柳叶刀》于2010年撤回。作者因学术不端被英国医学总会(GMC)除名。",
    ),
    KnowledgeEntry(
        id="med-002",
        claim="随机对照试验(RCT)是评估医疗干预效果的金标准。观察性研究只能发现关联，不能证明因果。",
        source_title="循证医学基本原理 (牛津循证医学中心)",
        source_url="https://www.cebm.ox.ac.uk/resources/levels-of-evidence",
        source_type="international_consensus",
        citation="Oxford Centre for Evidence-Based Medicine. (2009). Levels of Evidence.",
        evidence_level="strong",
    ),
    KnowledgeEntry(
        id="med-003",
        claim="中药/天然产物中有部分已被现代科学方法验证有效(如青蒿素治疗疟疾)，也有大量产品缺乏高质量RCT证据。需要具体分析。",
        source_title="屠呦呦 (2015 诺贝尔生理学/医学奖)",
        source_url="https://www.nobelprize.org/prizes/medicine/2015/tu/facts/",
        source_type="academic_paper",
        citation="Tu Y. (2011). The discovery of artemisinin (qinghaosu) and gifts from Chinese medicine. Nature Medicine, 17(10), 1217-1220.",
        evidence_level="moderate",
        limitations="青蒿素的成功不能推广为'所有中药都有效'。每个药物/疗法需要独立的RCT证据。",
    ),
]

# =============================================================================
# 经济金融
# =============================================================================

ECONOMICS_KB = [
    KnowledgeEntry(
        id="eco-001",
        claim="GDP、CPI等宏观指标的统计有国际标准化方法。中国的统计制度采用SNA(国民账户体系)和IMF SDDS(数据公布特殊标准)规范。",
        source_title="国家统计局, IMF SDDS",
        source_url="https://www.stats.gov.cn/",
        source_type="government",
        citation="国家统计局. 国民经济核算体系. IMF. Special Data Dissemination Standard (SDDS).",
        evidence_level="strong",
        limitations="任何统计估计都有误差范围。GDP统计尤其存在未观测经济(灰色经济)的估计困难。这是全球性的方法论挑战，而非中国独有。",
    ),
    KnowledgeEntry(
        id="eco-002",
        claim="名义增速与实际增速的区别: 名义增速未扣除通胀因素，实际增速扣除了通胀影响。引用增速时应明确口径。",
        source_title="宏观经济学基础 (通用教科书知识)",
        source_url="https://www.imf.org/en/Publications/WEO",
        source_type="international_consensus",
        citation="IMF. (2025). World Economic Outlook — 统计附录中明确说明了名义GDP与实际GDP的计算方法。",
        evidence_level="strong",
    ),
]

# =============================================================================
# 法律法规
# =============================================================================

LAW_KB = [
    KnowledgeEntry(
        id="law-001",
        claim="法律条文有严格的适用范围和例外条款(但书)。引用法条时应查询原文，不应仅凭他人转述。",
        source_title="《中华人民共和国立法法》",
        source_url="https://www.npc.gov.cn/",
        source_type="national_standard",
        citation="全国人民代表大会. (2023修正). 中华人民共和国立法法.",
        evidence_level="strong",
    ),
    KnowledgeEntry(
        id="law-002",
        claim="法律草案≠法律。草案在审议过程中可能大幅修改。将草案当作已生效法律传播是常见的信息错误。",
        source_title="立法程序常识",
        source_url="https://www.npc.gov.cn/",
        source_type="government",
        citation="全国人民代表大会. 立法程序说明.",
        evidence_level="strong",
    ),
]

# =============================================================================
# 环境气候
# =============================================================================

CLIMATE_KB = [
    KnowledgeEntry(
        id="env-001",
        claim="人类活动导致的温室气体排放是过去一个多世纪全球变暖的主导因素。此结论获得全球195个国家政府认可。",
        source_title="IPCC 第六次评估报告 (AR6)",
        source_url="https://www.ipcc.ch/report/ar6/",
        source_type="international_consensus",
        citation="IPCC. (2021-2023). Sixth Assessment Report (AR6). Working Group I: The Physical Science Basis. Cambridge University Press.",
        evidence_level="strong",
        limitations="气候模型存在不确定性，但趋势方向是稳健的。本地极端天气事件的归因(attribution)仍在科学进步中。",
    ),
    KnowledgeEntry(
        id="env-002",
        claim="天气不等于气候。某地某天的寒冷不能反驳全球变暖趋势。全球变暖甚至可能导致某些地区的极端寒潮。",
        source_title="WMO (世界气象组织) 气候服务",
        source_url="https://public.wmo.int/",
        source_type="international_consensus",
        citation="WMO. (2024). State of the Global Climate 2023. WMO-No. 1347.",
        evidence_level="strong",
    ),
    KnowledgeEntry(
        id="env-003",
        claim="通信基站使用非电离辐射(射频辐射)，能量远不足以破坏DNA引起癌症。IARC将射频辐射列为2B类(证据有限)，与咖啡和腌制蔬菜同一类。",
        source_title="WHO/IARC, 国际非电离辐射防护委员会 (ICNIRP)",
        source_url="https://www.who.int/news-room/questions-and-answers/item/radiation-5g-mobile-networks-and-health",
        source_type="international_consensus",
        citation="IARC. (2013). Non-Ionizing Radiation, Part 2: Radiofrequency Electromagnetic Fields. IARC Monographs, Vol. 102.",
        evidence_level="strong",
        limitations="IARC分类是对证据强度的分类(2B=可能致癌，证据有限)，不是对风险的定量评估。",
    ),
]

# =============================================================================
# 科技
# =============================================================================

TECH_KB = [
    KnowledgeEntry(
        id="tech-001",
        claim="AI目前的'毁灭人类'叙事是基于科幻想象，而非技术现实。当前的AI系统(包括LLM)没有自主意识、没有意图、没有生存本能。",
        source_title="学术共识 (多位AI研究者公开声明)",
        source_url="https://hai.stanford.edu/",
        source_type="academic_paper",
        citation="Stanford HAI. (2024). AI Index Report. 注意区分: 长期AI对齐(alignment)研究是合理的学术领域，与AI会'觉醒'的科幻叙事是两个不同的概念。",
        evidence_level="moderate",
        limitations="关于未来AGI/ASI的讨论属于推测范畴。目前关于AI安全的研究主要是关于对齐(alignment)、偏见(bias)和滥用(misuse)等问题。",
    ),
]

# =============================================================================
# 教育
# =============================================================================

EDUCATION_KB = [
    KnowledgeEntry(
        id="edu-001",
        claim="'这一代年轻人被毁了'的叙事在每个时代都反复出现。从小说→广播→漫画→电视→游戏→互联网→手机→短视频——道德恐慌的结构高度一致。",
        source_title="历史社会心理学研究 (道德恐慌史)",
        source_url="https://en.wikipedia.org/wiki/Moral_panic",
        source_type="academic_paper",
        citation="Cohen, S. (1972). Folk Devils and Moral Panics. 后续研究: springhall J. (1998), Sternheimer K. (2003) 等。",
        evidence_level="strong",
        limitations="这不意味着新技术/新媒体对青少年没有任何影响——只是说历史表明'彻底被毁'的预测极少成立。合理的影响评估应该基于实证而非恐慌。",
    ),
]

# =============================================================================
# 领域索引
# =============================================================================

DOMAIN_KB = {
    "food_safety": FOOD_SAFETY_KB,
    "medicine_health": MEDICINE_KB,
    "economics_finance": ECONOMICS_KB,
    "law_regulation": LAW_KB,
    "environment_climate": CLIMATE_KB,
    "tech": TECH_KB,
    "education": EDUCATION_KB,
}


# =============================================================================
# 查询接口
# =============================================================================

def search_knowledge(query: str, domain: str | None = None, limit: int = 5) -> list[KnowledgeEntry]:
    """跨知识库搜索相关条目"""
    results = []
    q = query.lower()

    domains = [domain] if domain else list(DOMAIN_KB.keys())
    for d in domains:
        entries = DOMAIN_KB.get(d, [])
        for entry in entries:
            if (q in entry.claim.lower() or q in entry.citation.lower() or
                q in entry.source_title.lower()):
                results.append(entry)

    return results[:limit]


def get_fact_check(claim_hint: str) -> list[dict]:
    """根据主张提示查找相关的已知事实核查"""
    entries = search_knowledge(claim_hint, limit=3)
    return [e.to_dict() for e in entries]


def generate_reference_list(domain: str) -> list[dict]:
    """生成完整的参考文献列表"""
    entries = DOMAIN_KB.get(domain, [])
    return [{
        "source": e.source_title,
        "url": e.source_url,
        "type": e.source_type,
        "citation": e.citation,
    } for e in entries]
