"""
辟谣验证模块测试 — RumorDetector, CrossReferencer
"""

import pytest
from datetime import datetime
from app.verifier.rumor_detect import RumorDetector
from app.verifier.cross_ref import CrossReferencer


# Mock Event and Source classes for testing
class MockSource:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockPlatform:
    def __init__(self, value):
        self.value = value


class MockEvent:
    def __init__(self, title="", sources=None):
        self.title = title
        self.sources = sources or []


# === RumorDetector ===

@pytest.mark.asyncio
async def test_rumor_template_detection():
    """谣言模板词检测"""
    detector = RumorDetector()
    event = MockEvent(
        title="紧急通知：央视曝光！速看删前速看！",
        sources=[
            MockSource(
                content="惊天爆料！内部消息曝光",
                platform=MockPlatform("weibo"),
                author="匿名",
            )
        ],
    )
    result = await detector.detect(event)
    assert result["risk_level"] in ("medium", "high")
    assert len(result["flags"]) > 0
    assert any("rumor_template" in str(f.get("type", "")) for f in result["flags"])


@pytest.mark.asyncio
async def test_rumor_single_source():
    """单来源高风险"""
    detector = RumorDetector()
    event = MockEvent(
        title="某普通事件",
        sources=[
            MockSource(
                content="普通内容",
                platform=MockPlatform("general"),
                author=None,
            )
        ],
    )
    result = await detector.detect(event)
    # 单来源 + 无作者 → 应触发 single_source + anonymous
    has_single = any(f.get("type") == "single_source" for f in result["flags"])
    assert has_single is True


@pytest.mark.asyncio
async def test_rumor_no_sources():
    """无来源检测"""
    detector = RumorDetector()
    event = MockEvent(title="无来源事件", sources=[])
    result = await detector.detect(event)
    assert any(f.get("type") == "no_sources" for f in result["flags"])


@pytest.mark.asyncio
async def test_rumor_normal_content():
    """普通内容不应触发高风险"""
    detector = RumorDetector()
    event = MockEvent(
        title="普通新闻标题",
        sources=[
            MockSource(
                content="今天天气晴，适合出行。记者张三报道。",
                platform=MockPlatform("news"),
                author="张三",
            ),
            MockSource(
                content="本周天气持续晴朗，市民出行便利。",
                platform=MockPlatform("news"),
                author="李四",
            ),
            MockSource(
                content="气象部门发布本周天气预报，以晴天为主。",
                platform=MockPlatform("general"),
                author="气象局",
            ),
        ],
    )
    result = await detector.detect(event)
    assert result["risk_level"] == "low"


@pytest.mark.asyncio
async def test_rumor_single_platform_risk():
    """所有来源同平台 → 触发 single_platform 标记"""
    detector = RumorDetector()
    sources = [
        MockSource(
            content=f"相同内容变体 {i}",
            platform=MockPlatform("weibo"),
            author=f"用户{i}",
        )
        for i in range(4)
    ]
    event = MockEvent(title="测试事件", sources=sources)
    result = await detector.detect(event)
    has_flag = any(f.get("type") == "single_platform" for f in result["flags"])
    assert has_flag is True


@pytest.mark.asyncio
async def test_rumor_check_templates_function():
    """_check_templates 单元测试"""
    detector = RumorDetector()
    flags = detector._check_templates("紧急通知：刚曝光！内部消息！删前速看！")
    assert len(flags) >= 3  # 紧急通知 + 刚曝光 + 内部消息 + 删前速看

    flags_normal = detector._check_templates("今天天气晴朗，适合户外运动。")
    assert flags_normal == []


# === CrossReferencer ===

@pytest.mark.asyncio
async def test_cross_ref_empty():
    """空来源交叉验证"""
    cr = CrossReferencer()
    result = await cr.analyze([])
    assert result["source_count"] == 0
    assert result["score"] == 50.0
    assert result["consensus_level"] == "low"


@pytest.mark.asyncio
async def test_cross_ref_single_source():
    """单来源验证"""
    cr = CrossReferencer()
    sources = [
        MockSource(
            content="测试内容",
            platform=MockPlatform("general"),
            url="https://example.com",
        )
    ]
    result = await cr.analyze(sources)
    assert result["source_count"] == 1
    assert result["consensus_level"] == "low"


@pytest.mark.asyncio
async def test_cross_ref_multi_source():
    """多来源多平台验证"""
    cr = CrossReferencer()
    sources = [
        MockSource(content="相同事件报道A", platform=MockPlatform("news"), url="https://news1.com", published_at=datetime(2024, 1, 1, 10, 0)),
        MockSource(content="相同事件报道B", platform=MockPlatform("weibo"), url="https://weibo.com/1", published_at=datetime(2024, 1, 1, 11, 0)),
        MockSource(content="相同事件报道C", platform=MockPlatform("zhihu"), url="https://zhihu.com/1", published_at=datetime(2024, 1, 1, 12, 0)),
        MockSource(content="相同事件报道D", platform=MockPlatform("twitter"), url="https://x.com/1", published_at=datetime(2024, 1, 1, 13, 0)),
        MockSource(content="相同事件报道E", platform=MockPlatform("reddit"), url="https://reddit.com/1", published_at=datetime(2024, 1, 1, 14, 0)),
    ]
    result = await cr.analyze(sources)
    assert result["source_count"] == 5
    assert result["unique_platforms"] == 5
    assert result["consensus_level"] == "high"
    assert result["score"] > 65  # 多源多平台应该得高分


@pytest.mark.asyncio
async def test_cross_ref_content_consistency():
    """内容一致性评分"""
    cr = CrossReferencer()
    sources = [
        MockSource(
            content="相同事件，细节一致。官方发布。",
            platform=MockPlatform("news"),
            url="https://news.com",
            published_at=datetime(2024, 1, 1),
        ),
        MockSource(
            content="相同事件，细节一致。二次转载。",
            platform=MockPlatform("weibo"),
            url="https://weibo.com",
            published_at=datetime(2024, 1, 1, 2),
        ),
    ]
    result = await cr.analyze(sources)
    assert result["source_count"] == 2
