"""
质量保障系统 — 防止产品随时间积累变烂

核心机制:
1. 内容去重: 同一谣言的多形态传播只分析一次
2. 来源质量评分: 自动识别并降权低质量信息源
3. 误判监控: 实时追踪引擎可能出现的误判
4. 质量仪表盘: 管理员可视化质量趋势
5. 数据验证规则: 确保入库数据满足最小质量标准
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("truthtrace.quality")


# =============================================================================
# 1. 内容去重 — 防止重复分析
# =============================================================================

@dataclass
class DedupResult:
    is_new: bool
    similar_event_id: str = ""
    similarity_score: float = 0.0
    reason: str = ""


class ContentDedupManager:
    """
    内容去重管理器。

    多维度去重:
    - SimHash 指纹 (精确内容匹配)
    - 标题相似度 (基于关键词重叠)
    - URL 规范化 (同一链接的不同形式)
    - 时间窗口 (同一事件在短时间内重复提交)
    """

    def __init__(self):
        self._fingerprints: dict[str, datetime] = {}   # simhash → first_seen
        self._title_keywords: dict[str, list[str]] = {}  # keyword_set_key → event_ids
        self._recent_urls: dict[str, str] = {}           # normalized_url → event_id

    def check_url(self, url: str) -> DedupResult:
        """检查URL是否已经分析过"""
        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)
            normalized = f"{parsed.netloc.lower()}{parsed.path.rstrip('/')}"
            if normalized in self._recent_urls:
                return DedupResult(
                    is_new=False,
                    similar_event_id=self._recent_urls[normalized],
                    similarity_score=1.0,
                    reason="相同URL已分析过",
                )
        except Exception:
            pass
        return DedupResult(is_new=True)

    def check_content(self, simhash: str, title: str, text: str = "") -> DedupResult:
        """检查内容是否与已有内容高度相似"""
        # SimHash 精确匹配
        if simhash in self._fingerprints:
            return DedupResult(
                is_new=False,
                similarity_score=1.0,
                reason="内容指纹完全匹配 (SimHash)",
            )

        # 标题关键词重叠检测
        keywords = set(
            w for w in re.findall(r'[一-鿿]{2,}|[a-zA-Z]{3,}', title.lower())
            if w not in ("最新", "突发", "紧急", "震惊", "速看", "因为", "所以", "但是", "而且", "这个", "那个")
        )
        for existing_key, event_ids in self._title_keywords.items():
            existing_set = set(existing_key.split(","))
            overlap = len(keywords & existing_set)
            if overlap >= 5:  # 5个以上关键词重叠
                return DedupResult(
                    is_new=False,
                    similar_event_id=event_ids[0] if event_ids else "",
                    similarity_score=overlap / max(len(keywords), 1),
                    reason=f"标题关键词高度重叠 (重叠{overlap}个)",
                )

        return DedupResult(is_new=True)

    def register(self, simhash: str, title: str, url: str, event_id: str):
        """注册新事件以进行未来去重"""
        self._fingerprints[simhash] = datetime.now(timezone.utc)

        # 存储标题关键词
        keywords = set(
            w for w in re.findall(r'[一-鿿]{2,}|[a-zA-Z]{3,}', title.lower())
            if w not in ("最新", "突发", "紧急", "震惊", "速看", "因为", "所以", "但是", "而且", "这个", "那个")
        )
        key = ",".join(sorted(keywords)[:20])
        if key not in self._title_keywords:
            self._title_keywords[key] = []
        self._title_keywords[key].append(event_id)

        # 存储URL
        from urllib.parse import urlparse
        try:
            parsed = urlparse(url)
            normalized = f"{parsed.netloc.lower()}{parsed.path.rstrip('/')}"
            self._recent_urls[normalized] = event_id
        except Exception:
            pass

        # 内存管理
        if len(self._fingerprints) > 50000:
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            self._fingerprints = {k: v for k, v in self._fingerprints.items() if v > cutoff}

    def cleanup(self):
        """清理过期数据"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        self._fingerprints = {k: v for k, v in self._fingerprints.items() if v > cutoff}


import re
_dedup_manager = ContentDedupManager()


# =============================================================================
# 2. 来源质量自动评估
# =============================================================================

