"""
实时谣言预警与求真卡推送 — 第15号引擎

对标抖音"AI求真"的主动预警模式:
  1. 多级阈值触发 — 当风险指标超过阈值时自动告警
  2. 求真卡生成 — 可被外部引用的标准化事实核查卡片
  3. 易感人群定向 — 向风险暴露用户精准推送辟谣
  4. 预警分级 — 🔴红色/🟠橙色/🟡黄色/🔵信息

行业参考:
  - 抖音"AI求真卡": 用户浏览疑似不实信息时一键查看事件全貌
  - 南方+辟谣: 从被动补救到主动防控
  - 中国人民大学: "AI压缩谣言生命周期，事实核查需多方共守"

核心原则:
  - 预警不是判定 — "疑似"≠"确认虚假"
  - 每个告警附带完整的证据链
  - 求真卡可独立引用和分享
"""

from __future__ import annotations
import uuid
import hashlib
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger("truthtrace.rumor_alert")


class AlertLevel(str, Enum):
    """告警等级"""
    RED = "red"          # 🔴 极高风险 — 立即阻断
    ORANGE = "orange"    # 🟠 高风险 — 需立即核实
    YELLOW = "yellow"    # 🟡 中等风险 — 保持监测
    BLUE = "blue"        # 🔵 信息提示 — 持续跟踪
    GREEN = "green"      # 🟢 低风险 — 正常传播


@dataclass
class AlertTrigger:
    """触发告警的条件"""
    rule: str                      # 触发规则名称
    value: float                   # 当前值
    threshold: float               # 阈值
    severity: AlertLevel = AlertLevel.YELLOW
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "rule": self.rule, "value": round(self.value, 1),
            "threshold": round(self.threshold, 1),
            "severity": self.severity.value, "description": self.description,
        }


@dataclass
class TruthCard:
    """
    求真卡 — 可被外部引用的标准化事实核查卡片

    对标抖音"求真卡"，用户浏览疑似不实时一键查看:
    - 事件全貌
    - 判定依据
    - 证据来源
    """
    card_id: str = ""
    title: str = ""
    rumor_claim: str = ""           # 原始谣言声称
    verdict: str = ""               # 核实判定
    credibility_score: float = 50.0
    key_evidence: list[str] = field(default_factory=list)
    authoritative_sources: list[str] = field(default_factory=list)
    ai_detection_flag: bool = False
    propagation_risk: str = ""
    correction_message: str = ""
    share_text: str = ""
    related_cards: list[str] = field(default_factory=list)
    generated_at: str = ""
    expires_at: str = ""            # 求真卡有效期（信息会更新）

    def to_dict(self) -> dict:
        return {
            "card_id": self.card_id,
            "title": self.title,
            "rumor_claim": self.rumor_claim,
            "verdict": self.verdict,
            "credibility_score": round(self.credibility_score, 1),
            "key_evidence": self.key_evidence,
            "authoritative_sources": self.authoritative_sources,
            "ai_detection_flag": self.ai_detection_flag,
            "propagation_risk": self.propagation_risk,
            "correction_message": self.correction_message,
            "share_text": self.share_text,
            "related_cards": self.related_cards,
            "generated_at": self.generated_at,
            "expires_at": self.expires_at,
        }


@dataclass
class RumorAlertResult:
    """谣言预警完整结果"""
    alert_level: AlertLevel = AlertLevel.GREEN
    triggers: list[AlertTrigger] = field(default_factory=list)
    truth_card: TruthCard | None = None
    recommended_actions: list[str] = field(default_factory=list)
    vulnerable_groups: list[str] = field(default_factory=list)
    alert_id: str = ""
    generated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "alert_level": self.alert_level.value,
            "triggers": [t.to_dict() for t in self.triggers],
            "truth_card": self.truth_card.to_dict() if self.truth_card else None,
            "recommended_actions": self.recommended_actions,
            "vulnerable_groups": self.vulnerable_groups,
            "alert_id": self.alert_id,
            "generated_at": self.generated_at,
        }


