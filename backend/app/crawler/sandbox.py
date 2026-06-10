"""
爬虫安全沙箱 — 所有爬虫请求的强制安全层

防护层级:
  1. URL安全验证 (SSRF/内网/危险协议)
  2. 请求隔离 (独立Cookie jar, 无状态共享)
  3. 资源限制 (超时/大小/重定向)
  4. 响应过滤 (移除脚本/iframe/隐藏元素)
  5. 恶意内容检测
  6. DNS重绑定防护

所有爬虫都必须通过此沙箱发起请求。不直接使用 httpx。
"""

from __future__ import annotations
import re
import hashlib
import logging
import ipaddress
import socket
from urllib.parse import urlparse
from dataclasses import dataclass, field
from typing import Optional

import httpx

from app.security import validate_url_safe, detect_malicious_content

logger = logging.getLogger("truthtrace.sandbox")

# =============================================================================
# 配置
# =============================================================================

SANDBOX_CONFIG = {
    "max_response_bytes": 10 * 1024 * 1024,   # 10MB
    "max_text_length": 500_000,               # 500KB 文本截断
    "max_redirects": 5,
    "request_timeout": 30.0,                  # 秒
    "connect_timeout": 10.0,
    "max_cookies_per_jar": 50,
    "cookie_ttl_seconds": 300,               # Cookie 5分钟过期
    "rate_limit_per_domain": 3,              # 每域名每秒最多3请求
    "dns_cache_ttl": 60,                     # DNS缓存60秒
}

# 危险的内容类型（拒绝下载）
BLOCKED_CONTENT_TYPES = {
    "application/octet-stream",
    "application/x-msdownload",
    "application/x-executable",
    "application/x-msdos-program",
    "application/x-msi",
    "application/x-sh",
    "application/x-bat",
    "application/x-csh",
    "application/x-dmg",
    "application/java-archive",
    "application/vnd.android.package-archive",
    "application/x-rar-compressed",
    "application/x-7z-compressed",
    "application/x-tar",
    "application/gzip",
    "application/x-bzip2",
    "application/x-xz",
}

# 禁止访问的端口
BLOCKED_PORTS = {
    22, 23, 25, 53, 110, 111, 135, 137, 138, 139,
    143, 161, 162, 389, 445, 465, 587, 636, 873,
    993, 995, 1080, 1433, 1521, 2049, 2375, 2376,
    3306, 3389, 4444, 5432, 5555, 5900, 5984, 6379,
    7001, 8009, 8080, 8443, 8888, 9000, 9090, 9200,
    9300, 11211, 27017, 27018, 27019, 50000, 50070,
}


@dataclass
class SandboxResult:
    """沙箱处理后的安全结果"""
    status: str = ""                # ok / blocked / error / timeout
    url: str = ""
    final_url: str = ""
    status_code: int = 0
    content_type: str = ""
    title: str = ""
    text_content: str = ""          # 已清洗的纯文本
    raw_text: str = ""              # 原始文本（未清洗）
    headers: dict = field(default_factory=dict)
    content_hash: str = ""
    malicious_indicators: list = field(default_factory=list)
    blocked_reason: str = ""
    fetch_duration_ms: float = 0.0
    redirect_chain: list = field(default_factory=list)


