"""
Celery 异步任务 Worker
处理爬取、分析、溯源等耗时操作

依赖 celery/redis 仅在启用了 Worker 的部署中需要，
FastAPI 主进程可独立运行 (trace API 提交任务时不 import celery)。
"""

# Lazy import: only import celery when running as worker
# FastAPI can start without celery installed
try:
    from celery import Celery
    _CELERY_AVAILABLE = True
except ImportError:
    _CELERY_AVAILABLE = False


def _get_celery_app():
    """延迟初始化 Celery app (仅在 worker 进程中使用)"""
    if not _CELERY_AVAILABLE:
        return None
    from app.config import get_settings
    settings = get_settings()

    app = Celery(
        "truthtrace",
        broker=settings.celery_broker_url,
        backend=settings.celery_result_backend,
    )
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Shanghai",
        enable_utc=True,
        task_track_started=True,
        task_acks_late=True,
        worker_prefetch_multiplier=1,
    )
    return app


_celery_app = None  # 延迟加载


def get_celery_app():
    """获取或创建 Celery 应用实例 (懒加载)"""
    global _celery_app
    if _celery_app is None:
        _celery_app = _get_celery_app()
    return _celery_app


def trace_url_task(
    url: str,
    title: str | None = None,
    description: str | None = None,
    deep_trace: bool = False,
    progress_callback=None,
):
    """
    同步溯源追踪任务

    完整流程：
    1. URL 跳转链解析
    2. 爬取目标页面内容
    3. NLP 事件提取 + 实体识别
    4. 搜索关联内容
    5. 构建传播图
    6. 识别原始来源
    7. 持久化 PostgreSQL
    8. 生成辟谣报告

    可通过 progress_callback(msg) 接收进度更新。
    """
    import asyncio
    from datetime import datetime, timezone
    from app.config import get_settings

    settings = get_settings()

    def progress(msg: str):
        """进度报告"""
        if progress_callback:
            progress_callback(msg)

    progress("解析 URL 跳转链...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            _run_trace_pipeline(url, title, description, deep_trace, progress)
        )
        return result

    except Exception as e:
        raise
    finally:
        loop.close()