# =============================================================================
# 预警阈值规则
# =============================================================================

ALERT_RULES = [
    # 可信度阈值
    {"rule": "credibility_low", "field": "credibility_score", "threshold": 20,
     "op": "lt", "level": AlertLevel.RED, "desc": "可信度<20 — 极可能是虚假信息，建议立即阻断传播"},
    {"rule": "credibility_medium", "field": "credibility_score", "threshold": 40,
     "op": "lt", "level": AlertLevel.ORANGE, "desc": "可信度<40 — 多项指标触发，需要人工核实"},
    {"rule": "credibility_elevated", "field": "credibility_score", "threshold": 55,
     "op": "lt", "level": AlertLevel.YELLOW, "desc": "可信度<55 — 存在可疑信号，建议保持监测"},

    # 传播速度阈值
    {"rule": "propagation_burst", "field": "propagation_speed_index", "threshold": 20,
     "op": "gt", "level": AlertLevel.RED, "desc": "传播速度>20节点/小时 — 疑似协同推送网络"},
    {"rule": "propagation_fast", "field": "propagation_speed_index", "threshold": 10,
     "op": "gt", "level": AlertLevel.ORANGE, "desc": "传播速度>10 — 超过正常扩散速度"},
    {"rule": "propagation_abnormal", "field": "anomaly_score", "threshold": 60,
     "op": "gt", "level": AlertLevel.ORANGE, "desc": "传播异常度>60 — 时间线不符合有机传播模式"},

    # AI检测阈值
    {"rule": "ai_generated", "field": "ai_risk_score", "threshold": 60,
     "op": "gt", "level": AlertLevel.ORANGE, "desc": "AI生成风险>60 — 内容由AI生成的可能性很高"},
    {"rule": "ai_watermark", "field": "ai_watermark_detected", "threshold": 0.5,
     "op": "gt", "level": AlertLevel.RED, "desc": "检测到AI生成水印 — 确认由AI工具生成"},

    # 操纵评分阈值
    {"rule": "manipulation_high", "field": "manipulation_score", "threshold": 70,
     "op": "gt", "level": AlertLevel.RED, "desc": "操纵性评分>70 — 呈现典型的协同操纵模式"},
    {"rule": "manipulation_elevated", "field": "manipulation_score", "threshold": 50,
     "op": "gt", "level": AlertLevel.ORANGE, "desc": "操纵性评分>50 — 存在有组织的叙事框架"},

    # 失真/谬误数量
    {"rule": "distortion_many", "field": "distortion_count", "threshold": 5,
     "op": "gt", "level": AlertLevel.RED, "desc": "检测到5+处信息失真 — 可能是系统性的误导内容"},
    {"rule": "fallacy_many", "field": "fallacy_count", "threshold": 3,
     "op": "gt", "level": AlertLevel.ORANGE, "desc": "检测到3+处逻辑谬误 — 推理存在结构性缺陷"},
]

# 易感人群画像
VULNERABLE_GROUPS = {
    "health_elderly": {"name": "中老年健康关注者", "domains": ["medicine_health", "food_safety"],
                       "triggers": ["致癌", "偏方", "老中医", "祖传", "养生"]},
    "parent_anxiety": {"name": "家长焦虑群体", "domains": ["education"],
                       "triggers": ["孩子", "学校", "疫苗", "近视", "成绩"]},
    "tech_fear": {"name": "技术恐慌群体", "domains": ["tech"],
                  "triggers": ["5G", "辐射", "AI", "监控", "芯片"]},
    "conspiracy_prone": {"name": "阴谋论倾向者", "domains": ["general"],
                         "triggers": ["真相", "内幕", "不敢说", "被封杀", "秘密"]},
}


# =============================================================================
# 主分析器
# =============================================================================

