"""
传播图构建器 — 构建信息传播网络图
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlparse

from loguru import logger


@dataclass
class GraphNode:
    """传播图节点"""
    id: str
    url: str
    platform: str
    author: str = ""
    author_id: str = ""
    title: str = ""
    content_hash: str = ""
    published_at: datetime | None = None
    authority_score: float = 0.0
    engagement: dict = field(default_factory=dict)
    is_original: bool = False

    def __hash__(self):
        return hash(self.id)


@dataclass
class GraphEdge:
    """传播图边"""
    source_id: str
    target_id: str
    edge_type: str = "reference"  # repost / quote / reference
    weight: float = 1.0
    propagated_at: datetime | None = None


@dataclass
class PropagationGraph:
    """传播图"""
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    def add_node(self, node: GraphNode):
        if not any(n.id == node.id for n in self.nodes):
            self.nodes.append(node)

    def add_edge(self, edge: GraphEdge):
        self.add_node(GraphNode(id=edge.source_id, url="", platform=""))
        self.add_node(GraphNode(id=edge.target_id, url="", platform=""))
        if not any(
            e.source_id == edge.source_id and e.target_id == edge.target_id
            for e in self.edges
        ):
            self.edges.append(edge)


class PropagationGraphBuilder:
    """
    传播图构建器

    从种子 URL 出发，通过以下方式构建传播网络：
    1. 搜索引擎反向搜索（谁引用了这个 URL）
    2. 社交平台搜索（谁转发了这个帖子）
    3. 内容引用链分析
    """

    def __init__(self):
        self.fingerprinter = None  # lazy load

    async def build(
        self,
        seed_url: str,
        seed_content: str,
        seed_author: str = "",
        entities: dict | None = None,
        deep: bool = False,
        references: list[str] | None = None,
    ) -> PropagationGraph:
        """
        从种子构建传播图

        Args:
            seed_url: 用户输入的 URL
            seed_content: 种子页面内容
            seed_author: 种子页面作者
            entities: NLP 提取的实体
            deep: 是否深度追溯（爬取更多引用链）
            references: 深度采集提取的引用链接列表

        Returns:
            PropagationGraph
        """
        graph = PropagationGraph()

        # 添加种子节点
        seed_id = self._node_id_from_url(seed_url)
        seed_node = GraphNode(
            id=seed_id,
            url=seed_url,
            platform=self._detect_platform(seed_url),
            author=seed_author,
            title=seed_content[:100] if seed_content else "",
            content_hash=self._get_fingerprinter().compute(seed_content),
            published_at=datetime.now(timezone.utc),
        )
        graph.add_node(seed_node)

        # Step 1: 深度采集的引用链接 — 实际爬取每个引用页面的正文
        if references:
            ref_nodes = await self._crawl_reference_pages(references[:10])
            for node in ref_nodes:
                graph.add_node(node)
                graph.add_edge(GraphEdge(
                    source_id=seed_id,
                    target_id=node.id,
                    edge_type="reference",
                    weight=0.8,
                    propagated_at=node.published_at,
                ))

        # Step 2: 通过搜索引擎查找引用
        search_nodes = await self._find_references(seed_url, seed_content, entities)
        for node in search_nodes:
            if not any(n.id == node.id for n in graph.nodes):
                graph.add_node(node)
                graph.add_edge(GraphEdge(
                    source_id=seed_id,
                    target_id=node.id,
                    edge_type="quote",
                    weight=0.5,
                    propagated_at=node.published_at,
                ))

        # Step 3: 如果深度追溯，深入爬取搜索结果的页面
        if deep and search_nodes:
            to_crawl = [n.url for n in (references[:5] if references else []) +
                       [n.url for n in search_nodes[:5]]]
            for ref_node in search_nodes[:3]:
                sub_refs = await self._find_references(
                    ref_node.url, "", entities
                )
                for sub_node in sub_refs:
                    if not any(n.id == sub_node.id for n in graph.nodes):
                        graph.add_node(sub_node)
                        graph.add_edge(GraphEdge(
                            source_id=ref_node.id,
                            target_id=sub_node.id,
                            edge_type="reference",
                            weight=0.3,
                            propagated_at=sub_node.published_at,
                        ))

        # Step 4: 节点间关系推断（基于内容相似度）
        self._infer_edges_by_similarity(graph)

        logger.info(
            f"传播图构建完成: {len(graph.nodes)} 节点, {len(graph.edges)} 边"
        )
        return graph

    async def _crawl_reference_pages(self, urls: list[str]) -> list[GraphNode]:
        """实际爬取引用页面的正文内容，而不仅仅是标题"""
        import httpx
        from bs4 import BeautifulSoup

        nodes: list[GraphNode] = []
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            for ref_url in urls[:8]:
                try:
                    resp = await client.get(ref_url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    })
                    if resp.status_code >= 400:
                        continue

                    soup = BeautifulSoup(resp.text[:50000], "lxml")
                    title = ""
                    t = soup.select_one("title") or soup.select_one("h1") or soup.select_one("meta[property='og:title']")
                    if t:
                        title = (t.get("content") or t.get_text()).strip()[:200]

                    # 提取正文摘要
                    content_text = ""
                    for sel in ["article", "main", '[role="main"]', ".content", ".post-content"]:
                        el = soup.select_one(sel)
                        if el:
                            content_text = el.get_text(separator=" ", strip=True)[:2000]
                            break
                    if not content_text:
                        body = soup.find("body")
                        if body:
                            content_text = body.get_text(separator=" ", strip=True)[:500]

                    node_id = self._node_id_from_url(ref_url)
                    nodes.append(GraphNode(
                        id=node_id,
                        url=ref_url,
                        platform=self._detect_platform(ref_url),
                        title=title,
                        content_hash=self._get_fingerprinter().compute(content_text) if content_text else "",
                        published_at=datetime.now(timezone.utc),
                    ))
                    logger.debug(f"[爬取引用] {ref_url[:50]}: {title[:40]}")

                except Exception as e:
                    logger.debug(f"[爬取引用失败] {ref_url[:50]}: {e}")

        return nodes

    async def _find_references(
        self,
        url: str,
        content: str,
        entities: dict | None,
    ) -> list[GraphNode]:
        """
        通过搜索引擎查找引用了该 URL 的页面

        使用 DuckDuckGo/Bing 搜索 "link:URL" 或关键词匹配
        """
        nodes: list[GraphNode] = []

        try:
            import httpx
            from bs4 import BeautifulSoup

            # 提取用于搜索的关键词
            search_query = self._build_search_query(content, entities)
            if not search_query:
                return nodes

            search_url = f"https://html.duckduckgo.com/html/?q={search_query}&max_results=15"

            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(
                    search_url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    },
                )
                soup = BeautifulSoup(response.text, "lxml")

                for link in soup.select(".result__a")[:10]:
                    href = link.get("href", "")
                    if href and href.startswith("http") and href != url:
                        node_id = self._node_id_from_url(href)
                        nodes.append(GraphNode(
                            id=node_id,
                            url=href,
                            platform=self._detect_platform(href),
                            title=link.get_text(strip=True),
                        ))

        except Exception as e:
            logger.warning(f"引用搜索失败: {e}")

        return nodes

    def _build_search_query(self, content: str, entities: dict | None) -> str:
        """从内容和实体中构建搜索关键词"""
        parts = []

        if entities:
            for key in ["EVENT", "PERSON", "ORG"]:
                values = entities.get(key, [])
                if values:
                    parts.append(values[0])

        if not parts and content:
            # 使用 TextRank 关键词
            try:
                import jieba.analyse
                keywords = jieba.analyse.extract_tags(content, topK=5)
                parts = keywords
            except Exception:
                parts = [content[:50]]

        return " ".join(parts[:3]) if parts else ""

    def _infer_edges_by_similarity(self, graph: PropagationGraph):
        """基于内容相似度推断节点间关系"""
        for i, node_a in enumerate(graph.nodes):
            for node_b in graph.nodes[i+1:]:
                if not node_a.content_hash or not node_b.content_hash:
                    continue
                fp = self._get_fingerprinter()
                if fp.is_duplicate(node_a.content_hash, node_b.content_hash, threshold=4):
                    # 内容相似 → 可能存在引用关系
                    graph.add_edge(GraphEdge(
                        source_id=node_a.id,
                        target_id=node_b.id,
                        edge_type="reference",
                        weight=0.2,
                    ))

    def _detect_platform(self, url: str) -> str:
        """根据 URL 检测平台类型"""
        domain = urlparse(url).netloc.lower()

        platform_map = {
            "weibo.com": "weibo",
            "m.weibo.cn": "weibo",
            "zhihu.com": "zhihu",
            "mp.weixin.qq.com": "wechat",
            "weixin.qq.com": "wechat",
            "twitter.com": "twitter",
            "x.com": "twitter",
            "reddit.com": "reddit",
            "t.cn": "weibo",
        }

        for key, platform in platform_map.items():
            if key in domain:
                return platform

        return "general"

    def _node_id_from_url(self, url: str) -> str:
        """从 URL 生成节点 ID"""
        import hashlib
        return hashlib.md5(url.encode()).hexdigest()[:12]

    def _get_fingerprinter(self):
        """懒加载内容指纹器"""
        if self.fingerprinter is None:
            from app.analyzer.fingerprint import ContentFingerprinter
            self.fingerprinter = ContentFingerprinter()
        return self.fingerprinter
