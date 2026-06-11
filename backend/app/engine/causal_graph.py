"""
GraphRAG-Causal 因果图谱引擎 (#20)

基于图结构的因果推理，用于追踪信息传播中的因果关系：
1. 因果主张提取 — 从文本中识别因果关系声明
2. 因果图谱构建 — 节点(事件/主张) + 边(因果链)
3. 因果谬误检测 — 后此谬误、相关≠因果、反向因果等
4. 溯源图推理 — 沿因果链追踪信息来源的可信度传导

核心原则：
- 因果不等同于相关 — 需要时间顺序+机制+排除混淆变量
- 单条因果链的可信度 ≤ 最弱环节的可信度
- 循环因果链 = 无效推理
"""

from __future__ import annotations
import re
import logging
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict

logger = logging.getLogger("truthtrace.causal_graph")


# =============================================================================
# 因果声明类型
# =============================================================================

class CausalClaimType:
    """因果主张的分类"""
    DIRECT_CAUSE = "direct_cause"           # A 直接导致 B
    CONTRIBUTING = "contributing"           # A 是 B 的促成因素
    CORRELATION_AS_CAUSATION = "corr_as_cause"  # 相关被当作因果
    REVERSED_CAUSALITY = "reversed"         # 因果倒置
    POST_HOC = "post_hoc"                   # 后此谬误
    MISSING_MECHANISM = "missing_mechanism" # 缺乏因果机制
    CONFOUNDER_OMISSION = "confounder_omit" # 遗漏混淆变量
    SLIPPERY_SLOPE = "slippery_slope"       # 滑坡论证
    SINGLE_CAUSE_FALLACY = "single_cause"   # 单一原因谬误


# =============================================================================
# 因果图谱节点与边
# =============================================================================

@dataclass
class CausalNode:
    """因果图谱中的节点 — 一个事件/主张"""
    node_id: str
    label: str                          # 简短描述
    description: str = ""               # 完整上下文
    evidence_level: str = "none"        # 证据等级 (none/low/medium/high/authoritative)
    credibility: float = 50.0           # 节点自身的可信度 0-100
    source_url: str = ""                # 引用来源
    is_root: bool = False               # 是否为根节点 (无入边)
    is_effect: bool = False             # 是否为末端节点 (无出边)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "description": self.description[:200],
            "evidence_level": self.evidence_level,
            "credibility": round(self.credibility, 1),
            "source_url": self.source_url,
            "is_root": self.is_root,
            "is_effect": self.is_effect,
        }


@dataclass
class CausalEdge:
    """因果图谱中的边 — A → B 的因果关系"""
    source_id: str                      # 原因节点
    target_id: str                      # 结果节点
    relation: str = "causes"            # 关系类型
    claim_type: str = ""                # 因果主张类型
    evidence_quote: str = ""            # 文本中的证据引用
    confidence: float = 50.0            # 这条边的置信度 0-100
    fallacy_detected: bool = False      # 是否检测到因果谬误
    fallacy_type: str = ""              # 谬误类型 (如有)

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "claim_type": self.claim_type,
            "evidence_quote": self.evidence_quote[:150],
            "confidence": round(self.confidence, 1),
            "fallacy_detected": self.fallacy_detected,
            "fallacy_type": self.fallacy_type,
        }


# =============================================================================
# 因果谬误检测模式
# =============================================================================

