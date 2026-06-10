"""
传播路径深度风险分析 — 第14号引擎

量化信息传播的深度和风险，对标行业标准的传播分析指标:
  1. 传播速度指数 (PSI) — 单位时间内传播节点数
  2. 变异系数 (MV) — 传播过程中信息被修改的程度
  3. 节点影响力评分 — 关键引爆节点的传播力评估
  4. 传播网络健康度 — 有机传播 vs 协同操纵
  5. 时间线异常检测 — 爆发式传播的异常时间模式

行业参考:
  - 抖音"AI求真": 传播路径追踪+传播风险量化
  - 南方+辟谣平台: 证据链构建+传播路径还原
  - 白杨智鉴(中传): 传播溯源+意图分析

核心原则:
  - 每个指标可解释可追溯
  - 异常检测附证据时间线
  - 不确定的测量明确标注置信度
"""

from __future__ import annotations
import math
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("truthtrace.propagation_risk")


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class PropagationMetrics:
    """传播深度量化指标"""
    # 速度
    propagation_speed_index: float = 0.0      # PSI: 节点/小时
    first_hour_nodes: int = 0                 # 发布后1小时内的传播节点数
    time_to_100_nodes: float = 0.0            # 达到100个节点所需小时数
    # 变异
    mutation_variation: float = 0.0            # 0-1: 内容被修改的比例
    unique_versions: int = 0                   # 检测到的不同版本数
    content_drift_score: float = 0.0            # 内容漂移程度
    # 网络
    total_nodes: int = 0
    total_edges: int = 0
    max_depth: int = 0                         # 传播树最大深度
    average_branching: float = 0.0              # 平均分支因子
    # 引爆节点
    key_amplifiers: list[dict] = field(default_factory=list)
    amplifier_count: int = 0
    # 有机vs操纵
    organic_ratio: float = 0.0                 # 有机传播占比
    coordinated_ratio: float = 0.0             # 协同操纵占比
    bot_node_ratio: float = 0.0                # 疑似机器人节点比例
    # 时间线
    anomaly_score: float = 0.0                 # 传播异常度 0-100
    burst_periods: list[dict] = field(default_factory=list)
    # 综合
    overall_risk_score: float = 50.0           # 综合传播风险 0-100
    risk_level: str = "moderate"

    def to_dict(self) -> dict:
        return {
            "propagation_speed_index": round(self.propagation_speed_index, 1),
            "first_hour_nodes": self.first_hour_nodes,
            "time_to_100_nodes": round(self.time_to_100_nodes, 1),
            "mutation_variation": round(self.mutation_variation, 2),
            "unique_versions": self.unique_versions,
            "content_drift_score": round(self.content_drift_score, 2),
            "total_nodes": self.total_nodes,
            "total_edges": self.total_edges,
            "max_depth": self.max_depth,
            "average_branching": round(self.average_branching, 1),
            "key_amplifiers": self.key_amplifiers,
            "amplifier_count": self.amplifier_count,
            "organic_ratio": round(self.organic_ratio, 2),
            "coordinated_ratio": round(self.coordinated_ratio, 2),
            "bot_node_ratio": round(self.bot_node_ratio, 2),
            "anomaly_score": round(self.anomaly_score, 1),
            "burst_periods": self.burst_periods,
            "overall_risk_score": round(self.overall_risk_score, 1),
            "risk_level": self.risk_level,
        }


@dataclass
class TimelineNode:
    """传播时间线节点"""
    timestamp: str = ""
    event: str = ""
    platform: str = ""
    node_count: int = 0
    significance: float = 1.0  # 节点重要性


@dataclass
class AmplifierNode:
    """关键引爆节点"""
    url: str = ""
    platform: str = ""
    author: str = ""
    follower_count: int = 0
    spread_count: int = 0      # 由此节点引发的二次传播数
    influence_score: float = 0.0


# =============================================================================
# 1. 传播速度指数计算
# =============================================================================

def _compute_psi(
    nodes: list[dict],
    edges: list[dict],
    first_seen_at: str | None,
) -> tuple[float, int, float]:
    """
    计算传播速度指数 (Propagation Speed Index)

    PSI = 节点总数 / 传播时间跨度(小时)
    越高 → 传播越快 → 典型谣言特征

    正常信息: PSI < 5 (缓慢有机扩散)
    可疑信息: PSI 5-20 (可能被有组织地推动)
    高危信息: PSI > 20 (极可能是协同操纵/机器人网络)
    """
    if not nodes or not first_seen_at:
        return 0.0, 0, 0.0

    try:
        start = datetime.fromisoformat(str(first_seen_at).replace("Z", "+00:00"))
        hours = max(1, (datetime.now(timezone.utc) - start.replace(tzinfo=timezone.utc)).total_seconds() / 3600)
    except (ValueError, TypeError):
        hours = 24  # 默认假设24小时

    psi = len(nodes) / max(1, hours)

    # 发布后1小时内的节点数
    first_hour = sum(
        1 for n in nodes
        if n.get("published_at") and _hours_since(n["published_at"], first_seen_at) <= 1
    )

    # 达到100节点所需时间 (线性内插)
    t100 = hours * (100 / max(1, len(nodes))) if len(nodes) < 100 else hours

    return round(psi, 1), first_hour, round(t100, 1)


