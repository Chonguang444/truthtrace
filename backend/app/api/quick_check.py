"""
Quick-Check API — 轻量级虚假信息快速检测端点

给第三方产品/Chrome插件/聊天机器人提供极速检测能力：
- POST /api/quick-check/text — 提交文本，<500ms返回核心判定
- POST /api/quick-check/url — 提交URL，自动抓取+分析
- GET /api/quick-check/stats — 查询用量统计

设计目标：
- 响应速度 <500ms (仅运行确定性引擎)
- 无需认证 (使用IP级限流)
- 返回精简结果：可靠度/失真的具体模式/一句话总结
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, field_validator
from datetime import datetime, timezone
from collections import defaultdict
import time as _time
import re

router = APIRouter()

# =============================================================================
# 请求模型
# =============================================================================

class QuickCheckTextRequest(BaseModel):
    text: str
    title: str = ""

    @field_validator("text")
    @classmethod
    def valid_text(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 10:
            raise ValueError("文本至少10个字符")
        if len(v) > 5000:
            raise ValueError("文本不能超过5000字符")
        return v


class QuickCheckUrlRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def valid_url(cls, v: str) -> str:
        from app.security import validate_url_safe
        if not validate_url_safe(v):
            raise ValueError("URL 不安全或不被允许 (不支持内网/私有IP)")
        return v


# =============================================================================
# IP 级别限流 (轻量级 — 无Redis依赖)
# =============================================================================

_ip_limits: dict[str, list[float]] = defaultdict(list)
_QUICK_CHECK_LIMIT = 30   # 每IP每分钟30次
_QUICK_CHECK_WINDOW = 60

def _check_quick_rate(client_ip: str) -> bool:
    now = _time.time()
    _ip_limits[client_ip] = [
        t for t in _ip_limits[client_ip]
        if now - t < _QUICK_CHECK_WINDOW
    ]
    if len(_ip_limits[client_ip]) >= _QUICK_CHECK_LIMIT:
        return False
    _ip_limits[client_ip].append(now)
    # Cleanup old entries
    if len(_ip_limits) > 5000:
        expired = [
            ip for ip, ts in _ip_limits.items()
            if not ts or now - max(ts) > _QUICK_CHECK_WINDOW * 2
        ]
        for ip in expired:
            del _ip_limits[ip]
    return True


_usage_stats: dict[str, int] = defaultdict(int)  # hourly (capped at 100K entries)

_MAX_USAGE_ENTRIES = 100000

def _record_usage(client_ip: str):
    hour_key = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
    key = f"{client_ip}_{hour_key}"
    _usage_stats[key] += 1
    # Cleanup: purge entries older than 24h when exceeding cap
    if len(_usage_stats) > _MAX_USAGE_ENTRIES:
        current_hour = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H")
        cutoff_prefix = current_hour[:10]  # today's date
        expired = [k for k in _usage_stats if k[-13:-3] < cutoff_prefix]
        for k in expired: del _usage_stats[k]


# =============================================================================
# 快速分析 — 运行确定性引擎 (不调用LLM，不访问外部API)
# =============================================================================

def _quick_analyze(text: str, title: str = "", url: str = "") -> dict:
    """
    快速分析管道：
    仅运行纯Python确定性引擎 (distortion/fallacy/statistical/composite/narrative/causal)
    — 均在<200ms内完成，无网络IO
    """
    # 并行运行多个确定性引擎
    results = {}

    # 1. 失真检测
    try:
        from app.engine.distortion import detect_distortions
        distortion = detect_distortions(text=text, title=title)
        results["distortion"] = {
            "count": len(distortion.matches),
            "matches": [
                {
                    "type": m.abuse_type if hasattr(m, 'abuse_type') else m.description[:30],
                    "description": m.description[:120],
                    "confidence": m.confidence.value if hasattr(m.confidence, 'value') else str(m.confidence),
                    "snippet": (m.evidence_snippet or "")[:100],
                }
                for m in distortion.matches[:5]
            ],
            "overall_risk": distortion.overall_risk.value if hasattr(distortion.overall_risk, 'value') else str(distortion.overall_risk),
        }
    except Exception:
        results["distortion"] = {"count": 0, "matches": [], "overall_risk": "unknown"}

    # 2. 谬误检测
    try:
        from app.engine.fallacy import detect_fallacies
        fallacy = detect_fallacies(text=text, title=title)
        results["fallacy"] = {
            "count": fallacy.fallacy_count if hasattr(fallacy, 'fallacy_count') else len(fallacy.matches),
            "matches": [
                {
                    "type": m.abuse_type if hasattr(m, 'abuse_type') else m.description[:30],
                    "description": m.description[:120],
                    "correction": (getattr(m, 'correction_hint', ''))[:100],
                    "snippet": (m.evidence_snippet or "")[:100],
                }
                for m in fallacy.matches[:5]
            ],
        }
    except Exception:
        results["fallacy"] = {"count": 0, "matches": []}

    # 3. 因果谬误检测 (快速 — 纯正则在 <50ms)
    try:
        from app.engine.causal_graph import extract_causal_claims, detect_causal_fallacies
        claims = extract_causal_claims(text, title)
        fallacies = detect_causal_fallacies(text, claims)
        results["causal"] = {
            "claim_count": len(claims),
            "fallacy_count": len(fallacies),
            "fallacies": [
                {
                    "type": f.fallacy_type,
                    "description": f.description[:120],
                    "severity": f.severity,
                    "snippet": f.evidence_snippet[:100],
                }
                for f in fallacies[:5]
            ],
        }
    except Exception:
        results["causal"] = {"claim_count": 0, "fallacy_count": 0, "fallacies": []}

    # 4. 英文补充检测 (对非中文内容提供英文模式匹配)
    try:
        from app.engine.english_patterns import score_english_misinfo
        # 检测是否主要为英文内容
        ascii_ratio = sum(1 for c in text if c.isascii() and c.isalpha()) / max(1, sum(1 for c in text if c.isalpha()))
        if ascii_ratio > 0.5:
            en_score = score_english_misinfo(text)
            results["english"] = en_score
        else:
            results["english"] = {"risk_score": 0, "matches": [], "match_count": 0, "language": "zh"}
    except Exception:
        results["english"] = {"risk_score": 0, "matches": [], "match_count": 0}

    # 5. 计算快速可信度评分
    risk_components = []

    # 失真风险
    d_count = results["distortion"]["count"]
    if d_count > 0:
        risk_components.append(("distortion", d_count * 12))

    # 谬误风险
    f_count = results["fallacy"]["count"]
    if f_count > 0:
        risk_components.append(("fallacy", f_count * 10))

    # 因果谬误风险
    cf_count = results["causal"]["fallacy_count"]
    if cf_count > 0:
        risk_components.append(("causal_fallacy", cf_count * 15))

    # 情感操纵/恐慌信号 (快速检测)
    fear_signals = len(re.findall(
        r'(?:速看|马上被删|赶快转发|不转不是|太可怕了|不敢想象|毁掉|毒害|扩散|紧急)',
        text
    ))
    if fear_signals > 0:
        risk_components.append(("fear_signals", fear_signals * 8))

    # 绝对化表述
    absolute_count = len(re.findall(
        r'(?:完全|全部|绝对|肯定|100%|一定|必须|从不|永远)',
        text
    ))
    if absolute_count > 2:
        risk_components.append(("absolute_claims", (absolute_count - 2) * 5))

    total_risk = sum(r[1] for r in risk_components)
    # 加上英文检测风险
    en_risk = results.get("english", {}).get("risk_score", 0)
    total_risk += en_risk
    credibility = max(5.0, 100.0 - total_risk)

    # 判定
    if credibility >= 75:
        verdict = "likely_true"
    elif credibility >= 55:
        verdict = "unverifiable"
    elif credibility >= 35:
        verdict = "misleading"
    else:
        verdict = "likely_false"

    # 一句话总结
    summary_parts = []
    if d_count > 2:
        summary_parts.append(f"检测到{d_count}处信息失真信号")
    elif d_count > 0:
        summary_parts.append(f"检测到{d_count}处可疑信息失真")
    if f_count > 2:
        summary_parts.append(f"{f_count}处逻辑谬误")
    elif f_count > 0:
        summary_parts.append(f"存在{f_count}处潜在逻辑问题")
    if cf_count > 0:
        summary_parts.append(f"{cf_count}处因果谬误")
    if fear_signals > 1:
        summary_parts.append("含情感操纵信号")

    if not summary_parts:
        summary_parts.append("未检测到明显的信息操纵信号")
    summary = "；".join(summary_parts) + "。"

    return {
        "credibility_score": round(credibility, 1),
        "verdict": verdict,
        "summary": summary,
        "risk_signals": risk_components,
        "analysis": results,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "method": "Quick-Check (纯确定性引擎, 无LLM, 无外部API)",
        "disclaimer": "此分析基于文本模式自动匹配，不构成事实判定。详细分析请使用完整溯源引擎。",
    }


# =============================================================================
# 端点
# =============================================================================

@router.post("/quick-check/text")
async def quick_check_text(req: QuickCheckTextRequest, request: Request):
    """
    轻量级文本快速检测

    对提交的文本运行确定性引擎（失真/谬误/因果谬误/情感信号），
    返回精简的可靠度评分和关键发现。

    **无需认证** · IP限流 30次/分钟
    """
    client_ip = request.client.host if request.client else "unknown"

    if not _check_quick_rate(client_ip):
        raise HTTPException(429, "请求过于频繁 (30次/分钟)。请稍后重试或注册API获取更高配额。")

    _record_usage(client_ip)

    result = _quick_analyze(text=req.text, title=req.title)

    result["input"] = {
        "type": "text",
        "length": len(req.text),
        "title": req.title,
    }

    return result


@router.post("/quick-check/url")
async def quick_check_url(req: QuickCheckUrlRequest, request: Request):
    """
    轻量级 URL 快速检测

    抓取URL内容（10秒超时），提取标题+正文后运行快速分析管道。
    适合浏览器插件、聊天机器人等场景。

    **无需认证** · IP限流 30次/分钟
    """
    client_ip = request.client.host if request.client else "unknown"

    if not _check_quick_rate(client_ip):
        raise HTTPException(429, "请求过于频繁 (30次/分钟)。请稍后重试或注册API获取更高配额。")

    _record_usage(client_ip)

    # 抓取URL内容
    fetch_error = None
    title = ""
    text = ""

    try:
        from app.security import CrawlerSandbox
        sandbox = CrawlerSandbox()
        fetch_result = await sandbox.safe_fetch(req.url)

        if fetch_result["status"] == "ok":
            raw_content = fetch_result.get("content", "")
            # 提取标题
            import re as _re
            title_match = _re.search(r'<title[^>]*>(.*?)</title>', raw_content, _re.IGNORECASE)
            if title_match:
                title = title_match.group(1).strip()[:200]

            # 提取正文 (简化版)
            # 去除 script/style 标签
            cleaned = _re.sub(r'<script[^>]*>.*?</script>', '', raw_content, flags=_re.IGNORECASE | _re.DOTALL)
            cleaned = _re.sub(r'<style[^>]*>.*?</style>', '', cleaned, flags=_re.IGNORECASE | _re.DOTALL)
            # 去除HTML标签
            cleaned = _re.sub(r'<[^>]+>', ' ', cleaned)
            # 规范化空白
            cleaned = _re.sub(r'\s+', ' ', cleaned).strip()
            text = cleaned[:5000]
        else:
            fetch_error = fetch_result.get("reason", "URL抓取失败")
    except Exception as e:
        fetch_error = f"抓取异常: {str(e)[:100]}"

    if fetch_error and not text:
        raise HTTPException(400, f"无法获取URL内容: {fetch_error}")

    result = _quick_analyze(text=text, title=title, url=req.url)

    result["input"] = {
        "type": "url",
        "url": req.url,
        "title": title,
        "text_length": len(text),
        "fetch_error": fetch_error,
    }

    return result


@router.get("/quick-check/stats")
async def quick_check_stats(request: Request):
    """查询当前IP的用量统计"""
    client_ip = request.client.host if request.client else "unknown"

    now = _time.time()
    recent_count = len([
        t for t in _ip_limits.get(client_ip, [])
        if now - t < 60
    ])

    return {
        "client_ip": f"{client_ip[:4]}****",
        "requests_last_minute": recent_count,
        "limit_per_minute": _QUICK_CHECK_LIMIT,
        "remaining": max(0, _QUICK_CHECK_LIMIT - recent_count),
        "total_ips_tracked": len(_ip_limits),
    }


@router.get("/quick-check/health")
async def quick_check_health():
    """Quick-Check 服务健康检查"""
    return {
        "status": "ok",
        "endpoints": [
            "POST /api/quick-check/text",
            "POST /api/quick-check/url",
            "GET /api/quick-check/stats",
            "GET /api/quick-check/health",
        ],
        "limits": f"{_QUICK_CHECK_LIMIT}/min per IP",
        "engines": ["distortion", "fallacy", "causal_graph"],
    }
