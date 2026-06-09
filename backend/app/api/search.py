"""
搜索 API — 事件搜索、关键词搜索、URL 搜索
三级搜索策略: PostgreSQL 全文搜索 → JSONB 关键词匹配 → ILIKE 回退
可选 Elasticsearch 增强
"""

import re
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, and_, func, text, String, case, desc
from sqlalchemy.orm import selectinload

from app.models.base import get_db
from app.models.event import Event, Source, EventStatus

logger = logging.getLogger("truthtrace.search")
router = APIRouter()

# 安全: 限制搜索关键词长度，防止 DoS
MAX_QUERY_LENGTH = 200


def _is_postgresql() -> bool:
    """检测是否使用 PostgreSQL（只有 PG 支持 tsvector/tsquery）"""
    from app.config import get_settings
    return get_settings().database_url.startswith("postgresql")


def sanitize_query(q: str) -> str:
    """清洗搜索输入: 去首尾空白、限制长度、移除危险字符"""
    q = q.strip()[:MAX_QUERY_LENGTH]
    # 移除可能被用于 SQL 注入的特殊字符
    q = re.sub(r"[;\\]", "", q)
    return q


def tokenize_for_tsquery(q: str) -> str | None:
    """
    将中文/英文关键词转为 PostgreSQL tsquery 格式。
    中文用 jieba 分词后 & 连接，英文直接传入。
    返回 None 表示无法构建 tsquery。
    """
    if not q.strip():
        return None
    try:
        import jieba
        tokens = [w.strip() for w in jieba.cut(q) if len(w.strip()) > 1]
    except Exception:
        tokens = [w for w in q.split() if len(w) > 1]
    if not tokens:
        tokens = [q]
    # 用 & 连接各词，要求全部匹配; 每个词后加 :* 支持前缀匹配
    parts = [f"{t}:*" for t in tokens[:8]]  # 最多8个词防止超长
    return " & ".join(parts)


def _build_tsvector_expression():
    """构建 PostgreSQL tsvector 表达式 (title + summary 复合)"""
    return func.to_tsvector(
        text("'simple'"),
        func.coalesce(Event.title, text("''"))
    ).op("||")(
        func.to_tsvector(
            text("'simple'"),
            func.coalesce(Event.summary, text("''"))
        )
    )


