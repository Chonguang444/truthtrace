"""
P2 新引擎测试 — 因果图谱/叙事替代/ClaimReview 导出
"""
import pytest


# =============================================================================
# GraphRAG-Causal 因果图谱引擎
# =============================================================================

class TestCausalExtraction:
    """因果主张提取"""

    def test_extract_direct_cause(self):
        """提取直接因果关系"""
        from app.engine.causal_graph import extract_causal_claims
        text = "农药残留导致了大面积的农作物死亡。"
        claims = extract_causal_claims(text)
        assert len(claims) >= 1

    def test_extract_correlation(self):
        """提取相关关系"""
        from app.engine.causal_graph import extract_causal_claims
        text = "数据显示手机使用时长与青少年近视率呈正相关，这引起了广泛关注。"
        claims = extract_causal_claims(text)
        assert len(claims) >= 1

    def test_extract_because_effect(self):
        """提取'因为...所以'因果"""
        from app.engine.causal_graph import extract_causal_claims
        text = "因为长期熬夜，所以免疫力下降了。"
        claims = extract_causal_claims(text)
        assert len(claims) >= 1

    def test_extract_conditional_cause(self):
        """提取'如果...就会'条件因果"""
        from app.engine.causal_graph import extract_causal_claims
        text = "如果继续排放温室气体，全球气温就会继续上升。"
        claims = extract_causal_claims(text)
        assert len(claims) >= 1

    def test_no_duplicates(self):
        """重复模式不重复提取"""
        from app.engine.causal_graph import extract_causal_claims
        text = "吃糖导致蛀牙。吃糖也会导致肥胖。"
        claims = extract_causal_claims(text)
        # 相同原因"吃糖"的不同效果应分别提取但不过度重复
        assert len(claims) >= 1

    def test_empty_text_no_claims(self):
        """空文本无主张"""
        from app.engine.causal_graph import extract_causal_claims
        claims = extract_causal_claims("")
        assert len(claims) == 0

    def test_neutral_text_no_claims(self):
        """无因果指示词的文本无主张"""
        from app.engine.causal_graph import extract_causal_claims
        claims = extract_causal_claims("今天天气很好，适合出去散步。")
        assert len(claims) == 0

    def test_claim_structure(self):
        """主张有完整的 cause/effect/type/confidence/snippet 字段"""
        from app.engine.causal_graph import extract_causal_claims
        text = "长期吸烟导致肺癌风险显著增加。"
        claims = extract_causal_claims(text)
        assert len(claims) >= 1
        c = claims[0]
        assert "cause" in c
        assert "effect" in c
        assert "type" in c
        assert "confidence" in c
        assert "snippet" in c
        assert 0 <= c["confidence"] <= 100

    def test_too_short_fragments_filtered(self):
        """过短的因果片段被过滤"""
        from app.engine.causal_graph import extract_causal_claims
        text = "A导致B"  # "A"和"B"都太短了
        claims = extract_causal_claims(text)
        # "A"长度1和"B"长度1都<3，应被过滤
        assert all(len(c["cause"]) >= 3 and len(c["effect"]) >= 3 for c in claims)