async def _run_trace_pipeline(
    url: str,
    title: str | None,
    description: str | None,
    deep_trace: bool,
    progress,
) -> dict:
    """执行完整的溯源分析管线"""
    from app.crawler.resolver import URLResolver
    from app.crawler.general import GeneralCrawler
    from app.analyzer.event_extractor import EventExtractor
    from app.analyzer.entity import EntityRecognizer
    from app.analyzer.fingerprint import ContentFingerprinter

    # ===== 安全与质量守卫 =====
    from app.security import validate_url_safe, sanitize_input, CrawlerSandbox, compute_content_hash
    from app.quality import get_dedup_manager, DataValidator, SourceQualityEvaluator, get_quality_monitor

    # 1. URL 安全验证
    if not validate_url_safe(url):
        return {"status": "blocked", "url": url, "message": "URL 不在安全爬取范围内"}

    # 2. 输入净化
    safe_title = sanitize_input(title or "", max_length=500, field_name="title")
    safe_desc = sanitize_input(description or "", max_length=2000, field_name="description")
    from app.tracer.graph import PropagationGraphBuilder
    from app.tracer.original_finder import OriginalFinder

    # Step 1: 解析 URL 跳转链
    progress("解析 URL 跳转链...")
    resolver = URLResolver()
    url_chain = await resolver.resolve(url)
    final_url = url_chain[-1][0] if url_chain else url

    # Step 2: 爬取目标页面
    progress(f"爬取目标页面: {final_url[:50]}...")
    crawler = GeneralCrawler()
    page_data = await crawler.fetch(final_url)

    if not page_data or not page_data.content:
        return {
            "status": "error",
            "url": url,
            "final_url": final_url,
            "message": "无法获取页面内容",
        }

    # Step 3: NLP 事件提取
    progress("NLP 事件提取...")
    extractor = EventExtractor()
    event_info = await extractor.extract(
        page_data.content or "",
        title=title or page_data.title,
    )

    # Step 4: 实体识别
    progress("实体识别...")
    entity_recognizer = EntityRecognizer()
    entities = await entity_recognizer.extract(page_data.content or "")

    # Step 5: 内容指纹
    progress("内容指纹计算...")
    fingerprinter = ContentFingerprinter()
    content_hash = fingerprinter.compute(page_data.content or "")

    # Step 6: 搜索相关引用
    progress("搜索相关引用和传播链...")
    graph_builder = PropagationGraphBuilder()
    graph = await graph_builder.build(
        seed_url=final_url,
        seed_content=page_data.content or "",
        seed_author=page_data.author,
        entities=entities,
        deep=deep_trace,
    )

    # Step 7: 识别原始来源
    progress("识别原始/权威来源...")
    finder = OriginalFinder()
    originals = await finder.find(graph)

    # Step 8: 持久化到 PostgreSQL
    progress("保存溯源结果到数据库...")
    event_id = await _persist_trace_result(
        url=url,
        final_url=final_url,
        url_chain=[u for u, _ in url_chain],
        title=event_info.get("title", title or ""),
        summary=event_info.get("summary", ""),
        keywords=event_info.get("keywords", []),
        content_hash=content_hash,
        graph=graph,
        originals=originals,
        page_data=page_data,
    )

    # Step 9: 自动生成辟谣报告
    rumor_result = None
    if event_id:
        progress("生成辟谣报告...")
        rumor_result = await _generate_rumor_report(event_id)

    # Step 10: 推理引擎 — 深度分析
    progress("推理引擎分析中...")
    url_chain_urls = [u for u, _ in url_chain] if url_chain else []
    engine_analysis = await _run_reasoning_analysis(
        url=url,
        title=event_info.get("title", title or ""),
        text=f"{event_info.get('title', '')}\n{event_info.get('summary', '')}\n{page_data.content or ''}",
        content_hash=content_hash,
        url_chain=url_chain_urls,
        author=page_data.author or "",
        platform=getattr(page_data, 'platform', ''),
    )

    # 持久化引擎分析结果
    if event_id and engine_analysis:
        await _save_engine_analysis(str(event_id), engine_analysis)
        # 通知订阅者
        try:
            from app.notifications.notification_service import match_and_notify
            notified = await match_and_notify(
                event_id=str(event_id),
                event_title=event_info.get("title", title or ""),
                engine_analysis=engine_analysis,
                event_keywords=event_info.get("keywords", []),
            )
            if notified > 0:
                progress(f"已通知 {notified} 位订阅者")
        except Exception:
            pass  # 通知失败不影响主流程

    return {
        "status": "success",
        "url": url,
        "final_url": final_url,
        "url_chain": [u for u, _ in url_chain],
        "title": event_info.get("title", title or ""),
        "summary": event_info.get("summary", ""),
        "entities": entities,
        "content_hash": content_hash,
        "sources_found": len(graph.nodes),
        "original_sources": [
            {"url": s.url, "author": s.author, "score": s.score}
            for s in originals
        ],
        "propagation_graph": {
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
        },
        "event_id": str(event_id) if event_id else None,
        "rumor_analysis": rumor_result,
        "engine_analysis": engine_analysis,
    }


async def _save_engine_analysis(event_id: str, analysis: dict):
    """将引擎分析结果持久化到 Event 表"""
    if not event_id or not analysis:
        return
    try:
        import uuid as _uuid
        from app.models.base import async_session_factory
        from app.models.event import Event
        from sqlalchemy import select, update
        uid = _uuid.UUID(event_id)
        async with async_session_factory() as session:
            stmt = select(Event).where(Event.id == uid)
            result = await session.execute(stmt)
            event = result.scalar_one_or_none()
            if event:
                event.engine_analysis = analysis
                # 跨语言关键词扩充
                if event.keywords:
                    from app.search_crosslang import enrich_keywords_crosslang
                    event.keywords = enrich_keywords_crosslang(event.keywords)
                await session.commit()
    except Exception:
        pass  # non-critical


async def _run_reasoning_analysis(
    url: str,
    title: str,
    text: str,
    content_hash: str,
    url_chain: list[str],
    author: str = "",
    platform: str = "",
) -> dict | None:
    """
    调用推理引擎进行全维度分析 (Step 10)
    返回引擎分析的 dict 版本（可序列化）
    """
    try:
        from app.engine.reasoning import run_reasoning_pipeline
        result = await run_reasoning_pipeline(
            url=url,
            title=title,
            text=text,
            content_hash=content_hash,
            url_chain=url_chain or None,
            author=author,
            platform=platform,
        )
        return result.to_dict()
    except Exception as e:
        from loguru import logger
        logger.warning(f"推理引擎分析跳过 (非致命): {e}")
        return None


