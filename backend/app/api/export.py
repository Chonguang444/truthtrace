"""
数据导出 API — PDF 溯源报告 + CSV 数据导出
"""

import io
import csv
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.base import get_db
from app.models.event import Event, Source, PropagationEdge, TimelineNode, RumorReport
from app.auth.jwt import get_current_active_user
from app.models.user import User

logger = logging.getLogger("truthtrace.export")
router = APIRouter()

# CSV 字段配置 (防止公式注入)
CSV_FIELDS_EVENTS = [
    "id", "title", "summary", "keywords", "status",
    "credibility_score", "first_seen_at", "last_updated_at", "created_at",
]

CSV_FIELDS_SOURCES = [
    "id", "event_id", "url", "platform", "author",
    "title", "content_hash", "published_at", "is_original", "authority_score",
]


def _sanitize_csv_value(value) -> str:
    """清洗 CSV 值，防止公式注入"""
    s = str(value) if value is not None else ""
    # 以 =, +, -, @ 开头的值在 Excel 中可能被视为公式
    if s and s[0] in "=+-@":
        s = "'" + s
    return s


# ---------------------------------------------------------------------------
# CSV Export
# ---------------------------------------------------------------------------

@router.get("/export/events/csv")
async def export_events_csv(current_user = Depends(get_current_active_user),
    status: str | None = Query(None),
    credibility_min: float | None = Query(None),
    credibility_max: float | None = Query(None),
    limit: int = Query(1000, ge=1, le=10000),
    db: AsyncSession = Depends(get_db),
):
    """
    导出事件列表为 CSV 文件
    """
    stmt = select(Event)

    if status:
        from app.models.event import EventStatus
        try:
            stmt = stmt.where(Event.status == EventStatus(status))
        except ValueError:
            raise HTTPException(400, f"无效的状态值: {status}")

    if credibility_min is not None:
        stmt = stmt.where(Event.credibility_score >= credibility_min)
    if credibility_max is not None:
        stmt = stmt.where(Event.credibility_score <= credibility_max)

    stmt = stmt.order_by(Event.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    events = result.scalars().all()

    output = io.StringIO()
    output.write("﻿")  # UTF-8 BOM (Excel 兼容)
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "ID", "标题", "摘要", "关键词", "状态",
        "可信度评分", "首次发现", "最后更新", "创建时间",
    ])

    for ev in events:
        writer.writerow([
            _sanitize_csv_value(str(ev.id)),
            _sanitize_csv_value(ev.title),
            _sanitize_csv_value(ev.summary or ""),
            _sanitize_csv_value(", ".join(ev.keywords) if ev.keywords else ""),
            _sanitize_csv_value(ev.status.value if ev.status else ""),
            _sanitize_csv_value(ev.credibility_score),
            _sanitize_csv_value(ev.first_seen_at.isoformat() if ev.first_seen_at else ""),
            _sanitize_csv_value(ev.last_updated_at.isoformat() if ev.last_updated_at else ""),
            _sanitize_csv_value(ev.created_at.isoformat() if ev.created_at else ""),
        ])

    filename = f"truthtrace_events_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "X-Export-Count": str(len(events)),
        },
    )


