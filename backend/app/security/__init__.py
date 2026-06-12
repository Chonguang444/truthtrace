"""
TruthTrace 安全中间件 — 爬虫沙箱/输入净化/CSRF/XSS防护/安全头/隐私合规

这是产品的安全防线。面对恶意攻击时的五层防护:
L1: 输入净化 — 防止注入
L2: 爬虫沙箱 — 隔离恶意网页
L3: 内容过滤 — 检测恶意负载
L4: 安全头 — 浏览器端防护
L5: 隐私合规 — 数据保护
"""

from __future__ import annotations
import re
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("truthtrace.security")

# =============================================================================
# L1: 输入净化与验证
# =============================================================================

# 危险模式 — 检测注入尝试
DANGEROUS_PATTERNS = [
    # SQL 注入
    (r"(?i)(\b(union\s+select|select\s+.*\s+from|insert\s+into|drop\s+table|delete\s+from|1\s*=\s*1)\b)", "SQL注入"),
    # 命令注入
    (r"(?i)(;\s*(cat|rm\s+-rf|wget|curl|bash|sh|cmd|powershell)\b)", "命令注入"),
    # 路径遍历
    (r"(\.\.\/){2,}|(\.\.\\){2,}", "路径遍历"),
    # XSS 基础
    (r"(?i)(<script[\s>]|javascript\s*:|on\w+\s*=\s*[\"'])", "XSS攻击"),
    # 模板注入
    (r"\{\{.*?\}\}|\{%.*?%\}|\$\{.*?\}", "模板注入"),
    # 文件包含
    (r"(?i)((\.\./)+[\w.]+|(file|php|http)://)", "文件包含"),
]

# URL 安全验证
URL_BLACKLIST = [
    "127.0.0.1", "localhost", "0.0.0.0", "::1",
    "10.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
    "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
    "172.30.", "172.31.", "192.168.", "169.254.",
    "metadata.google.internal", "metadata.tencentyun.com",
]


def sanitize_input(value: str, max_length: int = 5000, field_name: str = "input") -> str:
    """
    清洗用户输入 — 检测注入/截断/转义

    原则: 宁可拒绝可疑输入，也不能让恶意数据进入系统。
    """
    if not value:
        return ""

    # 长度检查
    if len(value) > max_length:
        logger.warning(f"输入过长 ({len(value)} > {max_length}): {field_name}")
        value = value[:max_length]

    # 注入检测
    for pattern, attack_type in DANGEROUS_PATTERNS:
        if re.search(pattern, value):
            logger.warning(f"检测到 {attack_type} 尝试: {field_name} = {value[:80]}...")
            raise HTTPException(status_code=400, detail=f"输入包含不安全内容 ({attack_type})")

    # 去除空字节
    if "\x00" in value:
        raise HTTPException(status_code=400, detail="输入包含非法字符")

    return value.strip()


def validate_url_safe(url: str) -> bool:
    """
    验证URL是否安全可爬取。

    阻止:
    - 内网地址 (SSRF 防护)
    - 元数据服务端点
    - file:// 协议
    - 已知恶意域名模式
    """
    if not url:
        return False

    # 协议白名单
    if url.startswith("file://") or url.startswith("ftp://"):
        return False

    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        # 内网检测
        if hostname in URL_BLACKLIST:
            return False
        for blocked in URL_BLACKLIST:
            if hostname.startswith(blocked) or hostname.endswith(".local"):
                return False

        # 端口白名单
        if parsed.port and parsed.port not in (80, 443, 8080, 8000, 3000):
            return False

        return True
    except Exception:
        return False


async def require_safe_url(url: str) -> str:
    """
    FastAPI 依赖: 验证 URL 安全性。

    用法:
        @router.post("/trace")
        async def trace(url: str = Depends(require_safe_url)): ...
    """
    if not validate_url_safe(url):
        raise HTTPException(status_code=400, detail=f"URL 不安全或不被允许: {url[:100]}")
    return url


# =============================================================================
# L2: 爬虫沙箱
# =============================================================================

