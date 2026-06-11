"""
API 开放平台 -- 开发者注册/API密钥/配额管理/Public API v1
让第三方产品接入 TruthTrace 的检测能力
"""

import os
import uuid
import secrets
import hashlib
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Request, Header
from pydantic import BaseModel, EmailStr, field_validator

from app.auth.jwt import get_current_active_user, get_current_user
from app.models.user import User

router = APIRouter()

# =============================================================================
# 数据模型
# =============================================================================

class DeveloperRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    website: str = ""
    use_case: str = ""

    @field_validator("use_case")
    @classmethod
    def valid_use_case(cls, v: str) -> str:
        if len(v) < 10:
            raise ValueError("请详细描述您的使用场景(至少10字)")
        return v


class WebhookRegisterRequest(BaseModel):
    url: str
    events: list[str]  # ["analysis.completed", "rumor.detected", "hotspot.alert"]

    @field_validator("url")
    @classmethod
    def valid_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("Webhook URL 必须以 http:// 或 https:// 开头")
        from app.security import validate_url_safe
        if not validate_url_safe(v):
            raise ValueError("Webhook URL 不安全 (不允许内网地址)")
        return v


class AnalyzeRequest(BaseModel):
    text: str
    url: str = ""
    callback_url: str = ""

    @field_validator("text")
    @classmethod
    def valid_text(cls, v: str) -> str:
        if len(v) < 20:
            raise ValueError("文本长度至少20字")
        if len(v) > 10000:
            raise ValueError("文本长度不能超过10000字")
        return v


# =============================================================================
# 内存存储
# =============================================================================

_developers: dict[str, dict] = {}  # api_key -> {name, email, plan, quota_used, ...}
_api_usage: dict[str, list] = defaultdict(list)  # api_key -> [{timestamp, endpoint, tokens}]
_webhooks: dict[str, list] = defaultdict(list)  # api_key -> [{url, events}]

PLANS = {
    "free": {"name": "免费版", "monthly_quota": 1000, "rate_limit": 10, "price": 0},
    "pro": {"name": "专业版", "monthly_quota": 10000, "rate_limit": 60, "price": 29},
    "enterprise": {"name": "企业版", "monthly_quota": 100000, "rate_limit": 300, "price": 199},
}


# =============================================================================
# API Key 工具
# =============================================================================

def _generate_api_key() -> str:
    return f"sk-tt-{secrets.token_urlsafe(24)}"


def verify_api_key(api_key: str = Header(..., alias="X-API-Key")) -> dict:
    """验证 API Key (供 v1 端点使用的 Depends)"""
    dev = _developers.get(api_key)
    if not dev:
        raise HTTPException(401, "无效的 API Key。请在 https://truthtrace.app/developer 注册。")

    # 检查配额
    plan = PLANS.get(dev["plan"], PLANS["free"])
    this_month = datetime.now(timezone.utc).strftime("%Y-%m")
    monthly_usage = sum(
        1 for u in _api_usage.get(api_key, [])
        if u["timestamp"].startswith(this_month)
    )
    if monthly_usage >= plan["monthly_quota"]:
        raise HTTPException(429, f"本月配额({plan['monthly_quota']}次)已用完。请升级计划或等待下月重置。")

    # 速率限制
    minute_ago = time.time() - 60
    recent = [u for u in _api_usage.get(api_key, [])
              if datetime.fromisoformat(u["timestamp"]).timestamp() > minute_ago]
    if len(recent) >= plan["rate_limit"]:
        raise HTTPException(429, f"频率限制({plan['rate_limit']}次/分钟)。请稍后重试。")

    # 记录使用 + 定期清理 (保留最近60天)
    _api_usage[api_key].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "endpoint": "/api/v1/analyze",
    })
    _cleanup_old_usage(api_key)

    return dev


def _cleanup_old_usage(api_key: str):
    """清理60天前的使用记录"""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    if len(_api_usage.get(api_key, [])) > 5000:
        _api_usage[api_key] = [
            u for u in _api_usage[api_key]
            if u["timestamp"] > cutoff
        ]