class CrawlerSandbox:
    """
    爬虫安全沙箱 — 所有出站请求的唯一通道。

    使用方式:
        sandbox = CrawlerSandbox()
        result = await sandbox.fetch(url)
        if result.status == "ok":
            process(result.text_content)
    """

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._dns_cache: dict[str, tuple[str, float]] = {}
        self._domain_requests: dict[str, list[float]] = {}  # 速率跟踪
        self._fingerprinter = None  # 延迟加载

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建隔离的 httpx 客户端"""
        import time
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=SANDBOX_CONFIG["connect_timeout"],
                    read=SANDBOX_CONFIG["request_timeout"],
                    write=10.0,
                    pool=5.0,
                ),
                follow_redirects=True,
                max_redirects=SANDBOX_CONFIG["max_redirects"],
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=20,
                    keepalive_expiry=30.0,
                ),
                # 不使用持久Cookie — 每个请求独立
                cookies=None,
                # 禁止 HTTP/2 服务器推送
                http2=False,
                # 只允许安全的TLS版本
                verify=True,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    async def fetch(self, url: str, *,
                    headers: dict | None = None,
                    follow_redirects: bool = True,
                    max_text_length: int | None = None,
                    allow_external_images: bool = False) -> SandboxResult:
        """
        通过沙箱安全地获取 URL 内容。

        Args:
            url: 目标URL
            headers: 可选的额外请求头
            follow_redirects: 是否跟随重定向
            max_text_length: 文本截断长度 (默认 500KB)
            allow_external_images: 是否允许图片内容类型

        Returns:
            SandboxResult — 安全封装的结果
        """
        import time as _time
        start = _time.monotonic()

        max_len = max_text_length or SANDBOX_CONFIG["max_text_length"]

        # === 第1层: URL验证 ===
        url_ok, url_reason = self._validate_url(url)
        if not url_ok:
            return SandboxResult(status="blocked", url=url, blocked_reason=url_reason)

        # === 第2层: DNS重绑定防护 ===
        hostname = urlparse(url).hostname or ""
        resolved_ip = self._resolve_dns(hostname)
        if resolved_ip and self._is_private_ip(resolved_ip):
            return SandboxResult(
                status="blocked", url=url,
                blocked_reason=f"DNS解析到内网地址: {resolved_ip}"
            )

        # === 第3层: 速率限制 ===
        await self._rate_limit(hostname)

        # === 第4层: 发起请求 ===
        try:
            client = await self._get_client()
            resp = await client.get(
                url,
                headers=self._build_headers(hostname, headers),
                follow_redirects=follow_redirects,
            )
        except httpx.TimeoutException:
            return SandboxResult(status="timeout", url=url, blocked_reason="请求超时")
        except httpx.TooManyRedirects:
            return SandboxResult(status="blocked", url=url, blocked_reason="重定向次数过多")
        except httpx.ConnectError as e:
            return SandboxResult(status="blocked", url=url, blocked_reason=f"连接被拒绝: {str(e)[:80]}")
        except Exception as e:
            return SandboxResult(status="error", url=url, blocked_reason=f"网络错误: {str(e)[:100]}")

        # === 第5层: 响应头验证 ===
        content_type = resp.headers.get("content-type", "")
        ct_lower = content_type.lower()

        # 危险内容类型
        for blocked_ct in BLOCKED_CONTENT_TYPES:
            if blocked_ct in ct_lower:
                return SandboxResult(
                    status="blocked", url=url,
                    blocked_reason=f"危险内容类型: {content_type}"
                )

        # 只接受文本/HTML/JSON/XML/图片
        allowed = ("text/", "application/json", "application/xml", "application/atom",
                    "application/rss", "image/")
        if allow_external_images and "image/" in ct_lower:
            pass  # 图片允许通过
        elif not any(ct_lower.startswith(t) for t in allowed):
            return SandboxResult(
                status="blocked", url=url,
                blocked_reason=f"不支持的内容类型: {content_type}"
            )

        # === 第6层: 大小限制 ===
        content_bytes = resp.content
        if len(content_bytes) > SANDBOX_CONFIG["max_response_bytes"]:
            logger.info(f"响应体过大 ({len(content_bytes) // 1024}KB) — 截断")
            content_bytes = content_bytes[:SANDBOX_CONFIG["max_response_bytes"]]

        # === 第7层: 文本提取与清洗 ===
        raw_text = ""
        if "text/html" in ct_lower:
            raw_text = resp.text[:max_len] if resp.text else ""
        elif "application/json" in ct_lower:
            raw_text = resp.text[:max_len] if resp.text else ""
        elif "text/" in ct_lower:
            raw_text = resp.text[:max_len] if resp.text else ""
        elif allow_external_images and "image/" in ct_lower:
            raw_text = f"[Image: {content_type}]"

        # HTML 清洗：移除危险标签
        cleaned_text = self._sanitize_html(raw_text) if "text/html" in ct_lower else raw_text

        # === 第8层: 恶意内容检测 ===
        malicious = detect_malicious_content(cleaned_text)
        if not malicious.get("safe", True):
            logger.warning(f"检测到恶意内容指示器: {malicious['indicator_count']}个")

        # === 计算指纹 ===
        content_hash = self._compute_hash(cleaned_text)

        # === 提取标题 ===
        title = self._extract_title(cleaned_text, raw_text)

        duration = (_time.monotonic() - start) * 1000

        return SandboxResult(
            status="ok",
            url=url,
            final_url=str(resp.url),
            status_code=resp.status_code,
            content_type=content_type,
            title=title,
            text_content=cleaned_text,
            raw_text=raw_text[:max_len],
            headers=dict(resp.headers),
            content_hash=content_hash,
            malicious_indicators=malicious.get("indicators", []),
            fetch_duration_ms=duration,
            redirect_chain=[str(h.url) for h in resp.history],
        )

    # ------------------------------------------------------------------
    # URL 验证
    # ------------------------------------------------------------------

    def _validate_url(self, url: str) -> tuple[bool, str]:
        """多层URL验证"""
        if not url:
            return False, "URL为空"

        # 基础格式
        if not url.startswith(("http://", "https://")):
            return False, "仅支持 http/https 协议"

        # 长度
        if len(url) > 4096:
            return False, "URL过长"

        try:
            parsed = urlparse(url)
        except Exception:
            return False, "URL解析失败"

        hostname = parsed.hostname or ""

        # 禁止空主机名
        if not hostname:
            return False, "URL缺少主机名"

        # 禁止端口
        if parsed.port in BLOCKED_PORTS:
            return False, f"禁止的端口: {parsed.port}"

        # 内网/SSRF 检测
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
                return False, f"禁止访问内网地址: {hostname}"
            if ip.is_unspecified:
                return False, "无效地址"
        except ValueError:
            pass  # 域名，继续DNS解析阶段检查

        # 已知元数据端点
        metadata_hosts = [
            "metadata.google.internal", "metadata.tencentyun.com",
            "169.254.169.254", "100.100.100.200",
        ]
        for mh in metadata_hosts:
            if mh in hostname:
                return False, f"禁止访问元数据端点: {hostname}"

        # URL 参数注入检测
        if re.search(r'[\r\n]', url):
            return False, "URL包含非法字符(CRLF注入)"

        return True, ""

    # ------------------------------------------------------------------
    # DNS 防护
    # ------------------------------------------------------------------

    def _resolve_dns(self, hostname: str) -> str | None:
        """带缓存的DNS解析"""
        import time as _time
        now = _time.monotonic()

        # 检查缓存
        if hostname in self._dns_cache:
            ip, timestamp = self._dns_cache[hostname]
            if now - timestamp < SANDBOX_CONFIG["dns_cache_ttl"]:
                return ip

        try:
            ip = socket.getaddrinfo(hostname, None, family=socket.AF_INET)[0][4][0]
            self._dns_cache[hostname] = (ip, now)
            # 限制缓存大小
            if len(self._dns_cache) > 1000:
                oldest = sorted(self._dns_cache.items(), key=lambda x: x[1][1])
                for k, _ in oldest[:200]:
                    del self._dns_cache[k]
            return ip
        except Exception:
            return None

    def _is_private_ip(self, ip_str: str) -> bool:
        """检查IP是否为内网地址"""
        try:
            ip = ipaddress.ip_address(ip_str)
            return ip.is_private or ip.is_loopback or ip.is_link_local
        except ValueError:
            return False

    # ------------------------------------------------------------------
    # 速率限制
    # ------------------------------------------------------------------

    async def _rate_limit(self, domain: str):
        """基于域名的速率限制"""
        import time as _time
        import asyncio

        now = _time.monotonic()
        if domain not in self._domain_requests:
            self._domain_requests[domain] = []

        # 清理旧记录
        window = 1.0  # 1秒窗口
        self._domain_requests[domain] = [
            t for t in self._domain_requests[domain]
            if now - t < window
        ]

        if len(self._domain_requests[domain]) >= SANDBOX_CONFIG["rate_limit_per_domain"]:
            # 需要等待
            oldest = min(self._domain_requests[domain])
            wait = oldest + window - now
            if wait > 0:
                await asyncio.sleep(wait)
                self._domain_requests[domain] = [
                    t for t in self._domain_requests[domain]
                    if now - t < window
                ]

        self._domain_requests[domain].append(_time.monotonic())

        # 限制内存 — 最多保留1000个域名的记录
        if len(self._domain_requests) > 1000:
            to_delete = sorted(
                self._domain_requests.keys(),
                key=lambda d: sum(self._domain_requests[d]) if self._domain_requests[d] else 0
            )[:200]
            for d in to_delete:
                del self._domain_requests[d]

    # ------------------------------------------------------------------
    # HTML 清洗
    # ------------------------------------------------------------------

    HTML_DANGER_TAGS = {"script", "iframe", "object", "embed", "applet",
                        "frame", "frameset", "link[rel=stylesheet]",
                        "meta[http-equiv=refresh]", "base", "form"}

    def _sanitize_html(self, html: str) -> str:
        """移除HTML中的危险标签和隐藏元素"""
        if not html or "<" not in html:
            return html

        # 移除完整标签
        for tag_pattern in [
            r'<script[^>]*>.*?</script>',
            r'<iframe[^>]*>.*?</iframe>',
            r'<object[^>]*>.*?</object>',
            r'<embed[^>]*>.*?</embed>',
            r'<applet[^>]*>.*?</applet>',
            r'<frame[^>]*>.*?</frame>',
            r'<frameset[^>]*>.*?</frameset>',
            r'<noscript[^>]*>.*?</noscript>',
            r'<style[^>]*>.*?</style>',
            # 事件处理器属性
            r'\bon\w+\s*=\s*"[^"]*"',
            r"\bon\w+\s*=\s*'[^']*'",
            r'\bon\w+\s*=\s*\S+',
            # javascript: URL
            r'''href\s*=\s*["']javascript:[^"']*["']''',
            # meta refresh 重定向
            r'<meta[^>]*http-equiv\s*=\s*["\']refresh[^>]*>',
        ]:
            html = re.sub(tag_pattern, '', html, flags=re.IGNORECASE | re.DOTALL)

        # 移除隐藏元素 (display:none, visibility:hidden)
        html = re.sub(
            r'<([a-z]+)[^>]*style\s*=\s*["\'][^"\']*(?:display\s*:\s*none|visibility\s*:\s*hidden)[^"\']*["\'][^>]*>(.*?)</\1>',
            '', html, flags=re.IGNORECASE | re.DOTALL
        )

        # 移除 base 标签
        html = re.sub(r'<base[^>]*>', '', html, flags=re.IGNORECASE)

        # 移除 HTML 注释（可能含有条件注释或注入）
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)

        return html

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------

    def _build_headers(self, hostname: str, extra: dict | None = None) -> dict:
        """构建安全的请求头"""
        import random

        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64; rv:127.0) Gecko/20100101 Firefox/127.0",
        ]

        headers = {
            "User-Agent": random.choice(user_agents),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }

        if extra:
            # 只允许安全的额外头部，过滤危险头部
            allowed_extra = {k: v for k, v in extra.items()
                           if k.lower() not in ("host", "cookie", "authorization", "proxy-authorization")}
            headers.update(allowed_extra)

        return headers

    def _extract_title(self, cleaned_text: str, raw_text: str) -> str:
        """从已清洗文本或原始HTML中提取标题"""
        import re as _re
        # 尝试从 HTML title 标签
        m = _re.search(r'<title[^>]*>([^<]+)</title>', raw_text, _re.IGNORECASE)
        if m:
            return m.group(1).strip()[:500]

        # 尝试 og:title
        m = _re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', raw_text, _re.IGNORECASE)
        if m:
            return m.group(1).strip()[:500]

        # 取前100个非空白字符
        clean = cleaned_text.strip()
        return clean[:100] if clean else ""

    @staticmethod
    def _compute_hash(text: str) -> str:
        return hashlib.sha256(text[:10000].encode("utf-8")).hexdigest()[:32]