class CrawlerSandbox:
    """
    爬虫安全沙箱 — 限制爬虫的访问范围和资源消耗

    防护措施:
    1. 请求超时 (30秒)
    2. 响应体大小限制 (10MB)
    3. 禁止内网访问 (SSRF)
    4. 禁止危险协议
    5. 恶意内容类型检测
    6. 重定向链长度限制 (5跳)
    """

    MAX_RESPONSE_SIZE = 10 * 1024 * 1024   # 10MB
    MAX_REDIRECTS = 5                       # 最多跟随5次重定向
    REQUEST_TIMEOUT = 30                    # 30秒超时
    BLOCKED_CONTENT_TYPES = [
        "application/octet-stream",
        "application/x-msdownload",
        "application/x-executable",
        "application/x-msdos-program",
    ]

    async def safe_fetch(self, url: str) -> dict:
        """
        安全地获取URL内容。

        Returns: {"status": "ok", "content": "...", "headers": {...}}
                 或 {"status": "blocked", "reason": "..."}
        """
        if not validate_url_safe(url):
            return {"status": "blocked", "reason": "URL不在允许的范围内 (内网或危险地址)"}

        try:
            import httpx
            async with httpx.AsyncClient(
                timeout=self.REQUEST_TIMEOUT,
                follow_redirects=True,
                max_redirects=self.MAX_REDIRECTS,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            ) as client:
                resp = await client.get(
                    url,
                    headers={"User-Agent": "TruthTrace/2.0 (Information Verification Bot; contact@truthtrace.app)"},
                )

                # 内容类型检查
                content_type = resp.headers.get("content-type", "")
                if any(ct in content_type for ct in self.BLOCKED_CONTENT_TYPES):
                    return {"status": "blocked", "reason": f"不允许的内容类型: {content_type}"}

                # 大小限制
                content = resp.text[:self.MAX_RESPONSE_SIZE] if resp.text else ""

                if len(resp.content) > self.MAX_RESPONSE_SIZE:
                    logger.info(f"响应体过大 ({len(resp.content) // 1024}KB)，已截断至 {self.MAX_RESPONSE_SIZE // 1024}KB")

                return {
                    "status": "ok",
                    "url": str(resp.url),
                    "status_code": resp.status_code,
                    "content_type": content_type,
                    "content": content,
                    "headers": dict(resp.headers),
                }

        except httpx.TimeoutException:
            return {"status": "error", "reason": "请求超时"}
        except httpx.TooManyRedirects:
            return {"status": "blocked", "reason": "重定向次数过多"}
        except httpx.NetworkError as e:
            return {"status": "error", "reason": f"网络错误: {str(e)[:100]}"}
        except Exception as e:
            return {"status": "error", "reason": f"爬取失败: {str(e)[:100]}"}


# =============================================================================
# L3: 恶意内容检测
# =============================================================================

def detect_malicious_content(content: str) -> dict:
    """
    检测爬取到的内容是否包含恶意载荷。

    检测:
    - 恶意脚本注入
    - 钓鱼/诈骗模式
    - 病毒下载链接
    - 可疑重定向代码
    """
    indicators = []

    # 恶意脚本
    if re.search(r'<script[^>]*src\s*=\s*["\'][^"\']*\.(?:exe|dll|bin|sh|bat)["\']', content, re.IGNORECASE):
        indicators.append({"severity": "high", "type": "malicious_script", "desc": "检测到试图加载可执行文件的脚本标签"})

    # 隐藏iframe
    if re.search(r'<iframe[^>]*display\s*:\s*none', content, re.IGNORECASE):
        indicators.append({"severity": "medium", "type": "hidden_iframe", "desc": "检测到隐藏iframe"})

    # 可疑eval
    eval_count = len(re.findall(r'\beval\s*\(', content))
    if eval_count > 3:
        indicators.append({"severity": "medium", "type": "excessive_eval", "desc": f"检测到大量eval调用 ({eval_count}次)"})

    # 钓鱼模式
    phishing_patterns = [
        r"(?i)(urgent|verification required|account suspended|confirm your identity)",
        r"(?i)(click here to.*(?:login|verify|update|confirm))",
    ]
    for pat in phishing_patterns:
        if re.search(pat, content):
            indicators.append({"severity": "medium", "type": "phishing_pattern", "desc": "检测到可能的钓鱼文本模式"})
            break

    return {
        "safe": len([i for i in indicators if i["severity"] == "high"]) == 0,
        "indicator_count": len(indicators),
        "indicators": indicators,
    }


# =============================================================================
# L4: 安全头中间件
# =============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """为所有HTTP响应添加安全头"""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # 安全头
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # HSTS (仅HTTPS — 生产环境由 Nginx 处理，此处保留以防直连)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # CSP (Content-Security-Policy) — 仅对HTML响应
        # 生产环境: 移除 'unsafe-inline' 后使用 nonce 或 hash
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self'; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https: wss:; "
                "font-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "report-uri /api/system/security/csp-report; "
            )

        return response


# =============================================================================
# L5: 隐私合规
# =============================================================================

class PrivacyManager:
    """
    隐私合规管理 — GDPR/个保法基础合规

    原则:
    - 最小数据收集
    - 用户可删除自己的数据
    - 日志中不记录完整IP
    - URL中的个人信息脱敏
    """

    @staticmethod
    def anonymize_ip(ip: str) -> str:
        """IPv4最后8位清零, IPv6最后64位清零"""
        if ":" in ip:
            parts = ip.split(":")
            return ":".join(parts[:4] + ["0"] * (len(parts) - 4))
        parts = ip.split(".")
        return ".".join(parts[:3] + ["0"])

    @staticmethod
    def redact_url(url: str) -> str:
        """移除URL中的敏感参数"""
        from urllib.parse import urlparse, urlunparse
        try:
            parsed = urlparse(url)
            # 移除常见跟踪参数
            track_params = {"utm_source", "utm_medium", "utm_campaign", "fbclid", "gclid", "ref", "share_id"}
            if parsed.query:
                qs_parts = []
                for pair in parsed.query.split("&"):
                    key = pair.split("=")[0] if "=" in pair else pair
                    if key not in track_params:
                        qs_parts.append(pair)
                new_query = "&".join(qs_parts) if qs_parts else ""
                parsed = parsed._replace(query=new_query)
            return urlunparse(parsed)
        except Exception:
            return url

    @staticmethod
    def generate_privacy_report(user_id: str) -> dict:
        """生成用户数据报告"""
        return {
            "data_collected": ["邮箱", "用户名", "收藏的事件", "订阅设置", "提交的反馈"],
            "data_not_collected": ["浏览历史", "精确位置", "设备指纹", "第三方追踪数据"],
            "retention_policy": "用户账号数据持续保留至账号注销。通知记录保留30天。IP日志每24小时匿名化。",
            "deletion_instructions": "登录后在个人中心选择'注销账号'，所有个人数据将在30天内永久删除。",
        }