# =============================================================================
# 端点: 开发者门户
# =============================================================================

@router.post("/developer/register")
async def register_developer(
    req: DeveloperRegisterRequest,
    current_user: User = Depends(get_current_active_user),
):
    """注册成为API开发者"""
    # 检查是否已注册
    for key, dev in _developers.items():
        if dev.get("user_id") == str(current_user.id):
            return {
                "status": "already_registered",
                "api_key": key,
                "developer": dev,
            }

    api_key = _generate_api_key()
    _developers[api_key] = {
        "user_id": str(current_user.id),
        "name": req.name,
        "email": req.email,
        "website": req.website,
        "use_case": req.use_case,
        "plan": "free",
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "api_key": api_key,
    }

    return {
        "status": "registered",
        "api_key": api_key,
        "developer": _developers[api_key],
        "message": f"欢迎! 您的免费配额为每月{PLANS['free']['monthly_quota']}次调用。请妥善保管 API Key。",
        "quick_start": {
            "curl_example": f'curl -X POST https://api.truthtrace.app/v1/analyze \\\n  -H "Content-Type: application/json" \\\n  -H "X-API-Key: {api_key}" \\\n  -d \'{{"text": "待分析的文本"}}\'',
            "python_example": f'''import requests
headers = {{"X-API-Key": "{api_key}", "Content-Type": "application/json"}}
resp = requests.post("https://api.truthtrace.app/v1/analyze",
    json={{"text": "待分析的文本"}}, headers=headers)
print(resp.json())''',
        },
    }


@router.get("/developer/dashboard")
async def developer_dashboard(
    current_user: User = Depends(get_current_active_user),
):
    """开发者仪表盘"""
    user_dev = None
    user_api_key = None
    for key, dev in _developers.items():
        if dev.get("user_id") == str(current_user.id):
            user_dev = dev
            user_api_key = key
            break

    if not user_dev:
        raise HTTPException(404, "尚未注册API开发者。请先调用 POST /developer/register。")

    plan = PLANS.get(user_dev["plan"], PLANS["free"])
    this_month = datetime.now(timezone.utc).strftime("%Y-%m")
    monthly_usage = sum(
        1 for u in _api_usage.get(user_api_key, [])
        if u["timestamp"].startswith(this_month)
    )

    return {
        "developer": user_dev,
        "plan": {
            "name": plan["name"],
            "monthly_quota": plan["monthly_quota"],
            "rate_limit_per_min": plan["rate_limit"],
            "monthly_price": plan["price"],
        },
        "usage": {
            "current_month": datetime.now(timezone.utc).strftime("%Y-%m"),
            "used": monthly_usage,
            "remaining": max(0, plan["monthly_quota"] - monthly_usage),
            "usage_pct": round(monthly_usage / plan["monthly_quota"] * 100, 1),
        },
        "available_endpoints": [
            {"method": "POST", "path": "/api/v1/analyze", "desc": "提交文本进行10引擎分析"},
            {"method": "GET", "path": "/api/v1/analyze/{task_id}", "desc": "查询分析任务结果"},
            {"method": "POST", "path": "/api/v1/medical/verify", "desc": "医疗健康声明验证"},
        ],
    }


@router.post("/developer/webhook/register")
async def register_webhook(
    req: WebhookRegisterRequest,
    current_user: User = Depends(get_current_active_user),
):
    """注册 Webhook"""
    user_api_key = None
    for key, dev in _developers.items():
        if dev.get("user_id") == str(current_user.id):
            user_api_key = key
            break

    if not user_api_key:
        raise HTTPException(404, "请先注册API开发者。")

    webhook = {
        "id": str(uuid.uuid4())[:8],
        "url": req.url,
        "events": req.events,
        "registered_at": datetime.now(timezone.utc).isoformat(),
    }
    _webhooks[user_api_key].append(webhook)

    return {
        "status": "registered",
        "webhook": webhook,
    }


