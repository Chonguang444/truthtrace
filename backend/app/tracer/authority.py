"""
权威度评分器 — 评估信息来源的可信度
"""

from urllib.parse import urlparse

from app.tracer.graph import GraphNode


class AuthorityScorer:
    """
    来源权威度评分

    基于多维特征评估来源可信度 (0-100)：
    1. 域名权威（政府/.gov、教育/.edu、知名媒体）
    2. 平台类型（官方媒体 > 自媒体 > 社交平台 > 匿名来源）
    3. 认证状态（蓝V/黄V等平台认证）
    4. 历史表现（该发布者过往内容被验证为真的比例）
    5. 互动质量（是否有大量质疑评论/反驳）
    """

    # 高权威域名列表
    HIGH_AUTHORITY_DOMAINS = {
        "gov.cn", "xinhuanet.com", "people.com.cn", "cctv.com",
        "china.com.cn", "gmw.cn", "youth.cn", "ce.cn",
        "std.gov.cn", "samr.gov.cn", "nhc.gov.cn",
        "nature.com", "science.org", "cell.com", "lancet.com",
        "reuters.com", "apnews.com", "bbc.com", "bbc.co.uk",
        "nytimes.com", "wsj.com", "economist.com",
        "who.int", "un.org", "worldbank.org",
    }

    # 中等权威域名
    MEDIUM_AUTHORITY_DOMAINS = {
        "zhihu.com", "weixin.qq.com", "weibo.com",
        "thepaper.cn", "caixin.com", "jiemian.com",
        "36kr.com", "huxiu.com", "tmtpost.com",
        "cnn.com", "theguardian.com", "washingtonpost.com",
    }

    # 平台基础权威分
    PLATFORM_BASE_SCORES = {
        "news": 65,
        "weibo": 40,
        "zhihu": 45,
        "twitter": 35,
        "reddit": 30,
        "general": 40,
        "unknown": 20,
    }

    async def score_all(self, nodes: list[GraphNode]) -> dict[str, float]:
        """批量评分"""
        return {node.id: await self.score(node) for node in nodes}

    async def score(self, node: GraphNode) -> float:
        """
        计算单个来源的权威度

        Returns:
            0-100 的权威度评分
        """
        score = 0.0
        components = 0

        # 1. 域名权威 (0-100)
        domain_score = self._score_domain(node.url)
        score += domain_score
        components += 1

        # 2. 平台基础分 (0-100)
        platform_score = self.PLATFORM_BASE_SCORES.get(node.platform, 40)
        score += platform_score
        components += 1

        # 3. 互动数据质量
        if node.engagement:
            engagement_score = self._score_engagement(node.engagement)
            score += engagement_score
            components += 1

        # 4. 认证标记 (从 meta 中提取)
        if hasattr(node, "meta") and node.meta:
            verified = node.meta.get("verified", False)
            if verified:
                score += 100
            else:
                score += 30
            components += 1

        return round(score / max(components, 1), 1)

    def _score_domain(self, url: str) -> float:
        """评估域名权威度"""
        try:
            domain = urlparse(url).netloc.lower()
            domain = domain.replace("www.", "")

            if any(high_domain in domain for high_domain in self.HIGH_AUTHORITY_DOMAINS):
                return 95.0
            if any(med_domain in domain for med_domain in self.MEDIUM_AUTHORITY_DOMAINS):
                return 65.0
            if domain.endswith(".gov.cn") or domain.endswith(".edu.cn"):
                return 90.0
            if ".gov" in domain or ".edu" in domain:
                return 85.0

            return 35.0
        except Exception:
            return 20.0

    def _score_engagement(self, engagement: dict) -> float:
        """
        评估互动数据质量

        高质量互动：点赞/转发比合理、有评论讨论
        低质量互动：纯转发无评论、大量负面标记
        """
        likes = engagement.get("likes", 0) or engagement.get("upvotes", 0)
        shares = engagement.get("reposts", 0) or engagement.get("shares", 0)
        comments = engagement.get("comments", 0)

        if likes == 0:
            return 30.0

        # 计算评论/点赞比（有讨论说明内容引发思考）
        comment_ratio = comments / max(likes, 1)

        # 理想的互动比例：有赞有评
        if 0.05 <= comment_ratio <= 0.5 and shares > 0:
            return 75.0
        elif comment_ratio > 0.5:
            return 55.0  # 评论太多可能是争议内容
        elif shares > likes * 2:
            return 35.0  # 过度转发可能是煽动性内容
        else:
            return 50.0
