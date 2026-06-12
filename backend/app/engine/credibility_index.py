"""
溯源可信度指数 (Trace Credibility Index) — 传播链可信度传导模型

理论基础:
  - 西安康奈专利 CN120075074A (双阈值调节+溯源可信度指数)
  - 基于大数据和区块链的溯源方法 CN119557607A (责任传播概率模型+分级归因)
  - ISDR-M 传播模型 (系统科学与数学, 2026)

核心算法:
  1. 对传播链路中每个节点计算初始可信度
  2. 沿传播方向传导可信度 (可信度衰减模型)
  3. 在每个传播节点标注: 原始度/失真度/放大度
  4. 生成节点-边权重可视化数据

可信度公式:
  node_cred = source_authority × content_integrity × citation_quality
  downstream_cred = upstream_cred × (1 - distortion_penalty) × edge_confidence
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import math


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class TraceNodeCredibility:
    """传播链节点可信度"""
    node_id: str = ""
    node_url: str = ""
    node_platform: str = ""
    node_author: str = ""
    node_published_at: str = ""

    # 三维度初始评分
    source_authority: float = 0.5      # 来源权威度 0-1
    content_integrity: float = 0.5     # 内容完整度 0-1
    citation_quality: float = 0.5      # 引用质量 0-1

    # 初始综合可信度
    initial_credibility: float = 0.5   # 0-1

    # 传导结果
    upstream_credibility: float = 0.5  # 上游传导来的可信度
    final_credibility: float = 0.5     # 最终可信度 (初始 × 传导)

    # 传播角色标注
    is_original: bool = False          # 是否为原始来源
    distortion_detected: bool = False  # 是否检测到信息失真
    amplification_role: str = ""       # 传播角色: originator/amplifier/resharer/commentator

    # 边属性
    edge_type: str = ""                # 引用/转发/评论
    edge_confidence: float = 1.0       # 边置信度 (转发=0.9, 引用=0.7, 评论=0.5)
    propagation_delay_hours: float = 0 # 传播延迟(小时)

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "node_url": self.node_url[:120],
            "node_platform": self.node_platform,
            "node_author": self.node_author,
            "node_published_at": self.node_published_at,
            "source_authority": round(self.source_authority, 2),
            "content_integrity": round(self.content_integrity, 2),
            "citation_quality": round(self.citation_quality, 2),
            "initial_credibility": round(self.initial_credibility, 2),
            "upstream_credibility": round(self.upstream_credibility, 2),
            "final_credibility": round(self.final_credibility, 2),
            "is_original": self.is_original,
            "distortion_detected": self.distortion_detected,
            "amplification_role": self.amplification_role,
            "edge_type": self.edge_type,
            "edge_confidence": round(self.edge_confidence, 2),
            "propagation_delay_hours": round(self.propagation_delay_hours, 1),
        }


@dataclass
class CredibilityIndexResult:
    """溯源可信度指数完整结果"""
    nodes: list[TraceNodeCredibility] = field(default_factory=list)
    root_credibility: float = 0.5
    chain_integrity_score: float = 0.5    # 链路完整性 0-1
    average_decay_rate: float = 0.0       # 平均衰减率
    weakest_link: Optional[TraceNodeCredibility] = None
    strongest_link: Optional[TraceNodeCredibility] = None
    total_nodes: int = 0
    original_sources_count: int = 0
    summary: str = ""
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "root_credibility": round(self.root_credibility, 2),
            "chain_integrity_score": round(self.chain_integrity_score, 2),
            "average_decay_rate": round(self.average_decay_rate, 3),
            "weakest_link": self.weakest_link.to_dict() if self.weakest_link else None,
            "strongest_link": self.strongest_link.to_dict() if self.strongest_link else None,
            "total_nodes": self.total_nodes,
            "original_sources_count": self.original_sources_count,
            "summary": self.summary,
            "recommendations": self.recommendations,
        }


# =============================================================================
# 来源权威度评估
# =============================================================================

AUTHORITY_DOMAINS_SCORE = {
    "gov.cn": 0.98, "stats.gov.cn": 0.99, "samr.gov.cn": 0.95,
    "nhc.gov.cn": 0.95, "nmpa.gov.cn": 0.95,
    "who.int": 0.99, "un.org": 0.98, "worldbank.org": 0.95,
    "edu.cn": 0.85, ".edu": 0.85,
    "xinhuanet.com": 0.80, "people.com.cn": 0.78, "cctv.com": 0.78,
    "pubmed.ncbi.nlm.nih.gov": 0.90, "doi.org": 0.85,
    "nature.com": 0.88, "science.org": 0.88, "springer.com": 0.82,
    "thepaper.cn": 0.70, "caixin.com": 0.72,
    "weibo.com": 0.35, "zhihu.com": 0.40, "mp.weixin.qq.com": 0.30,
    "tieba.baidu.com": 0.20, "douyin.com": 0.25,
}

PLATFORM_BASE_SCORES = {
    "weibo": 0.35, "twitter": 0.30, "wechat": 0.30,
    "zhihu": 0.40, "bilibili": 0.45, "douyin": 0.25,
    "xiaohongshu": 0.30, "kuaishou": 0.25,
    "youtube": 0.40, "facebook": 0.30, "reddit": 0.35,
    "news_official": 0.80, "government": 0.95, "academic": 0.90,
    "blog": 0.30, "forum": 0.25, "unknown": 0.40,
}

EDGE_CONFIDENCE = {
    "quote": 0.90,      # 直接引用 — 高置信度
    "reference": 0.75,  # 参考/提及 — 中高置信度
    "reshare": 0.60,    # 转发 — 中等置信度
    "reply": 0.40,      # 评论回复 — 偏低置信度
    "citation": 0.85,   # 引用(学术) — 高置信度
    "related": 0.30,    # 相关 — 低置信度
    "unknown": 0.50,
}


# =============================================================================
# 可信度传播算法
# =============================================================================

class CredibilityPropagation:
    """可信度传播引擎 — 沿传播链传导可信度分值"""

    @staticmethod
    def compute_source_authority(url: str = "", platform: str = "") -> float:
        """从URL和平台评估来源权威度"""
        from urllib.parse import urlparse
        score = PLATFORM_BASE_SCORES.get(platform, 0.40)

        if url:
            try:
                hostname = urlparse(url).hostname or ""
                for domain, domain_score in AUTHORITY_DOMAINS_SCORE.items():
                    if domain in hostname:
                        score = max(score, domain_score)
                        break
            except Exception:
                pass

        return score

    @staticmethod
    def compute_content_integrity(
        content_length: int = 0,
        has_citations: bool = False,
        has_sources: bool = False,
        has_original_data: bool = False,
        distortion_count: int = 0,
        fallacy_count: int = 0,
    ) -> float:
        """计算内容完整性"""
        score = 0.5  # 基础分

        if content_length > 500:
            score += 0.10
        if content_length > 2000:
            score += 0.05
        if has_citations:
            score += 0.15
        if has_sources:
            score += 0.10
        if has_original_data:
            score += 0.10

        # 失真/谬误惩罚
        if distortion_count > 0:
            score -= min(0.3, distortion_count * 0.10)
        if fallacy_count > 0:
            score -= min(0.2, fallacy_count * 0.07)

        return max(0.05, min(1.0, score))

    @staticmethod
    def compute_citation_quality(
        cited_urls: list[str] | None = None,
        cited_authorities: int = 0,
    ) -> float:
        """计算引用质量"""
        if not cited_urls:
            return 0.3

        quality_sum = 0.0
        for url in cited_urls[:10]:
            quality_sum += CredibilityPropagation.compute_source_authority(url)

        avg_quality = quality_sum / max(1, len(cited_urls[:10]))

        # 引用数量加分 (但边际递减)
        count_bonus = min(0.15, len(cited_urls) * 0.02)

        return min(1.0, avg_quality * 0.7 + 0.15 + count_bonus)

    @staticmethod
    def compute_decay_factor(
        edge_type: str = "unknown",
        propagation_delay_hours: float = 0,
        amplification_role: str = "resharer",
    ) -> float:
        """
        计算可信度衰减因子 — 沿传播链路衰减

        衰减源:
        - 边类型: 转发衰减 > 引用衰减
        - 传播延迟: 时间越久衰减越多（信息在传播中扭曲）
        - 传播角色: 放大者衰减 > 原始发布者
        """
        edge_conf = EDGE_CONFIDENCE.get(edge_type, 0.50)

        # 时间衰减: 每24小时 -2%
        time_decay = max(0.85, 1.0 - propagation_delay_hours / 1200)

        # 角色因子
        role_factor = {
            "originator": 1.0,
            "amplifier": 0.88,
            "resharer": 0.82,
            "commentator": 0.75,
        }.get(amplification_role, 0.82)

        return edge_conf * time_decay * role_factor

    @staticmethod
    def propagate(
        nodes: list[dict],
        edges: list[dict] | None = None,
        root_url: str = "",
    ) -> CredibilityIndexResult:
        """
        沿传播链传导可信度。

        Args:
            nodes: 传播节点列表 [{id, url, platform, author, content, ...}]
            edges: 边列表 [{from, to, type, delay_hours}]
            root_url: 根URL（被溯源信息本身）

        Returns:
            可信度指数结果
        """
        result = CredibilityIndexResult()
        if not nodes:
            result.summary = "无传播节点数据"
            return result

        credential_nodes: list[TraceNodeCredibility] = []

        for node in nodes:
            n = TraceNodeCredibility(
                node_id=node.get("id", ""),
                node_url=node.get("url", ""),
                node_platform=node.get("platform", ""),
                node_author=node.get("author", ""),
                node_published_at=node.get("published_at", ""),
                is_original=node.get("is_original", False),
                amplification_role=node.get("role", "resharer"),
            )

            # 三维度评估
            n.source_authority = CredibilityPropagation.compute_source_authority(
                n.node_url, n.node_platform
            )
            n.content_integrity = CredibilityPropagation.compute_content_integrity(
                content_length=len(node.get("content", "")),
                has_citations=bool(node.get("citations")),
                has_sources=bool(node.get("sources")),
                has_original_data=bool(node.get("original_data")),
                distortion_count=node.get("distortion_count", 0),
                fallacy_count=node.get("fallacy_count", 0),
            )
            n.citation_quality = CredibilityPropagation.compute_citation_quality(
                cited_urls=node.get("cited_urls", []),
                cited_authorities=node.get("cited_authorities", 0),
            )

            # 初始可信度 = 加权三维度
            n.initial_credibility = (
                n.source_authority * 0.40 +
                n.content_integrity * 0.35 +
                n.citation_quality * 0.25
            )
            credential_nodes.append(n)

        # 沿边传导可信度
        if edges and len(credential_nodes) > 1:
            # 构建节点索引
            node_index = {n.node_id: i for i, n in enumerate(credential_nodes)}

            for edge in edges:
                from_id = edge.get("from", "")
                to_id = edge.get("to", "")
                if from_id in node_index and to_id in node_index:
                    from_node = credential_nodes[node_index[from_id]]
                    to_node = credential_nodes[node_index[to_id]]

                    # 衰减因子
                    decay = CredibilityPropagation.compute_decay_factor(
                        edge_type=edge.get("type", "unknown"),
                        propagation_delay_hours=edge.get("delay_hours", 0),
                        amplification_role=to_node.amplification_role,
                    )

                    to_node.edge_type = edge.get("type", "")
                    to_node.edge_confidence = EDGE_CONFIDENCE.get(to_node.edge_type, 0.5)
                    to_node.propagation_delay_hours = edge.get("delay_hours", 0)

                    # 传导: 上游最终可信度 × 衰减因子
                    upstream = from_node.final_credibility or from_node.initial_credibility
                    to_node.upstream_credibility = upstream
                    # 最终可信度 = max(自身初始值, 上游传导值×衰减)
                    to_node.final_credibility = max(
                        to_node.initial_credibility * 0.3,
                        upstream * decay,
                    )

        # 无边的节点: 最终可信度 = 初始可信度
        for n in credential_nodes:
            if n.final_credibility == 0.5 and n.upstream_credibility == 0.5:
                n.final_credibility = n.initial_credibility

        result.nodes = credential_nodes
        result.total_nodes = len(credential_nodes)
        result.original_sources_count = sum(1 for n in credential_nodes if n.is_original)

        if credential_nodes:
            credits = [n.final_credibility for n in credential_nodes]
            result.root_credibility = credits[0] if credits else 0.5

            # 链路完整性 = 平均可信度
            result.chain_integrity_score = sum(credits) / len(credits)

            # 平均衰减率
            initial_avg = sum(n.initial_credibility for n in credential_nodes) / len(credential_nodes)
            final_avg = sum(n.final_credibility for n in credential_nodes) / len(credential_nodes)
            result.average_decay_rate = max(0, (initial_avg - final_avg) / max(initial_avg, 0.01))

            # 最弱/最强链接
            result.weakest_link = min(credential_nodes, key=lambda n: n.final_credibility)
            result.strongest_link = max(credential_nodes, key=lambda n: n.final_credibility)

        # 生成摘要和建议
        if result.chain_integrity_score >= 0.75:
            result.summary = f"传播链路完整性良好(评分{result.chain_integrity_score:.2f})。{result.total_nodes}个节点中，{result.original_sources_count}个为原始来源。"
        elif result.chain_integrity_score >= 0.45:
            result.summary = f"传播链路完整性一般(评分{result.chain_integrity_score:.2f})。部分节点可信度较低，建议重点关注。"
        else:
            result.summary = f"传播链路完整性较差(评分{result.chain_integrity_score:.2f})。多个节点存在可信度问题，建议深入核查。"

        if result.weakest_link and result.weakest_link.final_credibility < 0.3:
            result.recommendations.append(
                f"关键薄弱节点: {result.weakest_link.node_url[:80]} (可信度{result.weakest_link.final_credibility:.2f})——建议删除或核查该来源"
            )

        if result.original_sources_count == 0:
            result.recommendations.append("未发现原始来源——所有节点都是二手/三手信息，建议回查原始出处")

        if result.average_decay_rate > 0.3:
            result.recommendations.append(f"信息在传播中显著失真(平均衰减{result.average_decay_rate:.1%})——传播链中可能存在内容篡改")

        return result


# =============================================================================
# 便捷函数
# =============================================================================

def compute_credibility_index(
    nodes: list[dict],
    edges: list[dict] | None = None,
    root_url: str = "",
) -> CredibilityIndexResult:
    """计算溯源可信度指数"""
    return CredibilityPropagation.propagate(nodes, edges, root_url)
