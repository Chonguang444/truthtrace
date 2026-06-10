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
    KnowledgeEntry(
        id="fs-006",
        claim="IARC致癌物分类是对证据强度的分类(1类=确定致癌, 2A=很可能, 2B=可能, 3类=无法分类)，不是对风险的定量评估",
        source_title="IARC Monographs on the Identification of Carcinogenic Hazards to Humans",
        source_url="https://monographs.iarc.who.int/",
        source_type="international_consensus",
        citation="IARC. (2024). Preamble to the IARC Monographs (Amended January 2019). Lyon: International Agency for Research on Cancer.",
        evidence_level="strong",
        limitations="IARC仅评估'危害'(hazard)，不评估'风险'(risk)。同一类别的物质实际风险可能相差巨大。如加工肉类(1类)和吸烟(1类)的致癌风险完全不同。",
    ),
    KnowledgeEntry(
        id="fs-007",
        claim="日本核废水排放: IAEA已审查并确认ALPS处理水中的放射性核素水平远低于国际安全标准。氚的排放浓度低于WHO饮用水标准的1/7。",
        source_title="IAEA Comprehensive Report on ALPS Treated Water",
        source_url="https://www.iaea.org/topics/response/fukushima-daiichi-nuclear-accident/fukushima-daiichi-alps-treated-water-discharge",
        source_type="international_consensus",
        citation="IAEA. (2023). Comprehensive Report on the Safety Review of the ALPS-Treated Water at the Fukushima Daiichi Nuclear Power Station.",
        evidence_level="strong",
        limitations="IAEA审查的是日本政府计划的合规性，独立监测仍在持续。周边国家的担忧主要涉及信任和沟通问题而非技术安全问题。",
    ),
    KnowledgeEntry(
        id="fs-008",
        claim="味精(谷氨酸钠)的食用安全性已获得多个权威机构的审查确认。正常膳食摄入量下无不良健康效应。",
        source_title="JECFA, FDA, EFSA 联合评估",
        source_url="https://www.fda.gov/food/food-additives-petitions/questions-and-answers-monosodium-glutamate-msg",
        source_type="international_consensus",
        citation="JECFA. (1988). L-Glutamic acid and its salts (TRS 776). FDA. (2012). MSG Safety Assessment. EFSA. (2017). Re-evaluation of glutamic acid (E620) (EFSA Journal 15(7):4910).",
        evidence_level="strong",
        limitations="极少数敏感个体可能在摄入大量味精后出现暂时性不适(MSG symptom complex)，但多中心双盲研究未证实此现象与味精有稳定关联。",
    ),
    KnowledgeEntry(
        id="fs-009",
        claim="中国预包装食品营养标签(GB 28050)要求标注能量、蛋白质、脂肪、碳水化合物和钠。'0添加''零防腐剂'等声称受法律规范。",
        source_title="GB 28050 食品安全国家标准 预包装食品营养标签通则",
        source_url="https://std.samr.gov.cn/",
        source_type="national_standard",
        citation="中华人民共和国国家卫生健康委员会. GB 28050 预包装食品营养标签通则.",
        evidence_level="strong",
        limitations="'零添加'是一种营销用语，不意味着产品更安全。在保质期内不加防腐剂的食品需要通过其他方式(如高盐/高糖/真空包装)来实现防腐。",
    ),
    KnowledgeEntry(
        id="fs-010",
        claim="反式脂肪酸主要来自部分氢化植物油。WHO建议将其摄入量限制在总能量摄入的1%以下(约每天<2.2g)。中国于GB 28050中要求标注反式脂肪含量。",
        source_title="WHO REPLACE 行动框架 + GB 28050",
        source_url="https://www.who.int/teams/nutrition-and-food-safety/replace-trans-fat",
        source_type="international_consensus",
        citation="WHO. (2018). REPLACE: An action package to eliminate industrially-produced trans-fatty acids. GB 28050 预包装食品营养标签通则.",
        evidence_level="strong",
        limitations="天然食品(如奶制品和反刍动物肉)中含有少量天然反式脂肪，这些与工业反式脂肪的健康影响可能不同。",
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
    KnowledgeEntry(
        id="med-004",
        claim="抗生素只能治疗细菌感染，对病毒感染(如流感、普通感冒、COVID-19)无效。滥用抗生素会导致耐药性。",
        source_title="WHO 抗微生物药物耐药性全球行动计划",
        source_url="https://www.who.int/health-topics/antimicrobial-resistance",
        source_type="international_consensus",
        citation="WHO. (2015). Global Action Plan on Antimicrobial Resistance. Geneva: WHO Press.",
        evidence_level="strong",
        limitations="某些特定的抗病毒药物可用于特定病毒感染(如奥司他韦用于流感)，这些不是抗生素。",
    ),
    KnowledgeEntry(
        id="med-005",
        claim="癌症不是单一疾病，是数百种疾病的统称。不同类型和分期的癌症预后差异巨大。'治愈癌症'的说法需要明确具体癌种和分期。",
        source_title="NCI (美国国家癌症研究所) — Cancer Statistics",
        source_url="https://www.cancer.gov/about-cancer/understanding/statistics",
        source_type="government",
        citation="National Cancer Institute. (2024). Cancer Statistics. SEER Program.",
        evidence_level="strong",
        limitations="某些早期癌症的5年生存率超过90%，某些晚期癌症的5年生存率低于10%。5年生存率≠治愈率。",
    ),
    KnowledgeEntry(
        id="med-006",
        claim="退热药(如对乙酰氨基酚/布洛芬)用于治疗发热，但不能消除病因。发热是人体免疫反应的一部分，适度发热(≤38.5°C)不一定需要药物干预。",
        source_title="WHO Model List of Essential Medicines + 临床共识",
        source_url="https://www.who.int/publications/i/item/WHO-MHP-HPS-EML-2023.02",
        source_type="international_consensus",
        citation="WHO. (2023). Model List of Essential Medicines, 23rd list. 临床共识: NICE Guideline NG143.",
        evidence_level="strong",
        limitations="婴儿和有基础疾病的患者需要个体化的发热管理方案。具体用药请遵医嘱。",
    ),
    KnowledgeEntry(
        id="med-007",
        claim="中国国家免疫规划(NIP)目前包含14种疫苗预防15种疾病。疫苗的群体免疫保护需要高接种率(通常>90-95%)。",
        source_title="中国疾病预防控制中心 — 国家免疫规划",
        source_url="https://www.chinacdc.cn/jkzt/ymyjz/",
        source_type="government",
        citation="国家卫生健康委员会. (2024). 国家免疫规划疫苗儿童免疫程序及说明.",
        evidence_level="strong",
        limitations="接种率下降可能导致已被控制的传染病卷土重来(如麻疹在多个国家重新爆发)。",
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
    KnowledgeEntry(
        id="eco-003",
        claim="CPI中的居住类权重在欧洲和美国较高(约30-40%)，在中国较低(历史上约13-20%)。这是将CPI与'实际感受'比较时常见的方法论差异。",
        source_title="国家统计局 CPI编制方法说明 + BLS CPI Methodology",
        source_url="https://www.stats.gov.cn/",
        source_type="government",
        citation="国家统计局. CPI编制方法说明. BLS. Consumer Price Index: Concepts and Methods.",
        evidence_level="strong",
        limitations="CPI是衡量一篮子商品和服务价格变化的指标，不是衡量绝对生活成本的指标。不同人群的消费结构不同，个人感受可能与总体CPI不同。",
    ),
    KnowledgeEntry(
        id="eco-004",
        claim="M2/GDP比率常被用来衡量经济货币化程度。中国M2/GDP较高(约200%+)的原因包括高储蓄率、以银行信贷为主的金融结构、以及统计口径差异。高M2/GDP不等于'货币超发'或'即将崩溃'。",
        source_title="中国人民银行统计数据 + BIS国际清算银行",
        source_url="http://www.pbc.gov.cn/",
        source_type="government",
        citation="中国人民银行. 货币统计概览. BIS. (2024). Credit-to-GDP gaps.",
        evidence_level="moderate",
        limitations="各国金融结构差异巨大(如美国以资本市场为主、中国以银行信贷为主)，直接比较M2/GDP比率需要结合金融体系结构来理解。",
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
    KnowledgeEntry(
        id="env-004",
        claim="中国提出的'双碳'目标(2030碳达峰、2060碳中和)已写入《国家适应气候变化战略2035》。中国是全球最大的可再生能源投资国和生产国。",
        source_title="国务院《2030年前碳达峰行动方案》+ IEA 全球能源报告",
        source_url="https://www.gov.cn/",
        source_type="government",
        citation="国务院. (2021). 2030年前碳达峰行动方案. IEA. (2024). World Energy Outlook.",
        evidence_level="strong",
        limitations="实现碳中和目标需要能源结构的根本性转型。目标本身不等于实现路径。煤炭目前仍是中国能源结构的重要组成部分。",
    ),
    KnowledgeEntry(
        id="env-005",
        claim="PM2.5的健康效应已有大量流行病学证据。WHO推荐年均PM2.5不超过5μg/m³。中国的年均浓度近年来持续下降但多数城市仍高于WHO推荐值。",
        source_title="WHO 全球空气质量指南 + 中国生态环境部数据",
        source_url="https://www.who.int/publications/i/item/9789240034228",
        source_type="international_consensus",
        citation="WHO. (2021). WHO Global Air Quality Guidelines. 生态环境部. (2024). 中国生态环境状况公报.",
        evidence_level="strong",
        limitations="中国的空气质量改善速度是全球最快的之一。但不同城市和季节的空气质量差异巨大。",
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
    KnowledgeEntry(
        id="tech-002",
        claim="5G基站使用非电离电磁辐射(射频辐射)。其能量远低于电离辐射(如X射线、γ射线)，不足以直接破坏DNA分子键。",
        source_title="WHO 电磁场与公共卫生",
        source_url="https://www.who.int/news-room/questions-and-answers/item/radiation-5g-mobile-networks-and-health",
        source_type="international_consensus",
        citation="WHO. (2020). 5G mobile networks and health. ICNIRP. (2020). Guidelines for Limiting Exposure to Electromagnetic Fields (100 kHz to 300 GHz). Health Physics, 118(5), 483-524.",
        evidence_level="strong",
        limitations="IARC将射频辐射列为2B类(可能致癌)——和咖啡、腌制蔬菜同一类。长期随访研究仍在进行中。",
    ),
    KnowledgeEntry(
        id="tech-003",
        claim="量子计算机目前处于含噪声中等规模量子(NISQ)阶段，尚未实现通用量子计算。'量子霸权'指的是在特定计算问题上超越经典计算机，不是全面超越。",
        source_title="Preskill (2018) + Nature Reviews Physics",
        source_url="https://arxiv.org/abs/1801.00862",
        source_type="academic_paper",
        citation="Preskill J. (2018). Quantum Computing in the NISQ era and beyond. Quantum, 2, 79. Arute F. et al. (2019). Quantum supremacy using a programmable superconducting processor. Nature, 574, 505-510.",
        evidence_level="strong",
        limitations="量子计算在不同基准上的表现差异巨大。Google和IBM等使用了不同的'量子优势'定义。",
    ),
    KnowledgeEntry(
        id="tech-004",
        claim="核聚变发电的商业化仍面临巨大工程挑战。'人造太阳'的实验装置(如ITER、EAST)是研究反应堆，不是商用发电站。学术界普遍估计商业化需20-30年以上。",
        source_title="ITER Project + 中国核工业集团",
        source_url="https://www.iter.org/",
        source_type="international_consensus",
        citation="ITER Organization. (2024). Project Timeline. 国家原子能机构. 中国核聚变研究进展.",
        evidence_level="strong",
        limitations="'人造太阳'运行103秒是指等离子体约束时间，而非持续能源输出。等离子体约束时间、能量增益因子Q值、材料耐受性是三个不同的问题。",
    ),
    KnowledgeEntry(
        id="tech-005",
        claim="'国产芯片'不等同于'完全自主知识产权'。芯片制造涉及设计、制造、封装、测试等多个环节，每个环节有不同程度的自主化。需要具体分析。",
        source_title="中国半导体行业协会 + SIA 行业报告",
        source_url="https://www.semiconductors.org/",
        source_type="government",
        citation="中国半导体行业协会. 中国集成电路产业发展报告. SIA. (2024). State of the U.S. Semiconductor Industry.",
        evidence_level="moderate",
        limitations="芯片产业的供应链高度全球化，各国依赖程度不同。具体芯片的自主化程度需要查阅其技术规格和供应链信息。",
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
    KnowledgeEntry(
        id="edu-002",
        claim="屏幕时间与儿童发展的关系复杂且依赖内容质量、互动方式和时长。不是'屏幕=有害'的简单等式。WHO建议2岁以下不应有屏幕时间，2-5岁每天不超过1小时。",
        source_title="WHO Guidelines on Physical Activity, Sedentary Behaviour and Sleep",
        source_url="https://www.who.int/publications/i/item/9789241550536",
        source_type="international_consensus",
        citation="WHO. (2019). Guidelines on physical activity, sedentary behaviour and sleep for children under 5 years of age. 美国儿科学会(AAP). (2016). Media and Young Minds.",
        evidence_level="strong",
        limitations="高质量的教育性互动内容与被动观看娱乐内容的效应可能截然不同。视频通话和观看视频也对儿童的影响不同。",
    ),
    KnowledgeEntry(
        id="edu-003",
        claim="游戏成瘾(游戏障碍)已于2019年被WHO列入ICD-11。但诊断标准严格(持续12个月以上、功能显著受损等)，绝大多数游戏玩家不符合诊断标准。",
        source_title="ICD-11 国际疾病分类第11版 + 多项流行病学调查",
        source_url="https://icd.who.int/browse11/l-m/en#/http://id.who.int/icd/entity/1448597234",
        source_type="international_consensus",
        citation="WHO. (2019). ICD-11: 6C51 Gaming disorder. Przybylski AK et al. (2017). Internet gaming disorder: Investigating the clinical relevance of a new phenomenon. American Journal of Psychiatry, 174(3), 230-236.",
        evidence_level="strong",
        limitations="游戏障碍的患病率估计在1-3%之间(因地区和诊断标准而异)。将'喜欢玩游戏'与'成瘾'混为一谈会导致过度恐慌。",
    ),
    KnowledgeEntry(
        id="edu-004",
        claim="中国的'双减'政策(2021)旨在减少义务教育阶段的作业负担和校外培训负担。其效果和影响仍在评估中。任何简单的'双减后一切都变了'的论断都不够严谨。",
        source_title="中共中央办公厅 国务院办公厅《关于进一步减轻义务教育阶段学生作业负担和校外培训负担的意见》",
        source_url="https://www.gov.cn/zhengce/2021-07/24/content_5627132.htm",
        source_type="government",
        citation="中共中央办公厅、国务院办公厅. (2021). 关于进一步减轻义务教育阶段学生作业负担和校外培训负担的意见.",
        evidence_level="strong",
        limitations="政策效果评估需要多年数据。目前的评估主要基于短期指标。教育政策的长期效果需要跟踪学生的全面发展而非仅看短期成绩变化。",
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