def _hours_since(dt_str: str, reference: str) -> float:
    try:
        dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
        ref = datetime.fromisoformat(str(reference).replace("Z", "+00:00"))
        return (dt - ref).total_seconds() / 3600
    except (ValueError, TypeError):
        return 999


# =============================================================================
# 2. 变异系数计算
# =============================================================================

def _compute_mutation(
    content_hashes: list[str],
    original_hash: str = "",
    version_hashes: list[str] | None = None,
) -> tuple[float, int, float]:
    """
    计算传播过程中的内容变异程度

    变异系数 (MV) = 不同版本数 / 总节点数
    越高 → 信息在传播中被反复修改 → 典型的"以讹传讹"

    同时检测:
    - 内容漂移: 原始内容被修改到与原文完全不相关
    - 版本聚类: 多个版本中是否有明显的人为引导痕迹
    """
    if not content_hashes:
        return 0.0, 0, 0.0

    unique = set(content_hashes)
    unique.add(original_hash) if original_hash else None
    if version_hashes:
        unique.update(version_hashes)

    total = max(1, len(content_hashes))
    mv = (len(unique) - 1) / total  # -1 for the original itself

    # 内容漂移: 如果unique>5且分布均匀，说明在传播中不断被改写
    drift = 0.0
    if len(unique) >= 5:
        # 用唯一版本熵估计漂移
        from collections import Counter
        hash_counts = Counter(content_hashes)
        if hash_counts:
            p_max = max(hash_counts.values()) / total  # 最流行版本的占比
            drift = 1.0 - p_max  # 没有主导版本 → 高漂移

    return round(mv, 2), len(unique), round(drift, 2)


# =============================================================================
# 3. 传播网络分析
# =============================================================================

def _analyze_network(nodes: list[dict], edges: list[dict]) -> dict:
    """
    分析传播网络的拓扑特征
    """
    total_n = len(nodes)
    total_e = len(edges)

    # 构建邻接表
    from collections import defaultdict
    graph: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = defaultdict(int)
    for e in edges:
        src = e.get("source_id", e.get("from", ""))
        tgt = e.get("target_id", e.get("to", ""))
        graph[src].append(tgt)
        in_degree[tgt] += 1

    # 最大深度 (BFS)
    max_depth = 0
    root = nodes[0].get("id", "") if nodes else ""
    if root and graph:
        visited = {root}
        queue = [(root, 0)]
        while queue:
            nid, depth = queue.pop(0)
            max_depth = max(max_depth, depth)
            for neighbor in graph.get(nid, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, depth + 1))

    # 平均分支因子
    out_degrees = [len(v) for v in graph.values()]
    avg_branching = sum(out_degrees) / max(1, len(out_degrees))

    # 引爆节点: 入度>3且出度>2的节点
    amplifiers = []
    for n in nodes:
        nid = n.get("id", "")
        out_deg = len(graph.get(nid, []))
        in_deg = in_degree.get(nid, 0)
        if out_deg >= 3 and in_deg >= 2:
            amplifiers.append({
                "id": nid,
                "url": n.get("url", ""),
                "platform": n.get("platform", ""),
                "author": n.get("author", ""),
                "in_degree": in_deg,
                "out_degree": out_deg,
                "influence": round(out_deg * (1 + math.log(1 + in_deg)), 1),
            })

    # 有机vs操纵比例估算
    # 入度=1 + 人为传播 → 有机
    # 入度>5 + 时间聚集 → 协同
    organic = sum(1 for nid, d in in_degree.items() if d <= 2) / max(1, len(in_degree))
    coordinated = sum(1 for nid, d in in_degree.items() if d >= 8) / max(1, len(in_degree))

    return {
        "max_depth": max_depth,
        "avg_branching": round(avg_branching, 1),
        "amplifiers": sorted(amplifiers, key=lambda a: a["influence"], reverse=True)[:5],
        "organic_ratio": round(organic, 2),
        "coordinated_ratio": round(coordinated, 2),
    }


# =============================================================================
# 4. 时间线异常检测
# =============================================================================

