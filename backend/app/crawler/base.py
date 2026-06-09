"""
爬虫基类 — 定义统一接口和通用功能
"""

import random
import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import httpx
from loguru import logger

from app.config import get_settings


@dataclass
class CrawlResult:
    """爬取结果统一数据结构"""
    url: str
    final_url: str = ""           # 最终 URL（经过重定向后）
    title: str = ""
    content: str = ""
    author: str = ""
    author_id: str = ""
    platform: str = "general"
    published_at: str = ""        # ISO 8601 格式
    content_hash: str = ""        # 内容指纹
    images: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)  # 引用/提及的其他 URL
    engagement: dict = field(default_factory=dict)       # {likes, shares, comments, views}
    raw_html: str = ""
    meta: dict = field(default_factory=dict)

    def __repr__(self):
        return f"<CrawlResult {self.platform}:{self.title[:30]}>"


class BaseCrawler(ABC):
    """爬虫抽象基类"""

    def __init__(self, timeout: int | None = None):
        settings = get_settings()
        self.timeout = timeout or settings.crawler_timeout
        self.user_agents = settings.crawler_user_agents
        self.concurrency = settings.crawler_concurrency

        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """懒加载 httpx 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers=self._default_headers(),
            )
        return self._client

    def _default_headers(self) -> dict:
        """默认请求头，随机 User-Agent"""
        ua = random.choice(self.user_agents)
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
        }

    @abstractmethod
    async def fetch(self, url: str) -> CrawlResult | None:
        """
        爬取指定 URL

        Args:
            url: 目标 URL

        Returns:
            CrawlResult 或 None（爬取失败时）
        """
        ...

    @abstractmethod
    async def search(self, keyword: str, limit: int = 20) -> list[CrawlResult]:
        """
        搜索关键词

        Args:
            keyword: 搜索关键词
            limit: 最大返回数量

        Returns:
            CrawlResult 列表
        """
        ...

    def _compute_hash(self, content: str) -> str:
        """计算内容 SHA-256 哈希"""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