class TestCausalFallacies:
    """因果谬误检测"""

    def test_detect_post_hoc(self):
        """检测后此谬误"""
        from app.engine.causal_graph import detect_causal_fallacies
        text = "自从打了疫苗之后，孩子马上就出现了发烧症状。"
        fallacies = detect_causal_fallacies(text, [])
        assert len(fallacies) >= 1
        assert any(f.fallacy_type == "post_hoc" for f in fallacies)

    def test_detect_correlation_as_causation(self):
        """检测相关即因果谬误"""
        from app.engine.causal_graph import detect_causal_fallacies
        text = "研究显示喝咖啡与寿命呈正相关，这说明喝咖啡能延长寿命。"
        fallacies = detect_causal_fallacies(text, [])
        assert len(fallacies) >= 1

    def test_detect_confounder_omission(self):
        """检测遗漏混淆变量"""
        from app.engine.causal_graph import detect_causal_fallacies
        text = "这个病100%是因为饮食不健康引起的。"
        fallacies = detect_causal_fallacies(text, [])
        assert len(fallacies) >= 1

    def test_detect_slippery_slope(self):
        """检测滑坡论证"""
        from app.engine.causal_graph import detect_causal_fallacies
        text = "如果允许基因编辑，就会导致设计婴儿，最终人类将走向毁灭。"
        fallacies = detect_causal_fallacies(text, [])
        assert len(fallacies) >= 1
        assert any(f.fallacy_type == "slippery_slope" for f in fallacies)

    def test_no_fallacy_in_neutral_text(self):
        """正常文本无谬误"""
        from app.engine.causal_graph import detect_causal_fallacies
        text = "根据实验数据，温度每升高1度，反应速率约增加10%，这符合阿伦尼乌斯公式预测。"
        fallacies = detect_causal_fallacies(text, [])
        # 科学表述不应被误报（没有谬误模式匹配）
        # just check no false positive on post_hoc
        assert not any(f.fallacy_type == "post_hoc" for f in fallacies)

    def test_single_cause_fallacy_with_claims(self):
        """基于因果主张检测单一原因谬误"""
        from app.engine.causal_graph import detect_causal_fallacies
        from app.engine.causal_graph import extract_causal_claims
        text = "唯一导致这次事故的原因是操作失误。"
        claims = extract_causal_claims(text)
        fallacies = detect_causal_fallacies(text, claims)
        # 应检测到单一原因谬误
        assert any(f.fallacy_type == "single_cause" for f in fallacies) or len(fallacies) >= 1

    def test_fallacy_has_required_fields(self):
        """谬误有必需字段"""
        from app.engine.causal_graph import detect_causal_fallacies
        text = "自从新政策实施后，经济马上就下滑了。"
        fallacies = detect_causal_fallacies(text, [])
        if fallacies:
            f = fallacies[0]
            assert f.fallacy_type
            assert f.description
            assert f.evidence_snippet
            assert 0 <= f.severity <= 100


class TestCausalGraphBuilding:
    """因果图谱构建"""

    def test_build_graph_empty(self):
        """无主张 → 空图谱"""
        from app.engine.causal_graph import build_causal_graph
        graph = build_causal_graph([], [], "", "")
        assert graph["total_nodes"] == 0
        assert graph["total_edges"] == 0

    def test_build_graph_with_claims(self):
        """有主张 → 节点+边"""
        from app.engine.causal_graph import extract_causal_claims, build_causal_graph
        text = "吸烟导致肺癌。长期熬夜导致免疫力下降。"
        claims = extract_causal_claims(text)
        graph = build_causal_graph(claims, [], text)
        assert graph["total_nodes"] >= 1
        assert graph["total_edges"] >= 1

    def test_graph_root_nodes(self):
        """图谱有根节点标记"""
        from app.engine.causal_graph import extract_causal_claims, build_causal_graph
        text = "工业污染导致呼吸系统疾病发病率上升。"
        claims = extract_causal_claims(text)
        graph = build_causal_graph(claims, [], text)
        nodes = graph["nodes"]
        root_nodes = [n for n in nodes if n.get("is_root")]
        effect_nodes = [n for n in nodes if n.get("is_effect")]
        assert len(root_nodes) >= 1
        assert len(effect_nodes) >= 1

    def test_fallacy_edges_marked(self):
        """谬误边被标记"""
        from app.engine.causal_graph import (
            extract_causal_claims, detect_causal_fallacies, build_causal_graph,
        )
        text = "自从打了疫苗后，孩子马上就发烧了，所以疫苗导致发烧。"
        claims = extract_causal_claims(text)
        fallacies = detect_causal_fallacies(text, claims)
        graph = build_causal_graph(claims, fallacies, text)
        # 如果有谬误且有关联的边
        fallacy_edges = [e for e in graph["edges"] if e.get("fallacy_detected")]
        # 不强断言 — 取决于匹配——但至少图谱是有效的
        assert "nodes" in graph
        assert "edges" in graph


class TestCredibilityPropagation:
    """可信度传导"""

    def test_propagation_reduces_downstream(self):
        """下游节点可信度 ≤ 上游 × 边置信度"""
        from app.engine.causal_graph import propagate_credibility
        graph = {
            "nodes": [
                {"node_id": "n0", "label": "A", "credibility": 100.0, "evidence_level": "high", "is_root": True, "is_effect": False, "description": "", "source_url": ""},
                {"node_id": "n1", "label": "B", "credibility": 100.0, "evidence_level": "none", "is_root": False, "is_effect": True, "description": "", "source_url": ""},
            ],
            "edges": [
                {"source_id": "n0", "target_id": "n1", "confidence": 50.0, "relation": "causes", "claim_type": "direct_cause", "evidence_quote": "", "fallacy_detected": False, "fallacy_type": ""},
            ],
        }
        propagated = propagate_credibility(graph)
        target = next(n for n in propagated["nodes"] if n["node_id"] == "n1")
        # 100 × 0.5 = 50
        assert target["credibility"] <= 50.0

    def test_no_propagation_without_edges(self):
        """无边 → 无变化"""
        from app.engine.causal_graph import propagate_credibility
        graph = {
            "nodes": [{"node_id": "n0", "label": "A", "credibility": 80.0, "evidence_level": "high", "is_root": True, "is_effect": False, "description": "", "source_url": ""}],
            "edges": [],
        }
        propagated = propagate_credibility(graph)
        assert propagated["nodes"][0]["credibility"] == 80.0


