"""
事件聚类器 — 将不同来源的报道聚类为同一事件

使用层次聚类 + 内容指纹相似度
"""

from dataclasses import dataclass, field
from itertools import combinations

from loguru import logger

from app.analyzer.fingerprint import ContentFingerprinter


@dataclass
class Cluster:
    """事件簇"""
    id: str
    sources: list[dict] = field(default_factory=list)
    centroid_hash: str = ""
    keywords: set[str] = field(default_factory=set)
    title: str = ""


class EventClusterer:
    """
    事件聚类器

    使用两阶段聚类：
    1. SimHash 快速去重分组
    2. 基于关键词 Jaccard 相似度合并
    """

    def __init__(
        self,
        simhash_threshold: int = 6,
        keyword_similarity_threshold: float = 0.3,
    ):
        self.simhash_threshold = simhash_threshold
        self.keyword_threshold = keyword_similarity_threshold
        self.fingerprinter = ContentFingerprinter()

    async def cluster(
        self,
        sources: list[dict],
    ) -> list[Cluster]:
        """
        对来源列表进行聚类

        Args:
            sources: [{"id": ..., "content": ..., "content_hash": ..., "keywords": [...]}, ...]

        Returns:
            聚类结果列表
        """
        if not sources:
            return []

        # 确保每个 source 有 content_hash
        for s in sources:
            if not s.get("content_hash") and s.get("content"):
                s["content_hash"] = self.fingerprinter.compute(s["content"])

        # Phase 1: SimHash 快速分组
        clusters = self._simhash_cluster(sources)

        # Phase 2: 关键词相似度合并
        clusters = self._merge_similar_clusters(clusters)

        # 为每个簇生成标识
        for i, cluster in enumerate(clusters):
            cluster.id = f"cluster_{i}"
            if cluster.keywords:
                cluster.title = "、".join(list(cluster.keywords)[:3])

        logger.info(f"聚类完成: {len(sources)} 个来源 -> {len(clusters)} 个簇")
        return clusters

    def _simhash_cluster(self, sources: list[dict]) -> list[Cluster]:
        """
        基于 SimHash 的快速聚类

        汉明距离在阈值内的归为一组
        """
        clusters: list[Cluster] = []

        for source in sources:
            source_hash = source.get("content_hash", "")
            if not source_hash:
                # 无法计算指纹 — 单独成簇
                cluster = Cluster(
                    id="",
                    sources=[source],
                    centroid_hash=source_hash,
                    keywords=set(source.get("keywords", [])),
                )
                clusters.append(cluster)
                continue

            # 查找最相似的已知簇
            best_cluster = None
            best_distance = self.simhash_threshold + 1

            for cluster in clusters:
                if not cluster.centroid_hash:
                    continue
                distance = self.fingerprinter.hamming_distance(
                    source_hash, cluster.centroid_hash
                )
                if distance < best_distance:
                    best_distance = distance
                    best_cluster = cluster

            if best_cluster and best_distance <= self.simhash_threshold:
                # 加入现有簇
                best_cluster.sources.append(source)
                best_cluster.keywords.update(source.get("keywords", []))
                # 更新质心（简单平均：取第一个 hash，实际应用中可优化）
            else:
                # 创建新簇
                cluster = Cluster(
                    id="",
                    sources=[source],
                    centroid_hash=source_hash,
                    keywords=set(source.get("keywords", [])),
                )
                clusters.append(cluster)

        return clusters

    def _merge_similar_clusters(self, clusters: list[Cluster]) -> list[Cluster]:
        """
        基于关键词 Jaccard 相似度合并簇
        """
        merged_indices: set[int] = set()
        result: list[Cluster] = []

        for i, cluster_i in enumerate(clusters):
            if i in merged_indices:
                continue

            for j, cluster_j in enumerate(clusters):
                if j <= i or j in merged_indices:
                    continue

                similarity = self._jaccard(cluster_i.keywords, cluster_j.keywords)
                if similarity >= self.keyword_threshold:
                    # 合并
                    cluster_i.sources.extend(cluster_j.sources)
                    cluster_i.keywords.update(cluster_j.keywords)
                    merged_indices.add(j)

            result.append(cluster_i)

        return result

    def _jaccard(self, set1: set, set2: set) -> float:
        """计算 Jaccard 相似度"""
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0