class RumorAlertEngine:
    """
    谣言预警与求真卡生成引擎

    用法:
        engine = RumorAlertEngine()
        result = engine.evaluate(
            credibility_score=12,
            propagation_speed_index=25,
            ai_risk_score=75,
            ...
        )
    """

    def evaluate(
        self,
        # 可信度
        credibility_score: float = 50.0,
        # 传播
        propagation_speed_index: float = 0.0,
        anomaly_score: float = 0.0,
        coordinated_ratio: float = 0.0,
        # AI检测
        ai_risk_score: float = 0.0,
        ai_watermark_detected: bool = False,
        # 操纵
        manipulation_score: float = 0.0,
        # 失真/谬误
        distortion_count: int = 0,
        fallacy_count: int = 0,
        # 内容
        title: str = "",
        rumor_claim: str = "",
        verdict: str = "unverifiable",
        correction: str = "",
        # 来源
        key_sources: list[str] | None = None,
        authoritative_sources: list[str] | None = None,
        # 领域
        keywords: list[str] | None = None,
        domain: str = "general",
    ) -> RumorAlertResult:

        # 收集所有指标值
        metrics = {
            "credibility_score": credibility_score,
            "propagation_speed_index": propagation_speed_index,
            "anomaly_score": anomaly_score,
            "coordinated_ratio": coordinated_ratio,
            "ai_risk_score": ai_risk_score,
            "ai_watermark_detected": 1.0 if ai_watermark_detected else 0.0,
            "manipulation_score": manipulation_score,
            "distortion_count": distortion_count,
            "fallacy_count": fallacy_count,
        }

        # === 检查触发规则 ===
        triggers = []
        for rule in ALERT_RULES:
            value = metrics.get(rule["field"], 0)
            if rule["op"] == "lt" and value < rule["threshold"]:
                triggers.append(AlertTrigger(
                    rule=rule["rule"], value=value, threshold=rule["threshold"],
                    severity=rule["level"], description=rule["desc"],
                ))
            elif rule["op"] == "gt" and value > rule["threshold"]:
                triggers.append(AlertTrigger(
                    rule=rule["rule"], value=value, threshold=rule["threshold"],
                    severity=rule["level"], description=rule["desc"],
                ))

        # === 判定告警等级 ===
        highest = AlertLevel.GREEN
        for t in triggers:
            order = {AlertLevel.RED: 4, AlertLevel.ORANGE: 3, AlertLevel.YELLOW: 2, AlertLevel.BLUE: 1, AlertLevel.GREEN: 0}
            if order.get(t.severity, 0) > order.get(highest, 0):
                highest = t.severity

        # === 生成求真卡 ===
        card_id = hashlib.sha256(
            f"{title}{verdict}{credibility_score}".encode()
        ).hexdigest()[:12]

        verdict_cn = {
            "false": "🚨 确认虚假", "likely_false": "⚠️ 可能虚假", "misleading": "⚠️ 误导性信息",
            "likely_true": "✅ 可能真实", "true": "✅ 确认真实", "unverifiable": "📋 暂无法验证",
        }

        share_text = (
            f"【求真卡 #{card_id}】{title[:40]}\n"
            f"判定: {verdict_cn.get(verdict, verdict)} | 可信度: {credibility_score:.0f}/100\n"
            f"{correction[:120] if correction else '请查阅完整分析报告。'}\n"
            f"🔍 查看完整分析: https://truthtrace.app/events/{card_id}"
        )

        truth_card = TruthCard(
            card_id=card_id,
            title=title,
            rumor_claim=rumor_claim or title,
            verdict=verdict_cn.get(verdict, verdict),
            credibility_score=credibility_score,
            key_evidence=[
                f"可信度评分: {credibility_score:.0f}/100",
                f"检测到 {distortion_count} 处信息失真",
                f"检测到 {fallacy_count} 处逻辑谬误",
                f"操纵性评分: {manipulation_score:.0f}/100",
            ] + ([f"AI生成风险: {ai_risk_score:.0f}/100"] if ai_risk_score > 0 else []),
            authoritative_sources=authoritative_sources or [],
            ai_detection_flag=ai_watermark_detected or ai_risk_score >= 60,
            propagation_risk="high" if propagation_speed_index >= 10 else "normal",
            correction_message=correction,
            share_text=share_text,
            generated_at=datetime.now(timezone.utc).isoformat(),
            expires_at=(datetime.now(timezone.utc) + __import__("datetime").timedelta(days=30)).isoformat(),
        )

        # === 推荐行动 ===
        actions = {
            AlertLevel.RED: [
                "立即标记为高优先级，通知平台运营团队",
                "启动溯源深度分析，确认传播网络",
                "向已接触用户推送求真卡",
                "准备应急处置预案",
            ],
            AlertLevel.ORANGE: [
                "标记为高风险，纳入当日重点监控",
                "启动事实核查流程，联系权威信息来源",
                "向搜索相关关键词的用户展示求真卡",
                "通知辟谣工坊生成辟谣内容",
            ],
            AlertLevel.YELLOW: [
                "标记为可疑，保持日常监测",
                "记录为潜在风险事件",
                "持续跟踪传播态势变化",
            ],
            AlertLevel.BLUE: ["记录事件，纳入例行监控"],
            AlertLevel.GREEN: ["正常传播，无需特殊处理"],
        }

        # === 易感人群 ===
        kws = keywords or []
        text_kws = " ".join(kws) + title + (rumor_claim or "")
        vulnerable = []
        for group_id, group_info in VULNERABLE_GROUPS.items():
            if any(t in text_kws for t in group_info["triggers"]):
                vulnerable.append(group_info["name"])

        return RumorAlertResult(
            alert_level=highest,
            triggers=triggers,
            truth_card=truth_card,
            recommended_actions=actions.get(highest, actions[AlertLevel.GREEN]),
            vulnerable_groups=vulnerable,
            alert_id=f"alert-{uuid.uuid4().hex[:12]}",
            generated_at=datetime.now(timezone.utc).isoformat(),
        )