@router.get("/export/events/{event_id}/sources/csv")
async def export_event_sources_csv(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """导出特定事件的所有来源为 CSV"""
    try:
        uid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(400, "无效的事件 ID")

    # 验证事件存在
    event = await db.get(Event, uid)
    if not event:
        raise HTTPException(404, "事件不存在")

    result = await db.execute(
        select(Source).where(Source.event_id == uid).order_by(Source.published_at.desc().nulls_last())
    )
    sources = result.scalars().all()

    output = io.StringIO()
    output.write("﻿")
    writer = csv.writer(output)

    writer.writerow([
        "ID", "URL", "平台", "作者", "标题",
        "内容摘要", "发布时间", "是否原始来源", "权威度评分",
    ])

    for s in sources:
        writer.writerow([
            _sanitize_csv_value(str(s.id)),
            _sanitize_csv_value(s.url),
            _sanitize_csv_value(s.platform.value if s.platform else ""),
            _sanitize_csv_value(s.author or ""),
            _sanitize_csv_value(s.title or ""),
            _sanitize_csv_value((s.content or "")[:200]),
            _sanitize_csv_value(s.published_at.isoformat() if s.published_at else ""),
            _sanitize_csv_value("是" if s.is_original else "否"),
            _sanitize_csv_value(s.authority_score),
        ])

    # 使用安全文件名
    safe_title = event.title[:30].replace("/", "_").replace("\\", "_")
    filename = f"truthtrace_{safe_title}_sources_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "X-Export-Count": str(len(sources)),
        },
    )


# ---------------------------------------------------------------------------
# PDF Export (HTML-based — WeasyPrint fallback)
# ---------------------------------------------------------------------------