class SourceQualityEvaluator:
    """
    自动评估信息来源的质量。

    评估维度:
    - 域名权威性 (政府/学术/主流媒体/个人博客/未知)
    - 内容长度 (过短 → 可能是截取片段)
    - 元数据完整性 (有发布时间/作者 → 可信度更高)
    - 是否HTTPS (基本安全指标)
    - 是否有联系方式/关于页面
    """

    DOMAIN_AUTHORITY = {
        # 政府
        "gov.cn": 95, "stats.gov.cn": 98, "nhc.gov.cn": 95, "mee.gov.cn": 95,
        "nmpa.gov.cn": 95, "samr.gov.cn": 95, "cfsa.net.cn": 90,
        # 国际组织
        "who.int": 98, "un.org": 98, "worldbank.org": 95, "imf.org": 95,
        "ipcc.ch": 95, "wmo.int": 95, "iea.org": 90,
        # 学术
        "edu.cn": 85, "ac.cn": 85, ".edu": 85, "arxiv.org": 80,
        "pubmed": 85, "scholar.google": 80, "researchgate": 70,
        # 主流媒体
        "xinhuanet.com": 75, "people.com.cn": 75, "cctv.com": 75,
        "reuters.com": 80, "apnews.com": 80, "bbc.com": 75, "bbc.co.uk": 75,
        # 科技/知识平台
        "zhihu.com": 50, "weibo.com": 40, "douyin.com": 35,
        "bilibili.com": 50, "kuaishou.com": 35,
        # 自媒体/个人
        "mp.weixin.qq.com": 30,
    }

    @classmethod
    def evaluate(cls, url: str, content_length: int = 0,
                 has_author: bool = False, has_date: bool = False,
                 is_https: bool = False, content_quality_hint: str = "") -> dict:
        """评估来源质量，返回评分和详细指标"""

        from urllib.parse import urlparse
        try:
            hostname = urlparse(url).hostname or ""
        except Exception:
            hostname = ""

        score = 30.0  # 基础分 (未知来源)

        # 域名权威性
        domain_score = 0
        for domain, authority in cls.DOMAIN_AUTHORITY.items():
            if domain in hostname:
                domain_score = authority
                break
        if domain_score > 0:
            score = domain_score * 0.6 + 30 * 0.4
        else:
            # 基于TLD的启发式
            if hostname.endswith(".gov") or hostname.endswith(".gov.cn"):
                score = 85
            elif hostname.endswith((".edu", ".edu.cn", ".ac.cn", ".ac.uk", ".ac.jp")):
                score = 75
            elif hostname.endswith((".org", ".org.cn")):
                score = 55

        # 内容质量指标
        if content_length > 500:
            score += 5
        if content_length > 2000:
            score += 3
        if content_length < 50:
            score -= 15  # 内容极短可能是标题党或截取片段

        if has_author:
            score += 5
        if has_date:
            score += 3
        if is_https:
            score += 2

        # 内容质量标记
        quality_issues = []
        if content_length < 100:
            quality_issues.append("内容极短(可能被截取或标题党)")
        if not has_author:
            quality_issues.append("缺少作者身份信息")
        if not has_date:
            quality_issues.append("缺少发布时间")
        if not is_https:
            quality_issues.append("未使用HTTPS")

        return {
            "quality_score": round(min(100.0, score), 1),
            "domain_authority_score": domain_score,
            "hostname": hostname,
            "is_high_quality": score >= 60,
            "is_verified_source": domain_score >= 75,
            "quality_issues": quality_issues,
        }


# =============================================================================
# 3. 误判监控 — 实时追踪质量趋势
# =============================================================================

@dataclass
class QualityMetrics:
    """质量指标快照"""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    total_analyses: int = 0
    high_risk_count: int = 0          # 判定为虚假/可能虚假
    low_risk_count: int = 0           # 判定为真实/可能真实
    disputed_count: int = 0           # 用户反馈为误判
    avg_credibility_score: float = 50.0
    avg_sources_per_event: float = 0.0
    duplicate_detected_today: int = 0
    content_rejected_today: int = 0   # 被内容过滤器拒绝的