CAUSAL_FALLACY_PATTERNS = [
    # 后此谬误 (Post Hoc Ergo Propter Hoc)
    {
        "type": CausalClaimType.POST_HOC,
        "patterns": [
            r"自从(.{1,30})(?:之后|以后|以来).{1,30}(?:就|便|于是)",
            r"(?:在|自从)(.{1,30})(?:发生|出现|实施).{1,30}(?:马上|立即|迅速|很快)",
            r"(?:一|刚).{1,20}(?:就|便).{1,20}",
        ],
        "description": "后此谬误 — 仅因时间先后就推断因果关系",
        "severity": 30,
    },
    # 相关即因果
    {
        "type": CausalClaimType.CORRELATION_AS_CAUSATION,
        "patterns": [
            r"(?:研究|数据|统计|调查).{1,30}(?:显示|表明|发现).{1,20}(?:相关|关联|联系).{1,20}(?:证明|说明|意味着|就是)",
            r"(?:成正比|呈正相关|显著相关).{1,30}(?:因此|所以|说明|意味着)",
            r"数据.{1,30}(?:显示|表明).{1,20}(?:越高|越多|越大).{1,20}(?:证明|说明|可见)",
        ],
        "description": "相关即因果 — 将统计相关性等同于因果关系",
        "severity": 40,
    },
    # 反向因果
    {
        "type": CausalClaimType.REVERSED_CAUSALITY,
        "patterns": [
            r"(?:因为|由于)(.{1,40})(?:所以|因此|导致|造成)(.{1,40})",
        ],
        "description": "可能因果倒置 — 需验证因果方向",
        "severity": 25,
    },
    # 遗漏混淆变量
    {
        "type": CausalClaimType.CONFOUNDER_OMISSION,
        "patterns": [
            r"(?:唯一|根本|绝对).{0,10}(?:原因|因素|根源)",
            r"(?:就是|完全是|绝对是)(?:因为|由于)",
            r"100%.{0,10}(?:致癌|致死|导致|引起)",
        ],
        "description": "单一原因谬误 — 忽视多重因素和混淆变量",
        "severity": 35,
    },
    # 滑坡论证
    {
        "type": CausalClaimType.SLIPPERY_SLOPE,
        "patterns": [
            r"(?:如果|一旦|要是).{1,30}(?:就会|就会导致|必将|必然).{1,30}(?:最终|最后|迟早|总有一天)",
            r"(?:第一步|首先).{1,30}(?:然后|接着|之后).{1,30}(?:最终|最后)",
            r".{1,20}(?:连锁反应|多米诺|蝴蝶效应)",
        ],
        "description": "滑坡论证 — 假设一系列未经证实的因果连锁",
        "severity": 35,
    },
    # 缺乏因果机制
    {
        "type": CausalClaimType.MISSING_MECHANISM,
        "patterns": [
            r"(?:神奇的|惊人的|不可思议).{0,10}(?:效果|疗效|作用)",
            r"(?:能|可以|能够).{1,20}(?:治愈|治疗|消除|预防).{1,20}(?:但|然而|可是).{0,10}(?:不清楚|不明|未知|尚不)",
            r"(?:机制|原理|原因).{0,5}(?:不明|尚不清楚|有待研究)",
        ],
        "description": "缺乏因果机制 — 声称效果但无法解释生物学/物理学机制",
        "severity": 30,
    },
]


@dataclass
class CausalFallacyMatch:
    """检测到的因果谬误"""
    fallacy_type: str
    description: str
    evidence_snippet: str
    severity: float = 30.0      # 严重程度 0-100
    suggested_correction: str = ""

    def to_dict(self) -> dict:
        return {
            "fallacy_type": self.fallacy_type,
            "description": self.description,
            "evidence_snippet": self.evidence_snippet[:150],
            "severity": self.severity,
            "suggested_correction": self.suggested_correction,
        }


# =============================================================================
# 因果主张提取
# =============================================================================

CAUSAL_INDICATORS_CN = [
    # 强因果指示词
    (r"(.{1,60})(?:导致|造成|引起|引发|触发)(.{1,60})", "direct_cause", 70),
    (r"(.{1,60})(?:因为|由于|归因于)(.{1,60})", "direct_cause", 60),
    (r"(.{1,60})(?:所以|因此|因而|于是)(.{1,60})", "direct_cause", 55),
    # 促成因素
    (r"(.{1,60})(?:促进|推动|加速|加剧|加重)(.{1,60})", "contributing", 45),
    (r"(.{1,60})(?:有助于|有利于)(.{1,60})", "contributing", 35),
    # 弱因果/相关
    (r"(.{1,60})(?:与.{1,10}有关|与.{1,10}相关|与.{1,10}关联)(.{1,60})", "corr_as_cause", 25),
    (r"(.{1,60})(?:成正比|呈正相关|呈负相关)(.{1,60})", "corr_as_cause", 30),
    # 条件因果
    (r"(?:如果|假如|倘若|一旦)(.{1,40})(?:那么|就会|则会|便会)(.{1,40})", "contributing", 30),
]

# English causal indicators (parallel detection for non-Chinese text)
CAUSAL_INDICATORS_EN = [
    # Strong causal
    (r"(.{1,80})\s*(?:causes?|leads?\s+to|results?\s+in|triggers?|induces?)\s*(.{1,80})", "direct_cause", 70),
    (r"(.{1,80})\s*(?:because\s+of|due\s+to|as\s+a\s+result\s+of|owing\s+to)\s*(.{1,80})", "direct_cause", 65),
    (r"(.{1,80})\s*(?:therefore|thus|hence|consequently|as\s+a\s+consequence),?\s*(.{1,80})", "direct_cause", 60),
    # Contributing factors
    (r"(.{1,80})\s*(?:contributes?\s+to|promotes?|increases?\s+risk\s+of|enhances?)\s*(.{1,80})", "contributing", 45),
    (r"(.{1,80})\s*(?:is\s+(?:linked|associated|correlated)\s+(?:to|with))\s*(.{1,80})", "corr_as_cause", 30),
    # Conditional causal
    (r"(?:if|when|should)\s*(.{1,60})\s*(?:then|will|would|may|might|could)\s*(.{1,60})", "contributing", 35),
]


