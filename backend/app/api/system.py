"""
系统管理 API — 安全/质量/进化/回归测试/隐私
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from datetime import datetime, timezone

from app.auth.jwt import get_current_active_user, get_admin_user
from app.models.user import User

router = APIRouter()

# =============================================================================
# 安全端点
# =============================================================================

@router.get("/system/security/status")
async def security_status(
    current_user: User = Depends(get_admin_user),
):
    """安全系统状态 (仅管理员)"""
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/system/privacy/report")
async def privacy_report(
    current_user: User = Depends(get_current_active_user),
):
    """当前用户数据隐私报告 (需认证)"""
    from app.security import PrivacyManager
    return PrivacyManager.generate_privacy_report(str(current_user.id))


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
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/system/quality/dashboard")
async def quality_dashboard():
    """
    综合质量仪表盘 — 聚合质量监控+演化校准+反馈统计+去重+知识健康

    返回结构:
      - overview: 关键数字摘要
      - engine_health: 各引擎模块评分分布
      - feedback_trends: 反馈趋势统计
      - calibration: 校准器状态
      - misjudgment: 活跃误判模式
      - dedup_status: 去重系统状态
      - knowledge_health: 知识库时效性
      - anomalies: 检测到的异常
    """
    result = {
        "overview": {},
        "engine_health": {},
        "feedback_trends": {},
        "calibration": {},
        "misjudgment": {},
        "dedup_status": {},
        "knowledge_health": {},
        "anomalies": [],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # 1. 质量监控
    from app.quality import get_quality_monitor
    monitor = get_quality_monitor()
    snapshot = monitor.snapshot()
    anomalies = monitor.check_anomalies()
    total = max(snapshot.total_analyses, 1)

    result["overview"] = {
        "total_analyses": snapshot.total_analyses,
        "credibility_avg": round(snapshot.avg_credibility_score, 1),
        "high_risk_pct": round(snapshot.high_risk_count / total * 100, 1),
        "low_risk_pct": round(snapshot.low_risk_count / total * 100, 1),
        "dispute_rate": round(snapshot.disputed_count / total * 100, 1),
        "duplicates_blocked": snapshot.duplicate_detected_today,
        "content_rejected": snapshot.content_rejected_today,
    }
    result["anomalies"] = [a.get("message", "") for a in anomalies] if anomalies else []

    # 2. 校准器状态
    from app.evolution.calibrator import get_calibrator
    calibrator = get_calibrator()
    c_snap = calibrator.snapshot()
    result["calibration"] = {
        "tracked_events": c_snap.total_events,
        "estimated_accuracy": c_snap.feedback_accuracy,
        "avg_score": c_snap.avg_score,
        "score_std": c_snap.score_std,
        "dispute_rate": round(c_snap.disputed_rate * 100, 1),
        "current_weights": c_snap.weights.to_dict(),
        "data_quality": "adequate" if c_snap.total_events >= 100 else "gathering",
    }

    # 3. 引擎健康 — 基于校准权重反映各引擎是否正常
    w = c_snap.weights
    engine_modules = [
        ("失真检测", w.distortion_weight, 0.5, 1.5),
        ("逻辑谬误", w.fallacy_weight, 0.5, 1.5),
        ("统计滥用", w.statistical_weight, 0.5, 1.5),
        ("拼接式造谣", w.composite_weight, 0.5, 1.5),
        ("叙事框架", w.narrative_weight, 0.5, 1.5),
        ("模态漂移", w.drift_weight, 0.5, 1.5),
    ]
    result["engine_health"] = {
        "modules": [
            {
                "name": name,
                "weight": weight,
                "healthy": min_val <= weight <= max_val,
                "deviation": round(abs(weight - 1.0), 2),
                "trend": "normal" if min_val <= weight <= max_val else ("dampened" if weight < 1.0 else "amplified"),
            }
            for name, weight, min_val, max_val in engine_modules
        ]
    }

    # 4. 反馈趋势
    from app.api.feedback import _feedback_store, _appeal_store
    feedback_list = [fb for feeds in _feedback_store.values() for fb in feeds]
    inaccurate = [fb for fb in feedback_list if fb.get("rating") == "inaccurate"]
    helpful = [fb for fb in feedback_list if fb.get("rating") == "helpful"]
    result["feedback_trends"] = {
        "total_feedback": len(feedback_list),
        "inaccurate_count": len(inaccurate),
        "helpful_count": len(helpful),
        "not_helpful_count": sum(1 for fb in feedback_list if fb.get("rating") == "not_helpful"),
        "total_appeals": len(_appeal_store),
        "pending_appeals": sum(1 for a in _appeal_store if a.get("status") == "pending"),
        "appeal_acceptance_rate": round(
            sum(1 for a in _appeal_store if a.get("status") == "accepted") / max(1, len(_appeal_store)) * 100, 1
        ),
    }

    # 5. 误判模式
    from app.evolution import get_misjudgment_detector
    detector = get_misjudgment_detector()
    active = detector.get_active_patterns()
    result["misjudgment"] = {
        "active_patterns": len(active),
        "patterns": [p.to_dict() for p in active[:5]],
        "total_discovered": len(active),  # includes resolved
    }

    # 6. 去重状态
    try:
        from app.analyzer.dedup import get_dedup
        dedup = get_dedup()
        result["dedup_status"] = dedup.stats()
    except ImportError:
        result["dedup_status"] = {"status": "unavailable"}

    # 7. 知识库健康
    from app.evolution import get_knowledge_expiry_manager
    expiry_mgr = get_knowledge_expiry_manager()
    expired = expiry_mgr.check_expiry()
    result["knowledge_health"] = {
        "entries_needing_review": len(expired),
        "entries": expired[:5],
    }

    # 8. 反馈闭环状态
    try:
        from app.evolution.feedback_loop import get_feedback_loop
        loop = get_feedback_loop()
        result["feedback_loop"] = loop.status()
    except ImportError:
        result["feedback_loop"] = {"status": "unavailable"}

    return result


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
# CSP 违规报告收集
# =============================================================================

@router.post("/system/security/csp-report")
async def csp_report_endpoint(report: dict):
    """接收浏览器 CSP 违规报告 (report-uri)"""
    from app.security import record_csp_report
    record_csp_report(report.get("csp-report", report))
    return {"status": "recorded"}


@router.get("/system/security/csp-reports")
async def get_csp_reports_endpoint(
    current_user: User = Depends(get_admin_user),
):
    """获取最近的 CSP 违规报告 (仅管理员)"""
    from app.security import get_csp_reports
    return {"reports": get_csp_reports()}


# =============================================================================
# Prometheus 指标端点
# =============================================================================

_metrics_start_time = datetime.now(timezone.utc)

@router.get("/system/metrics")
async def prometheus_metrics():
    """Prometheus-compatible metrics endpoint"""
    from app.quality import get_quality_monitor
    from app.analyzer.dedup import get_dedup

    monitor = get_quality_monitor()
    snap = monitor.snapshot()
    dedup = get_dedup()

    lines = [
        "# HELP truthtrace_analyses_total Total number of analyses performed",
        "# TYPE truthtrace_analyses_total counter",
        f"truthtrace_analyses_total {snap.total_analyses}",
        "",
        "# HELP truthtrace_analyses_disputed Total disputed analyses",
        "# TYPE truthtrace_analyses_disputed counter",
        f"truthtrace_analyses_disputed {snap.disputed_count}",
        "",
        "# HELP truthtrace_credibility_avg Average credibility score",
        "# TYPE truthtrace_credibility_avg gauge",
        f"truthtrace_credibility_avg {snap.avg_credibility_score:.1f}",
        "",
        "# HELP truthtrace_duplicates_blocked Content duplicates blocked",
        "# TYPE truthtrace_duplicates_blocked counter",
        f"truthtrace_duplicates_blocked {snap.duplicate_detected_today}",
        "",
        "# HELP truthtrace_dedup_entries Content dedup entries",
        "# TYPE truthtrace_dedup_entries gauge",
        f"truthtrace_dedup_entries {dedup.stats().get('total_entries', 0)}",
        "",
        "# HELP truthtrace_uptime_seconds Application uptime",
        "# TYPE truthtrace_uptime_seconds gauge",
        f"truthtrace_uptime_seconds {(datetime.now(timezone.utc) - _metrics_start_time).total_seconds():.0f}",
        "",
    ]
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse("\n".join(lines), media_type="text/plain; charset=utf-8")


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
