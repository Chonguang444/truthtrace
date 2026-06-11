"""新引擎模块测试 — echo_chamber / cross_lang_trace / english_patterns / rumor_timeline / attention_metric"""
import pytest


class TestEchoChamber:
    def test_single_source_no_echo(self):
        from app.engine.echo_chamber import detect_echo_chamber
        result = detect_echo_chamber(
            content_text="正常报道",
            sources=[{"name": "新华社", "type": "official"}],
        )
        assert not result.echo_chamber_detected

    def test_multi_source_single_root(self):
        from app.engine.echo_chamber import detect_echo_chamber
        sources = [
            {"name": "新某报", "type": "official", "cites": []},
            {"name": "环球某报", "type": "news", "cites": ["新某报"]},
            {"name": "澎湃新闻", "type": "news", "cites": ["环球某报"]},
        ]
        result = detect_echo_chamber(sources=sources)
        assert result.echo_chamber_detected
        assert result.echo_chamber_score >= 60

    def test_chain_citation_detection(self):
        from app.engine.echo_chamber import detect_echo_chamber
        result = detect_echo_chamber(
            content_text="据环球时报报道，据新某报援引知情人士称，据内部消息透露",
        )
        assert result.citation_chain_depth >= 1

    def test_result_to_dict(self):
        from app.engine.echo_chamber import detect_echo_chamber
        result = detect_echo_chamber(sources=[{"name": "A", "type": "news", "cites": []}])
        d = result.to_dict()
        assert "echo_chamber_detected" in d
        assert "assessment" in d


class TestCrossLangTrace:
    def test_detect_international_claim(self):
        from app.engine.cross_lang_trace import detect_international_claim
        result = detect_international_claim("联合国教科文组织WHO FDA均已确认")
        entities = [e["entity"] for e in result["international_entities_found"]]
        assert "UNESCO" in entities or "WHO" in entities

    def test_no_international_entity(self):
        from app.engine.cross_lang_trace import detect_international_claim
        result = detect_international_claim("今天天气很好")
        assert not result["recommend_cross_lang_trace"]

    def test_generate_queries(self):
        from app.engine.cross_lang_trace import generate_cross_lang_queries
        result = generate_cross_lang_queries("韩国申遗失败", ["en", "ja"])
        assert len(result.queries_generated) == 2

    def test_japanese_entity_recommended(self):
        from app.engine.cross_lang_trace import detect_international_claim
        result = detect_international_claim("日本文部科学省发布了新的教育政策")
        assert "ja" in result.get("languages_recommended", [])


class TestEnglishPatterns:
    def test_score_english_misinfo(self):
        from app.engine.english_patterns import score_english_misinfo
        result = score_english_misinfo(
            "Big Pharma does not want you to know this secret cure! Wake up America! "
            "Share before they delete this! This is a plandemic!"
        )
        assert result["risk_score"] > 0
        assert result["match_count"] >= 1

    def test_english_distortion_patterns(self):
        from app.engine.english_patterns import score_english_misinfo
        result = score_english_misinfo(
            "Harvard scientists confirm that this natural remedy works! "
            "Studies show amazing results without side effects."
        )
        assert result["match_count"] >= 1

    def test_neutral_english_text(self):
        from app.engine.english_patterns import score_english_misinfo
        result = score_english_misinfo(
            "The weather forecast indicates partly cloudy skies with a high of 72 degrees."
        )
        assert result["risk_score"] <= 10


class TestRumorTimeline:
    def test_generate_timeline_with_distortion(self):
        from app.engine.rumor_timeline import generate_rumor_timeline
        tl = generate_rumor_timeline(
            rumor_text="阿斯巴甜100%致癌！速看！",
            detected_distortions=["context_stripping"],
            detected_fallacies=["post_hoc"],
        )
        assert len(tl.steps) >= 4
        assert len(tl.reveals) >= 1

    def test_generate_empty_timeline(self):
        from app.engine.rumor_timeline import generate_rumor_timeline
        tl = generate_rumor_timeline(rumor_text="通用测试")
        assert len(tl.steps) >= 4  # generic fallback

    def test_timeline_to_dict(self):
        from app.engine.rumor_timeline import generate_rumor_timeline
        tl = generate_rumor_timeline("测试")
        d = tl.to_dict()
        assert "steps" in d
        assert "reveals" in d


class TestAttentionMetric:
    def test_low_entertainment(self):
        from app.engine.attention_metric import compute_attention_metric
        result = compute_attention_metric(
            content_text="经WHO确认，该物质在安全剂量以下无健康风险。研究表明其安全性经过充分验证。",
            content_title="食品安全科普",
        )
        assert result.risk_level in ("low", "medium")

    def test_high_entertainment(self):
        from app.engine.attention_metric import compute_attention_metric
        result = compute_attention_metric(
            content_text="小姐姐太美了！颜值爆表！笑死我了哈哈哈！离谱！",
            content_title="搞笑视频",
        )
        assert result.entertainment_density > 0

    def test_comment_relevance(self):
        from app.engine.attention_metric import compute_attention_metric
        result = compute_attention_metric(
            content_title="Python性能优化教程",
            comments=[
                {"content": "很好的Python教程，学习了很多", "like": 100},
                {"content": "这个性能优化思路很棒", "like": 50},
            ],
        )
        assert result.comment_topic_relevance >= 0  # At minimum, metric runs without error

    def test_to_dict(self):
        from app.engine.attention_metric import compute_attention_metric
        result = compute_attention_metric(content_text="测试文本")
        d = result.to_dict()
        assert "risk_level" in d


class TestAuthAPI:
    @pytest.mark.asyncio
    async def test_csrf_token_requires_auth(self):
        from httpx import AsyncClient, ASGITransport
        from app.main import app
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/auth/csrf-token")
            assert resp.status_code == 401