def extract_causal_claims(text: str, title: str = "") -> list[dict]:
    """
    从文本中提取因果关系声明。

    返回: [{"cause": str, "effect": str, "type": str, "confidence": float, "snippet": str}, ...]
    """
    claims = []
    seen = set()

    full_text = f"{title}\n{text}" if title else text

    for pattern, claim_type, base_confidence in CAUSAL_INDICATORS_CN:
        for match in re.finditer(pattern, full_text):
            cause = match.group(1).strip()
            effect = match.group(2).strip()

            # 去重
            key = f"{cause[:30]}|{effect[:30]}"
            if key in seen:
                continue
            seen.add(key)

            # 过滤太短或太长的片段
            if len(cause) < 3 or len(effect) < 3:
                continue
            if len(cause) > 120 or len(effect) > 120:
                continue

            # 调整置信度: 片段越长越具体, 但太短则不确定
            adjusted_confidence = base_confidence
            if len(cause) < 8 or len(effect) < 8:
                adjusted_confidence -= 15
            if len(cause) > 40 and len(effect) > 20:
                adjusted_confidence += 10

            claims.append({
                "cause": cause,
                "effect": effect,
                "type": claim_type,
                "confidence": min(100, max(10, adjusted_confidence)),
                "snippet": match.group(0)[:200],
            })

    # English causal extraction (only if text is primarily English)
    ascii_ratio = sum(1 for c in full_text if c.isascii() and c.isalpha()) / max(1, sum(1 for c in full_text if c.isalpha()))
    if ascii_ratio > 0.5:
        for pattern, claim_type, base_confidence in CAUSAL_INDICATORS_EN:
            for match in re.finditer(pattern, full_text, re.IGNORECASE):
                cause = match.group(1).strip()
                effect = match.group(2).strip()

                key = f"en:{cause[:30]}|{effect[:30]}"
                if key in seen:
                    continue
                seen.add(key)

                if len(cause) < 3 or len(effect) < 3:
                    continue
                if len(cause) > 120 or len(effect) > 120:
                    continue

                adjusted_confidence = base_confidence
                if len(cause) < 8 or len(effect) < 8:
                    adjusted_confidence -= 15
                if len(cause) > 40 and len(effect) > 20:
                    adjusted_confidence += 10

                claims.append({
                    "cause": cause,
                    "effect": effect,
                    "type": claim_type,
                    "confidence": min(100, max(10, adjusted_confidence)),
                    "snippet": match.group(0)[:200],
                })

    return claims


# =============================================================================
# 因果谬误检测
# =============================================================================

def detect_causal_fallacies(text: str, claims: list[dict]) -> list[CausalFallacyMatch]:
    """检测因果主张中的逻辑谬误"""
    fallacies = []

    # 1. 模式匹配检测
    for fallacy_def in CAUSAL_FALLACY_PATTERNS:
        for pattern in fallacy_def["patterns"]:
            for match in re.finditer(pattern, text):
                snippet = match.group(0)[:150]
                # 去重
                if any(f.evidence_snippet == snippet for f in fallacies):
                    continue
                fallacies.append(CausalFallacyMatch(
                    fallacy_type=fallacy_def["type"],
                    description=fallacy_def["description"],
                    evidence_snippet=snippet,
                    severity=fallacy_def["severity"],
                ))
                break  # 每个模式只取第一个匹配

    # 2. 基于提取的因果主张检测
    for claim in claims:
        # 检查是否为单一原因声明
        if claim["type"] == "direct_cause":
            cause_text = claim["cause"]
            if re.search(r"(?:唯一|根本|绝对|完全|100%|一定)", cause_text):
                fallacies.append(CausalFallacyMatch(
                    fallacy_type=CausalClaimType.SINGLE_CAUSE_FALLACY,
                    description="单一原因谬误 — 声称某因素是唯一/根本原因",
                    evidence_snippet=claim["snippet"],
                    severity=35,
                ))

        # 相关→因果的过度推断
        if claim["type"] == "corr_as_cause" and claim["confidence"] > 50:
            fallacies.append(CausalFallacyMatch(
                fallacy_type=CausalClaimType.CORRELATION_AS_CAUSATION,
                description="相关被解释为因果 — 缺乏机制说明和时间顺序证据",
                evidence_snippet=claim["snippet"],
                severity=40,
            ))

    return fallacies