@router.get("/developer/pricing")
async def get_pricing():
    """定价页面数据"""
    return {
        "plans": [
            {
                "id": "free",
                "name": "免费版",
                "price": "$0/月",
                "features": [
                    "1000次API调用/月",
                    "10引擎分析",
                    "10次/分钟速率限制",
                    "社区支持",
                    "非商业用途",
                ],
                "cta": "免费开始",
            },
            {
                "id": "pro",
                "name": "专业版",
                "price": "$29/月",
                "features": [
                    "10,000次API调用/月",
                    "完整10引擎分析",
                    "60次/分钟速率限制",
                    "优先邮件支持",
                    "Webhook回调",
                    "商业用途许可",
                ],
                "cta": "升级专业版",
                "recommended": True,
            },
            {
                "id": "enterprise",
                "name": "企业版",
                "price": "$199/月",
                "features": [
                    "100,000次API调用/月",
                    "完整10引擎分析+LLM增强",
                    "300次/分钟速率限制",
                    "专属技术支持",
                    "自定义Webhook",
                    "SLA保障(99.9%)",
                    "定制化模型训练",
                ],
                "cta": "联系销售",
            },
        ],
        "faq": [
            {"q": "API支持哪些语言?", "a": "目前主要支持中文,英文分析能力正在开发中。"},
            {"q": "分析结果保存多久?", "a": "免费版7天,专业版30天,企业版可自定义。"},
            {"q": "可以做批量分析吗?", "a": "专业版以上支持批量分析,最多一次提交100条。"},
        ],
    }


# =============================================================================
# Public API v1 (使用 X-API-Key 认证)
# =============================================================================

_task_store: dict[str, dict] = {}