@router.get("/export/events/{event_id}/report/pdf")
async def export_event_report_pdf(
    event_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    导出事件溯源报告为 PDF

    使用 WeasyPrint 将 HTML 模板渲染为 PDF。
    如果 WeasyPrint 不可用，回退到 HTML 响应。
    """
    try:
        uid = uuid.UUID(event_id)
    except ValueError:
        raise HTTPException(400, "无效的事件 ID")

    # 加载 Event + 关联数据
    stmt = (
        select(Event)
        .where(Event.id == uid)
        .options(
            selectinload(Event.sources),
            selectinload(Event.rumor_report),
            selectinload(Event.timeline_nodes),
        )
    )
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()

    if not event:
        raise HTTPException(404, "事件不存在")

    # 构建 HTML 报告
    html = _build_report_html(event)

    # 尝试 PDF 渲染
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html).write_pdf()
        filename = f"truthtrace_report_{event_id[:8]}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
            },
        )
    except ImportError:
        logger.debug("WeasyPrint not installed, returning HTML")
    except Exception as e:
        logger.warning(f"PDF generation failed: {e}, falling back to HTML")

    # Fallback: 返回 HTML
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
    )


def _build_report_html(event: Event) -> str:
    """构建溯源报告 HTML"""
    rumor = event.rumor_report
    sources = event.sources or []
    timeline = event.timeline_nodes or []

    keywords_str = ", ".join(event.keywords) if event.keywords else "无"
    verdict_cn = {
        "false": "虚假信息 🚫",
        "misleading": "误导性信息 ⚠️",
        "unverified": "待验证 ❓",
        "true": "真实信息 ✅",
    }.get(rumor.verdict if rumor else "", "未判定")

    cred_color = (
        "#16a34a" if event.credibility_score >= 70 else
        "#ca8a04" if event.credibility_score >= 40 else
        "#dc2626"
    )

    original_sources = [s for s in sources if s.is_original]
    timeline_html = ""
    for tn in sorted(timeline, key=lambda x: x.timestamp if x.timestamp else datetime.min):
        timeline_html += f"""
        <tr>
          <td>{tn.timestamp.strftime('%Y-%m-%d %H:%M') if tn.timestamp else '未知'}</td>
          <td>{tn.description}</td>
          <td>{'⭐⭐' if tn.significance > 1 else '⭐'}</td>
        </tr>"""

    sources_html = ""
    for s in sources[:50]:
        original_badge = '<span style="background:#fbbf24;color:#000;padding:1px 6px;border-radius:4px;font-size:11px;">🎯 原始来源</span>' if s.is_original else ""
        sources_html += f"""
        <tr>
          <td>{s.platform.value if s.platform else '?'}</td>
          <td><a href="{s.url}">{s.title or s.url[:60]}</a></td>
          <td>{s.author or '-'}</td>
          <td>{s.authority_score:.0f}</td>
          <td>{original_badge}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>溯源报告 — {event.title}</title>
<style>
  body {{ font-family: 'Noto Sans SC', 'Microsoft YaHei', sans-serif; max-width: 900px; margin: 0 auto; padding: 40px 20px; color: #1a1a2e; }}
  h1 {{ font-size: 28px; border-bottom: 3px solid #2563eb; padding-bottom: 12px; }}
  h2 {{ font-size: 20px; margin-top: 32px; color: #2563eb; }}
  .meta {{ display: flex; gap: 20px; margin: 16px 0; flex-wrap: wrap; }}
  .badge {{ padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; }}
  .cred-score {{ font-size: 32px; font-weight: bold; color: {cred_color}; }}
  table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
  th, td {{ padding: 8px 12px; border: 1px solid #e5e7eb; text-align: left; font-size: 14px; }}
  th {{ background: #f9fafb; font-weight: 600; }}
  a {{ color: #2563eb; }}
  .footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid #e5e7eb; color: #9ca3af; font-size: 12px; }}
</style>
</head>
<body>
  <h1>📋 事件溯源报告</h1>

  <h2>{event.title}</h2>
  <p>{event.summary or '（无摘要）'}</p>

  <div class="meta">
    <div>
      <div style="font-size:12px;color:#6b7280;">可信度评分</div>
      <div class="cred-score">{event.credibility_score:.0f}/100</div>
    </div>
    <div>
      <div style="font-size:12px;color:#6b7280;">信息来源</div>
      <div style="font-size:24px;font-weight:bold;">{len(sources)}</div>
    </div>
    <div>
      <div style="font-size:12px;color:#6b7280;">首次发现</div>
      <div>{event.first_seen_at.strftime('%Y-%m-%d %H:%M') if event.first_seen_at else '未知'}</div>
    </div>
    <div>
      <div style="font-size:12px;color:#6b7280;">状态</div>
      <div class="badge" style="background:#dbeafe;color:#1e40af;">{event.status.value if event.status else '?'}</div>
    </div>
  </div>

  <p><strong>关键词:</strong> {keywords_str}</p>

  {"<h2>🔍 辟谣判定</h2>" if rumor else ""}
  {f'''
  <div class="meta">
    <div class="badge" style="background:#fef2f2;color:#991b1b;">判定: {verdict_cn}</div>
  </div>
  <p><strong>谣言声称:</strong> {rumor.rumor_claim}</p>
  <p><strong>核查结果:</strong> {rumor.fact_check_result}</p>
  <p><strong>纠正建议:</strong> {rumor.correction or "无"}</p>
  ''' if rumor else ""}

  <h2>🎯 原始/权威来源 ({len(original_sources)})</h2>
  {'<table><tr><th>平台</th><th>链接</th><th>作者</th><th>权威度</th></tr>' + ''.join(f'<tr><td>{s.platform.value if s.platform else "?"}</td><td><a href="{s.url}">{s.title or s.url[:60]}</a></td><td>{s.author or "-"}</td><td>{s.authority_score:.0f}</td></tr>' for s in original_sources[:10]) + '</table>' if original_sources else '<p>未发现明确的原始来源</p>'}

  <h2>⏱️ 事件时间线</h2>
  {'<table><tr><th>时间</th><th>事件</th><th>重要性</th></tr>' + timeline_html + '</table>' if timeline_html else '<p>暂无时间线数据</p>'}

  <h2>🌐 所有来源 ({len(sources)})</h2>
  {'<table><tr><th>平台</th><th>链接</th><th>作者</th><th>权威度</th><th>标记</th></tr>' + sources_html + '</table>' if sources_html else '<p>暂无来源数据</p>'}

  <div class="footer">
    <p>由 <strong>TruthTrace</strong> 自动生成 | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
    <p>本报告由算法自动生成，仅供参考。重要判断请结合人工审核。</p>
  </div>
</body>
</html>"""