# =============================================================================
# 因果图谱构建
# =============================================================================

def build_causal_graph(
    claims: list[dict],
    fallacies: list[CausalFallacyMatch],
    text: str = "",
    url: str = "",
) -> dict:
    """
    从因果主张构建因果图谱。

    返回包含 nodes 和 edges 的图谱结构。
    """
    nodes: list[CausalNode] = []
    edges: list[CausalEdge] = []
    node_ids: dict[str, int] = {}  # label → index

    fallacy_types = {f.fallacy_type: f for f in fallacies}

    for i, claim in enumerate(claims):
        cause_label = claim["cause"]
        effect_label = claim["effect"]

        # 创建/获取节点
        for label, is_effect_flag in [(cause_label, False), (effect_label, True)]:
            if label not in node_ids:
                node_id = f"node_{len(nodes)}"
                node_ids[label] = len(nodes)

                # 评估节点可信度
                node_cred = 50.0
                if any(f.evidence_snippet and label[:30] in f.evidence_snippet for f in fallacies):
                    node_cred -= 20

                nodes.append(CausalNode(
                    node_id=node_id,
                    label=label[:80],
                    description=label,
                    evidence_level="low",
                    credibility=node_cred,
                    source_url=url,
                    is_effect=is_effect_flag,
                ))

        # 创建边
        cause_idx = node_ids[cause_label]
        effect_idx = node_ids[effect_label]

        # 检查是否有谬误
        edge_fallacy = False
        edge_fallacy_type = ""
        for f in fallacies:
            if f.evidence_snippet and (
                cause_label[:30] in f.evidence_snippet or
                effect_label[:30] in f.evidence_snippet
            ):
                edge_fallacy = True
                edge_fallacy_type = f.fallacy_type
                break

        edge_confidence = claim["confidence"]
        if edge_fallacy:
            edge_confidence = max(10, edge_confidence - 30)

        edges.append(CausalEdge(
            source_id=nodes[cause_idx].node_id,
            target_id=nodes[effect_idx].node_id,
            relation="causes" if claim["type"] == "direct_cause" else "contributes_to",
            claim_type=claim["type"],
            evidence_quote=claim["snippet"],
            confidence=edge_confidence,
            fallacy_detected=edge_fallacy,
            fallacy_type=edge_fallacy_type,
        ))

    # 标记根节点和叶节点
    has_incoming = set()
    has_outgoing = set()
    for e in edges:
        has_outgoing.add(e.source_id)
        has_incoming.add(e.target_id)

    for node in nodes:
        if node.node_id not in has_incoming:
            node.is_root = True
        if node.node_id not in has_outgoing:
            node.is_effect = True

    return {
        "nodes": [n.to_dict() for n in nodes],
        "edges": [e.to_dict() for e in edges],
        "total_nodes": len(nodes),
        "total_edges": len(edges),
    }


# =============================================================================
# 因果链可信度传导
# =============================================================================

def propagate_credibility(graph: dict) -> dict:
    """
    沿因果链传导可信度: 下游节点的可信度 ≤ 上游节点可信度 × 边的置信度。

    返回每个节点的最终可信度调整。
    """
    nodes = {n["node_id"]: n for n in graph["nodes"]}
    edges = graph["edges"]

    # 构建邻接表: source → [(target, edge_confidence)]
    adj = defaultdict(list)
    for e in edges:
        adj[e["source_id"]].append((e["target_id"], e["confidence"] / 100.0))

    # BFS 传导
    visited = set()
    queue = [n["node_id"] for n in graph["nodes"] if n.get("is_root")]

    while queue:
        source_id = queue.pop(0)
        if source_id in visited:
            continue
        visited.add(source_id)

        source_cred = nodes.get(source_id, {}).get("credibility", 50.0)

        for target_id, edge_confidence in adj.get(source_id, []):
            if target_id not in nodes:
                continue
            # 传导公式: target.credibility = min(target.credibility, source.credibility × edge.confidence)
            propagated = source_cred * edge_confidence
            current = nodes[target_id].get("credibility", 50.0)
            nodes[target_id]["credibility"] = round(min(current, propagated), 1)

            if target_id not in visited:
                queue.append(target_id)

    return graph


