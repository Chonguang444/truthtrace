"""
系统管理 API — 安全/质量/进化/回归测试/隐私
"""

from fastapi import APIRouter, Query, HTTPException
from datetime import datetime

router = APIRouter()

# =========================================================================
# 错误修复
# =========================================================================
import sqlite3
try:
    conn = sqlite3.connect("E:/C++/truthtrace/truthtrace_local.db")
    conn.execute("ALTER TABLE events ADD COLUMN engine_analysis TEXT")
    conn.commit()
    conn.close()
except Exception:
    pass

# =============================================================================
# 安全端点
# =============================================================================

@router.get("/system/security/status")
async def security_status():
    """安全系统状态"""
    from app.security import _csrf_tokens, _content_hashes
    return {
        "input_sanitization": "active",
        "csrf_protection": "active",
        "content_header_security": "active",
        "crawler_sandbox": "active",
        "content_dedup": "active",
        "privacy_compliance": "active",
        "active_csrf_tokens": len(_csrf_tokens),
        "content_hashes_tracked": len(_content_hashes),
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/system/privacy/report/{user_id}")
async def privacy_report(user_id: str):
    """用户数据隐私报告"""
    from app.security import PrivacyManager
    return PrivacyManager.generate_privacy_report(user_id)


# =============================================================================
# 质量端点
# =============================================================================

@router.get("/system/quality/metrics")
async def quality_metrics():
    """当前质量指标"""
    from app.quality import get_quality_monitor
    monitor = get_quality_monitor()
    snapshot = monitor.snapshot()
    anomalies = monitor.check_anomalies()
    return {
        "metrics": {
            "total_analyses": snapshot.total_analyses,
            "high_risk_count": snapshot.high_risk_count,
            "low_risk_count": snapshot.low_risk_count,
            "disputed_count": snapshot.disputed_count,
            "avg_credibility_score": round(snapshot.avg_credibility_score, 1),
            "duplicate_detected": snapshot.duplicate_detected_today,
            "content_rejected": snapshot.content_rejected_today,
        },
        "anomalies": anomalies,
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/system/quality/check-source")
async def check_source_quality(url: str = Query(..., description="要检测的URL")):
    """检查来源质量"""
    from app.security import validate_url_safe
    from app.quality import SourceQualityEvaluator
    is_safe = validate_url_safe(url)
    if not is_safe:
        return {"url": url, "safe": False, "reason": "URL不在安全范围内"}
    quality = SourceQualityEvaluator.evaluate(url)
    return {"url": url, "safe": True, **quality}


# =============================================================================
# 进化/回归测试端点
# =============================================================================

@router.post("/system/evolution/regression-test")
async def run_regression_tests_endpoint():
    """运行回归测试"""
    from app.evolution import run_regression_tests
    result = await run_regression_tests()
    return result


@router.get("/system/evolution/rule-history")
async def rule_change_history(module: str | None = Query(None)):
    """规则变更历史"""
    from app.evolution import get_rule_version_manager
    mgr = get_rule_version_manager()
    history = mgr.get_history(module)
    return {
        "total_changes": len(history),
        "current_versions": mgr.get_current_versions(),
        "history": [
            {"module": v.module, "rule_id": v.rule_id, "version": v.version,
             "reason": v.change_reason, "changed_by": v.changed_by,
             "at": v.created_at.isoformat()}
            for v in history[-50:]
        ],
    }


@router.get("/system/evolution/misjudgment-patterns")
async def list_misjudgment_patterns():
    """活跃的误判模式"""
    from app.evolution import get_misjudgment_detector
    detector = get_misjudgment_detector()
    patterns = detector.get_active_patterns()
    return {"patterns": [p.to_dict() for p in patterns], "count": len(patterns)}


@router.post("/system/evolution/misjudgment/{pattern_id}/resolve")
async def resolve_misjudgment(pattern_id: str, resolution: str = Query("")):
    """标记误判模式为已解决"""
    from app.evolution import get_misjudgment_detector
    detector = get_misjudgment_detector()
    detector.resolve(pattern_id, resolution)
    return {"status": "resolved"}


@router.get("/system/evolution/knowledge-expiry")
async def check_knowledge_expiry():
    """检查知识库条目的时效性"""
    from app.evolution import get_knowledge_expiry_manager
    mgr = get_knowledge_expiry_manager()
    expired = mgr.check_expiry()
    return {"expired_entries": expired, "count": len(expired)}


# =============================================================================
# 蜜罐端点 (用于入侵检测 — 正常用户不应访问)
# =============================================================================

@router.get("/admin/login")
async def honeypot_admin_login():
    """⚠ 蜜罐端点 — 访问即记录"""
    import logging
    logging.getLogger("truthtrace.security").warning("蜜罐被触发: /admin/login")
    return {"message": "Unauthorized"}


@router.get("/api/internal/debug")
async def honeypot_debug():
    """⚠ 蜜罐端点 — 访问即记录"""
    import logging
    logging.getLogger("truthtrace.security").warning("蜜罐被触发: /api/internal/debug")
    return {"message": "Not Found"}