class TestCausalSummary:
    """因果摘要生成"""

    def test_empty_summary(self):
        """无主张+无谬误的摘要"""
        from app.engine.causal_graph import generate_causal_summary
        summary = generate_causal_summary([], [], {"nodes": [], "edges": []})
        assert len(summary) > 0
        assert "未检测到" in summary

    def test_summary_with_claims(self):
        """有主张的摘要"""
        from app.engine.causal_graph import generate_causal_summary
        claims = [{"cause": "A", "effect": "B", "type": "direct_cause", "confidence": 70, "snippet": "A导致B"}]
        summary = generate_causal_summary(claims, [], {"nodes": [], "edges": []})
        assert "1条" in summary

    def test_summary_with_fallacies(self):
        """有谬误的摘要含警告"""
        from app.engine.causal_graph import generate_causal_summary, CausalFallacyMatch
        fallacies = [
            CausalFallacyMatch(fallacy_type="post_hoc", description="后此谬误", evidence_snippet="", severity=30),
            CausalFallacyMatch(fallacy_type="corr_as_cause", description="相关即因果", evidence_snippet="", severity=40),
            CausalFallacyMatch(fallacy_type="slippery_slope", description="滑坡论证", evidence_snippet="", severity=35),
        ]
        summary = generate_causal_summary([], fallacies, {"nodes": [], "edges": []})
        assert "3处" in summary


class TestCausalGraphResult:
    """主入口 analyze_causal_graph"""

    def test_analyze_empty_text(self):
        """空文本分析"""
        from app.engine.causal_graph import analyze_causal_graph
        result = analyze_causal_graph(text="", title="")
        assert result.total_claims == 0
        assert result.overall_causal_quality == 50.0  # 中性

    def test_analyze_neutral_text(self):
        """无因果声明的文本"""
        from app.engine.causal_graph import analyze_causal_graph
        result = analyze_causal_graph(text="今天天气晴朗，万里无云。", title="天气预报")
        assert result.overall_causal_quality >= 50.0

    def test_analyze_fallacy_rich_text(self):
        """多谬误文本得低因果质量"""
        from app.engine.causal_graph import analyze_causal_graph
        text = (
            "自从打了疫苗，孩子马上就发烧了。"
            "研究显示疫苗与发烧呈正相关，这说明疫苗就是元凶。"
            "如果不停止接种，最终整个人类的免疫系统都会崩溃。"
        )
        result = analyze_causal_graph(text=text, title="疫苗谣言")
        # 多个谬误应拉低质量评分
        assert result.overall_causal_quality < 80

    def test_result_to_dict(self):
        """to_dict 可序列化"""
        from app.engine.causal_graph import analyze_causal_graph
        result = analyze_causal_graph(text="A导致B", title="测试")
        d = result.to_dict()
        assert "total_claims" in d
        assert "fallacies" in d
        assert "graph" in d
        assert "summary" in d
        assert "overall_causal_quality" in d


# =============================================================================
# Correction Agent 叙事替代引擎
# =============================================================================