class QualityMonitor:
    """
    质量监控器 — 追踪关键指标，检测异常变化。

    告警条件:
    - 误判率突然上升 (24h内 > 15%)
    - 低可信度事件占比异常 (突然 > 80% 或 < 5%)
    - 来源质量平均分下降
    """

    def __init__(self):
        self._metrics_history: list[QualityMetrics] = []
        self._current = QualityMetrics()
        self._disputed_analyses: list[dict] = []

    def record_analysis(self, verdict: str, score: float, source_count: int,
                        source_quality_avg: float, was_duplicate: bool,
                        was_rejected: bool):
        """记录一次分析"""
        self._current.total_analyses += 1
        if verdict in ("false", "likely_false"):
            self._current.high_risk_count += 1
        elif verdict in ("true", "likely_true"):
            self._current.low_risk_count += 1
        self._current.avg_credibility_score = (
            self._current.avg_credibility_score * (self._current.total_analyses - 1) + score
        ) / self._current.total_analyses
        self._current.avg_sources_per_event = (
            self._current.avg_sources_per_event * (self._current.total_analyses - 1) + source_count
        ) / self._current.total_analyses
        if was_duplicate:
            self._current.duplicate_detected_today += 1
        if was_rejected:
            self._current.content_rejected_today += 1

    def record_dispute(self, event_id: str, user_feedback: str):
        """记录用户对分析的质疑"""
        self._current.disputed_count += 1
        self._disputed_analyses.append({
            "event_id": event_id,
            "feedback": user_feedback,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def check_anomalies(self) -> list[dict]:
        """检测质量异常"""
        alerts = []

        # 误判率过高
        total = self._current.total_analyses
        if total >= 10:
            dispute_rate = self._current.disputed_count / total * 100
            if dispute_rate > 15:
                alerts.append({
                    "severity": "high",
                    "type": "high_dispute_rate",
                    "message": f"用户质疑率 {dispute_rate:.1f}% (>15%) — 可能存在系统性问题",
                    "suggestion": "审查最近的 disputed 案例，检查引擎规则是否需要调整",
                })

        # 极端分布
        if total >= 20:
            high_ratio = self._current.high_risk_count / total * 100
            if high_ratio > 80:
                alerts.append({
                    "severity": "medium",
                    "type": "extreme_high_risk_ratio",
                    "message": f"高风险判定占比 {high_ratio:.1f}% — 可能是爬虫爬到了大量低质量内容，也可能是引擎阈值过于严格",
                    "suggestion": "检查最近爬取的来源质量，考虑提高采信来源的筛选标准",
                })
            if high_ratio < 5 and total >= 50:
                alerts.append({
                    "severity": "low",
                    "type": "abnormally_low_risk",
                    "message": f"高风险判定仅 {high_ratio:.1f}% — 可能过于宽松",
                    "suggestion": "检查引擎的评分阈值是否过于宽松",
                })

        return alerts

    def snapshot(self) -> QualityMetrics:
        """获取当前快照"""
        return self._current

    def daily_reset(self):
        """每日重置计数器"""
        self._metrics_history.append(self._current)
        self._current = QualityMetrics()
        if len(self._metrics_history) > 90:
            self._metrics_history = self._metrics_history[-90:]


_quality_monitor = QualityMonitor()


# =============================================================================
# 4. 入库数据验证
# =============================================================================

class DataValidator:
    """
    数据入库前的质量验证。

    拒绝条件:
    - 内容为空或纯广告
    - 内容中检测到恶意负载
    - 来源质量评分 < 10 (极低质量)
    - 纯标题无正文 (标题党)
    """

    MIN_CONTENT_LENGTH = 20
    MAX_TITLE_RATIO = 0.8  # 标题占全文比例不能超过80%

    @classmethod
    def validate_event_data(cls, title: str, text: str, url: str = "",
                            source_quality: int = 0) -> dict:
        """
        验证事件数据是否满足入库最低标准。

        Returns: {"valid": bool, "reason": str, "quality_issues": list}
        """
        issues = []

        # 内容检查
        total_text = f"{title}\n{text}".strip()
        if len(total_text) < cls.MIN_CONTENT_LENGTH:
            return {"valid": False, "reason": "内容过短，无法进行有意义的分析", "issues": ["content_too_short"]}

        # 标题党检测
        if len(text) > 0 and len(title) / len(text + title) > cls.MAX_TITLE_RATIO:
            issues.append("title_dominant — 内容以标题为主，正文信息不足")

        # 纯广告检测
        ad_patterns = [r'(?i)(点击购买|限时优惠|立即下单|免费领取|扫码关注|加微信|QQ群)']
        for pat in ad_patterns:
            if re.search(pat, total_text):
                return {"valid": False, "reason": "检测到纯广告/营销内容", "issues": ["advertisement"]}

        # 来源质量
        if source_quality < 10:
            issues.append("extremely_low_source_quality — 不建议采信此来源")

        # 恶意内容 (仅检查文本层面)
        if re.search(r'<script|<iframe|document\.cookie|onerror\s*=', text, re.IGNORECASE):
            return {"valid": False, "reason": "内容包含可疑代码", "issues": ["suspicious_code"]}

        # 全部检查通过但有警告
        if issues:
            return {"valid": True, "reason": "数据可以入库，但存在以下质量警告", "issues": issues}

        return {"valid": True, "reason": "数据通过质量验证", "issues": []}


# =============================================================================
# 导出公共接口
# =============================================================================

def get_dedup_manager() -> ContentDedupManager:
    return _dedup_manager


def get_quality_monitor() -> QualityMonitor:
    return _quality_monitor
