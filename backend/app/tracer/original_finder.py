"""
原始来源识别器 — 综合多维信息找到最早/最权威的来源
"""

from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger

from app.tracer.graph import PropagationGraph, GraphNode
from app.tracer.source_rank import SourceRank
from app.tracer.authority import AuthorityScorer


@dataclass
class OriginalSource:
    """原始来源结果"""
    url: str
    author: str
    platform: str
    score: float           # 综合得分 (0-100)
    is_earliest: bool       # 是否时间最早
    is_most_authoritative: bool  # 是否最权威
    published_at: datetime | None = None
    evidence: list[str] = field(default_factory=list)  # 证据说明


class OriginalFinder:
    """
    原始来源查找器

    综合以下维度评分：
    1. 时间优先级（30% 权重）— 发布最早的来源得分高
    2. 网络结构（25% 权重）— 在传播图中被引用多但引用少的得分高
    3. 权威度（25% 权重）— 官方认证、历史信誉
    4. 内容原创度（20% 权重）— 内容与其它来源的差异度
    """

    WEIGHTS = {
        "temporal": 0.30,
        "structural": 0.25,
        "authority": 0.25,
        "originality": 0.20,
    }

    def __init__(self):
        self.source_rank = SourceRank()
        self.authority_scorer = AuthorityScorer()

    async def find(self, graph: PropagationGraph) -> list[OriginalSource]:
        """
        从传播图中找出一手/原始来源

        Returns:
            按综合得分降序排列的原始来源列表
        """
        if not graph.nodes:
            return []

        # 计算各维度得分
        temporal_scores = self._compute_temporal_scores(graph)
        structural_scores = self.source_rank.compute(graph)
        authority_scores = await self.authority_scorer.score_all(graph.nodes)
        originality_scores = self._compute_originality_scores(graph)

        # 综合评分
        results: list[OriginalSource] = []
        for node in graph.nodes:
            score = (
                self.WEIGHTS["temporal"] * temporal_scores.get(node.id, 0)
                + self.WEIGHTS["structural"] * structural_scores.get(node.id, 0.5) * 100
                + self.WEIGHTS["authority"] * authority_scores.get(node.id, 0)
                + self.WEIGHTS["originality"] * originality_scores.get(node.id, 0)
            )

            evidence = []
            if temporal_scores.get(node.id, 0) > 70:
                evidence.append("时间最早")
            if structural_scores.get(node.id, 0.5) > 0.7:
                evidence.append("在网络中处于源头位置")
            if authority_scores.get(node.id, 0) > 60:
                evidence.append("来源权威度高")

            results.append(OriginalSource(
                url=node.url,
                author=node.author,
                platform=node.platform,
                score=round(score, 1),
                is_earliest=temporal_scores.get(node.id, 0) > 80,
                is_most_authoritative=authority_scores.get(node.id, 0) > 70,
                published_at=node.published_at,
                evidence=evidence,
            ))

        # 按得分降序排列
        results.sort(key=lambda x: x.score, reverse=True)

        # 标记 top 结果
        for i, r in enumerate(results[:5]):
            r.is_original = True

        logger.info(
            f"原始来源识别完成: top={results[0].url if results else 'N/A'}"
        )
        return results

    def _compute_temporal_scores(self, graph: PropagationGraph) -> dict[str, float]:
        """计算时间维度得分（越早得分越高）"""
        # 收集所有有时间的节点
        timed_nodes = [
            (n.id, n.published_at)
            for n in graph.nodes
            if n.published_at is not None
        ]

        if not timed_nodes:
            return {n.id: 50.0 for n in graph.nodes}

        # 找到最早和最晚时间
        times = [t for _, t in timed_nodes]
        earliest = min(times)
        latest = max(times)
        time_span = (latest - earliest).total_seconds()

        if time_span == 0:
            return {nid: 100.0 for nid, _ in timed_nodes}

        scores = {}
        for nid, t in timed_nodes:
            # 线性映射：越早得分越高
            offset = (t - earliest).total_seconds()
            scores[nid] = 100.0 * (1 - offset / time_span)

        # 缺失时间的节点给 50 分
        for node in graph.nodes:
            if node.id not in scores:
                scores[node.id] = 50.0

        return scores

    def _compute_originality_scores(self, graph: PropagationGraph) -> dict[str, float]:
        """计算内容原创度得分"""
        if not graph.nodes:
            return {}

        # 基于出边/入边比例
        scores = {}
        for node in graph.nodes:
            out_count = sum(
                1 for e in graph.edges if e.source_id == node.id
            )
            in_count = sum(
                1 for e in graph.edges if e.target_id == node.id
            )

            total = out_count + in_count
            if total == 0:
                scores[node.id] = 50.0
            else:
                # 被引用多 + 引用少 = 内容原创度高
                originality = in_count / total
                scores[node.id] = originality * 100

        return scores