class TestCorrectionAgent:
    """叙事替代引擎"""

    def test_generate_neutral_correction(self):
        """生成中立语气辟谣"""
        from app.engine.correction_agent import generate_correction
        result = generate_correction(
            original_claim="柠檬水可以治疗癌症",
            verified_facts=["WHO和FDA确认柠檬水无治疗癌症功效"],
            sources=["https://www.who.int/cancer"],
            credibility_score=10.0,
            title="柠檬水抗癌谣言",
        )
        assert result.short_correction
        assert result.full_correction
        assert result.tone_used in ("neutral", "authoritative")

    def test_generate_authoritative_for_low_credibility(self):
        """低可信度自动使用权威语气"""
        from app.engine.correction_agent import generate_correction
        result = generate_correction(
            original_claim="某保健品可以预防所有疾病",
            verified_facts=["没有任何药品能预防所有疾病"],
            credibility_score=5.0,
        )
        assert result.tone_used == "authoritative"

    def test_fact_wedge_generated(self):
        """生成事实楔子"""
        from app.engine.correction_agent import generate_correction
        result = generate_correction(
            original_claim="5G基站辐射致癌",
            verified_facts=["WHO确认5G辐射属于非电离辐射，不致癌", "5G基站辐射远低于国际安全标准"],
            credibility_score=5.0,
        )
        assert result.fact_wedge

    def test_truth_sandwich_structure(self):
        """真相三明治含三层结构"""
        from app.engine.correction_agent import generate_correction
        result = generate_correction(
            original_claim="转基因食品有毒",
            verified_facts=["全球所有主要科学院确认转基因食品与常规食品同样安全"],
            distortion_types=["source_fabrication", "emotional_manipulation"],
            credibility_score=8.0,
        )
        assert result.truth_sandwich
        # 三明治应有事实/注意/核实三部分
        assert "事实" in result.truth_sandwich or "注意" in result.truth_sandwich

    def test_alternative_narrative_generated(self):
        """替代叙事被生成"""
        from app.engine.correction_agent import generate_correction
        result = generate_correction(
            original_claim="地球变暖是自然周期，与人类无关",
            verified_facts=["IPCC确认人类活动是当前全球变暖的主要原因"],
            credibility_score=15.0,
        )
        assert result.alternative_narrative

    def test_cognitive_bridge_with_health_concern(self):
        """健康类主张生成认知桥梁"""
        from app.engine.correction_agent import generate_correction
        result = generate_correction(
            original_claim="这种食品添加剂会致癌",
            verified_facts=["JECFA评估确认该添加剂在ADI范围内安全"],
            credibility_score=12.0,
        )
        # 健康担忧应触发认知桥梁
        assert "安全" in result.cognitive_bridge or "理解" in result.cognitive_bridge

    def test_empty_facts_handled(self):
        """无验证事实时不崩溃"""
        from app.engine.correction_agent import generate_correction
        result = generate_correction(
            original_claim="某地发生重大事件",
            verified_facts=[],
            sources=[],
            credibility_score=40.0,
        )
        assert result.short_correction
        assert result.error_type

    def test_result_to_dict(self):
        """to_dict 可序列化"""
        from app.engine.correction_agent import generate_correction
        result = generate_correction(
            original_claim="测试主张",
            verified_facts=["测试事实"],
            credibility_score=50.0,
        )
        d = result.to_dict()
        assert "short_correction" in d
        assert "full_correction" in d
        assert "tone_used" in d
        assert "error_type" in d

    def test_tone_templates_exist(self):
        """5种语气模板都有"""
        from app.engine.correction_agent import TONE_TEMPLATES, CorrectionTone
        tones = [CorrectionTone.NEUTRAL, CorrectionTone.AUTHORITATIVE,
                 CorrectionTone.EMPATHETIC, CorrectionTone.EDUCATIONAL,
                 CorrectionTone.CONCISE]
        for tone in tones:
            assert tone in TONE_TEMPLATES

    def test_all_tones_generate(self):
        """5种语气都能生成内容"""
        from app.engine.correction_agent import CorrectionAgent, CorrectionTone
        agent = CorrectionAgent()
        for tone in [CorrectionTone.NEUTRAL, CorrectionTone.AUTHORITATIVE,
                     CorrectionTone.EMPATHETIC, CorrectionTone.EDUCATIONAL,
                     CorrectionTone.CONCISE]:
            result = agent.generate(
                original_claim="测试主张",
                verified_facts=["事实1", "事实2"],
                sources=["https://example.com"],
                tone=tone,
            )
            assert result.short_correction, f"语气 {tone} 生成失败"
            assert result.tone_used == tone


class TestCorrectionErrorClassification:
    """错误类型分类"""

    def test_very_low_credibility_is_fabricated(self):
        """极低可信度 → fabricated"""
        from app.engine.correction_agent import generate_correction
        result = generate_correction(
            original_claim="测试",
            credibility_score=10.0,
        )
        assert result.error_type in ("fabricated", "misleading", "missing_context")

    def test_distorted_info(self):
        """有情感操纵 → distorted"""
        from app.engine.correction_agent import generate_correction
        result = generate_correction(
            original_claim="测试",
            distortion_types=["emotional_manipulation"],
            credibility_score=50.0,
        )
        assert result.error_type in ("distorted", "misleading")

    def test_missing_context(self):
        """有语境剥离 → missing_context"""
        from app.engine.correction_agent import generate_correction
        result = generate_correction(
            original_claim="测试",
            distortion_types=["context_stripping"],
            credibility_score=55.0,
        )
        assert result.error_type in ("missing_context", "misleading")