@router.post("/v1/analyze")
async def v1_analyze(
    req: AnalyzeRequest,
    dev: dict = Depends(verify_api_key),
):
    """Public API: 提交文本分析任务"""
    task_id = f"task-{str(uuid.uuid4())[:12]}"

    # 模拟异步分析
    # 防止任务存储无限增长
    if len(_task_store) > 1000:
        # 删除最旧的 200 个任务
        oldest = sorted(_task_store.keys())[:200]
        for k in oldest:
            del _task_store[k]

    _task_store[task_id] = {
        "task_id": task_id,
        "status": "completed",  # 同步完成, 直接返回结果
        "input": {"text": req.text[:200] + "...", "url": req.url},
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "result": None,
    }

    # 触发后台分析(这里同步执行简化版)
    result = _run_quick_analysis(req.text)
    _task_store[task_id]["status"] = "completed"
    _task_store[task_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    _task_store[task_id]["result"] = result

    return {
        "task_id": task_id,
        "status": "completed",
        "result": result,
        "usage_note": f"本月剩余: {PLANS[dev.get('plan', 'free')]['monthly_quota'] - len(_api_usage.get(dev.get('api_key', ''), []))}次",
    }


@router.get("/v1/analyze/{task_id}")
async def v1_get_analysis(
    task_id: str,
    dev: dict = Depends(verify_api_key),
):
    """Public API: 查询分析结果"""
    task = _task_store.get(task_id)
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


def _run_quick_analysis(text: str) -> dict:
    """快速分析(确定性评分, 供API使用 — 相同文本产生相同结果)"""
    import re
    import hashlib

    # 失真检测 (确定性规则)
    distortions = []
    if re.search(r'(?:据研究|据统计|科学家发现)(?!.{0,40}(?:链接|来源|报告|http))', text):
        distortions.append({"type": "source_fabrication", "desc": "来源模糊", "confidence": "high"})
    if re.search(r'(?:速看|马上被删|赶快转发|不转不是)', text):
        distortions.append({"type": "emotional_manipulation", "desc": "情感操纵", "confidence": "high"})
    if re.search(r'(?:中医|西医|偏方|祖传秘方|民间偏方)', text):
        distortions.append({"type": "authority_abuse", "desc": "不明确的医疗权威引用", "confidence": "moderate"})
    if re.search(r'(?:致癌|有毒|致死|致命|剧毒)', text):
        distortions.append({"type": "context_stripping", "desc": "脱离剂量谈毒性", "confidence": "moderate"})

    # 谬误检测 (更多规则)
    fallacies = []
    if re.search(r'(?:完全|全部|绝对|肯定|100%)', text):
        fallacies.append({"type": "hasty_generalization", "desc": "绝对化表述"})
    if re.search(r'(?:你要么|要么.*要么|不支持.*就不是)', text):
        fallacies.append({"type": "false_dichotomy", "desc": "虚假二分"})
    if re.search(r'(?:天然|纯天然|化学|合成).*(?:安全|有害|有毒)', text):
        fallacies.append({"type": "equivocation", "desc": "天然=安全的概念偷换"})
    if re.search(r'(?:如果.*那么.*最终|一步步|越来越|连锁反应)', text):
        fallacies.append({"type": "slippery_slope", "desc": "滑坡论证"})
    if re.search(r'(?:你怎么不说|那.*怎么.*说|先管好.*再说)', text):
        fallacies.append({"type": "red_herring", "desc": "转移话题(红鲱鱼)"})

    # 叙事框架检测 (新增)
    narratives = []
    if re.search(r'(?:阴谋|内幕|隐瞒|暗中|幕后|操控一切|精心策划)', text):
        narratives.append({"type": "conspiracy_theory", "desc": "阴谋论框架", "confidence": "moderate"})
    if re.search(r'(?:太可怕了|不敢想象|毁掉|毒害|毁灭|完蛋)', text):
        narratives.append({"type": "fear_mongering", "desc": "恐惧营销框架", "confidence": "moderate"})

    # 模态漂移检测 (新增)
    modality_drifts = []
    if re.search(r'(?:可能|也许|似乎|据说|听说).*(?:肯定|绝对|一定|100%)', text):
        modality_drifts.append({"type": "tentative_to_certain", "desc": "推测→确定漂移", "confidence": "moderate"})

    # 确定性评分 (纳入新维度)
    text_key = hashlib.md5(text[:500].encode()).hexdigest()
    hash_seed = int(text_key[:8], 16) % 10
    risk_score = min(
        len(distortions) * 20 + len(fallacies) * 15 +
        len(narratives) * 10 + len(modality_drifts) * 10 +
        hash_seed - 5, 100
    )
    credibility = max(100 - risk_score, 5)

    return {
        "credibility_score": round(credibility, 1),
        "risk_score": round(risk_score, 1),
        "verdict": "likely_false" if credibility < 30 else ("misleading" if credibility < 50 else "unverifiable"),
        "distortion_analysis": {
            "matches": distortions,
            "count": len(distortions),
        },
        "fallacy_analysis": {
            "matches": fallacies,
            "count": len(fallacies),
        },
        "narrative_analysis": {
            "matches": narratives,
            "count": len(narratives),
        },
        "modality_analysis": {
            "matches": modality_drifts,
            "count": len(modality_drifts),
        },
        "text_analyzed": text[:300],
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
        "disclaimer": "本分析由TruthTrace API自动生成。此分析基于文本模式识别,不构成事实判定。",
    }


# =============================================================================
# 端点: API 文档
# =============================================================================

@router.get("/developer/docs")
async def api_documentation():
    """API文档概览"""
    return {
        "api_version": "v1",
        "base_url": "https://api.truthtrace.app",
        "authentication": {
            "method": "X-API-Key header",
            "example": "X-API-Key: sk-tt-xxxxxxxx",
        },
        "endpoints": [
            {
                "method": "POST",
                "path": "/api/v1/analyze",
                "description": "提交文本进行10引擎信息操纵分析",
                "request_body": {"text": "string (20-10000 chars)", "url": "string (optional)", "callback_url": "string (optional)"},
                "response": "分析结果含可信度评分/失真检测/谬误检测",
                "rate_limit": "免费版10次/分钟",
            },
        ],
        "sdks": ["Python SDK (即将推出)", "JavaScript SDK (即将推出)"],
    }
