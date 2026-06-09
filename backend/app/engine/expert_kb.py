"""
多领域专家知识引擎 — 10大领域权威知识库

这不是一个简单的关键词匹配库。
每个领域包含:
1. 基础概念 —— 该领域的基本公理和共识
2. 权威来源 —— 可引用的权威数据和文献
3. 常见谬误 —— 该领域最常见的错误认知及其纠正
4. 传播陷阱 —— 该领域信息在传播中最容易被扭曲的地方
5. 识别标志 —— 帮助识别该领域虚假信息的特征

覆盖领域:
- 心理学 (基础/社会/认知/临床)
- 社会学 (群体行为/社会结构/社会变迁)
- 犯罪学 (犯罪心理/犯罪预防/司法)
- 管理学 (组织行为/决策/公共管理)
- 数学 (统计/概率/逻辑/基础)
- 化学 (基础/毒理学/日用化学)
- 物理学 (基础/核/电磁/气候物理)
- 生物学 (进化/遗传/生态/微生物)
- 政治学 (制度/国际关系/政治传播)
- 传播学 (媒体/舆论/谣言研究/网络传播)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import re
import logging

logger = logging.getLogger("truthtrace.expert")

# =============================================================================
# 知识条目
# =============================================================================

@dataclass
class ExpertKnowledge:
    """一条专家知识"""
    id: str
    domain: str
    category: str                   # basic_concept / authoritative_source / common_fallacy / trap / identifier
    title: str
    content: str
    source: str                     # 引用来源
    source_url: str
    confidence: str = "high"        # high / moderate
    correction_hint: str = ""       # 如何纠正这个错误认知
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "domain": self.domain, "category": self.category,
            "title": self.title, "content": self.content,
            "source": self.source, "source_url": self.source_url,
            "confidence": self.confidence, "correction_hint": self.correction_hint,
            "tags": self.tags,
        }


# =============================================================================
# 1. 心理学 (Psychology)
# =============================================================================
PSYCHOLOGY_KB = [
    ExpertKnowledge(
        id="psych-001", domain="psychology", category="basic_concept",
        title="确认偏误 (Confirmation Bias) — 人类最普遍的认知偏差",
        content="确认偏误是指人们倾向于搜索、解读、偏好和回忆那些能确认自己已有信念或假设的信息。这是信息传播中最常被利用的心理机制之一——谣言制造者深知人们会不加批判地接受与自己既有观点一致的信息。",
        source="Nickerson, R.S. (1998). Confirmation bias: A ubiquitous phenomenon in many guises. Review of General Psychology, 2(2), 175-220.",
        source_url="https://doi.org/10.1037/1089-2680.2.2.175",
        correction_hint="当你看到一条让你'果然如此'的信息时，请特别警惕——这可能正是确认偏误在起作用。主动寻找反驳这条信息的证据。",
        tags=["认知偏差", "谣言传播", "信息评估"],
    ),
    ExpertKnowledge(
        id="psych-002", domain="psychology", category="common_fallacy",
        title="错误: '群体恐慌是非理性的'",
        content="社会心理学研究表明，危机中的群体行为通常比媒体描述的更理性、更有组织。'恐慌'往往是小概率事件被媒体放大后的认知偏差。在绝大多数灾难中，人们表现出的是互助、理性和有序撤离。'群体恐慌'的叙事常被用来正当化信息管控。",
        source="Drury, J. (2018). The role of social identity processes in mass emergency behaviour. European Review of Social Psychology, 29(1), 38-81.",
        source_url="https://doi.org/10.1080/10463283.2018.1471948",
        correction_hint="当媒体用'陷入恐慌'来描述人群时，请注意这可能是一种叙事话语而非事实描述。实际的人类群体行为比媒体描述的复杂得多。",
        tags=["群体行为", "恐慌叙事", "媒体偏差"],
    ),
    ExpertKnowledge(
        id="psych-003", domain="psychology", category="trap",
        title="恐惧诉求的效果与伦理边界",
        content="恐惧诉求(fear appeal)是利用恐惧情绪推动态度或行为改变的一种说服策略。研究(Witte & Allen, 2000)表明：恐惧诉求只有在同时提供'有效的应对方案'和'自我效能感'时才有效。如果只制造恐惧而不给解决方案，受众会转向否认和回避—这也是为什么只恐吓不教育的谣言特别容易传播。",
        source="Witte, K., & Allen, M. (2000). A meta-analysis of fear appeals. Health Education & Behavior, 27(5), 591-615.",
        source_url="https://doi.org/10.1177/109019810002700506",
        correction_hint="注意区分'合理警示'和'恐惧操纵'：前者提供具体可行动的应对方案，后者只是制造焦虑。",
        tags=["恐惧诉求", "说服", "伦理"],
    ),
    ExpertKnowledge(
        id="psych-004", domain="psychology", category="basic_concept",
        title="可得性启发 (Availability Heuristic)",
        content="人们倾向于根据记忆中容易想到的实例来评估事件发生的概率。媒体对罕见事件的密集报道(如飞机失事、恐怖袭击、罕见病案例)会让人大幅高估这些事件的实际发生率。这是'飞机比汽车危险'、'现在比过去更不安全'等常见误判的认知根源。",
        source="Tversky, A., & Kahneman, D. (1973). Availability: A heuristic for judging frequency and probability. Cognitive Psychology, 5(2), 207-232.",
        source_url="https://doi.org/10.1016/0010-0285(73)90033-9",
        tags=["认知偏差", "风险评估", "媒体效应"],
    ),
    ExpertKnowledge(
        id="psych-005", domain="psychology", category="identifier",
        title="如何识别利用心理脆弱性的信息操纵",
        content="以下信号表明信息可能在利用心理脆弱性：(1) 使用极度两极化的情感语言 (2) 声称自己是'唯一敢说真话的' (3) 将信息源描述为'被隐瞒的真相' (4) 用'他们不想让你知道'激发逆反心理 (5) 将复杂的多因素问题简化为单一的'罪魁祸首'。这些策略利用了人类的认知捷径和情感需求。",
        source="综合认知心理学与社会心理学共识 (Cialdini, Kahneman, Petty & Cacioppo)",
        source_url="https://en.wikipedia.org/wiki/List_of_cognitive_biases",
        tags=["信息操纵", "认知心理学", "媒体素养"],
    ),
]

# =============================================================================
# 2. 社会学 (Sociology)
# =============================================================================
SOCIOLOGY_KB = [
    ExpertKnowledge(
        id="soc-001", domain="sociology", category="basic_concept",
        title="道德恐慌 (Moral Panic) — 社会学经典理论",
        content="Stanley Cohen (1972) 提出的道德恐慌理论描述了社会如何周期性地将某个群体、行为或技术定义为对社会价值和利益的威胁。经典案例包括：1960年代的'摩登族与摇滚族'恐慌、1980年代的'撒旦仪式虐待'恐慌、1990年代的'电子游戏暴力'恐慌、2000年代的'互联网成瘾'恐慌、2010年代的'屏幕时间'恐慌。每个时代的恐慌结构高度一致，但预言的社会崩溃从未发生。",
        source="Cohen, S. (1972). Folk Devils and Moral Panics. London: MacGibbon and Kee.",
        source_url="https://en.wikipedia.org/wiki/Moral_panic",
        correction_hint="当你听到'这一代XX被毁了'时，去搜索一下历史上人们说同样的话有多少次——你会发现问题不在于'这一代'。",
        tags=["道德恐慌", "代际焦虑", "社会变迁"],
    ),
    ExpertKnowledge(
        id="soc-002", domain="sociology", category="common_fallacy",
        title="错误: '社会道德在滑坡' / '世风日下'",
        content="'世风日下'是人类最古老的抱怨之一。Furedi (2010) 指出，从古希腊到当代，每个年代的人都认为道德在衰退。但从长期数据看：全球暴力犯罪率(不包括战争)在过去几个世纪大幅下降(Pinker, 2011)，识字率大幅上升，人均寿命翻倍。'道德滑坡'的感知更多来自老年人对年轻文化的天然疏离和媒体的负面偏误，而非真实的社会恶化。",
        source="Pinker, S. (2011). The Better Angels of Our Nature. Viking. + Furedi, F. (2010) 相关研究.",
        source_url="https://en.wikipedia.org/wiki/The_Better_Angels_of_Our_Nature",
        tags=["道德恐慌", "社会变迁", "代际"],
    ),
    ExpertKnowledge(
        id="soc-003", domain="sociology", category="basic_concept",
        title="群体极化 (Group Polarization)",
        content="当志同道合的人聚集在一起讨论时，他们的观点会趋向于比讨论前更加极端。互联网让以前分散的极端观点持有者可以轻易找到彼此——这也是网络谣言和阴谋论社区自我强化的社会心理机制之一。算法推荐进一步加速了这个过程。",
        source="Sunstein, C.R. (2002). The Law of Group Polarization. Journal of Political Philosophy, 10(2), 175-195.",
        source_url="https://doi.org/10.1111/1467-9760.00148",
        tags=["群体极化", "社交媒体", "谣言传播"],
    ),
]

# =============================================================================
# 3. 犯罪学 (Criminology)
# =============================================================================
CRIMINOLOGY_KB = [
    ExpertKnowledge(
        id="crim-001", domain="criminology", category="common_fallacy",
        title="错误: '犯罪率在飙升' / '现在比以前更危险'",
        content="全球数据一致表明，过去30年世界大部分地区的暴力犯罪率显著下降。UNODC的数据显示全球凶杀率从1990年代的高点稳步下降。人们对犯罪的感知往往与媒体报道频率相关而非实际犯罪率——媒体对暴力事件的报道在过去20年大幅增加，但实际犯罪大多在减少。这是一个典型的可得性启发。",
        source="UNODC Global Study on Homicide 2023; 中国公安部/最高法每年公布的犯罪统计数据。",
        source_url="https://www.unodc.org/unodc/en/data-and-analysis/global-study-on-homicide.html",
        tags=["犯罪率", "安全感", "媒体偏差"],
    ),
    ExpertKnowledge(
        id="crim-002", domain="criminology", category="basic_concept",
        title="犯罪学中的理性选择理论 — 犯罪不是随机的",
        content="犯罪学研究表明，犯罪行为通常是理性计算成本收益后的结果(至少对财产犯罪如此)，而非媒体描述的'丧心病狂的恶魔随机作案'。理解犯罪的理性成分有助于制定更有效的预防策略——增加犯罪被抓的概率比增加刑罚严酷度更能威慑犯罪。随机性'恶魔作案'的叙事更容易引发公众恐慌，但不利于有效预防。",
        source="Cornish, D.B., & Clarke, R.V. (1986). The Reasoning Criminal. Springer-Verlag.",
        source_url="https://doi.org/10.1007/978-1-4613-8625-4",
        tags=["犯罪预防", "理性选择", "公众安全"],
    ),
]

# =============================================================================
# 4. 管理学 (Management)
# =============================================================================
MANAGEMENT_KB = [
    ExpertKnowledge(
        id="mgmt-001", domain="management", category="common_fallacy",
        title="错误: '一个国家的经济就像一个家庭预算' / '国家应该像家庭一样量入为出'",
        content="这是最常见的宏观经济学错误类比之一。国家经济≠家庭预算，原因：(1) 国家可以发行货币，家庭不能；(2) 国家可以运用货币政策和财政政策进行逆周期调节，家庭无法做到；(3) 政府债务与家庭债务的性质完全不同——政府的负债对应的是私人部门的资产；(4) 国家不存在'退休'或'死亡'，它的时间跨度是无限的。将国家经济简化为家庭理财是利用公众对个人财务的熟悉度来误导公众对复杂宏观经济问题的理解。",
        source="Krugman, P. — 多次解释'国家≠家庭'的谬误; MMT(现代货币理论)基础文献。",
        source_url="https://www.imf.org/en/Publications/fandd/issues/Series/Back-to-Basics",
        tags=["宏观经济学", "财政政策", "错误类比"],
    ),
    ExpertKnowledge(
        id="mgmt-002", domain="management", category="basic_concept",
        title="组织行为学中的基本归因错误",
        content="基本归因错误是指人们在解释他人行为时过度归因于个人特质而忽视情境因素的倾向。在公共管理中，这表现为将复杂的社会问题归因于'某些人腐败'或'某些人无能'而忽视系统性因素(制度设计、激励结构、资源约束等)。有效的组织管理需要同时关注系统设计和人员素质。",
        source="Ross, L. (1977). The intuitive psychologist and his shortcomings. Advances in Experimental Social Psychology, 10, 173-220.",
        source_url="https://doi.org/10.1016/S0065-2601(08)60357-3",
        tags=["归因错误", "组织行为", "公共管理"],
    ),
]

# =============================================================================
# 5. 数学与统计 (Mathematics)
# =============================================================================
MATH_KB = [
    ExpertKnowledge(
        id="math-001", domain="mathematics", category="common_fallacy",
        title="错误: 将'统计显著'等同于'实际重要'",
        content="p < 0.05 只表示'如果零假设为真，观察到该数据或更极端数据的概率小于5%'。它不能告诉你：效应量有多大？样本是否代表总体？结果是否可以被重复？是否有发表偏倚？多重检验是否被校正？这些问题中任何一个被忽略，都可能导致完全虚假的结论。2016年ASA(美国统计协会)罕见地发表公开声明，提醒研究者不要将p值奉为圭臬。",
        source="Wasserstein, R.L., & Lazar, N.A. (2016). The ASA Statement on p-Values. The American Statistician, 70(2), 129-133.",
        source_url="https://doi.org/10.1080/00031305.2016.1154108",
        correction_hint="当看到'显著'一词时，请追问：多大的样本？效应量是多少？有其他研究重复了同样结果吗？",
        tags=["统计", "p值", "科学研究"],
    ),
    ExpertKnowledge(
        id="math-002", domain="mathematics", category="basic_concept",
        title="贝叶斯定理 — 如何理性地更新信念",
        content="贝叶斯定理是数学中更新概率的基本工具：后验概率 ∝ 先验概率 × 新证据的似然比。在信息评估中，这意味着：你不应该只根据一条新信息做出结论，而应该思考——在接触到这条信息之前，这个声称的先验概率是多少？新证据的可靠程度如何？如果你原本认为某声称极不可能(如'食用普通食物会立即致死')，一条来源模糊的报告不足以推翻先前的判断。",
        source="Bayes, T. (1763). 任何概率论教材。",
        source_url="https://en.wikipedia.org/wiki/Bayes%27_theorem",
        tags=["贝叶斯", "概率", "理性思考"],
    ),
    ExpertKnowledge(
        id="math-003", domain="mathematics", category="common_fallacy",
        title="错误: 辛普森悖论 — 聚合数据可以完全反转结论",
        content="辛普森悖论是指：当数据被聚合后，原本在每个子群中存在的趋势可能完全反转。经典例子：1973年UC Berkeley研究生录取数据——总体上男性录取率高于女性(44% vs 35%)，但当按院系分解后，女性在大部分院系的录取率反而更高。原因是女性更多申请了录取率本来就低的院系。这个悖论警示：任何不分子群的聚合统计都可能产生误导。",
        source="Bickel, P.J., Hammel, E.A., & O'Connell, J.W. (1975). Science, 187(4175), 398-404.",
        source_url="https://doi.org/10.1126/science.187.4175.398",
        tags=["统计", "辛普森悖论", "数据解读"],
    ),
]

# =============================================================================
# 6. 化学 (Chemistry)
# =============================================================================
CHEMISTRY_KB = [
    ExpertKnowledge(
        id="chem-001", domain="chemistry", category="common_fallacy",
        title="错误: '化学物质=有毒' / '天然=安全'",
        content="这是公众对化学最根本的误解。世界上所有物质都是化学物质——水是H2O，氧气是O2，维生素C是C6H8O6。'天然'和'人工合成'的区分在化学上没有安全意义——很多天然物质毒性极高(如河豚毒素、黄曲霉毒素、毒蘑菇毒素)，而大量人工合成物质经过严格测试证明安全。安全性取决于物质的化学结构、剂量、暴露途径和使用方式，而非其'天然'或'人工'的标签。",
        source="基础化学共识; ACS (美国化学学会) 多次科普声明。",
        source_url="https://www.acs.org/education/whatischemistry.html",
        correction_hint="下次看到'纯天然'作为安全保证时，请思考：蛇毒是纯天然的，氰化物也存在于天然植物中。'天然'≠'安全'。",
        tags=["化学", "天然谬误", "科学素养"],
    ),
    ExpertKnowledge(
        id="chem-002", domain="chemistry", category="basic_concept",
        title="毒理学基本原则: 剂量决定毒性 — Paracelsus原理",
        content="'所有物质都是毒物，没有无毒的物质。只有剂量才能区分毒物和药物。' — Paracelsus (1493-1541)。这是现代毒理学的基石。任何物质在足够高的剂量下都可能有害，包括水和氧气。相反，许多'有毒'物质在极低剂量下安全甚至有益(如微量元素硒、氟化物)。脱离剂量谈毒性是公众理解化学品安全的最大障碍。",
        source="Paracelsus (16世纪); 所有现代毒理学教材。WHO/IPCS 化学品安全基础。",
        source_url="https://www.who.int/health-topics/chemical-safety",
        tags=["毒理学", "剂量", "风险评估"],
    ),
]

# =============================================================================
# 7. 物理学 (Physics)
# =============================================================================
PHYSICS_KB = [
    ExpertKnowledge(
        id="phys-001", domain="physics", category="common_fallacy",
        title="错误: '5G/基站辐射致癌' — 混淆电离辐射与非电离辐射",
        content="电磁辐射分为电离辐射(如X射线、γ射线)和非电离辐射(如无线电波、微波、可见光)。电离辐射的能量足以破坏化学键和DNA，增加癌症风险。非电离辐射的能量远远低于此阈值——5G和WiFi使用的毫米波/厘米波能量仅为电离辐射的百万分之一到十亿分之一。IARC将射频辐射列为2B类致癌物(证据有限)，与咖啡、腌制蔬菜同一级别——这意味着'可能但不充分'的证据，而非'确认致癌'。",
        source="WHO/IARC; ICNIRP Guidelines; 基础物理学教科书(电磁辐射能量级)。",
        source_url="https://www.who.int/news-room/questions-and-answers/item/radiation-5g-mobile-networks-and-health",
        tags=["电磁辐射", "5G", "物理基础"],
    ),
    ExpertKnowledge(
        id="phys-002", domain="physics", category="basic_concept",
        title="能量守恒与永动机的不可能性",
        content="能量守恒定律(热力学第一定律)是物理学最基本的定律之一。任何声称可以'无限产生能量'或'零能耗运行'的装置都是在否认这一定律。这包括了永动机、'自由能源'设备、'水变油'等常见骗局。这不是观点，而是经过数百年反复验证的物理定律——如果你的设计违反能量守恒，那一定是你的设计有问题，不需要做实验来验证。",
        source="任何物理学教材; 热力学第一定律。",
        source_url="https://en.wikipedia.org/wiki/Conservation_of_energy",
        tags=["热力学", "永动机", "物理学基础"],
    ),
]

# =============================================================================
# 8. 生物学 (Biology)
# =============================================================================
BIOLOGY_KB = [
    ExpertKnowledge(
        id="bio-001", domain="biology", category="common_fallacy",
        title="错误: '进化论只是理论' / '缺少过渡化石'",
        content="在科学术语中，'理论'(Theory)是最高级别的解释框架，如引力理论、细胞理论、进化理论——它们已经被大量独立证据反复验证。进化论有来自古生物学(化石记录)、比较解剖学、分子生物学(DNA序列)、生物地理学和实验进化等至少5条独立证据链的交叉验证。'缺少过渡化石'的说法已经被成千上万个过渡化石(如始祖鸟、提塔利克鱼等)证伪。这是用日常语言中的'理论'偷换科学术语中的'理论'。",
        source="达尔文(C. Darwin, 1859). 现代综合进化论。任何大学生物学教材。NCBI 基因组数据库。",
        source_url="https://www.nature.com/scitable/knowledge/library/evolution-is-change-in-the-inherited-traits-15164254/",
        tags=["进化论", "科学方法", "术语滥用"],
    ),
    ExpertKnowledge(
        id="bio-002", domain="biology", category="trap",
        title="基因编辑恐慌 — CRISPR不是弗兰肯斯坦",
        content="CRISPR基因编辑技术引发了大量伦理讨论，但许多公众恐慌来自于对基因技术的根本性误解。基因编辑不等同于'制造怪物'。现代生物医学对基因编辑的监管远比公众想象的严格——体细胞编辑(不遗传)和生殖细胞编辑(可遗传)有截然不同的伦理和法律标准。将基因编辑与'弗兰肯斯坦'类比是一种情感操纵，它绕过了对具体技术、具体应用和具体监管的理性讨论。",
        source="NASEM (2017). Human Genome Editing: Science, Ethics, and Governance.",
        source_url="https://nap.nationalacademies.org/catalog/24623",
        tags=["基因编辑", "CRISPR", "生物伦理"],
    ),
]

# =============================================================================
# 9. 政治学 (Political Science)
# =============================================================================
POLITICAL_KB = [
    ExpertKnowledge(
        id="pol-001", domain="political_science", category="common_fallacy",
        title="错误: '阴谋论解释比官方解释更可信，因为官方有动机说谎'",
        content="这种推理存在一个根本性的逻辑问题：它假设官方是单一实体(忽略政府部门内部的分歧和制衡)，同时假设'阴谋参与者'具有不可思议的完美执行力。实际上：政府内部有多个互相制衡的部门，信息在多个环节流通，每个环节都有泄密风险。大型阴谋(如登月骗局、气候变化骗局)需要成千上万人几十年的完美保密——这在实际操作中几乎不可能。'官方说谎'不等于'任何对官方的质疑都自动成立'。",
        source="政治学基础共识; Keeley, B.L. (1999). Of Conspiracy Theories. Journal of Philosophy, 96(3), 109-126.",
        source_url="https://doi.org/10.2307/2564659",
        tags=["阴谋论", "政治传播", "批判思维"],
    ),
    ExpertKnowledge(
        id="pol-002", domain="political_science", category="basic_concept",
        title="'他们vs我们'的政治动员机制",
        content="对立叙事是政治动员最古老的工具之一。它通过将复杂的社会问题简化为'我们(善良的受害者)'与'他们(邪恶的压迫者)'的简单对立，激发群体的部落忠诚和战斗本能。社会心理学研究(Tajfel的Social Identity Theory)表明，即使是最微小的、随机的分组也足以让人们偏袒'自己人'、贬低'外人'。在信息传播中，'他们vs我们'的对立框架大幅增加了传播力和情感共鸣——但也大幅降低了信息的准确性和复杂性。",
        source="Tajfel, H., & Turner, J.C. (1979). An integrative theory of intergroup conflict.",
        source_url="https://doi.org/10.1093/acprof:oso/9780199269464.003.0005",
        tags=["对立叙事", "社会认同", "政治传播"],
    ),
]

# =============================================================================
# 10. 传播学 (Communication Studies)
# =============================================================================
COMMUNICATION_KB = [
    ExpertKnowledge(
        id="comm-001", domain="communication", category="basic_concept",
        title="两级传播理论 (Two-Step Flow) — 意见领袖的作用",
        content="Katz & Lazarsfeld (1955) 的两级传播理论指出：信息不是直接从媒体流向公众，而是先从媒体流向'意见领袖'，再由意见领袖解读后传播给他们的追随者。这解释了为什么：即使原始媒体信息是准确的，经过意见领袖的'解读'后可能变得完全扭曲。在社交媒体时代，每个转发者都是一个潜在的'意见领袖'，信息的变形在每一跳传播中都在发生。这也是TruthTrace追溯传播链的意义所在。",
        source="Katz, E., & Lazarsfeld, P.F. (1955). Personal Influence. Free Press.",
        source_url="https://en.wikipedia.org/wiki/Two-step_flow_of_communication",
        tags=["传播理论", "意见领袖", "两级传播"],
    ),
    ExpertKnowledge(
        id="comm-002", domain="communication", category="trap",
        title="谣言传播的公式: Rumor = Importance × Ambiguity (Allport & Postman, 1947)",
        content="Allport & Postman 的经典谣言公式: 谣言的传播强度 = 事件对受众的重要性 × 信息的模糊程度。当某件事对人们很重要(如食品安全、孩子健康)且官方信息模糊/滞后/不透明时，谣言就会填补信息真空。后来研究者补充了一个分母: / Critical Thinking(批判思维能力)。这意味着：减少谣言的最有效方法不是封堵，而是提高信息透明度和公众的批判思维能力。",
        source="Allport, G.W., & Postman, L. (1947). The Psychology of Rumor. Henry Holt.",
        source_url="https://psycnet.apa.org/record/1947-03191-000",
        tags=["谣言研究", "传播学", "信息透明"],
    ),
    ExpertKnowledge(
        id="comm-003", domain="communication", category="identifier",
        title="如何识别信息中的操纵性说服技巧",
        content="基于Cialdini (1984) 的六条影响力原则和传播学研究，以下信号提示信息可能正在使用操纵性说服：(1) 互惠：'我告诉了你真相，你应该转发'(2) 稀缺与紧迫：'马上被删！速看！'(3) 权威：引用不相关或无法验证的'专家'(4) 一致性：'如果你之前相信我，这次也要相信我'(5) 社会认同：'99%的人都转了'(6) 喜好：美女/可爱动物+信息捆绑传播。这些技巧本身并不必然使信息错误，但它们是信息被设计来操纵而非告知的强烈信号。",
        source="Cialdini, R.B. (1984). Influence: The Psychology of Persuasion. HarperBusiness.",
        source_url="https://www.influenceatwork.com/principles-of-persuasion/",
        tags=["说服", "操纵", "媒体素养"],
    ),
]

# =============================================================================
# 领域索引
# =============================================================================
EXPERT_KNOWLEDGE_BASE = {
    "psychology": PSYCHOLOGY_KB,
    "sociology": SOCIOLOGY_KB,
    "criminology": CRIMINOLOGY_KB,
    "management": MANAGEMENT_KB,
    "mathematics": MATH_KB,
    "chemistry": CHEMISTRY_KB,
    "physics": PHYSICS_KB,
    "biology": BIOLOGY_KB,
    "political_science": POLITICAL_KB,
    "communication": COMMUNICATION_KB,
}

# 领域关键词 → 用于自动识别领域
DOMAIN_SIGNALS = {
    "psychology": ["心理", "认知", "偏误", "焦虑", "抑郁", "恐慌", "人格", "行为", "情感", "创伤", "记忆", "偏见"],
    "sociology": ["社会", "阶层", "群体", "道德", "世风", "阶级", "歧视", "不平等", "城市化", "移民"],
    "criminology": ["犯罪", "犯罪率", "杀人", "盗窃", "诈骗", "暴力", "安全", "警察", "司法", "刑罚"],
    "management": ["管理", "组织", "领导", "效率", "团队", "决策", "预算", "政策", "政府预算"],
    "mathematics": ["概率", "统计", "数据", "百分比", "倍数", "相关", "因果", "显著", "样本", "算法", "模型"],
    "chemistry": ["化学", "分子", "元素", "反应", "合成", "毒性", "剂量", "浓度", "pH", "酸碱", "添加剂", "农药"],
    "physics": ["物理", "能量", "辐射", "电磁", "量子", "力", "速度", "温度", "热", "核", "光"],
    "biology": ["基因", "DNA", "RNA", "细胞", "进化", "物种", "生态", "微生物", "细菌", "病毒", "免疫"],
    "political_science": ["政治", "民主", "专制", "选举", "政府", "官员", "腐败", "权力", "统治", "治理", "制度"],
    "communication": ["传播", "媒体", "舆论", "谣言", "新闻", "信息", "转发", "标题党", "报道", "公众号", "短视频"],
}


def identify_expert_domains(text: str) -> list[str]:
    """根据文本自动识别涉及的专业领域"""
    scores: dict[str, int] = {}
    text_lower = text.lower()
    for domain, keywords in DOMAIN_SIGNALS.items():
        score = 0
        for kw in keywords:
            if kw in text_lower:
                score += 1
        if score >= 2:
            scores[domain] = score
    return [d for d, _ in sorted(scores.items(), key=lambda x: -x[1])[:5]]


def query_expert_kb(text: str, domain: str | None = None) -> list[dict]:
    """查询专家知识库中与文本相关的知识条目"""
    if domain:
        domains = [domain]
    else:
        domains = identify_expert_domains(text)

    results = []
    text_lower = text.lower()

    for dom in domains:
        entries = EXPERT_KNOWLEDGE_BASE.get(dom, [])
        for entry in entries:
            # 关键词匹配
            relevance = 0
            for tag in entry.tags:
                if tag in text_lower:
                    relevance += 1
            for kw in DOMAIN_SIGNALS.get(dom, []):
                if kw in text_lower:
                    relevance += 0.5

            if relevance > 0 or domain:  # 如果指定了领域则全部返回
                results.append({
                    "entry": entry.to_dict(),
                    "relevance": relevance,
                    "domain": dom,
                })

    results.sort(key=lambda x: -x["relevance"])
    return [r["entry"] for r in results[:8]]
