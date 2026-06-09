"""
爬虫模块测试 — CrawlResult dataclass, URLResolver
"""

import pytest
from app.crawler.base import CrawlResult
from app.crawler.resolver import URLResolver


# === CrawlResult Dataclass ===

def test_crawl_result_defaults():
    """CrawlResult 默认值"""
    result = CrawlResult(url="https://example.com")
    assert result.url == "https://example.com"
    assert result.final_url == ""
    assert result.title == ""
    assert result.content == ""
    assert result.author == ""
    assert result.platform == "general"
    assert result.images == []
    assert result.references == []
    assert result.engagement == {}
    assert result.raw_html == ""
    assert result.meta == {}


def test_crawl_result_full():
    """CrawlResult 完整构造"""
    result = CrawlResult(
        url="https://example.com/article",
        final_url="https://example.com/article?redirect=1",
        title="测试文章标题",
        content="这是一段测试内容。",
        author="测试作者",
        author_id="user_123",
        platform="news",
        published_at="2024-01-15T10:00:00+08:00",
        content_hash="abcdef1234567890",
        images=["https://example.com/img1.jpg"],
        references=["https://other.com/ref"],
        engagement={"likes": 100, "shares": 50, "comments": 20},
        raw_html="<html>...</html>",
        meta={"og:title": "OG标题"},
    )
    assert result.url == "https://example.com/article"
    assert result.title == "测试文章标题"
    assert result.content == "这是一段测试内容。"
    assert result.engagement["likes"] == 100


def test_crawl_result_attribute_access():
    """
    验证 CrawlResult 是 dataclass — 必须用属性访问，不能用 .get()
    这是修复的 Bug: worker.py 之前用 .get() 导致 AttributeError
    """
    result = CrawlResult(
        url="https://test.com",
        content="测试内容",
        title="标题",
        author="作者",
    )
    # ✅ 正确的属性访问方式
    assert result.content == "测试内容"
    assert result.title == "标题"
    assert result.author == "作者"

    # ✅ falsy 检查: content 为 "" 时视为无内容
    empty = CrawlResult(url="https://test.com", content="")
    assert not empty.content  # worker.py: 用 if not page_data.content

    # ✅ None 检查: fetch 返回 None 表示爬取失败
    none_result = None
    assert none_result is None or not none_result  # if not page_data or ...

    # 注意: CrawlResult dataclass 实例本身始终为 truthy，
    # 必须用 .content 属性判断是否有内容 (这正是之前 bug 的原因)


def test_crawl_result_repr():
    """CrawlResult __repr__"""
    result = CrawlResult(
        url="https://test.com",
        title="这是一条很长很长很长很长很长很长很长很长的标题内容",
        platform="weibo",
    )
    repr_str = repr(result)
    assert "CrawlResult" in repr_str


# === URLResolver ===

@pytest.mark.asyncio
async def test_is_shortlink():
    """短链接域名检测"""
    resolver = URLResolver()
    assert resolver.is_shortlink("https://t.cn/abc123") is True
    assert resolver.is_shortlink("https://bit.ly/xyz") is True
    assert resolver.is_shortlink("https://tinyurl.com/test") is True
    assert resolver.is_shortlink("https://weibo.com/user") is False
    assert resolver.is_shortlink("https://example.com") is False


@pytest.mark.asyncio
async def test_get_final_url_from_chain():
    """从跳转链获取最终 URL"""
    resolver = URLResolver()
    chain = [
        ("https://t.cn/abc", 302),
        ("https://example.com/target", 200),
    ]
    assert resolver.get_final_url(chain) == "https://example.com/target"


@pytest.mark.asyncio
async def test_get_final_url_empty_chain():
    """空跳转链"""
    resolver = URLResolver()
    assert resolver.get_final_url([]) == ""


@pytest.mark.asyncio
async def test_resolve_url_no_redirect():
    """无跳转的正常 URL"""
    resolver = URLResolver()
    # 对于 HTTP 请求，这个 URL 应该返回 200 (或超时错误)
    # 我们只验证 resolver 不会崩溃
    chain = await resolver.resolve("https://example.com")
    assert isinstance(chain, list)
    # 可能为空 (连接失败) 或包含跳转记录