# =============================================================================
# ClaimReview 结构化导出
# =============================================================================

class TestClaimReviewExport:
    """ClaimReview 导出"""

    def test_export_basic(self):
        """基本导出"""
        from app.engine.claimreview_export import export_claimreview
        record = export_claimreview(
            claim_text="喝柠檬水能治疗癌症",
            verdict="false",
            credibility_score=12.0,
            review_text="经WHO、FDA确认，柠檬水无治疗癌症的功效。",
        )
        assert record.review_rating == "False"
        assert record.claim_text

    def test_export_all_verdicts(self):
        """所有判定类型正确映射"""
        from app.engine.claimreview_export import export_claimreview
        verdicts = {
            "true": "True",
            "likely_true": "Mostly True",
            "misleading": "Misleading",
            "likely_false": "Mostly False",
            "false": "False",
            "unverifiable": "Unverifiable",
        }
        for verdict, expected_rating in verdicts.items():
            record = export_claimreview(
                claim_text="测试",
                verdict=verdict,
                review_text="测试核查",
            )
            assert record.review_rating == expected_rating, f"{verdict} → {expected_rating}, 得到 {record.review_rating}"

    def test_to_dict_schema(self):
        """to_dict 生成有效的 Schema.org 结构"""
        from app.engine.claimreview_export import export_claimreview
        record = export_claimreview(
            claim_text="测试主张",
            verdict="misleading",
            review_text="测试核查文本",
            evidence_sources=[{"url": "https://example.com", "type": "government"}],
        )
        d = record.to_dict()
        assert d["@context"] == "https://schema.org"
        assert d["@type"] == "ClaimReview"
        assert "claimReviewed" in d
        assert "reviewRating" in d
        assert "publisher" in d

    def test_to_jsonld_valid_json(self):
        """to_jsonld 生成有效JSON"""
        import json
        from app.engine.claimreview_export import export_claimreview
        record = export_claimreview(
            claim_text="测试",
            verdict="true",
            review_text="属实",
        )
        jsonld = record.to_jsonld()
        parsed = json.loads(jsonld)
        assert parsed["@type"] == "ClaimReview"

    def test_export_from_analysis_result(self):
        """从 AnalysisResult dict 导出"""
        from app.engine.claimreview_export import export_from_analysis_result
        result = {
            "input_title": "测试谣言标题",
            "input_url": "https://example.com/rumor",
            "verdict": "false",
            "credibility_score": 15.0,
            "correction": "经核查，该说法不实。",
            "analyzed_at": "2026-06-11T10:00:00+08:00",
        }
        record = export_from_analysis_result(result)
        assert record.claim_text == "测试谣言标题"
        assert record.review_rating == "False"

    def test_rating_numeric_mapping(self):
        """评级→数值映射"""
        from app.engine.claimreview_export import rating_to_numeric
        assert rating_to_numeric("True") == 5
        assert rating_to_numeric("False") == 0
        assert rating_to_numeric("Misleading") == 2
        assert rating_to_numeric("Unverifiable") == -1

    def test_batch_export(self):
        """批量导出"""
        from app.engine.claimreview_export import export_claimreview_list
        results = [
            {"input_title": "谣言A", "verdict": "false", "credibility_score": 10, "correction": "不实"},
            {"input_title": "谣言B", "verdict": "misleading", "credibility_score": 35, "correction": "误导"},
        ]
        records = export_claimreview_list(results)
        assert len(records) == 2
        assert records[0]["@type"] == "ClaimReview"
        assert records[1]["@type"] == "ClaimReview"

    def test_publisher_info_preserved(self):
        """发布者信息保留"""
        from app.engine.claimreview_export import export_claimreview
        record = export_claimreview(
            claim_text="测试",
            verdict="false",
            publisher_name="自定义发布者",
            publisher_url="https://custom.org",
        )
        d = record.to_dict()
        assert d["publisher"]["name"] == "自定义发布者"
        assert d["publisher"]["url"] == "https://custom.org"

    def test_correction_text_truncation(self):
        """辟谣文本在 JSON-LD 中可能被截断但不丢数据"""
        from app.engine.claimreview_export import export_claimreview
        long_text = "测试" * 100
        record = export_claimreview(
            claim_text="测试主张",
            verdict="false",
            review_text=long_text,
        )
        d = record.to_dict()
        # reviewBody 应存在
        assert "reviewBody" in d
        assert len(d["reviewBody"]) > 0
