"""
溯源模块测试 — PropagationGraph, SourceRank, OriginalFinder, AuthorityScorer
"""

import pytest
from datetime import datetime
from app.tracer.graph import (
    PropagationGraph, PropagationGraphBuilder,
    GraphNode, GraphEdge,
)
from app.tracer.source_rank import SourceRank
from app.tracer.authority import AuthorityScorer
from app.tracer.original_finder import OriginalFinder


# === PropagationGraph ===

def test_create_graph():
    """创建传播图"""
    graph = PropagationGraph()
    assert len(graph.nodes) == 0
    assert len(graph.edges) == 0


def test_add_node():
    """添加节点"""
    graph = PropagationGraph()
    node = GraphNode(
        id="n1",
        url="https://weibo.com/123",
        platform="weibo",
        author="test",
    )
    graph.add_node(node)
    assert len(graph.nodes) == 1

    # 重复添加去重
    graph.add_node(node)
    assert len(graph.nodes) == 1


def test_add_edge_auto_adds_nodes():
    """添加边时自动创建缺失节点"""
    graph = PropagationGraph()
    edge = GraphEdge(
        source_id="n1",
        target_id="n2",
        edge_type="reference",
        weight=1.0,
    )
    graph.add_edge(edge)
    assert len(graph.nodes) >= 2  # stub nodes created
    assert len(graph.edges) == 1


def test_multiple_nodes():
    """多节点图"""
    graph = PropagationGraph()
    for i in range(5):
        graph.add_node(GraphNode(
            id=f"n{i}",
            url=f"https://example.com/{i}",
            platform="general",
        ))
    assert len(graph.nodes) == 5


# === GraphNode ===

def test_graph_node_hash():
    """节点 hash 用于去重"""
    n1 = GraphNode(id="n1", url="https://a.com", platform="general")
    n2 = GraphNode(id="n1", url="https://a.com", platform="general")
    assert hash(n1) == hash(n2)

    nodes = set()
    nodes.add(n1)
    nodes.add(n2)
    assert len(nodes) == 1


def test_graph_node_defaults():
    """节点默认值"""
    node = GraphNode(id="test", url="https://x.com", platform="general")
    assert node.author == ""
    assert node.authority_score == 0.0
    assert node.is_original is False
    assert isinstance(node.engagement, dict)


# === SourceRank ===

def test_pagerank_on_simple_graph():
    """简单图 PageRank 计算"""
    graph = PropagationGraph()
    n1 = GraphNode(id="a", url="https://a.com", platform="general")
    n2 = GraphNode(id="b", url="https://b.com", platform="general")
    n3 = GraphNode(id="c", url="https://c.com", platform="general")
    graph.add_node(n1)
    graph.add_node(n2)
    graph.add_node(n3)
    graph.add_edge(GraphEdge(source_id="a", target_id="b"))
    graph.add_edge(GraphEdge(source_id="b", target_id="c"))

    ranker = SourceRank()
    scores = ranker.compute(graph)

    assert len(scores) == 3
    # 被引用最多的节点 (c) 应该源得分最低
    assert scores["c"] <= scores["a"]
    # 所有得分在 0-1 范围
    for v in scores.values():
        assert 0.0 <= v <= 1.0


def test_pagerank_empty_graph():
    """空图 PageRank"""
    ranker = SourceRank()
    scores = ranker.compute(PropagationGraph())
    assert scores == {}


# === AuthorityScorer ===

@pytest.mark.asyncio
async def test_high_authority_domain():
    """高权威域名评分"""
    scorer = AuthorityScorer()
    node = GraphNode(id="t1", url="https://xinhuanet.com/politics/123", platform="news")
    score = await scorer.score(node)
    assert score > 60  # xinhuanet.com + news platform


@pytest.mark.asyncio
async def test_low_authority_unknown():
    """低权威未知来源评分"""
    scorer = AuthorityScorer()
    node = GraphNode(id="t2", url="https://random-blog.com/post", platform="unknown")
    score = await scorer.score(node)
    assert score < 50


# === OriginalFinder ===

@pytest.mark.asyncio
async def test_find_original_empty_graph():
    """空图原始来源查找"""
    finder = OriginalFinder()
    result = await finder.find(PropagationGraph())
    assert result == []


@pytest.mark.asyncio
async def test_find_original():
    """找原始来源"""
    graph = PropagationGraph()

    early = datetime(2024, 1, 1, 10, 0, 0)
    late = datetime(2024, 1, 3, 10, 0, 0)

    n1 = GraphNode(
        id="a", url="https://news.com/original",
        platform="news", author="一手媒体",
        published_at=early,
    )
    n2 = GraphNode(
        id="b", url="https://weibo.com/repost",
        platform="weibo", author="转贴用户",
        published_at=late,
    )
    graph.add_node(n1)
    graph.add_node(n2)
    graph.add_edge(GraphEdge(source_id="a", target_id="b", edge_type="reference"))

    finder = OriginalFinder()
    result = await finder.find(graph)

    assert len(result) >= 2
    # 最早的节点得分应该最高
    top = result[0]
    assert top.url == "https://news.com/original"


# === PropagationGraphBuilder ===

@pytest.mark.asyncio
async def test_build_simple_graph():
    """构建传播图"""
    builder = PropagationGraphBuilder()
    graph = await builder.build(
        seed_url="https://example.com/event",
        seed_content="这是一条测试新闻内容，关于食品安全事件",
        seed_author="测试作者",
    )

    assert len(graph.nodes) >= 1  # seed node
    seed_node = graph.nodes[0]
    assert seed_node.url == "https://example.com/event"
    assert seed_node.platform == "general"
    assert seed_node.author == "测试作者"


def test_detect_platform():
    """平台检测"""
    builder = PropagationGraphBuilder()
    assert builder._detect_platform("https://weibo.com/12345") == "weibo"
    assert builder._detect_platform("https://m.weibo.cn/detail/abc") == "weibo"
    assert builder._detect_platform("https://zhihu.com/question/123") == "zhihu"
    assert builder._detect_platform("https://x.com/user/status") == "twitter"
    assert builder._detect_platform("https://reddit.com/r/news") == "reddit"
    assert builder._detect_platform("https://example.com/page") == "general"