# =============================================================================
# 因果摘要生成
# =============================================================================

def generate_causal_summary(
    claims: list[dict],
    fallacies: list[CausalFallacyMatch],
    graph: dict,
) -> str:
    """生成因果分析的自然语言摘要"""
    parts = []

    if not claims:
        parts.append("文本中未检测到明确的因果关系声明。")
        if fallacies:
            parts.append(f"但检测到{len(fallacies)}处因果谬误信号。")
        return " ".join(parts)

    parts.append(f"从文本中提取{len(claims)}条因果关系声明。")

    # 统计谬误
    if fallacies:
        fallacy_summary = defaultdict(int)
        for f in fallacies:
            fallacy_summary[f.fallacy_type] += 1
        parts.append(f"检测到{len(fallacies)}处因果谬误: ")
        for ftype, count in fallacy_summary.items():
            type_label = {
                "post_hoc": "后此谬误",
                "corr_as_cause": "相关即因果",
                "reversed": "可能因果倒置",
                "confounder_omit": "遗漏混淆变量",
                "slippery_slope": "滑坡论证",
                "missing_mechanism": "缺乏因果机制",
                "single_cause": "单一原因谬误",
            }.get(ftype, ftype)
            parts.append(f"  · {type_label}: {count}处")

    # 图谱统计
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    if nodes:
        avg_cred = sum(n.get("credibility", 50) for n in nodes) / len(nodes)
        fallacy_edges = [e for e in edges if e.get("fallacy_detected")]
        parts.append(
            f"因果图谱: {len(nodes)}节点, {len(edges)}条边, "
            f"平均节点可信度{avg_cred:.0f}/100, "
            f"{len(fallacy_edges)}条边含因果谬误。"
        )

    # 整体评估
    if len(fallacies) >= 3:
        parts.append("⚠ 因果关系中存在多个逻辑谬误，可信度较低。")
    elif len(claims) >= 3 and len(fallacies) == 0:
        parts.append("因果关系声明较为清晰，但仍需独立验证每条主张。")
    else:
        parts.append("因果关系需要进一步验证。相关不等于因果。")

    return " ".join(parts)


# =============================================================================
# 主分析入口
# =============================================================================

@dataclass
class CausalGraphResult:
    """因果图谱分析的完整结果"""
    total_claims: int = 0
    causal_claims: list[dict] = field(default_factory=list)
    fallacies: list[CausalFallacyMatch] = field(default_factory=list)
    graph: dict = field(default_factory=dict)
    propagated_graph: dict = field(default_factory=dict)
    summary: str = ""
    overall_causal_quality: float = 50.0  # 因果推理质量 0-100

    def to_dict(self) -> dict:
        return {
            "total_claims": self.total_claims,
            "causal_claims": self.causal_claims,
            "fallacies": [f.to_dict() for f in self.fallacies],
            "graph": self.propagated_graph or self.graph,
            "summary": self.summary,
            "overall_causal_quality": round(self.overall_causal_quality, 1),
        }


def analyze_causal_graph(
    text: str = "",
    title: str = "",
    url: str = "",
) -> CausalGraphResult:
    """
    GraphRAG-Causal 因果图谱分析主入口。

    分析流程:
    1. 提取因果主张
    2. 检测因果谬误
    3. 构建因果图谱
    4. 传导可信度
    5. 生成摘要
    """
    # 1. 提取因果主张
    claims = extract_causal_claims(text, title)

    # 2. 检测因果谬误
    fallacies = detect_causal_fallacies(text, claims)

    # 3. 构建因果图谱
    graph = build_causal_graph(claims, fallacies, text, url)

    # 4. 传导可信度
    propagated = propagate_credibility(graph) if graph["edges"] else graph

    # 5. 整体因果质量评分
    # 基础分：100 - 每条谬误扣分 - 低质量主张扣分
    quality = 100.0
    for f in fallacies:
        quality -= f.severity * 0.5
    for claim in claims:
        if claim["confidence"] < 30:
            quality -= 5
    quality = max(10.0, min(100.0, quality))

    # 无主张 → 中性
    if not claims and not fallacies:
        quality = 50.0

    # 6. 生成摘要
    summary = generate_causal_summary(claims, fallacies, propagated)

    return CausalGraphResult(
        total_claims=len(claims),
        causal_claims=claims,
        fallacies=fallacies,
        graph=graph,
        propagated_graph=propagated,
        summary=summary,
        overall_causal_quality=quality,
    )