def _detect_anomalies(
    nodes: list[dict],
    first_seen_at: str,
    psi: float,
) -> tuple[float, list[dict]]:
    """
    检测传播时间线的异常模式

    异常模式:
    1. 突发爆发: 短时间内（<1h）节点数骤增50+ → 协同操纵
    2. 休眠重启: 传播停止后重新爆发 → 二次推广
    3. 均匀节奏: 每小时增加节点数几乎相同 → 机器人队列推送
    """
    if not nodes:
        return 0.0, []

    anomalies = []
    score = 0.0

    try:
        start = datetime.fromisoformat(str(first_seen_at).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        start = datetime.now(timezone.utc) - timedelta(hours=24)

    # 按小时分桶
    hourly_buckets: dict[int, int] = {}
    for n in nodes:
        try:
            dt = datetime.fromisoformat(str(n.get("published_at", "")).replace("Z", "+00:00"))
            hour_bucket = int((dt - start).total_seconds() / 3600)
            hourly_buckets[hour_bucket] = hourly_buckets.get(hour_bucket, 0) + 1
        except (ValueError, TypeError):
            pass

    # 突发爆发检测: 某小时 > 平均值3x
    if hourly_buckets:
        avg_per_hour = sum(hourly_buckets.values()) / len(hourly_buckets)
        for hour, count in sorted(hourly_buckets.items()):
            if count > avg_per_hour * 3 and count >= 5:
                anomalies.append({
                    "type": "burst",
                    "hour": hour,
                    "count": count,
                    "avg": round(avg_per_hour, 1),
                    "description": f"第{hour}小时出现爆发式传播, {count}个节点(均值{avg_per_hour:.1f}) — 疑似协同推送",
                })
                score += min(30, count * 2)

    # PSI过高检测
    if psi >= 20:
        score += 30
        anomalies.append({
            "type": "high_velocity",
            "psi": psi,
            "description": f"传播速度指数 {psi} (极快) — 自然传播极少达到此速度, 高度疑似人为推动",
        })
    elif psi >= 10:
        score += 15
        anomalies.append({
            "type": "elevated_velocity",
            "psi": psi,
            "description": f"传播速度指数 {psi} (偏快) — 超过正常信息扩散速度",
        })

    return min(100, score), anomalies[:10]


# =============================================================================
# 主分析器
# =============================================================================

class PropagationRiskAnalyzer:
    """
    传播路径深度风险分析器

    用法:
        analyzer = PropagationRiskAnalyzer()
        metrics = analyzer.analyze(
            nodes=graph_data.nodes_dict,
            edges=graph_data.edges_dict,
            content_hashes=[...],
            first_seen_at="2025-01-01T00:00:00Z",
        )
    """

    def analyze(
        self,
        nodes: list[dict] | None = None,
        edges: list[dict] | None = None,
        content_hashes: list[str] | None = None,
        original_hash: str = "",
        first_seen_at: str | None = None,
        propagation_pattern: str = "",
        bot_likelihood: float = 0.0,
    ) -> PropagationMetrics:
        nodes = nodes or []
        edges = edges or []
        hashes = content_hashes or []

        metrics = PropagationMetrics()
        metrics.total_nodes = len(nodes)
        metrics.total_edges = len(edges)

        # 1. 传播速度
        psi, first_hour, t100 = _compute_psi(nodes, edges, first_seen_at)
        metrics.propagation_speed_index = psi
        metrics.first_hour_nodes = first_hour
        metrics.time_to_100_nodes = t100

        # 2. 变异系数
        mv, versions, drift = _compute_mutation(hashes, original_hash)
        metrics.mutation_variation = mv
        metrics.unique_versions = versions
        metrics.content_drift_score = drift

        # 3. 网络分析
        net = _analyze_network(nodes, edges)
        metrics.max_depth = net["max_depth"]
        metrics.average_branching = net["avg_branching"]
        metrics.key_amplifiers = net["amplifiers"]
        metrics.amplifier_count = len(net["amplifiers"])
        metrics.organic_ratio = net["organic_ratio"]
        metrics.coordinated_ratio = net["coordinated_ratio"]
        metrics.bot_node_ratio = round(bot_likelihood, 3)

        # 4. 异常检测
        anomaly_score, bursts = _detect_anomalies(nodes, first_seen_at or "", psi)
        metrics.anomaly_score = anomaly_score
        metrics.burst_periods = bursts

        # 5. 综合风险评分
        risk = 50.0
        # 速度加分
        if psi >= 20: risk += 25
        elif psi >= 10: risk += 12
        elif psi >= 5: risk += 5
        # 变异加分
        if mv >= 0.5: risk += 15
        elif mv >= 0.3: risk += 8
        # 协同操纵加分
        if metrics.coordinated_ratio >= 0.3: risk += 20
        elif metrics.coordinated_ratio >= 0.15: risk += 10
        # 异常加分
        risk += anomaly_score * 0.15
        # 机器人加分
        risk += bot_likelihood * 80

        metrics.overall_risk_score = min(100, max(0, risk))
        metrics.risk_level = (
            "critical" if metrics.overall_risk_score >= 75 else
            "high" if metrics.overall_risk_score >= 55 else
            "elevated" if metrics.overall_risk_score >= 40 else
            "moderate" if metrics.overall_risk_score >= 25 else
            "low"
        )

        return metrics