# =============================================================================
# 预计算 — 从引擎分析结果快速评估
# =============================================================================

def alert_from_analysis(
    engine_analysis: dict,
    propagation_metrics: dict | None = None,
    ai_detection: dict | None = None,
    title: str = "",
) -> RumorAlertResult:
    """便捷方法: 从引擎分析结果直接生成预警"""
    distortion = engine_analysis.get("distortion_analysis", {})
    fallacy = engine_analysis.get("fallacy_analysis", {})
    narrative = engine_analysis.get("narrative_analysis", {})

    engine = RumorAlertEngine()
    return engine.evaluate(
        credibility_score=float(engine_analysis.get("credibility_score", 50)),
        propagation_speed_index=float(propagation_metrics.get("propagation_speed_index", 0)) if propagation_metrics else 0.0,
        anomaly_score=float(propagation_metrics.get("anomaly_score", 0)) if propagation_metrics else 0.0,
        coordinated_ratio=float(propagation_metrics.get("coordinated_ratio", 0)) if propagation_metrics else 0.0,
        ai_risk_score=float(ai_detection.get("risk_score", 0)) if ai_detection else 0.0,
        ai_watermark_detected=bool(ai_detection.get("matches")) if ai_detection else False,
        manipulation_score=float(narrative.get("manipulation_score", 0)) if isinstance(narrative, dict) else 0.0,
        distortion_count=len(distortion.get("matches", [])),
        fallacy_count=fallacy.get("fallacy_count", 0),
        title=title,
        verdict=str(engine_analysis.get("verdict", "unverifiable")),
        correction=str(engine_analysis.get("correction", "")),
        authoritative_sources=engine_analysis.get("correction_references", []),
    )
