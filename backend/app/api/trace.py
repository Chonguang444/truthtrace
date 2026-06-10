"""
溯源追踪 API — 提交追踪任务、批量溯源、查询进度、获取结果
支持 Celery 异步 + 内存 fallback
"""

import asyncio
import uuid as _uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, HttpUrl, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import get_db

logger = logging.getLogger("truthtrace.trace")
router = APIRouter()


class TraceRequest(BaseModel):
    """追踪任务请求"""
    url: str
    title: str | None = None
    description: str | None = None
    deep_trace: bool = False

    @field_validator("url")
    @classmethod
    def url_must_be_valid(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL 必须以 http:// 或 https:// 开头")
        return v


class TraceResponse(BaseModel):
    """追踪任务响应"""
    task_id: str
    url: str
    status: str
    message: str


class BatchTraceRequest(BaseModel):
    """批量追踪请求"""
    urls: list[str]
    deep_trace: bool = False
    max_concurrency: int = 5  # 最大并发数

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("urls 不能为空")
        if len(v) > 100:
            raise ValueError("单次最多提交 100 个 URL")
        for url in v:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"无效 URL: {url}")
        return v


# 内存任务状态 (Celery 不可用时的 fallback)
_task_store: dict[str, dict] = {}
_task_store_lock = asyncio.Lock()


def _submit_celery_task(request: TraceRequest) -> str | None:
    """尝试提交到 Celery，返回 task_id 或 None"""
    try:
        from app.tasks.worker import get_celery_app, trace_url_task

        celery_app = get_celery_app()
        if celery_app:
            celery_task = celery_app.task(bind=True, name="trace_url")(trace_url_task)
            async_result = celery_task.delay(
                url=request.url,
                title=request.title,
                description=request.description,
                deep_trace=request.deep_trace,
            )
            return async_result.id
    except Exception as e:
        logger.debug(f"Celery submit failed, using sync fallback: {e}")
    return None


async def _run_trace_sync(request: TraceRequest, task_id: str):
    """同步执行追踪任务 (fallback)"""
    from app.tasks.worker import trace_url_task

    async with _task_store_lock:
        _task_store[task_id] = {"status": "STARTED", "progress": "开始处理..."}

    loop = asyncio.get_event_loop()

    try:
        result = await loop.run_in_executor(
            None,
            lambda: trace_url_task(
                url=request.url,
                title=request.title,
                description=request.description,
                deep_trace=request.deep_trace,
                progress_callback=lambda msg: _task_store.update(
                    {task_id: {"status": "STARTED", "progress": msg}}
                ),
            ),
        )
        async with _task_store_lock:
            _task_store[task_id] = {"status": "SUCCESS", "result": result}
    except Exception as e:
        logger.error(f"Trace task failed ({task_id[:8]}...): {e}")
        async with _task_store_lock:
            _task_store[task_id] = {"status": "FAILURE", "error": str(e)}


@router.post("/trace", response_model=TraceResponse)
async def submit_trace_task(request: TraceRequest):
    """
    提交溯源追踪任务

    完整流程：
    1. 爬取该页面内容
    2. 提取事件关键信息
    3. 搜索相关引用和转发
    4. 构建传播链路图
    5. 识别原始/权威来源

    优先使用 Celery 异步执行，不可用时回退到线程池同步。
    """
    task_id = str(_uuid.uuid4())

    # 尝试 Celery 异步
    celery_id = _submit_celery_task(request)
    if celery_id:
        return TraceResponse(
            task_id=celery_id,
            url=request.url,
            status="submitted",
            message="追踪任务已提交到 Celery Worker，使用 GET /api/tasks/{task_id} 查询进度",
        )

    # Fallback: 在线程池中同步执行
    asyncio.create_task(_run_trace_sync(request, task_id))

    return TraceResponse(
        task_id=task_id,
        url=request.url,
        status="submitted",
        message="追踪任务已开始（同步模式），使用 GET /api/tasks/{task_id} 查询结果",
    )


