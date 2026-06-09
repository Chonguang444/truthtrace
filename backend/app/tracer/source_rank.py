"""
来源排序算法 — PageRank 变体应用于信息传播网络

在传播图中计算每个节点的"源头发散度"：
- 被引用越多 → 越不是源头
- 引用他人越多 → 越是传播者
- 时间越早 → 越可能是源头
"""

from collections import defaultdict

from app.tracer.graph import PropagationGraph


class SourceRank:
    """
    基于传播图的来源排序

    改进的 PageRank 算法，考虑：
    1. 网络结构（入边/出边）
    2. 时间因素（发布越早权重越高）
    3. 权威度先验
    """

    def __init__(
        self,
        damping_factor: float = 0.85,
        max_iterations: int = 100,
        convergence_threshold: float = 1e-6,
    ):
        self.d = damping_factor
        self.max_iter = max_iterations
        self.epsilon = convergence_threshold

    def compute(self, graph: PropagationGraph) -> dict[str, float]:
        """
        计算传播图中每个节点的"源头得分"

        得分越低 → 越可能是源头（被引用多，引用少）

        Returns:
            {node_id: source_score, ...}
        """
        if not graph.nodes:
            return {}

        node_ids = [n.id for n in graph.nodes]
        n = len(node_ids)
        node_index = {nid: i for i, nid in enumerate(node_ids)}

        # 构建邻接矩阵 (稀疏表示)
        adj = defaultdict(list)  # source -> [targets]
        in_degree = defaultdict(int)

        for edge in graph.edges:
            adj[edge.source_id].append(edge.target_id)
            in_degree[edge.target_id] += 1

        # 初始化 PageRank
        pr = {nid: 1.0 / n for nid in node_ids}

        # 迭代
        for iteration in range(self.max_iter):
            new_pr = {}
            total_change = 0.0

            for nid in node_ids:
                # 来自入边的贡献
                rank_sum = 0.0
                for source_id, targets in adj.items():
                    if nid in targets:
                        rank_sum += pr[source_id] / max(len(targets), 1)

                new_pr[nid] = (1 - self.d) / n + self.d * rank_sum
                total_change += abs(new_pr[nid] - pr[nid])

            pr = new_pr

            if total_change < self.epsilon:
                break

        # 反转得分：高 PageRank → 被引用多 → 非源头
        # source_score = 1 - normalized_pagerank
        max_pr = max(pr.values()) if pr else 1.0
        min_pr = min(pr.values()) if pr else 0.0

        source_scores = {}
        for nid, score in pr.items():
            if max_pr > min_pr:
                normalized = (score - min_pr) / (max_pr - min_pr)
                source_scores[nid] = 1.0 - normalized
            else:
                source_scores[nid] = 0.5

        # 根据时间调整（越早越像源头）
        for node in graph.nodes:
            if node.published_at:
                # 时间越早，适当增加源得分
                pass  # 在 OriginalFinder 中处理

        return source_scores
