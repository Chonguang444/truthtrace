"""
JWT 密钥安全性测试 — 验证弱密钥检测逻辑
"""
import pytest


class TestJWTKeyStrength:
    """测试 JWT 密钥强度检测 (_is_weak_key)"""

    def test_rejects_short_key(self):
        """拒绝长度不足32字符的密钥"""
        from app.auth.jwt import _is_weak_key
        assert _is_weak_key("short-key") is True
        assert _is_weak_key("a" * 31) is True

    def test_accepts_strong_key(self):
        """接受强随机密钥"""
        import secrets
        from app.auth.jwt import _is_weak_key
        strong = secrets.token_urlsafe(64)
        assert _is_weak_key(strong) is False

    def test_rejects_dev_pattern_keys(self):
        """拒绝包含 dev 模式的密钥"""
        from app.auth.jwt import _is_weak_key
        assert _is_weak_key("truthtrace-dev-2026-local") is True
        assert _is_weak_key("dev-secret-key-for-testing") is True
        assert _is_weak_key("test-jwt-key-12345678901234567890") is True

    def test_rejects_changeme_placeholder(self):
        """拒绝 changeme 占位符密钥"""
        from app.auth.jwt import _is_weak_key
        assert _is_weak_key("changeme") is True
        assert _is_weak_key("CHANGEME_PLEASE") is True

    def test_rejects_obvious_placeholders(self):
        """拒绝常见占位符模式"""
        from app.auth.jwt import _is_weak_key
        assert _is_weak_key("secret-key-here-12345678901234567890") is True
        assert _is_weak_key("your-secret-goes-here-1234567890") is True
        assert _is_weak_key("please-change-this-in-production") is True

    def test_rejects_toy_keys(self):
        """拒绝玩具密钥"""
        from app.auth.jwt import _is_weak_key
        assert _is_weak_key("12345678901234567890123456789012") is True
        assert _is_weak_key("abcdefghijklmnopqrstuvwxyz12345") is True
        assert _is_weak_key("password123456789012345678901234") is True

    def test_weak_key_raises_runtime_error(self):
        """验证弱密钥导致 RuntimeError — 通过子进程测试模块级守卫"""
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-c", """
import os
os.environ["JWT_SECRET_KEY"] = "truthtrace-dev-2026-weak"
from app.auth import jwt
"""],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode != 0
        assert "弱 JWT 密钥" in result.stderr or "弱 JWT 密钥" in str(result)
