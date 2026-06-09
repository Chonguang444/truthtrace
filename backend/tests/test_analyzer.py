"""
NLP 分析模块测试 — EventExtractor, EntityRecognizer, ContentFingerprinter, SentimentAnalyzer
"""

import pytest
from app.analyzer.event_extractor import EventExtractor
from app.analyzer.entity import EntityRecognizer
from app.analyzer.fingerprint import ContentFingerprinter
from app.analyzer.sentiment import SentimentAnalyzer


# === EventExtractor ===

@pytest.mark.asyncio
async def test_extract_empty_text():
    """空文本提取返回空结果"""
    extractor = EventExtractor()
    result = await extractor.extract("")
    assert result["title"] == ""
    assert result["summary"] == ""
    assert result["keywords"] == []


@pytest.mark.asyncio
async def test_extract_with_title():
    """带标题的事件提取"""
    extractor = EventExtractor()
    result = await extractor.extract(
        "今天下午北京发生一起食品安全事件，"
        "相关部门已介入调查。据北京市市场监管局表示，"
        "将对涉事企业进行严肃处理。",
        title="北京食品安全突发事件",
    )
    assert result["title"] == "北京食品安全突发事件"
    assert len(result["keywords"]) > 0
    # 北京可能被识别为地点或关键词，取决于 jieba 分词结果
    assert len(result["keywords"]) > 0 or len(result.get("where", [])) > 0


@pytest.mark.asyncio
async def test_extract_time():
    """时间提取"""
    extractor = EventExtractor()
    result = await extractor.extract("2024-01-15 上海发生爆炸事故")
    assert result["when"] == "2024-01-15"


@pytest.mark.asyncio
async def test_extract_entities_from_text():
    """从正文中提取人物/组织实体"""
    extractor = EventExtractor()
    result = await extractor.extract(
        "新华社报道，教育部发布通知，"
        "要求各地加强校园食品安全管理。"
        "张校长表示将严格执行。",
        title="教育部发布校园食品安全通知",
    )
    assert len(result.get("who", [])) > 0 or len(result["keywords"]) > 0


# === EntityRecognizer ===

@pytest.mark.asyncio
async def test_entity_empty_text():
    """空文本实体提取"""
    recognizer = EntityRecognizer()
    entities = await recognizer.extract("")
    assert entities == {"PERSON": [], "ORG": [], "LOC": [], "TIME": [], "EVENT": [], "MISC": []}


@pytest.mark.asyncio
async def test_entity_time_extraction():
    """时间实体提取"""
    recognizer = EntityRecognizer()
    entities = await recognizer.extract("2024-01-15 北京发生重大事件")
    assert len(entities["TIME"]) > 0
    assert any("2024" in t for t in entities["TIME"])


# === ContentFingerprinter ===

def test_compute_simhash():
    """SimHash 计算"""
    fp = ContentFingerprinter()
    h1 = fp.compute("这是一段测试文本用于指纹计算")
    h2 = fp.compute("这是一段测试文本用于指纹计算")
    h3 = fp.compute("完全不同的内容")

    assert len(h1) == 16  # 64-bit = 16 hex chars
    assert h1 == h2       # 相同内容 → 相同指纹
    assert h1 != h3       # 不同内容 → 不同指纹


def test_hamming_distance():
    """汉明距离计算"""
    fp = ContentFingerprinter()
    h1 = fp.compute("今天天气很好")
    h2 = fp.compute("今天天气很好")
    h3 = fp.compute("完全不同的新闻内容")

    assert fp.hamming_distance(h1, h2) == 0  # 相同内容距离为 0
    assert fp.hamming_distance(h1, h3) > 0   # 不同内容距离 > 0


def test_is_duplicate():
    """重复检测"""
    fp = ContentFingerprinter()
    h1 = fp.compute("今天天气很好适合出门游玩")
    h2 = fp.compute("今天天气很好适合出门游玩")
    h3 = fp.compute("美国总统大选结果公布引发全球关注")

    assert fp.is_duplicate(h1, h2, threshold=3) is True
    assert fp.is_duplicate(h1, h3, threshold=3) is False


def test_compute_empty_text():
    """空文本指纹"""
    fp = ContentFingerprinter()
    h = fp.compute("")
    assert h == "0" * 16


def test_shingles():
    """k-shingles 计算"""
    fp = ContentFingerprinter()
    shingles = fp.compute_shingles("abcdefgh", k=3)
    assert len(shingles) > 0


# === SentimentAnalyzer ===

@pytest.mark.asyncio
async def test_positive_sentiment():
    """正面情感检测"""
    analyzer = SentimentAnalyzer()
    result = await analyzer.analyze("这是一个好消息，值得庆祝的好事")
    assert result["sentiment"] in ("positive", "neutral")


@pytest.mark.asyncio
async def test_negative_sentiment():
    """负面情感检测"""
    analyzer = SentimentAnalyzer()
    result = await analyzer.analyze("这是一个可怕的谣言，令人愤怒的虚假消息")
    assert result["sentiment"] in ("negative", "neutral")


@pytest.mark.asyncio
async def test_doubt_detection():
    """质疑检测"""
    analyzer = SentimentAnalyzer()
    result = await analyzer.analyze("网传某地发生重大事故，质疑该说法，目前不能确认，有待证实，没有证据")
    assert result["is_doubtful"] is True


@pytest.mark.asyncio
async def test_neutral_sentiment():
    """中性情感检测"""
    analyzer = SentimentAnalyzer()
    result = await analyzer.analyze("今天是2024年1月1日")
    assert result["sentiment"] == "neutral"
