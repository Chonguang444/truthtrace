"""
安全模块测试 — 输入净化/URL验证/CSRF/隐私/CSP/恶意内容检测
"""

import pytest
from fastapi import HTTPException

from app.security import (
    sanitize_input,
    validate_url_safe,
    generate_csrf_token,
    verify_csrf_token,
    detect_malicious_content,
    compute_content_hash,
    content_seen,
    mark_content_seen,
    require_safe_url,
    record_csp_report,
    get_csp_reports,
    clear_csp_reports,
)
from app.security import PrivacyManager, CrawlerSandbox


# =============================================================================
# L1: 输入净化
# =============================================================================

class TestInputSanitization:
    """输入净化和注入检测"""

    def test_normal_input_passes(self):
        result = sanitize_input("正常的搜索关键词")
        assert result == "正常的搜索关键词"

    def test_empty_input_returns_empty(self):
        assert sanitize_input("") == ""

    def test_sql_injection_blocked(self):
        with pytest.raises(HTTPException, match="SQL注入"):
            sanitize_input("1=1 UNION SELECT * FROM users")

    def test_xss_blocked(self):
        with pytest.raises(HTTPException, match="XSS攻击"):
            sanitize_input("<script>alert('xss')</script>")

    def test_command_injection_blocked(self):
        with pytest.raises(HTTPException, match="命令注入"):
            sanitize_input("; rm -rf /")

    def test_path_traversal_blocked(self):
        with pytest.raises(HTTPException, match="路径遍历"):
            sanitize_input("../../../etc/passwd")

    def test_null_byte_blocked(self):
        with pytest.raises(HTTPException, match="非法字符"):
            sanitize_input("hello\x00world")

    def test_input_truncation(self):
        long_input = "A" * 10000
        result = sanitize_input(long_input, max_length=100)
        assert len(result) <= 100

    def test_leading_trailing_whitespace_stripped(self):
        assert sanitize_input("  hello  ") == "hello"


# =============================================================================
# L1: URL 安全验证
# =============================================================================

class TestURLValidation:
    """URL 安全验证 (SSRF 防护)"""

    def test_normal_url_passes(self):
        assert validate_url_safe("https://www.example.com/article") is True

    def test_localhost_blocked(self):
        assert validate_url_safe("http://localhost:8000/admin") is False

    def test_127_blocked(self):
        assert validate_url_safe("http://127.0.0.1/api") is False

    def test_private_ip_blocked(self):
        assert validate_url_safe("http://192.168.1.1/debug") is False

    def test_file_protocol_blocked(self):
        assert validate_url_safe("file:///etc/passwd") is False

    def test_ftp_protocol_blocked(self):
        assert validate_url_safe("ftp://evil.com/malware") is False

    def test_metadata_endpoint_blocked(self):
        assert validate_url_safe("http://metadata.google.internal/computeMetadata/v1") is False

    def test_empty_url_returns_false(self):
        assert validate_url_safe("") is False

    def test_unusual_port_blocked(self):
        assert validate_url_safe("http://example.com:22/ssh-tunnel") is False

    async def test_require_safe_url_dependency_passes(self):
        result = await require_safe_url("https://safe.example.com")
        assert result == "https://safe.example.com"

    async def test_require_safe_url_dependency_blocks(self):
        with pytest.raises(HTTPException, match="URL 不安全"):
            await require_safe_url("http://127.0.0.1/internal")


# =============================================================================
# CSRF 令牌
# =============================================================================

class TestCSRFToken:
    """CSRF 令牌生成和验证"""

    def test_generate_and_verify(self):
        token = generate_csrf_token()
        assert len(token) > 0
        assert verify_csrf_token(token) is True

    def test_invalid_token_fails(self):
        assert verify_csrf_token("invalid-token-12345") is False

    def test_empty_token_fails(self):
        assert verify_csrf_token("") is False

    def test_token_uniqueness(self):
        tokens = [generate_csrf_token() for _ in range(10)]
        assert len(set(tokens)) == 10  # All unique


# =============================================================================
# 恶意内容检测
# =============================================================================

class TestMaliciousContentDetection:
    """恶意内容检测"""

    def test_clean_content_safe(self):
        result = detect_malicious_content("这是正常的内容，没有任何恶意代码。")
        assert result["safe"] is True

    def test_malicious_script_detected(self):
        result = detect_malicious_content(
            '<script src="http://evil.com/malware.exe"></script>'
        )
        assert result["safe"] is False

    def test_hidden_iframe_detected(self):
        result = detect_malicious_content(
            '<iframe src="http://evil.com" style="display:none"></iframe>'
        )
        assert result["indicator_count"] >= 1

    def test_excessive_eval_detected(self):
        content = "eval('x') " * 5
        result = detect_malicious_content(content)
        assert result["indicator_count"] >= 1


# =============================================================================
# 内容指纹
# =============================================================================

class TestContentHash:
    """内容哈希和去重"""

    def test_hash_deterministic(self):
        h1 = compute_content_hash("Title", "Body text")
        h2 = compute_content_hash("Title", "Body text")
        assert h1 == h2

    def test_hash_differs_for_different_content(self):
        h1 = compute_content_hash("Title A", "Body")
        h2 = compute_content_hash("Title B", "Body")
        assert h1 != h2

    def test_hash_whitespace_normalized(self):
        h1 = compute_content_hash("Title", "Body  text")
        h2 = compute_content_hash("Title", "Body text")
        assert h1 == h2  # double space normalized to single

    def test_content_seen_tracking(self):
        h = compute_content_hash("Unique Title", "Unique Body")
        assert content_seen(h) is False
        mark_content_seen(h)
        assert content_seen(h) is True


