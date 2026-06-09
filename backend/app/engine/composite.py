"""
拼接式造谣检测引擎 — 检测"每块单独看都真，拼在一起是假"的信息操纵

这是最危险的信息操纵形式之一，因为:
- 每小块信息本身是真实的 → 辟谣时不能说"这是假的"
- 但组合/叠加的方式产生了完全虚假的结论
- 辟谣成本高: 需要逐一解释"为什么这些事实拼在一起不支撑这个结论"

## 检测的 5 种拼接模式:

1. 事实罗列 + 逻辑跳跃 — A真+B真+C真, 但A+B→D的逻辑漏洞巨大
2. 因果拼接 — A→B (真), C→D (真), 但把A→B和C→D拼成"A→D" (假)
3. 时间线操控 — 重新排列时间顺序制造虚假因果
4. 类比滥用 — A和B在某些方面相似 → "所以A和B在所有方面应该一样"
5. 再分享链突变 — 追踪传播中每个转发者的语义变化

## 检测方式:

与失真检测不同，本模块不是简单做正则匹配，
而是提取文本的逻辑结构，分析"信息块到结论"的推理跳跃。
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from app.engine.types import Confidence


# =============================================================================
# 检测结果类型
# =============================================================================

class CompositeAbuseType(str):
    LOGIC_LEAP = "logic_leap"                 # 事实 → 结论的逻辑跳跃
    CAUSAL_SUTURING = "causal_suturing"       # 因果缝合: 把独立因果链拼接
    TIMELINE_MANIPULATION = "timeline_manipulation"  # 时间线操控
    ANALOGY_ABUSE = "analogy_abuse"           # 类比滥用
    MEANING_MUTATION = "meaning_mutation"     # 再分享中的意义突变


@dataclass
class CompositeAbuseMatch:
    abuse_type: str
    description: str
    confidence: Confidence
    evidence_snippet: str = ""
    reasoning: str = ""
    # 提取的逻辑块
    premise_chunks: list[str] = field(default_factory=list)
    conclusion_chunk: str = ""
    leap_gap: str = ""  # 从前提→结论的缺口是什么

    def to_dict(self) -> dict:
        return {
            "abuse_type": self.abuse_type,
            "description": self.description,
            "confidence": self.confidence.value,
            "evidence_snippet": self.evidence_snippet,
            "reasoning": self.reasoning,
            "premise_chunks": self.premise_chunks,
            "conclusion_chunk": self.conclusion_chunk,
            "leap_gap": self.leap_gap,
        }


@dataclass
class CompositeAnalysis:
    matches: list[CompositeAbuseMatch] = field(default_factory=list)
    composite_risk_score: float = 0.0
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "matches": [m.to_dict() for m in self.matches],
            "composite_risk_score": self.composite_risk_score,
            "summary": self.summary,
        }


# =============================================================================
# 1. 事实罗列 + 逻辑跳跃
# =============================================================================
# 模式: "A是真的, B也是真的, C也是真的 → 所以D(假的)"
# 每个事实独立为真，但连接词（所以、因此、可见、说明）后面的结论不需要逻辑支撑

LOGIC_LEAP_PATTERNS = [
    # 多个事实陈述 + 跳跃性结论
    (r"(?:事实上?|众所周知|数据显示|...研究|...表明).{0,40}(?:而且|同时|也|另外|此外|再加上).{0,40}(?:所以|因此|可见|显然|说明|这?意味着|证明).{0,60}",
     "罗列了事实A和事实B之后，用'所以/因此'跳到一个与前提逻辑上不直接相连的结论。"
     "\n关键: A为真、B为真，不等于A+B→结论。检查从前提跳到结论的这一步是否成立。"),

    # "如果A(真)，又B(真)，那C肯定(假/真)"——AB不推C
    (r"(?:既然|因为).{0,40}(?:那么|所以|就|那).{0,20}(?:肯定|一定|必然|绝(?:对|非)|毫无疑问|毋庸置疑).{0,30}",
     "使用'既然...那肯定...'的句式，在前提和结论之间插入了确定性词汇（肯定/必然/毫无疑问），"
     "但这些词汇不能替代逻辑推理。'肯定'不能补偿论证的缺失。"),

    # "一个...的例子说明..." — 将一个例子当作普遍规律的证明
    (r"(?:看看?|想想?|就...说|拿...来说|比如|例如|以...为例).{0,30}(?:就|便|足|完全|充分|足够|彻底)(?:说明|证明|表明|揭示|...了|可以(?:看到|看出))",
     "用'一个例子/案例'来'证明'一个普遍结论——个案不能证明普遍规律。"
     "\n'看看X就知道了'是一种修辞手法而非逻辑论证。"),
]


# =============================================================================
# 2. 因果缝合
# =============================================================================
# A→B (真实的因果) + C→D (真实的因果) → 被缝合为"A→D"或"B→C" (假的)

CAUSAL_SUTURING_PATTERNS = [
    # 多重独立因果链的未经论证的连接
    (r"(?:因为|由于).{0,40}(?:而且|同时|再加上|另外|此外).{0,10}(?:因为|由于).{0,40}(?:所以|因此|于是|导致|造成|引起).{0,60}",
     "将两个或多个独立的因果关系串接起来，暗示它们之间存在联系——"
     "但第二个'因为'的因果链可能与第一个完全不相关。"),

    # "A导致了B，B导致了C，C最终导致了D"
    (r"(?:导致|造成|引起|引发|诱发).{0,20}(?:进而|接[着下]|随后|然后|又|最终|最后).{0,10}(?:导致|造成|引起|引发).{0,20}(?:进而|最终|最后)(?:导致|造成)",
     "构建了多步因果链，每步都可能是真的，但把链条的所有环节串接起来的推理可能不存在。"
     "\n因果链的每一跳都需要独立的证据，不能靠叙述的连贯性来替代。"),

    # 将相关性链条当作因果链条
    (r"(?:这|它|...)(?:与|和|同|跟).{0,20}(?:有关|相关|联系在一起|关联).{0,30}(?:这|它|...)(?:又|也|还).{0,15}(?:与|和).{0,20}(?:有关|相关).{0,30}(?:所以|因此|可见|这就|这说明)",
     "将多个相关关系串在一起，暗示存在因果链——但一组相关性(即使都是真的)不能组成因果关系。"
     "\n相关 ≠ 因果，多个相关叠加仍然 ≠ 因果。"),
]


# =============================================================================
# 3. 时间线操控
# =============================================================================

TIMELINE_PATTERNS = [
    # "XX事件发生(忽略时间)后, YY就发生了" — 暗示前者导致后者
    (r"(?:自从|从|打从|从...起|...后).{0,30}(?:就|便|于是|开始|出现|发生).{0,40}(?:越来越|日益|不断|持续|一直)",
     "将时间上的先后关系暗示为因果关系——'自从X以后，Y就越来越严重了'。"
     "\n注意: 这里的'自从'和'越来越'之间可能没有因果联系，只是时间上的巧合。"),

    # 反向时间线 — 把后来的事说成原因
    (r"(?:现在|如今|当下).{0,20}(?:之所以|...的原因|是因为)(?![\s\S]{0,30}(?:所以|因此|导致|造成|因为|由于).{0,20}(?:之前|以前|...的))",
     "把当前的现象归因于某个事件，但时间顺序可能是反向的。"),

    # 时间压缩 — "一夜之间/短短X天/突然"
    (r"(?:一夜之间|短短|仅仅|只用了?|突然|猛然).{0,10}(\d+(?:\.\d+)?)\s*(?:天|周|月|年|小时|分钟).{0,20}(?:就|便|竟然|居然|已经).{0,30}(?:了)",
     "压缩了实际发生的时间跨度，制造'突然/快速发生'的错觉。"
     "\n许多社会/经济/环境变化是长期过程的累积，但被压缩表述为'短时间内的剧变'以制造惊恐。"),
]


# =============================================================================
# 4. 类比滥用
# =============================================================================

ANALOGY_ABUSE_PATTERNS = [
    # "就像A一样，B也..." — 在不同领域间强行类比
    (r"(?:就(?:像|好比|跟|和)|如同|正如|仿佛|好像).{0,20}(?:一样|似的|那样|那般).{0,30}(?:所以|因此|可见|说明|这就|证明|...应该)",
     "使用类比进行论证——问题是不同领域/系统/国家之间的类比往往在关键特征上不成立。"
     "\n'就像某国这样做成功了，所以我们也可以'——但两个国家的制度/文化/历史完全不同。"),

    # 将复杂社会经济问题简化为比喻
    (r"(?:就像|好比|如同).{0,15}(?:家庭|公司|企业|...).{0,10}(?:一样).{0,30}(?:所以|因此|...应该|...也该)",
     "将复杂的国家/社会问题简化为'就像家庭/公司理财一样'的类比。"
     "\n国家经济≠家庭预算。国家可以发行货币、调节利率、进行逆周期操作——这些家庭都做不到。"),
]


# =============================================================================
# 5. 再分享链中的意义突变
# =============================================================================
# 追踪传播过程中每个转发者对原始信息的语义改变

MEANING_MUTATION_PATTERNS = [
    # "原文说的是X，但..."
    (r"(?:其实|实际上?|说白了|本质上?|归根到底|说穿了?|...的意思?就是).{0,40}(?![\s\S]{0,20}(?:原文|原话|作者|...说|[表阐]...的))",
     "'其实/说白了/实质上'之后的解释与原意可能完全不同——这是意义突变的最常见形式。"
     "\n当一个解释以'说白了就是...'开头时，它常常等于'用我自己的（更极端的）话说就是...'"),

    # 引号重新赋予含义
    (r"(?:所谓的?|号称的?|标榜的?)(?:'[^']{5,80}'|\"[^\"]{5,80}\")",
     "用引号引用对方的表述并赋予其负面含义——所谓的XX带有贬损意味，"
     "暗示引号内的内容名不副实。这种引用方式本身就是一种意义的重新赋予。"),

    # "你细品/你品/你细品品" — 暗示有隐藏含义
    (r"(?:你|大家|各位|读者|看官)(?:细品|品品|细品品|好好品|...品|想想|仔细想)(?![\s\S]{0,30}(?:原文|事实|证据|数据))",
     "'你细品'是意义改写的最常见提示——引导读者自己去'发现'文本中没有的暗示。"
     "\n这是一种操纵性的修辞: '我没说，但你懂的' —— 把没有说出口的暗示包装为读者的自我发现。"),
]


# 汇总
ALL_COMPOSITE_PATTERNS = [
    (CompositeAbuseType.LOGIC_LEAP, LOGIC_LEAP_PATTERNS),
    (CompositeAbuseType.CAUSAL_SUTURING, CAUSAL_SUTURING_PATTERNS),
    (CompositeAbuseType.TIMELINE_MANIPULATION, TIMELINE_PATTERNS),
    (CompositeAbuseType.ANALOGY_ABUSE, ANALOGY_ABUSE_PATTERNS),
    (CompositeAbuseType.MEANING_MUTATION, MEANING_MUTATION_PATTERNS),
]


# =============================================================================
# 提取逻辑结构: 找出前提块和结论块
# =============================================================================

def _extract_logical_chunks(text: str) -> dict:
    """
    尝试从文本中提取逻辑结构: 有哪些前提、什么结论、连接词是什么。
    """
    chunks = {
        "premises": [],
        "conclusion": "",
        "connector": "",  # 前提→结论的连接词
    }

    # 找因果连接词
    conclusion_patterns = [
        (r'(?:所以|因此|于是|可见|显然|这说明|这意味着|这就|由此|由此可见|由此可见|综上所述)(.{10,150})', "所以/因此"),
        (r'(?:所以(?:说|呢)?)(.{10,150})', "所以"),
        (r'(?:故|故而)(.{10,80})', "故"),
    ]

    for pattern, connector in conclusion_patterns:
        match = re.search(pattern, text)
        if match:
            chunks["conclusion"] = match.group(1).strip()
            chunks["connector"] = connector
            # 结论词之前的部分作为前提
            premise_text = text[:match.start()].strip()
            if len(premise_text) > 10:
                # 按标点拆分为多个前提块
                for segment in re.split(r'[。；;.\n]', premise_text):
                    segment = segment.strip()
                    if len(segment) > 10:
                        chunks["premises"].append(segment[:200])
            break

    return chunks


# =============================================================================
# 检测从前提跳到结论的逻辑缺口
# =============================================================================

def _analyze_leap_gap(premises: list[str], conclusion: str, connector: str) -> str:
    """
    分析从前提→结论的逻辑缺口。

    不求完美，但求提供有意义的分析提示。
    """
    if not premises or not conclusion:
        return "无法提取足够的逻辑结构进行分析。"

    gaps = []

    # 检查结论是否包含了前提中未出现的新概念
    premise_words = set()
    for p in premises:
        for w in re.findall(r'[一-鿿]{2,}', p):
            premise_words.add(w)

    conclusion_words = set(re.findall(r'[一-鿿]{2,}', conclusion))
    new_concepts = conclusion_words - premise_words
    if len(new_concepts) >= 3:
        gaps.append(f"结论中引入了 {len(new_concepts)} 个前提中未出现的新概念: "
                   f"{'、'.join(list(new_concepts)[:5])}")

    # 检查结论的范围是否超出了前提
    broad_terms = ["所有", "全部", "整个", "每个", "任何", "凡是", "都", "从来", "永远", "必然"]
    for bt in broad_terms:
        if bt in conclusion and not any(bt in p for p in premises):
            gaps.append(f"结论使用了全称量化词'{bt}'，但前提中并未出现全称量化")
            break

    # 检查前提到结论的跳跃程度
    if connector in ("所以", "因此", "故") and len(premises) <= 2:
        gaps.append(f"仅{len(premises)}个前提直接跳到结论('{connector}')——过于简化的因果推断")

    if not gaps:
        gaps.append("从前提→结论的逻辑跳跃不明显，但需要人工验证前提是否真正支撑结论。")

    return " | ".join(gaps)


# =============================================================================
# 主检测函数
# =============================================================================

def detect_composite_fabrication(text: str, title: str = "") -> CompositeAnalysis:
    """
    对输入文本进行 5 种拼接式造谣模式的检测。

    除了模式匹配，还尝试提取文本的逻辑结构（前提→结论），
    分析是否存在逻辑跳跃。
    """
    combined = f"{title}\n{title}\n{text}" if title else text

    all_matches: list[CompositeAbuseMatch] = []

    # 1. 模式匹配
    for abuse_type, patterns in ALL_COMPOSITE_PATTERNS:
        for pattern_regex, description in patterns:
            for match in re.finditer(pattern_regex, combined, re.IGNORECASE):
                snippet = _extract_context(combined, match.start(), match.end())

                if not _is_duplicate(all_matches, abuse_type, snippet):
                    # 提取逻辑结构
                    chunks = _extract_logical_chunks(snippet)
                    gap = _analyze_leap_gap(
                        chunks["premises"], chunks["conclusion"], chunks["connector"]
                    )

                    all_matches.append(CompositeAbuseMatch(
                        abuse_type=abuse_type,
                        description=description.split("\n")[0],
                        confidence=_composite_confidence(abuse_type, combined),
                        evidence_snippet=snippet,
                        reasoning=f"匹配模式 → 触发词: '{match.group()[:50]}'",
                        premise_chunks=chunks["premises"],
                        conclusion_chunk=chunks["conclusion"],
                        leap_gap=gap,
                    ))

    # 2. 额外: 尝试提取整体逻辑结构
    logical_structure = _extract_logical_chunks(combined)
    if logical_structure["premises"] and logical_structure["conclusion"]:
        gap = _analyze_leap_gap(
            logical_structure["premises"],
            logical_structure["conclusion"],
            logical_structure["connector"],
        )
        # 如果有新概念跳入但未被之前的模式匹配捕获
        if "引入了" in gap and not any(m.abuse_type == CompositeAbuseType.LOGIC_LEAP for m in all_matches):
            all_matches.append(CompositeAbuseMatch(
                abuse_type=CompositeAbuseType.LOGIC_LEAP,
                description=f"整体逻辑结构分析发现从{len(logical_structure['premises'])}个前提跳到结论时引入了新概念",
                confidence=Confidence.MODERATE,
                evidence_snippet=logical_structure["conclusion"][:150],
                reasoning="自动逻辑结构分析",
                premise_chunks=logical_structure["premises"],
                conclusion_chunk=logical_structure["conclusion"],
                leap_gap=gap,
            ))

    # 风险评分
    if not all_matches:
        return CompositeAnalysis(
            matches=[],
            composite_risk_score=0.0,
            summary="未检测到明显的拼接式造谣模式。"
        )

    types_seen = set(m.abuse_type for m in all_matches)
    risk = len(types_seen) * 15.0 + len(all_matches) * 3.0
    risk = min(100.0, risk)

    type_labels = {
        CompositeAbuseType.LOGIC_LEAP: "事实→结论逻辑跳跃",
        CompositeAbuseType.CAUSAL_SUTURING: "独立因果链缝合",
        CompositeAbuseType.TIMELINE_MANIPULATION: "时间线操控",
        CompositeAbuseType.ANALOGY_ABUSE: "不当类比滥用",
        CompositeAbuseType.MEANING_MUTATION: "再分享意义突变",
    }

    summary = (
        f"检测到 {len(types_seen)} 类拼接式造谣模式 (共 {len(all_matches)} 处匹配): "
        + "; ".join(type_labels.get(t, t) for t in sorted(types_seen))
        + f"。拼接风险评分: {risk:.0f}/100。"
        + " 核心问题: 将多个真实的信息片段组合后，通过逻辑跳跃得出了不成立的结论。"
    )

    return CompositeAnalysis(
        matches=all_matches,
        composite_risk_score=risk,
        summary=summary,
    )


# =============================================================================
# 再分享链突变追踪
# =============================================================================

@dataclass
class ShareChainNode:
    """传播链上的一个节点"""
    order: int
    url: str = ""
    author: str = ""
    content_snippet: str = ""
    added_by_this_node: str = ""  # 这个节点在前一个节点基础上新增了什么

    def to_dict(self) -> dict:
        return {
            "order": self.order,
            "url": self.url,
            "author": self.author,
            "content_snippet": self.content_snippet,
            "added_by_this_node": self.added_by_this_node,
        }


@dataclass
class MutationAnalysis:
    """再分享链突变分析"""
    chain: list[ShareChainNode] = field(default_factory=list)
    detected_mutations: list[dict] = field(default_factory=list)
    original_meaning: str = ""
    final_meaning: str = ""
    meaning_divergence_score: float = 0.0  # 0=完全相同, 100=完全相反

    def to_dict(self) -> dict:
        return {
            "chain": [n.to_dict() for n in self.chain],
            "detected_mutations": self.detected_mutations,
            "original_meaning": self.original_meaning,
            "final_meaning": self.final_meaning,
            "meaning_divergence_score": self.meaning_divergence_score,
        }


def analyze_reshare_chain(chain_data: list[dict]) -> MutationAnalysis:
    """
    分析传播链中每个跳转点的语义变化。

    输入: chain_data = [
        {"order": 1, "url": "...", "author": "...", "content": "..."},
        {"order": 2, ...},
        ...
    ]

    输出: MutationAnalysis 包含:
    - 每一跳的变化描述
    - 从原始意义到最终意义的偏离度
    """
    if not chain_data or len(chain_data) < 2:
        return MutationAnalysis(
            chain=[],
            detected_mutations=[],
            original_meaning="",
            final_meaning="",
            meaning_divergence_score=0.0,
        )

    chain = []
    mutations = []

    for i, node_data in enumerate(chain_data):
        content = node_data.get("content", "")
        prev_content = chain_data[i - 1].get("content", "") if i > 0 else ""

        added = ""
        if i > 0:
            # 找出这一跳新增的关键词
            prev_words = set(re.findall(r'[一-鿿]{2,}', prev_content))
            curr_words = set(re.findall(r'[一-鿿]{2,}', content))
            new_words = curr_words - prev_words
            if new_words:
                added = f"新增关键词: {'、'.join(list(new_words)[:8])}"

        chain.append(ShareChainNode(
            order=node_data.get("order", i + 1),
            url=node_data.get("url", ""),
            author=node_data.get("author", ""),
            content_snippet=content[:200],
            added_by_this_node=added,
        ))

        # 检测语义变化信号
        if i > 0:
            mutation_signals = []
            # 新增情感词汇
            if re.search(r'(?:震惊|愤怒|令人|可怕|恐怖|触目|发指|丧心)', content) and \
               not re.search(r'(?:震惊|愤怒|令人|可怕|恐怖|触目)', prev_content):
                mutation_signals.append(f"第{i}→{i+1}跳: 新增强烈情感词汇")

            # 新增阴谋信号
            if re.search(r'(?:真相|内幕|隐瞒|掩盖|背后|不为人知)', content) and \
               not re.search(r'(?:真相|内幕|隐瞒|掩盖|背后|不为人知)', prev_content):
                mutation_signals.append(f"第{i}→{i+1}跳: 引入阴谋/揭露叙事")

            # 新增强烈断言
            if re.search(r'(?:肯定|绝对|毫无疑问|毋庸置疑|必然|必定)', content) and \
               not re.search(r'(?:肯定|绝对|毫无疑问|毋庸置疑|必然|必定)', prev_content):
                mutation_signals.append(f"第{i}→{i+1}跳: 新增绝对化断言词汇")

            # 人物/机构的引入
            new_entities = set(re.findall(r'(?:[A-Z][a-z]+|[A-Z]{2,}|[一-鿿]{2,4}(?:集团|公司|组织|机构|部门|政府|国家))', content)) - \
                          set(re.findall(r'(?:[A-Z][a-z]+|[A-Z]{2,}|[一-鿿]{2,4}(?:集团|公司|组织|机构|部门|政府|国家))', prev_content))
            if new_entities:
                mutation_signals.append(f"第{i}→{i+1}跳: 引入新实体: {', '.join(list(new_entities)[:5])}")

            if mutation_signals:
                mutations.append({"hop": f"{i}→{i+1}", "signals": mutation_signals})

    original = chain[0].content_snippet if chain else ""
    final = chain[-1].content_snippet if chain else ""

    # 计算偏离度
    orig_words = set(re.findall(r'[一-鿿]{2,}', original))
    final_words = set(re.findall(r'[一-鿿]{2,}', final))
    if orig_words:
        overlap = len(orig_words & final_words)
        total = len(orig_words | final_words)
        divergence = 100 * (1 - overlap / total) if total > 0 else 0
    else:
        divergence = 0

    return MutationAnalysis(
        chain=chain,
        detected_mutations=mutations,
        original_meaning=original,
        final_meaning=final,
        meaning_divergence_score=round(divergence, 1),
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


def _is_duplicate(existing: list, abuse_type: str, snippet: str) -> bool:
    for m in existing:
        if m.abuse_type == abuse_type and m.evidence_snippet == snippet:
            return True
    return False


def _composite_confidence(abuse_type: str, text: str) -> Confidence:
    if abuse_type == CompositeAbuseType.MEANING_MUTATION:
        if re.search(r'(?:说白了|细品|你品|你细品|你品品|其实.{0,10}就是)', text):
            return Confidence.HIGH
        return Confidence.MODERATE
    if abuse_type == CompositeAbuseType.TIMELINE_MANIPULATION:
        if re.search(r'(?:一夜之间|短短.{0,5}天|突然.{0,10}就)', text):
            return Confidence.HIGH
        return Confidence.MODERATE
    return Confidence.MODERATE