# =============================================================================
# CSRF 令牌 (支持内存/Redis 双后端)
# =============================================================================

import secrets
import time

_csrf_tokens: dict[str, float] = {}


def _csrf_use_redis() -> bool:
    """检测 Redis 是否可用 — 用于 CSRF 令牌跨进程共享"""
    try:
        from app.config import get_settings
        import redis as _redis
        r = _redis.from_url(get_settings().redis_url, socket_connect_timeout=1)
        r.ping()
        r.close()
        return True
    except Exception:
        return False


def generate_csrf_token() -> str:
    """生成CSRF令牌 (有效期1小时, 优先使用Redis)"""
    token = secrets.token_urlsafe(32)
    if _csrf_use_redis():
        try:
            from app.config import get_settings
            import redis as _redis
            r = _redis.from_url(get_settings().redis_url, socket_connect_timeout=1)
            r.setex(f"csrf:{token}", 3600, "1")
            r.close()
            return token
        except Exception:
            pass  # 回退到内存存储
    _csrf_tokens[token] = time.time()
    # 清理过期token
    expired = [t for t, ts in _csrf_tokens.items() if time.time() - ts > 3600]
    for t in expired:
        del _csrf_tokens[t]
    return token


def verify_csrf_token(token: str) -> bool:
    """验证CSRF令牌 (原子操作，防TOCTOU竞态)"""
    if _csrf_use_redis():
        try:
            from app.config import get_settings
            import redis as _redis
            r = _redis.from_url(get_settings().redis_url, socket_connect_timeout=1)
            # GETDEL — 原子操作: 获取并删除 (Redis 6.2+)
            # 回退: Lua脚本保证原子性
            try:
                exists = r.getdel(f"csrf:{token}")
            except AttributeError:
                # Redis < 6.2 不支持 GETDEL, 使用 Lua 脚本回退
                lua = "local v = redis.call('GET', KEYS[1]); if v then redis.call('DEL', KEYS[1]) end; return v"
                exists = r.eval(lua, 1, f"csrf:{token}")
            r.close()
            return bool(exists)
        except Exception:
            pass  # 回退到内存存储
    # 内存路径: dict.pop 在单进程 asyncio 中是原子的
    ts = _csrf_tokens.pop(token, 0)
    if not ts:
        return False
    if time.time() - ts > 3600:
        return False
    return True


# =============================================================================
# 哈希去重 (用于内容指纹)
# =============================================================================

_content_hashes: set[str] = set()


def content_seen(content_hash: str) -> bool:
    """检查内容是否已经处理过"""
    return content_hash in _content_hashes


def mark_content_seen(content_hash: str):
    """标记内容为已处理"""
    _content_hashes.add(content_hash)
    # 限制内存使用
    if len(_content_hashes) > 100000:
        # 清空一半
        to_remove = list(_content_hashes)[:50000]
        for h in to_remove:
            _content_hashes.discard(h)


def compute_content_hash(title: str, text: str) -> str:
    """计算内容指纹 (用于去重)"""
    normalized = f"{title.strip()[:200]}|{text.strip()[:2000]}".lower()
    # 去除空格和标点差异
    normalized = re.sub(r'\s+', ' ', normalized)
    return hashlib.sha256(normalized.encode()).hexdigest()[:32]


# =============================================================================
# CSP 违规报告收集 (report-uri / report-to)
# =============================================================================

_csp_reports: list[dict] = []


def record_csp_report(report: dict) -> None:
    """记录 CSP 违规报告"""
    report["received_at"] = datetime.now(timezone.utc).isoformat()
    _csp_reports.append(report)
    if len(_csp_reports) > 1000:
        _csp_reports[:] = _csp_reports[-500:]  # 保留最近500条
    logger.warning(
        f"CSP 违规: {report.get('blocked-uri', 'unknown')} — "
        f"{report.get('violated-directive', 'unknown')}"
    )


def get_csp_reports(limit: int = 50) -> list[dict]:
    """获取最近的 CSP 违规报告"""
    return _csp_reports[-limit:]


def clear_csp_reports() -> int:
    """清除 CSP 违规报告"""
    count = len(_csp_reports)
    _csp_reports.clear()
    return count
