"""
知识图谱增强推理引擎 (KG-Enhanced Reasoning) — 第31号引擎

理论基础:
  - GraphCheck (Liu et al., 2025): KG驱动长文本核查，多跳推理链，击败DeepSeek-V3和o1
  - TrumorGPT (Hang, Yu & Tan, 2025): 图RAG-LLM事实核查
  - Hybrid KG+LLM+Search Fact-Checking (Kolli et al., 2025): F1=0.93

核心架构:
  1. 中文跨领域知识图谱 (基于expert_kb.py的10领域 + 权威域名映射)
  2. 实体识别 + 关系抽取 → 知识三元组
  3. 多跳推理链: 通过图遍历验证主张的可溯源性
  4. 证据链评分: 每条推理链的可信度加权

知识图谱节点类型:
  - ENTITY: 概念/实体 (阿斯巴甜, WHO, 致癌, 食品安全)
  - SOURCE: 权威来源 (gov.cn, who.int, pubmed)
  - CLAIM: 主张 (阿斯巴甜致癌)
  - EVIDENCE: 证据节点 (具体研究/报告)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import hashlib


@dataclass
class KGNode:
    """知识图节点"""
    node_id: str = ""
    node_type: str = ""  # entity / source / claim / evidence
    label: str = ""
    domain: str = ""
    confidence: float = 1.0
    properties: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "label": self.label,
            "domain": self.domain,
            "confidence": round(self.confidence, 2),
            "properties": self.properties,
        }


@dataclass
class KGEdge:
    """知识图边"""
    source_id: str = ""
    target_id: str = ""
    relation: str = ""  # supports / refutes / cites / relates_to / causes
    confidence: float = 0.5
    evidence_text: str = ""

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "confidence": round(self.confidence, 2),
            "evidence_text": self.evidence_text[:200],
        }


@dataclass
class KGReasoningResult:
    """知识图谱推理结果"""
    nodes: list[KGNode] = field(default_factory=list)
    edges: list[KGEdge] = field(default_factory=list)
    reasoning_chains: list[dict] = field(default_factory=list)
    verified_claims: list[dict] = field(default_factory=list)
    refuted_claims: list[dict] = field(default_factory=list)
    unverified_claims: list[dict] = field(default_factory=list)
    kg_coverage_score: float = 0.0
    multi_hop_paths: int = 0
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "reasoning_chains": self.reasoning_chains[:10],
            "verified_claims": self.verified_claims[:10],
            "refuted_claims": self.refuted_claims[:10],
            "unverified_claims": self.unverified_claims[:5],
            "kg_coverage_score": round(self.kg_coverage_score, 2),
            "multi_hop_paths": self.multi_hop_paths,
            "summary": self.summary,
        }


# =============================================================================
# 跨领域知识图谱 (精简版 — 核心事实节点)
# =============================================================================

KNOWLEDGE_GRAPH = {
    # 食品安全领域
    "aspartame": {
        "type": "entity", "domain": "food_safety",
        "relations": [
            ("aspartame_safe", "supports", 0.95, "WHO/IARC/EFSA多次评估确认安全"),
            ("cancer_myth", "refutes", 0.90, "无可靠证据支持阿斯巴甜致癌(在批准剂量下)"),
            ("approved_by_who", "cites", 0.95, "WHO食品添加剂联合专家委员会(JECFA)批准"),
            ("approved_by_fda", "cites", 0.95, "FDA 1981年批准使用"),
        ],
    },
    "monosodium_glutamate": {
        "type": "entity", "domain": "food_safety",
        "relations": [
            ("msg_safe", "supports", 0.92, "FDA/EFSA确认为GRAS(一般公认安全)"),
            ("msg_syndrome_myth", "refutes", 0.85, "双盲实验未证实'中餐馆综合征'与MSG的因果关系"),
        ],
    },
    "gmo": {
        "type": "entity", "domain": "food_safety",
        "relations": [
            ("gmo_safe_consensus", "supports", 0.90, "美国国家科学院/WHO/欧盟委员会确认GMO与传统作物同样安全"),
            ("gmo_cancer_myth", "refutes", 0.88, "无可靠证据支持GMO致癌"),
        ],
    },
    # 健康医疗领域
    "vaccine": {
        "type": "entity", "domain": "health",
        "relations": [
            ("vaccine_safe", "supports", 0.95, "WHO/CDC/全球数十亿剂接种数据确认安全有效"),
            ("vaccine_autism_myth", "refutes", 0.98, "Wakefield 1998论文已被撤回，百万级样本研究无关联"),
        ],
    },
    "5g": {
        "type": "entity", "domain": "physics",
        "relations": [
            ("5g_non_ionizing", "supports", 0.98, "5G使用非电离辐射，能量不足以破坏DNA"),
            ("5g_cancer_myth", "refutes", 0.95, "ICNIRP/IEEE安全标准内无线通信无致癌证据"),
        ],
    },
    "fluoride": {
        "type": "entity", "domain": "health",
        "relations": [
            ("fluoride_dental_safe", "supports", 0.90, "CDC将饮水氟化列为20世纪十大公共卫生成就"),
            ("fluoride_toxic_myth", "refutes", 0.85, "在推荐浓度(0.7mg/L)下安全，氟中毒仅在极高浓度发生"),
        ],
    },
    # 气候环境领域
    "climate_change": {
        "type": "entity", "domain": "climate",
        "relations": [
            ("anthropogenic_warming", "supports", 0.97, "IPCC: 97%+气候科学家共识——人类活动导致全球变暖"),
            ("climate_hoax_myth", "refutes", 0.95, "全球所有主要科学院一致确认气候变化的真实性"),
        ],
    },
    "nuclear_energy": {
        "type": "entity", "domain": "energy",
        "relations": [
            ("nuclear_safer_than_coal", "supports", 0.85, "每TWh死亡人数: 核能0.07 vs 煤炭24.6 (Our World in Data)"),
        ],
    },
    # 科技领域
    "ai": {
        "type": "entity", "domain": "technology",
        "relations": [
            ("ai_tool_not_conscious", "supports", 0.95, "当前AI为统计模型，不具备意识或自主意图"),
            ("ai_jobs_transform", "supports", 0.80, "AI将转变就业结构而非简单替代——历史技术革命规律"),
        ],
    },
}

# 权威来源知识
AUTHORITY_SOURCES = {
    "who": {"label": "世界卫生组织", "domain": "health", "credibility": 0.98, "url": "who.int"},
    "cdc": {"label": "美国疾控中心", "domain": "health", "credibility": 0.95, "url": "cdc.gov"},
    "fda": {"label": "美国食品药品管理局", "domain": "health", "credibility": 0.93, "url": "fda.gov"},
    "efsa": {"label": "欧洲食品安全局", "domain": "food_safety", "credibility": 0.93, "url": "efsa.europa.eu"},
    "iarc": {"label": "国际癌症研究机构", "domain": "health", "credibility": 0.92, "url": "iarc.who.int"},
    "ipcc": {"label": "政府间气候变化专门委员会", "domain": "climate", "credibility": 0.97, "url": "ipcc.ch"},
    "nas": {"label": "美国国家科学院", "domain": "science", "credibility": 0.95, "url": "nationalacademies.org"},
    "nhc": {"label": "中国国家卫健委", "domain": "health", "credibility": 0.93, "url": "nhc.gov.cn"},
    "samr": {"label": "中国市场监管总局", "domain": "food_safety", "credibility": 0.93, "url": "samr.gov.cn"},
}


class KnowledgeGraphReasoner:
    """知识图谱推理引擎 — 多跳推理链 + 证据验证"""

    # Chinese→English entity key mapping
    _zh_entity_map = {
        "阿斯巴甜": "aspartame", "味精": "monosodium_glutamate",
        "转基因": "gmo", "疫苗": "vaccine", "5g": "5g",
        "氟化物": "fluoride", "氟": "fluoride",
        "气候变化": "climate_change", "全球变暖": "climate_change",
        "核能": "nuclear_energy", "核电": "nuclear_energy",
        "人工智能": "ai", "AI": "ai",
    }

    @staticmethod
    def extract_entities(text: str) -> list[str]:
        """从文本中提取知识图谱中的已知实体"""
        found = []
        text_lower = text.lower()
        # Direct English key matching
        for entity_key in KNOWLEDGE_GRAPH:
            key_stripped = entity_key.replace("_", "").lower()
            if key_stripped in text_lower:
                found.append(entity_key)
        # Chinese entity matching
        for zh_term, en_key in KnowledgeGraphReasoner._zh_entity_map.items():
            if zh_term.lower() in text_lower and en_key not in found:
                if en_key in KNOWLEDGE_GRAPH:
                    found.append(en_key)
        return found

    @staticmethod
    def build_reasoning_graph(
        entities: list[str],
        claims: list[str],
    ) -> KGReasoningResult:
        """构建推理知识图谱"""
        result = KGReasoningResult()

        # 1. 添加实体节点
        for entity_key in entities:
            info = KNOWLEDGE_GRAPH.get(entity_key, {})
            if not info:
                continue
            node = KGNode(
                node_id=entity_key,
                node_type="entity",
                label=entity_key.replace("_", " ").title(),
                domain=info.get("domain", ""),
            )
            result.nodes.append(node)

        # 2. 添加关系和证据节点
        for entity_key in entities:
            info = KNOWLEDGE_GRAPH.get(entity_key, {})
            for rel_target, rel_type, confidence, evidence in info.get("relations", []):
                # 目标节点
                target_id = rel_target
                target = KGNode(
                    node_id=target_id,
                    node_type="evidence" if rel_type in ("supports", "refutes") else "entity",
                    label=rel_target.replace("_", " ").title(),
                    domain=info.get("domain", ""),
                )
                if target_id not in {n.node_id for n in result.nodes}:
                    result.nodes.append(target)

                # 边
                edge = KGEdge(
                    source_id=entity_key,
                    target_id=target_id,
                    relation=rel_type,
                    confidence=confidence,
                    evidence_text=evidence,
                )
                result.edges.append(edge)

        # 3. 对主张进行多跳推理
        for claim in claims:
            claim_lower = claim.lower()
            for entity_key in entities:
                info = KNOWLEDGE_GRAPH.get(entity_key, {})
                for rel_target, rel_type, confidence, evidence in info.get("relations", []):
                    target_label = rel_target.replace("_", " ")

                    # 检查主张是否与已知事实匹配
                    claim_words = set(claim_lower.replace(" ", ""))
                    entity_words = set(entity_key.replace("_", ""))
                    target_words = set(rel_target.replace("_", ""))

                    overlap_entity = len(claim_words & entity_words) / max(1, len(entity_words))
                    overlap_target = len(claim_words & target_words) / max(1, len(target_words))

                    if overlap_entity > 0.3 and overlap_target > 0.2:
                        chain = {
                            "claim": claim[:200],
                            "entity": entity_key,
                            "relation": rel_type,
                            "target": rel_target,
                            "confidence": confidence,
                            "evidence": evidence,
                            "hops": 1,
                        }
                        if rel_type == "supports":
                            result.verified_claims.append(chain)
                        elif rel_type == "refutes":
                            result.refuted_claims.append(chain)
                        result.reasoning_chains.append(chain)

        # 4. 尝试多跳推理 (2-hop)
        for chain in result.reasoning_chains[:10]:
            target_node = chain["target"]
            # 查找目标节点的进一步关系
            for entity_key, info in KNOWLEDGE_GRAPH.items():
                if entity_key in target_node or target_node in entity_key:
                    for rel2_target, rel2_type, conf2, ev2 in info.get("relations", []):
                        result.reasoning_chains.append({
                            "claim": chain["claim"],
                            "path": f"{chain['entity']} → {chain['target']} → {rel2_target}",
                            "hop1_confidence": chain["confidence"],
                            "hop2_relation": rel2_type,
                            "hop2_target": rel2_target,
                            "hop2_confidence": conf2,
                            "combined_confidence": round(chain["confidence"] * conf2, 2),
                            "hops": 2,
                        })
                        result.multi_hop_paths += 1
                        break  # 仅取第一个匹配的多跳路径

        # 5. 计算覆盖评分
        if claims:
            total_claims = len(claims)
            matched = len(result.verified_claims) + len(result.refuted_claims)
            result.kg_coverage_score = min(1.0, matched / max(1, total_claims))

        # 6. 未验证主张
        verified_texts = {c["claim"] for c in result.verified_claims}
        refuted_texts = {c["claim"] for c in result.refuted_claims}
        for claim in claims:
            if claim[:200] not in verified_texts and claim[:200] not in refuted_texts:
                result.unverified_claims.append({"claim": claim[:200]})

        # 7. 摘要
        result.summary = (
            f"知识图谱覆盖 {len(entities)} 个实体, {len(result.edges)} 条关系。"
            f"验证 {len(result.verified_claims)} 条主张, 反驳 {len(result.refuted_claims)} 条。"
            f"KG覆盖率 {result.kg_coverage_score:.0%}。"
        )

        return result


def run_kg_reasoning(
    text: str = "",
    claims: list[str] | None = None,
    title: str = "",
) -> KGReasoningResult:
    """运行知识图谱增强推理"""
    entities = KnowledgeGraphReasoner.extract_entities(text)

    if not claims:
        # 简单的主张提取 (基于因果指示词)
        import re
        claim_patterns = [
            r'(.{5,80}(?:导致|造成|引起|诱发|致癌|有毒|危险|有害|污染|致命).{5,80})',
            r'(.{5,80}(?:证明|证实|确认|发现|研究表明).{5,80})',
        ]
        claims = []
        for pat in claim_patterns:
            matches = re.findall(pat, text)
            claims.extend(matches)

    return KnowledgeGraphReasoner.build_reasoning_graph(entities, claims[:10])