# =============================================================================
# 隐私
# =============================================================================

class TestPrivacy:
    """隐私合规"""

    def test_ip_anonymization_ipv4(self):
        anon = PrivacyManager.anonymize_ip("192.168.1.100")
        assert anon == "192.168.1.0"

    def test_ip_anonymization_ipv6(self):
        anon = PrivacyManager.anonymize_ip("2001:db8:85a3::8a2e:370:7334")
        assert "0" in anon

    def test_url_redaction_utm_params(self):
        redacted = PrivacyManager.redact_url(
            "https://example.com/page?utm_source=fb&id=123"
        )
        assert "utm_source" not in redacted
        assert "id=123" in redacted  # non-tracking params preserved

    def test_url_redaction_fbclid(self):
        redacted = PrivacyManager.redact_url(
            "https://example.com?fbclid=abc123&ref=share"
        )
        assert "fbclid" not in redacted

    def test_privacy_report_generated(self):
        report = PrivacyManager.generate_privacy_report("user-123")
        assert "data_collected" in report
        assert "data_not_collected" in report
        assert "retention_policy" in report


# =============================================================================
# CSP 违规报告
# =============================================================================

class TestCSPReports:
    """CSP 违规报告收集"""

    def test_record_and_retrieve(self):
        clear_csp_reports()  # start clean
        record_csp_report({
            "blocked-uri": "http://evil.com/xss.js",
            "violated-directive": "script-src 'self'",
        })
        reports = get_csp_reports()
        assert len(reports) == 1
        assert reports[0]["blocked-uri"] == "http://evil.com/xss.js"

    def test_report_limit(self):
        clear_csp_reports()
        for i in range(10):
            record_csp_report({"blocked-uri": f"http://evil{i}.com"})
        reports = get_csp_reports(limit=3)
        assert len(reports) == 3

    def test_clear_reports(self):
        record_csp_report({"blocked-uri": "http://test.com"})
        count = clear_csp_reports()
        assert count >= 1
        assert len(get_csp_reports()) == 0


# =============================================================================
# 爬虫沙箱 URL 验证 (使用 security.CrawlerSandbox)
# =============================================================================

class TestSandboxUrlValidation:
    """SSRF / 内网 / 元数据端点拦截"""

    def test_blocks_private_ip(self):
        assert not validate_url_safe("http://127.0.0.1/admin"), "Should block localhost"
        assert not validate_url_safe("http://192.168.1.1/test"), "Should block 192.168"

    def test_blocks_metadata_endpoint(self):
        assert not validate_url_safe("http://169.254.169.254/latest/meta-data")

    def test_blocks_file_protocol(self):
        assert not validate_url_safe("file:///etc/passwd")

    def test_blocks_empty_url(self):
        assert not validate_url_safe("")

    def test_allows_normal_https(self):
        assert validate_url_safe("https://example.com/article")


# =============================================================================
# 严格逻辑推理测试
# =============================================================================

class TestRigorousLogic:
    """证据等级分类 + 乘法风险模型"""

    def test_classify_none_evidence(self):
        from app.engine.rigorous_logic import classify_evidence_level, EvidenceLevel
        level = classify_evidence_level("某物质致癌", "", "weibo")
        assert level == EvidenceLevel.NONE

    def test_classify_authority_source(self):
        from app.engine.rigorous_logic import classify_evidence_level, EvidenceLevel
        level = classify_evidence_level("添加剂安全", "GB 2760-2024", "national_standard")
        assert level in (EvidenceLevel.STRONG, EvidenceLevel.AUTHORITATIVE, EvidenceLevel.CONVERGENT)

    def test_evidence_authority_above_weak(self):
        from app.engine.rigorous_logic import classify_evidence_level, EvidenceLevel
        level = classify_evidence_level("疫苗安全", "WHO; FDA", "international_consensus")
        assert level.value >= EvidenceLevel.MODERATE.value

    def test_risk_model_returns_tuple(self):
        from app.engine.rigorous_logic import MultiplicativeRiskModel
        result = MultiplicativeRiskModel.compute(
            distortion_count=2, fallacy_count=1,
            evidence_average_level=2.0, causal_chain_count=1,
        )
        assert isinstance(result, tuple), "Should return (score, dict)"

    def test_weak_evidence_lowers_score(self):
        from app.engine.rigorous_logic import MultiplicativeRiskModel
        score1, _ = MultiplicativeRiskModel.compute(
            distortion_count=0, fallacy_count=0, evidence_average_level=6.0, causal_chain_count=0,
        )
        score2, _ = MultiplicativeRiskModel.compute(
            distortion_count=0, fallacy_count=0, evidence_average_level=1.0, causal_chain_count=0,
        )
        assert score2 <= score1, "Weak evidence should not score higher than authoritative"

    def test_media_fraction_parser(self):
        from app.engine.media_verifier import _parse_fraction
        assert abs(_parse_fraction("30000/1001") - 29.97) < 0.1
        assert _parse_fraction("0/1") == 0.0
        assert _parse_fraction("invalid") == 0.0