@router.post("/trace/batch")
async def submit_batch_trace(request: BatchTraceRequest):
    """
    批量提交溯源追踪 — 使用 asyncio.gather 并行执行

    每个 URL 在独立线程池中执行，总并发由 max_concurrency 控制。
    返回每个 URL 的 task_id 和初始状态。
    """
    semaphore = asyncio.Semaphore(request.max_concurrency)

    async def process_one(url: str) -> dict:
        from app.security import validate_url_safe
        if not validate_url_safe(url):
            return {"url": url, "task_id": "", "status": "blocked", "error": "URL 不安全或不允许"}
        task_id = str(_uuid.uuid4())
        trace_req = TraceRequest(url=url, deep_trace=request.deep_trace)

        async with semaphore:
            # 尝试 Celery
            celery_id = _submit_celery_task(trace_req)
            if celery_id:
                return {"url": url, "task_id": celery_id, "mode": "celery"}

            # 同步 fallback（在线程池中运行）
            async with _task_store_lock:
                _task_store[task_id] = {"status": "STARTED", "progress": f"开始处理: {url[:50]}..."}

            from app.tasks.worker import trace_url_task
            loop = asyncio.get_event_loop()

            try:
                result = await loop.run_in_executor(
                    None,
                    lambda u=url: trace_url_task(
                        url=u,
                        deep_trace=request.deep_trace,
                        progress_callback=lambda msg, tid=task_id: _task_store.update(
                            {tid: {"status": "STARTED", "progress": msg}}
                        ),
                    ),
                )
                async with _task_store_lock:
                    _task_store[task_id] = {"status": "SUCCESS", "result": result}
                return {"url": url, "task_id": task_id, "mode": "sync", "status": "SUCCESS"}
            except Exception as e:
                async with _task_store_lock:
                    _task_store[task_id] = {"status": "FAILURE", "error": str(e)}
                return {"url": url, "task_id": task_id, "mode": "sync", "status": "FAILURE", "error": str(e)}

    # 并行处理所有 URL，最多 max_concurrency 个并发
    results = await asyncio.gather(
        *(process_one(url) for url in request.urls),
        return_exceptions=True,
    )

    # 处理可能被 gather 捕获的异常
    tasks_out = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            tasks_out.append({
                "url": request.urls[i],
                "task_id": str(_uuid.uuid4()),
                "mode": "error",
                "error": str(r),
            })
        else:
            tasks_out.append(r)

    succeeded = sum(1 for t in tasks_out if t.get("status") == "SUCCESS")
    failed = sum(1 for t in tasks_out if t.get("status") == "FAILURE")

    return {
        "total": len(tasks_out),
        "succeeded": succeeded,
        "failed": failed,
        "tasks": tasks_out,
    }


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    查询追踪任务状态

    状态说明：
    - PENDING: 等待执行
    - STARTED: 正在爬取分析
    - SUCCESS: 完成，result 中包含 event_id
    - FAILURE: 失败，result 中包含错误信息
    """
    response = {"task_id": task_id, "status": "PENDING"}

    # 尝试 Celery
    try:
        from celery.result import AsyncResult
        from app.tasks.worker import get_celery_app

        celery_app = get_celery_app()
        if celery_app:
            task = AsyncResult(task_id, app=celery_app)
            if task.state != "PENDING":
                response["status"] = task.state
                if task.state == "SUCCESS":
                    response["result"] = task.result
                elif task.state == "FAILURE":
                    response["error"] = str(task.info)
                elif task.state == "STARTED":
                    if task.info:
                        response["progress"] = task.info
                return response
    except Exception:
        pass

    # Fallback: 内存任务状态
    if task_id in _task_store:
        info = _task_store[task_id]
        response["status"] = info["status"]
        if info["status"] == "SUCCESS":
            response["result"] = info.get("result")
        elif info["status"] == "FAILURE":
            response["error"] = info.get("error")
        elif info["status"] == "STARTED":
            response["progress"] = info.get("progress")

    return response


@router.get("/tasks")
async def list_tasks(
    status: str | None = Query(None, description="筛选状态"),
    limit: int = Query(20, ge=1, le=100),
):
    """列出最近的任务（内存 + Celery 汇总）"""
    tasks = []

    # 内存任务
    for tid, info in _task_store.items():
        if status and info.get("status") != status:
            continue
        tasks.append({
            "task_id": tid,
            "status": info.get("status"),
            "progress": info.get("progress"),
        })

    # 按插入顺序倒序 (最近在前)
    tasks.reverse()
    return {"tasks": tasks[:limit], "total": len(tasks)}


@router.get("/trace/url-chain")
async def resolve_url_chain(
    url: str = Query(..., description="需要解析的 URL"),
):
    """
    解析 URL 跳转链

    跟随 HTTP 重定向和常见短链接服务，还原原始 URL。
    支持：t.cn, bit.ly, ow.ly, short.com 等短链接服务。
    """
    from app.security import validate_url_safe
    if not validate_url_safe(url):
        raise HTTPException(400, "URL 不安全或不允许")
    from app.crawler.resolver import URLResolver

    resolver = URLResolver()
    chain = await resolver.resolve(url)

    return {
        "original_url": url,
        "resolved_url": chain[-1][0] if chain else url,
        "chain_length": len(chain),
        "redirect_chain": [
            {"step": i + 1, "url": u, "status": s}
            for i, (u, s) in enumerate(chain)
        ],
    }