async def _persist_trace_result(
    url: str,
    final_url: str,
    url_chain: list[str],
    title: str,
    summary: str,
    keywords: list[str],
    content_hash: str,
    graph,
    originals: list,
    page_data,
) -> str | None:
    """
    将溯源结果持久化到 PostgreSQL

    写入 Event → Source → PropagationEdge → TimelineNode，
    形成完整的数据闭环，使搜索 API 可以查到溯源结果。
    """
    import uuid
    from datetime import datetime, timezone
    from loguru import logger

    from app.models.base import async_session_factory
    from app.models.event import (
        Event, Source, PropagationEdge, TimelineNode,
        EventStatus, EdgeType, Platform,
    )

    try:
        async with async_session_factory() as session:
            # 1. 创建 Event 记录
            event = Event(
                title=title or summary[:100] or "未命名事件",
                summary=summary or "",
                keywords=keywords,
                status=EventStatus.EMERGING,
                credibility_score=50.0,
                first_seen_at=datetime.now(timezone.utc),
            )
            session.add(event)
            await session.flush()  # 获取 event.id

            # 2. 创建 Source 记录（传播图中的每个节点）
            source_map: dict[str, uuid.UUID] = {}
            original_urls = {o.url for o in originals}
            original_score_map = {o.url: o.score for o in originals}

            for node in graph.nodes:
                # 映射 platform 字符串到枚举
                try:
                    platform = Platform(node.platform)
                except ValueError:
                    platform = Platform.UNKNOWN

                is_original = node.url in original_urls
                authority_score = original_score_map.get(node.url, 0.0)

                source = Source(
                    event_id=event.id,
                    url=node.url,
                    platform=platform,
                    author=node.author or "",
                    author_id=node.author_id or "",
                    title=node.title or "",
                    content_hash=node.content_hash or "",
                    published_at=node.published_at,
                    fetched_at=datetime.now(timezone.utc),
                    is_original=is_original,
                    authority_score=authority_score,
                    engagement_count=node.engagement if node.engagement else None,
                )
                session.add(source)
                await session.flush()
                source_map[node.id] = source.id

            # 3. 创建 PropagationEdge 记录
            for edge in graph.edges:
                from_id = source_map.get(edge.source_id)
                to_id = source_map.get(edge.target_id)
                if not from_id or not to_id:
                    continue

                try:
                    edge_type = EdgeType(edge.edge_type)
                except ValueError:
                    edge_type = EdgeType.REFERENCE

                prop_edge = PropagationEdge(
                    from_source_id=from_id,
                    to_source_id=to_id,
                    edge_type=edge_type,
                    propagated_at=edge.propagated_at,
                    weight=edge.weight,
                )
                session.add(prop_edge)

            # 4. 创建 TimelineNode 记录（按时间排序）
            timed_nodes = sorted(
                (
                    (n, source_map[n.id])
                    for n in graph.nodes
                    if n.published_at and n.id in source_map
                ),
                key=lambda x: x[0].published_at,
            )
            for node, source_id in timed_nodes:
                significance = 1.5 if node.is_original else 1.0
                timeline_node = TimelineNode(
                    event_id=event.id,
                    source_id=source_id,
                    timestamp=node.published_at,
                    description=node.title or f"{node.platform} 发布",
                    significance=significance,
                )
                session.add(timeline_node)

            await session.commit()
            logger.info(
                f"溯源结果已持久化: event_id={event.id}, "
                f"sources={len(source_map)}, edges={len(graph.edges)}, "
                f"timeline_nodes={len(timed_nodes)}"
            )
            return str(event.id)

    except Exception as e:
        logger.error(f"持久化溯源结果失败 (url={url}): {e}")
        return None


