"""
DetectZoo Bridge — 跨平台谣言库共享与互操作

标准化接口实现与外部谣言库的双向数据交换:
- 导出: TruthTrace → Schema.org ClaimReview / Google Fact Check / IFCN 格式
- 导入: 外部谣言库 → TruthTrace 统一事件模型
- 查询: 跨库搜索 — 同时查 TruthTrace + Google Fact Check + Snopes 等
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from datetime import datetime, timezone
from collections import defaultdict
import uuid
import hashlib

from app.auth.jwt import get_current_active_user, get_admin_user
from app.models.user import User

router = APIRouter()


# =============================================================================
# 统一谣言条目格式 (DetectZoo Schema)
# =============================================================================

class DetectZooClaim(BaseModel):
    """标准化谣言主张"""
    claim_id: str = ""
    claim_text: str = ""
    claim_summary: str = ""
    claim_language: str = "zh"
    claim_author: str = ""
    claim_date: str = ""
    claim_urls: list[str] = []


class DetectZooVerdict(BaseModel):
    """标准化核查判定"""
    verdict: str = ""           # true / false / misleading / unverifiable / mixture
    credibility_score: float = 50.0
    confidence: str = "moderate"
    reviewer_name: str = "TruthTrace"
    review_date: str = ""
    review_summary: str = ""
    review_url: str = ""
    evidence_urls: list[str] = []
    correction_text: str = ""


class DetectZooEntry(BaseModel):
    """完整的标准化谣言条目"""
    entry_id: str = ""
    schema_version: str = "1.0"
    claim: DetectZooClaim = DetectZooClaim()
    verdict: DetectZooVerdict = DetectZooVerdict()
    tags: list[str] = []
    topics: list[str] = []
    platforms: list[str] = []
    propagation_summary: str = ""
    created_at: str = ""
    updated_at: str = ""


# =============================================================================
# 外部谣言库注册表
# =============================================================================

EXTERNAL_REGISTRY = {
    "google_factcheck": {
        "name": "Google Fact Check Tools",
        "api_base": "https://factchecktools.googleapis.com/v1alpha1/claims:search",
        "format": "claimreview",
        "requires_key": True,
        "status": "available",
    },
    "ifcn": {
        "name": "IFCN (International Fact-Checking Network)",
        "api_base": "https://api.poynter.org/ifcn",
        "format": "claimreview",
        "requires_key": True,
        "status": "available",
    },
    "snopes": {
        "name": "Snopes",
        "url": "https://www.snopes.com",
        "format": "html",
        "requires_key": False,
        "status": "external_crawl",
    },
    "politifact": {
        "name": "PolitiFact",
        "url": "https://www.politifact.com",
        "format": "html",
        "requires_key": False,
        "status": "external_crawl",
    },
    "fullfact": {
        "name": "Full Fact (UK)",
        "url": "https://fullfact.org",
        "format": "html",
        "requires_key": False,
        "status": "external_crawl",
    },
    "jppolitifact": {
        "name": "Japan Fact-check Center",
        "url": "https://factcheckcenter.jp",
        "format": "html",
        "requires_key": False,
        "status": "external_crawl",
    },
}


# =============================================================================
# 内存存储 (生产用 PostgreSQL)
# =============================================================================

_bridge_entries: dict[str, dict] = {}  # entry_id → DetectZooEntry dict (max 10K)
_import_log: list[dict] = []            # 导入记录 (max 5000)
_export_log: list[dict] = []            # 导出记录 (max 5000)
_BRIDGE_MAX_ENTRIES = 10000
_LOG_MAX_ENTRIES = 5000


# =============================================================================
# 端点: 导出
# =============================================================================

@router.post("/detectzoo/export/{event_id}")
async def export_to_detectzoo(
    event_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """
    将 TruthTrace 事件导出为 DetectZoo 标准格式。

    同时生成:
    - DetectZoo JSON
    - Schema.org ClaimReview JSON-LD
    - Google Fact Check 兼容格式
    """
    # 构造条目
    entry_id = f"tt-{event_id}-{datetime.now(timezone.utc).strftime('%Y%m%d')}"

    entry = DetectZooEntry(
        entry_id=entry_id,
        claim=DetectZooClaim(
            claim_text=f"TruthTrace event: {event_id}",
            claim_language="zh",
            claim_urls=[f"https://truthtrace.app/events/{event_id}"],
        ),
        verdict=DetectZooVerdict(
            reviewer_name="TruthTrace",
            review_date=datetime.now(timezone.utc).isoformat(),
            review_url=f"https://truthtrace.app/events/{event_id}/report",
        ),
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    entry_dict = entry.model_dump()
    _bridge_entries[entry_id] = entry_dict
    # Cap entries
    if len(_bridge_entries) > _BRIDGE_MAX_ENTRIES:
        oldest = sorted(_bridge_entries.keys(), key=lambda k: _bridge_entries[k].get("created_at",""))[:1000]
        for k in oldest: del _bridge_entries[k]

    if len(_export_log) > _LOG_MAX_ENTRIES:
        _export_log[:] = _export_log[-_LOG_MAX_ENTRIES//2:]
    _export_log.append({
        "entry_id": entry_id,
        "source_event": event_id,
        "exported_by": str(current_user.id),
        "exported_at": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "entry_id": entry_id,
        "detectzoo": entry_dict,
        "claimreview_jsonld": _to_claimreview_jsonld(entry_dict),
        "google_factcheck_format": _to_google_fc_format(entry_dict),
        "formats_available": ["detectzoo_json", "claimreview_jsonld", "google_factcheck"],
    }


@router.post("/detectzoo/export-batch")
async def export_batch_to_detectzoo(
    event_ids: list[str],
    current_user: User = Depends(get_admin_user),
):
    """批量导出多个事件 (管理员)"""
    results = []
    for eid in event_ids:
        entry_id = f"tt-{eid}-{datetime.now(timezone.utc).strftime('%Y%m%d')}"
        entry = DetectZooEntry(
            entry_id=entry_id,
            claim=DetectZooClaim(
                claim_text=f"TruthTrace event: {eid}",
                claim_urls=[f"https://truthtrace.app/events/{eid}"],
            ),
            verdict=DetectZooVerdict(
                reviewer_name="TruthTrace",
                review_date=datetime.now(timezone.utc).isoformat(),
                review_url=f"https://truthtrace.app/events/{eid}/report",
            ),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        entry_dict = entry.model_dump()
        _bridge_entries[entry_id] = entry_dict
        results.append(entry_dict)

    return {
        "exported": len(results),
        "entries": results,
        "claimreviews": [_to_claimreview_jsonld(e) for e in results],
    }


# =============================================================================
# 端点: 导入
# =============================================================================

@router.post("/detectzoo/import")
async def import_from_detectzoo(
    entry: DetectZooEntry,
    current_user: User = Depends(get_admin_user),
):
    """从外部谣言库导入条目 (管理员)"""
    entry_id = entry.entry_id or f"import-{uuid.uuid4().hex[:12]}"
    entry.entry_id = entry_id
    entry.schema_version = entry.schema_version or "1.0"

    if not entry.created_at:
        entry.created_at = datetime.now(timezone.utc).isoformat()

    entry_dict = entry.model_dump()
    _bridge_entries[entry_id] = entry_dict
    # Cap bridge entries
    if len(_bridge_entries) > _BRIDGE_MAX_ENTRIES:
        oldest = sorted(_bridge_entries.keys(), key=lambda k: _bridge_entries[k].get("created_at",""))[:1000]
        for k in oldest: del _bridge_entries[k]

    _import_log.append({
        "entry_id": entry_id,
        "source": "external_import",
        "imported_by": str(current_user.id),
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "claim_text": entry.claim.claim_text[:120],
    })

    return {
        "status": "imported",
        "entry_id": entry_id,
        "message": f"已导入条目: {entry.claim.claim_text[:60]}...",
    }


@router.post("/detectzoo/import-batch")
async def import_batch_from_detectzoo(
    entries: list[DetectZooEntry],
    current_user: User = Depends(get_admin_user),
):
    """批量导入 (管理员)"""
    imported = 0
    for entry in entries:
        try:
            entry_id = entry.entry_id or f"import-{uuid.uuid4().hex[:12]}"
            entry.entry_id = entry_id
            _bridge_entries[entry_id] = entry.model_dump()
            imported += 1
        except Exception:
            pass

    return {"imported": imported, "total": len(entries)}


# =============================================================================
# 端点: 查询
# =============================================================================

@router.get("/detectzoo/search")
async def search_detectzoo(
    q: str = Query("", min_length=2),
    limit: int = Query(20, ge=1, le=100),
    include_external: bool = Query(False),
):
    """
    跨库搜索谣言条目。

    搜索范围:
    - TruthTrace 本地桥接库
    - (include_external=true) Google Fact Check / Snopes 等外部库
    """
    results = []

    # 本地搜索
    q_lower = q.lower()
    for entry_id, entry in _bridge_entries.items():
        claim_text = entry.get("claim", {}).get("claim_text", "")
        verdict_text = entry.get("verdict", {}).get("review_summary", "")

        if q_lower in claim_text.lower() or q_lower in verdict_text.lower():
            results.append({
                "entry_id": entry_id,
                "claim_text": claim_text[:200],
                "verdict": entry.get("verdict", {}).get("verdict", ""),
                "credibility_score": entry.get("verdict", {}).get("credibility_score", 50),
                "source": "truthtrace_bridge",
                "review_url": entry.get("verdict", {}).get("review_url", ""),
            })

    # 外部搜索 (非阻塞 — 返回可用的外部查询链接)
    external_links = {}
    if include_external:
        for key, info in EXTERNAL_REGISTRY.items():
            if info["status"] == "available":
                if info["format"] == "claimreview":
                    external_links[key] = {
                        "name": info["name"],
                        "search_url": f"{info['api_base']}?query={q}",
                        "format": "claimreview",
                    }

    return {
        "query": q,
        "total": len(results),
        "results": results[:limit],
        "external_registry": EXTERNAL_REGISTRY,
        "external_search_links": external_links,
    }


@router.get("/detectzoo/entries")
async def list_detectzoo_entries(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    verdict: str = Query(""),
):
    """列出所有桥接条目"""
    entries = list(_bridge_entries.values())

    if verdict:
        entries = [e for e in entries if e.get("verdict", {}).get("verdict") == verdict]

    entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)

    return {
        "total": len(entries),
        "entries": entries[offset:offset+limit],
    }


@router.get("/detectzoo/registry")
async def get_detectzoo_registry():
    """获取外部谣言库注册表"""
    return {
        "registry": EXTERNAL_REGISTRY,
        "supported_formats": ["detectzoo_json", "claimreview_jsonld", "google_factcheck"],
        "bridge_stats": {
            "stored_entries": len(_bridge_entries),
            "imports": len(_import_log),
            "exports": len(_export_log),
        },
    }


# =============================================================================
# 格式转换工具
# =============================================================================

def _to_claimreview_jsonld(entry: dict) -> dict:
    """DetectZoo → Schema.org ClaimReview JSON-LD"""
    claim = entry.get("claim", {})
    verdict = entry.get("verdict", {})

    return {
        "@context": "https://schema.org",
        "@type": "ClaimReview",
        "claimReviewed": claim.get("claim_text", "")[:500],
        "author": {"@type": "Organization", "name": claim.get("claim_author", "未知来源")},
        "datePublished": claim.get("claim_date", ""),
        "reviewRating": {
            "@type": "Rating",
            "ratingValue": _verdict_to_numeric(verdict.get("verdict", "unverifiable")),
            "alternateName": verdict.get("verdict", "unverifiable"),
        },
        "url": verdict.get("review_url", ""),
        "publisher": {
            "@type": "Organization",
            "name": verdict.get("reviewer_name", "TruthTrace"),
        },
        "reviewBody": verdict.get("review_summary", "")[:2000],
    }


def _to_google_fc_format(entry: dict) -> dict:
    """DetectZoo → Google Fact Check Tools 兼容格式"""
    return {
        "claim_text": entry.get("claim", {}).get("claim_text", ""),
        "claim_date": entry.get("claim", {}).get("claim_date", ""),
        "claim_author": entry.get("claim", {}).get("claim_author", ""),
        "verdict": entry.get("verdict", {}).get("verdict", ""),
        "credibility_score": entry.get("verdict", {}).get("credibility_score", 50.0),
        "reviewer": entry.get("verdict", {}).get("reviewer_name", "TruthTrace"),
        "review_date": entry.get("verdict", {}).get("review_date", ""),
        "correction": entry.get("verdict", {}).get("correction_text", ""),
        "evidence_urls": entry.get("verdict", {}).get("evidence_urls", []),
    }


def _verdict_to_numeric(verdict: str) -> int:
    return {
        "true": 5, "mostly_true": 4, "mixture": 3,
        "misleading": 2, "mostly_false": 1,
        "false": 0, "unverifiable": -1,
    }.get(verdict, -1)
