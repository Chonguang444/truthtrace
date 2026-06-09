"""
邮件通知服务 — SMTP + HTML 模板 + 退订

依赖: aiosmtplib (pip install aiosmtplib)
"""

from __future__ import annotations
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional

logger = logging.getLogger("truthtrace.email")


# =============================================================================
# 邮件配置
# =============================================================================

def _get_smtp_config() -> dict:
    import os
    return {
        "host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "username": os.environ.get("SMTP_USERNAME", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from_address": os.environ.get("SMTP_FROM", "TruthTrace <noreply@truthtrace.app>"),
    }


# =============================================================================
# HTML 邮件模板
# =============================================================================

def _render_event_notification(event_title: str, verdict: str, score: float,
                               event_id: str, correction: str = "", base_url: str = "http://localhost:5173") -> str:
    """事件更新通知邮件模板"""
    score_color = "#16a34a" if score >= 60 else "#ca8a04" if score >= 40 else "#dc2626"
    verdict_icon = "🛡️" if score >= 60 else "⚠️" if score >= 40 else "🚨"

    verdict_labels = {
        "true": "真实信息", "likely_true": "可能真实", "misleading": "误导性信息",
        "likely_false": "可能虚假", "false": "虚假信息", "unverifiable": "无法验证",
    }

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="font-family:'Noto Sans SC','Microsoft YaHei',sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#1a1a2e;background:#f9fafb;">
  <div style="background:linear-gradient(135deg,#2563eb,#1d4ed8);color:white;padding:20px;border-radius:12px 12px 0 0;text-align:center;">
    <h1 style="margin:0;font-size:20px;">🛡️ TruthTrace</h1>
    <p style="margin:4px 0 0;opacity:0.85;font-size:13px;">你的订阅事件有更新</p>
  </div>
  <div style="background:white;padding:24px;border-radius:0 0 12px 12px;">
    <p style="font-size:15px;margin:0 0 16px;">你关注的事件有了新的分析结果:</p>
    <h2 style="font-size:18px;margin:0 0 12px;">{event_title}</h2>
    <div style="display:inline-block;padding:12px 20px;background:#f9fafb;border-radius:8px;margin-bottom:16px;">
      <div style="font-size:28px;font-weight:800;color:{score_color};">{score}<span style="font-size:14px;font-weight:400">/100</span></div>
      <div style="font-size:13px;color:#6b7280;margin-top:2px;">{verdict_icon} {verdict_labels.get(verdict, verdict)}</div>
    </div>
    {f'<div style="padding:12px;background:#fef2f2;border-left:3px solid #dc2626;border-radius:4px;margin-bottom:16px;"><p style="margin:0;font-size:13px;color:#991b1b;">{correction[:300]}</p></div>' if correction else ''}
    <a href="{base_url}/events/{event_id}" style="display:inline-block;padding:10px 20px;background:#2563eb;color:white;text-decoration:none;border-radius:8px;font-weight:600;font-size:13px;">查看完整分析 →</a>
  </div>
  <div style="text-align:center;padding:16px;font-size:11px;color:#9ca3af;">
    <p>此邮件由 TruthTrace 自动发送。要取消订阅，请登录后进入个人设置管理。</p>
  </div>
</body>
</html>"""


def _render_narrative_alert_email(alert_title: str, alert_desc: str, base_url: str = "http://localhost:5173") -> str:
    """叙事告警通知邮件"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"></head>
<body style="font-family:'Noto Sans SC',sans-serif;max-width:600px;margin:0 auto;padding:20px;">
  <div style="background:#fef2f2;padding:20px;border-radius:12px;border:2px solid #fecaca;">
    <h2 style="color:#991b1b;margin:0 0 12px;">🚨 叙事告警</h2>
    <h3 style="margin:0 0 8px;">{alert_title}</h3>
    <p style="color:#7f1d1d;font-size:14px;">{alert_desc}</p>
    <a href="{base_url}/search" style="display:inline-block;margin-top:12px;padding:8px 16px;background:#dc2626;color:white;text-decoration:none;border-radius:6px;font-weight:600;">查看详情 →</a>
  </div>
</body>
</html>"""


# =============================================================================
# 发送邮件
# =============================================================================

async def send_email(to: str, subject: str, html_body: str) -> bool:
    """通过 SMTP 发送邮件"""
    config = _get_smtp_config()
    if not config["username"] or not config["password"]:
        logger.debug("SMTP 未配置，跳过邮件发送")
        return False

    try:
        import aiosmtplib
        msg = MIMEMultipart("alternative")
        msg["From"] = config["from_address"]
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        await aiosmtplib.send(
            msg,
            hostname=config["host"],
            port=config["port"],
            username=config["username"],
            password=config["password"],
            start_tls=True,
        )
        logger.info(f"邮件已发送: {to} ({subject})")
        return True
    except ImportError:
        logger.debug("aiosmtplib 未安装，跳过邮件发送")
        return False
    except Exception as e:
        logger.warning(f"邮件发送失败 ({to}): {e}")
        return False


# =============================================================================
# 便捷方法
# =============================================================================

async def notify_user_by_email(
    email: str,
    event_title: str,
    verdict: str,
    score: float,
    event_id: str,
    correction: str = "",
):
    """向用户发送事件更新通知邮件"""
    html = _render_event_notification(event_title, verdict, score, event_id, correction)
    subject = f"[TruthTrace] 事件更新: {event_title[:30]}..."
    return await send_email(email, subject, html)


async def notify_narrative_alert_by_email(
    email: str,
    alert_title: str,
    alert_desc: str,
):
    """向用户发送叙事告警通知邮件"""
    html = _render_narrative_alert_email(alert_title, alert_desc)
    subject = f"[TruthTrace] 叙事告警: {alert_title[:30]}..."
    return await send_email(email, subject, html)