async def _generate_rumor_report(event_id: str) -> dict | None:
    """
    对已持久化的事件自动运行谣言检测，生成辟谣报告

    调用 RumorDetector + CrossReferencer 综合分析，
    结果写入 RumorReport 表，并更新 Event.credibility_score。
    """
    import uuid
    from loguru import logger

    from app.models.base import async_session_factory
    from app.models.event import Event, Source, RumorReport
    from app.verifier.rumor_detect import RumorDetector
    from app.verifier.cross_ref import CrossReferencer
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    try:
        uid = uuid.UUID(event_id) if isinstance(event_id, str) else event_id
    except (ValueError, TypeError):
        logger.error(f"无效的 event_id: {event_id}")
        return None

    try:
        async with async_session_factory() as session:
            # 加载 Event 及关联数据
            stmt = (
                select(Event)
                .where(Event.id == uid)
                .options(
                    selectinload(Event.sources),
                    selectinload(Event.rumor_report),
                )
            )
            result = await session.execute(stmt)
            event = result.scalar_one_or_none()

            if not event:
                logger.warning(f"事件不存在，无法生成辟谣报告: {event_id}")
                return None

            if not event.sources:
                # 没有来源数据，跳过
                return None

            # 1. 谣言检测
            detector = RumorDetector()
            rumor_result = await detector.detect(event)

            # 2. 交叉验证
            cross_ref = CrossReferencer()
            cross_result = await cross_ref.analyze(event.sources)

            # 3. 综合可信度评分（加权平均）
            rumor_score = rumor_result.get("score", 50)
            cross_score = cross_result.get("score", 50)
            credibility = round(rumor_score * 0.4 + cross_score * 0.6, 1)
            # 反转：谣言指数高 → 可信度低
            credibility = round(100 - credibility, 1)

            # 4. 更新 Event 可信度
            event.credibility_score = credibility

            # 5. 确定辟谣判定
            risk_level = rumor_result.get("risk_level", "low")
            if risk_level == "high":
                verdict = "false"
            elif risk_level == "medium":
                verdict = "misleading"
            else:
                verdict = "unverified"

            # 6. 收集验证来源
            verified_sources = []
            for s in event.sources:
                if s.is_original:
                    verified_sources.append({
                        "url": s.url,
                        "title": s.title or "",
                        "author": s.author or "",
                        "credibility": s.authority_score,
                    })

            # 7. 构建校正建议
            correction = _build_correction(verdict, rumor_result, cross_result)

            # 8. 创建或更新 RumorReport
            rumor_claim = event.title or ""
            fact_check = (
                rumor_result.get("analysis", "")
                + " | 交叉验证: "
                + cross_result.get("analysis", "")
            )

            if event.rumor_report:
                # 更新已有报告
                report = event.rumor_report
                report.rumor_claim = rumor_claim
                report.fact_check_result = fact_check
                report.verdict = verdict
                report.verified_sources = verified_sources
                report.correction = correction
            else:
                report = RumorReport(
                    event_id=event.id,
                    rumor_claim=rumor_claim,
                    fact_check_result=fact_check,
                    verdict=verdict,
                    verified_sources=verified_sources,
                    correction=correction,
                )
                session.add(report)

            await session.commit()
            logger.info(
                f"辟谣报告已生成: event_id={event_id}, "
                f"verdict={verdict}, credibility={credibility}"
            )

            return {
                "verdict": verdict,
                "risk_level": risk_level,
                "credibility_score": credibility,
                "rumor_score": rumor_score,
                "cross_ref_score": cross_score,
                "flags": rumor_result.get("flags", []),
            }

    except Exception as e:
        logger.error(f"生成辟谣报告失败 (event_id={event_id}): {e}")
        return None


def _build_correction(
    verdict: str,
    rumor_result: dict,
    cross_result: dict,
) -> str:
    """根据分析结果构建校正/辟谣建议"""
    flags = rumor_result.get("flags", [])

    if verdict == "false":
        parts = ["该信息展现出高度谣言特征，建议标记为不实信息。"]
        if flags:
            flag_descs = [f.get("description", "") for f in flags[:3]]
            parts.append("检测到: " + "；".join(flag_descs))
        return "".join(parts)

    elif verdict == "misleading":
        consensus = cross_result.get("consensus_level", "low")
        if consensus == "low":
            return "该信息部分内容具有误导性，缺乏足够独立的来源验证。建议读者保持审慎，等待更多权威来源确认。"
        else:
            return "该信息包含可疑元素，虽然有一定传播量，但关键信息有待权威渠道证实。建议交叉比对官方发布信息。"

    else:  # unverified
        return "当前信息尚无法确证或证伪。建议关注权威媒体和官方渠道的后续报道，对未经证实的信息保持警惕。"