@router.get("/search")
async def search_events(
    q: str = Query(..., min_length=1, max_length=MAX_QUERY_LENGTH, description="搜索关键词或 URL"),
    status: EventStatus | None = Query(None),
    credibility_min: float | None = Query(None, ge=0, le=100, description="最低可信度"),
    credibility_max: float | None = Query(None, ge=0, le=100, description="最高可信度"),
    date_from: str | None = Query(None, description="起始日期 ISO format"),
    date_to: str | None = Query(None, description="结束日期 ISO format"),
    sort: str = Query("relevance", description="排序: relevance / newest / credibility"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    搜索事件 — 三级策略 + 多维筛选 + 多排序

    搜索策略（按优先级回退）：
    1. PostgreSQL full-text search (to_tsvector @@ to_tsquery) — 精确匹配，支持中文分词
    2. JSONB 关键词包含查询 — 关键词数组匹配
    3. ILIKE 模糊匹配 — 标题/摘要回退

    排序策略：
    - relevance: 全文搜索相关性优先，回退到更新时间
    - newest: 按最后更新时间倒序
    - credibility: 按可信度评分倒序
    """
    from datetime import datetime

    q = sanitize_query(q)

    # 跨语言搜索扩展: "cancer" → "cancer 癌症 致癌"
    from app.search_crosslang import expand_query_crosslang
    q_expanded = expand_query_crosslang(q)

    # --- 构建搜索条件 ---
    conditions = []

    # 策略1: PostgreSQL 全文搜索 (仅 PG 引擎支持 tsvector/tsquery)
    relevance_score = None

    if _is_postgresql():
        tsquery_str = tokenize_for_tsquery(q)
        tsvector_expr = _build_tsvector_expression()
        if tsquery_str:
            try:
                tsquery = func.to_tsquery(text("'simple'"), tsquery_str)
                conditions.append(tsvector_expr.op("@@")(tsquery))
                relevance_score = func.ts_rank(tsvector_expr, tsquery).label("relevance")
            except Exception:
                logger.debug(f"tsquery parse failed for: {q[:50]}")

    # 策略2: Jieba 分词搜索 (SQLite兼容) — 精确分词匹配
    from app.search_jieba import build_search_conditions
    conditions.extend(
        build_search_conditions(q_expanded, Event.title, Event.summary, Event.keywords)
    )

    # 组合: 任意条件满足即可
    where_clause = or_(*conditions)

    # --- 构建查询 ---
    columns = [Event]
    if relevance_score is not None:
        columns.append(relevance_score)

    stmt = select(*columns).where(where_clause)

    # 状态筛选
    if status:
        stmt = stmt.where(Event.status == status)

    # 可信度筛选
    if credibility_min is not None:
        stmt = stmt.where(Event.credibility_score >= credibility_min)
    if credibility_max is not None:
        stmt = stmt.where(Event.credibility_score <= credibility_max)

    # 时间范围筛选
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            stmt = stmt.where(Event.first_seen_at >= dt_from)
        except ValueError:
            raise HTTPException(400, "date_from 格式无效，请使用 ISO 格式 (如 2026-01-01)")

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            stmt = stmt.where(Event.first_seen_at <= dt_to)
        except ValueError:
            raise HTTPException(400, "date_to 格式无效，请使用 ISO 格式 (如 2026-01-01)")

    # --- 排序 ---
    if sort == "relevance" and relevance_score is not None:
        stmt = stmt.order_by(desc(text("relevance")), Event.last_updated_at.desc().nulls_last())
    elif sort == "newest":
        stmt = stmt.order_by(Event.last_updated_at.desc().nulls_last())
    elif sort == "credibility":
        stmt = stmt.order_by(Event.credibility_score.desc().nulls_last())
    else:
        stmt = stmt.order_by(Event.last_updated_at.desc().nulls_last())

    # 去重子查询包装 (避免多条件匹配同一事件)
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    # 单列: 直接获取 Event 对象; 多列 (含 relevance): 取第一列
    if relevance_score is not None:
        rows = [(row[0], row[1]) for row in result.all()]
    else:
        rows = [(e,) for e in result.scalars().all()]

    # 去重 & 组装结果
    seen = set()
    unique_events = []
    for row in rows:
        event = row[0]
        if event.id not in seen:
            seen.add(event.id)
            unique_events.append(event)

    total_stmt = select(func.count(Event.id)).where(where_clause)
    if status:
        total_stmt = total_stmt.where(Event.status == status)
    total_result = await db.execute(total_stmt)
    total = total_result.scalar() or 0

    return {
        "query": q,
        "total": total,
        "offset": offset,
        "limit": limit,
        "sort": sort,
        "events": [
            {
                "id": str(e.id),
                "title": e.title,
                "summary": e.summary,
                "status": e.status.value if e.status else None,
                "credibility_score": e.credibility_score,
                "keywords": e.keywords or [],
                "first_seen_at": e.first_seen_at.isoformat() if e.first_seen_at else None,
                "last_updated_at": e.last_updated_at.isoformat() if e.last_updated_at else None,
                "has_engine_analysis": e.engine_analysis is not None,
                "engine_verdict": e.engine_analysis.get("verdict") if e.engine_analysis else None,
                "engine_distortion_count": len(e.engine_analysis.get("distortion_analysis", {}).get("matches", [])) if e.engine_analysis else 0,
                "engine_fallacy_count": e.engine_analysis.get("fallacy_analysis", {}).get("fallacy_count", 0) if e.engine_analysis else 0,
            }
            for e in unique_events
        ],
    }


@router.get("/search/trending")
async def trending_events(
    hours: int = Query(24, ge=1, le=168, description="最近 N 小时"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    热门/趋势事件

    基于最近 N 小时内信息来源数量和可信度综合排序。
    热度 = source_count * 0.6 + credibility_score * 0.4
    """
    from datetime import datetime, timedelta

    since = datetime.utcnow() - timedelta(hours=hours)

    # 统计每个事件的来源数量并按热度排序
    subq = (
        select(
            Event.id,
            func.count(Source.id).label("source_count"),
        )
        .outerjoin(Source, Source.event_id == Event.id)
        .where(Event.last_updated_at >= since)
        .group_by(Event.id)
        .subquery()
    )

    stmt = (
        select(
            Event,
            subq.c.source_count,
            (subq.c.source_count * 0.6 + Event.credibility_score * 0.4).label("hotness"),
        )
        .join(subq, Event.id == subq.c.id)
        .order_by(desc(text("hotness")))
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return {
        "hours": hours,
        "events": [
            {
                "id": str(row[0].id),
                "title": row[0].title,
                "summary": row[0].summary,
                "status": row[0].status.value if row[0].status else None,
                "credibility_score": row[0].credibility_score,
                "source_count": row[1],
                "hotness_score": round(row[2], 1),
                "last_updated_at": row[0].last_updated_at.isoformat() if row[0].last_updated_at else None,
            }
            for row in rows
        ],
    }


@router.get("/search/url")
async def search_by_url(
    url: str = Query(..., description="要追溯的 URL"),
    db: AsyncSession = Depends(get_db),
):
    """
    通过 URL 搜索

    查找包含指定 URL 的事件和来源。
    使用 URL 规范化匹配（忽略 http/https、www 差异）。
    """
    from urllib.parse import urlparse

    def normalize_url(u: str) -> str:
        try:
            parsed = urlparse(u)
            netloc = parsed.netloc.lower().replace("www.", "")
            path = parsed.path.rstrip("/")
            return f"{netloc}{path}{'?' + parsed.query if parsed.query else ''}"
        except Exception:
            return u

    normalized = normalize_url(url)

    # 查找已有来源 (精确匹配)
    stmt = select(Source).where(Source.url == url)
    stmt = stmt.options(selectinload(Source.event))
    result = await db.execute(stmt)
    sources = result.scalars().all()

    if sources:
        event = sources[0].event
        return {
            "found": True,
            "is_new": False,
            "event": {
                "id": str(event.id) if event else None,
                "title": event.title if event else "未知",
                "status": event.status.value if event and event.status else None,
                "credibility_score": event.credibility_score if event else 50,
            },
            "matched_sources": len(sources),
            "message": f"找到已有事件，包含 {len(sources)} 个匹配来源",
        }

    # 模糊匹配 (域名+路径相似)
    stmt = select(Source).where(Source.url.ilike(f"%{normalized[:100]}%"))
    stmt = stmt.options(selectinload(Source.event))
    result = await db.execute(stmt)
    fuzzy_sources = result.scalars().all()

    if fuzzy_sources:
        seen_events = {}
        for s in fuzzy_sources:
            if s.event and s.event_id not in seen_events:
                seen_events[s.event_id] = s.event
        events_list = list(seen_events.values())

        return {
            "found": True,
            "is_new": False,
            "events": [
                {
                    "id": str(e.id),
                    "title": e.title,
                    "status": e.status.value if e.status else None,
                    "credibility_score": e.credibility_score,
                }
                for e in events_list[:5]
            ],
            "message": f"找到 {len(events_list)} 个可能相关的事件（模糊匹配）",
        }

    return {
        "found": False,
        "is_new": True,
        "event": None,
        "message": "未找到该 URL 的相关事件。请使用 POST /api/trace 提交追踪任务。",
        "suggestion": f"POST /api/trace with url={url}",
    }


# --- Elasticsearch 可选增强 ---

_es_client = None


def _get_es_client():
    """延迟初始化 Elasticsearch 客户端"""
    global _es_client
    if _es_client is not None:
        return _es_client
    try:
        from elasticsearch import AsyncElasticsearch
        from app.config import get_settings
        settings = get_settings()
        _es_client = AsyncElasticsearch(
            [settings.elasticsearch_url],
            request_timeout=10,
            max_retries=2,
            retry_on_timeout=True,
        )
    except Exception:
        _es_client = False  # 标记不可用
    return _es_client


async def _es_search_events(q: str, limit: int = 20, offset: int = 0) -> list[dict]:
    """
    使用 Elasticsearch 搜索事件 (增强搜索)
    返回匹配的事件 ID 列表，按相关性排序
    """
    client = _get_es_client()
    if not client:
        return []

    try:
        resp = await client.search(
            index="truthtrace_events",
            body={
                "query": {
                    "multi_match": {
                        "query": q,
                        "fields": ["title^3", "summary^2", "keywords^1.5", "content"],
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                    }
                },
                "from": offset,
                "size": limit,
                "_source": False,
                "track_total_hits": min(limit * 10, 10000),
            },
        )
        hits = resp.get("hits", {}).get("hits", [])
        return [h["_id"] for h in hits]
    except Exception as e:
        logger.warning(f"Elasticsearch search failed: {e}")
        return []


async def _es_index_event(event_id: str, title: str, summary: str, keywords: list, content: str = ""):
    """将事件索引到 Elasticsearch"""
    client = _get_es_client()
    if not client:
        return

    try:
        await client.index(
            index="truthtrace_events",
            id=event_id,
            body={
                "title": title,
                "summary": summary or "",
                "keywords": keywords or [],
                "content": content or "",
            },
            refresh=False,
        )
    except Exception as e:
        logger.debug(f"ES index skipped: {e}")
