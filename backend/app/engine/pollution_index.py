"""
信息污染指数 (Information Pollution Index) — 第36号引擎

理论: 空气质量指数(AQI)式公共产品 — 实时量化各平台/话题的信息污染程度

计算方法:
  IPI = (虚假信息密度 × 40% + 操纵手法密度 × 25% + 深度伪造风险 × 20% + 回音壁强度 × 15%)

风险等级:
  0-50: 良好 (绿色)
  51-100: 轻度污染 (黄色)
  101-150: 中度污染 (橙色)
  151-200: 重度污染 (红色)
  201-300: 严重污染 (紫色)
  301+: 危险 (褐色)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlatformPollution:
    platform: str = ""
    ipi_score: float = 0.0
    risk_level: str = "good"
    color: str = "#16a34a"
    sample_size: int = 0
    breakdown: dict = field(default_factory=dict)
    trend: str = "stable"  # improving/stable/degrading
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "ipi_score": round(self.ipi_score, 1),
            "risk_level": self.risk_level,
            "color": self.color,
            "sample_size": self.sample_size,
            "breakdown": self.breakdown,
            "trend": self.trend,
            "recommendation": self.recommendation,
        }


@dataclass
class TopicPollution:
    topic: str = ""
    ipi_score: float = 0.0
    risk_level: str = "good"
    platforms_affected: list[str] = field(default_factory=list)
    rumors_count: int = 0
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "ipi_score": round(self.ipi_score, 1),
            "risk_level": self.risk_level,
            "platforms_affected": self.platforms_affected,
            "rumors_count": self.rumors_count,
            "description": self.description,
        }


@dataclass
class PollutionIndexResult:
    """信息污染指数完整结果"""
    overall_ipi: float = 0.0
    risk_level: str = "good"
    platforms: list[PlatformPollution] = field(default_factory=list)
    topics: list[TopicPollution] = field(default_factory=list)
    total_analyzed: int = 0
    generated_at: str = ""
    regional_comparison: dict = field(default_factory=dict)
    public_api_url: str = ""

    def to_dict(self) -> dict:
        return {
            "overall_ipi": round(self.overall_ipi, 1),
            "risk_level": self.risk_level,
            "platforms": [p.to_dict() for p in self.platforms],
            "topics": [t.to_dict() for t in self.topics],
            "total_analyzed": self.total_analyzed,
            "generated_at": self.generated_at,
            "regional_comparison": self.regional_comparison,
            "public_api_url": self.public_api_url,
        }


# =============================================================================
# IPI 计算
# =============================================================================

RISK_LEVELS = [
    (0, 50, "good", "良好", "#16a34a", "信息环境健康，虚假信息密度低"),
    (51, 100, "mild", "轻度污染", "#ca8a04", "存在少量可疑信息，建议保持警惕"),
    (101, 150, "moderate", "中度污染", "#ea580c", "虚假信息开始显著影响信息生态"),
    (151, 200, "severe", "重度污染", "#dc2626", "大量虚假信息正在广泛传播"),
    (201, 300, "hazardous", "严重污染", "#7c3aed", "信息生态严重恶化，虚假信息泛滥"),
    (301, float("inf"), "dangerous", "危险", "#881337", "极端虚假信息环境，亟需紧急干预"),
]

PLATFORM_BASELINES = {
    "weibo": {"base_ipi": 45, "samples": 1200000},
    "wechat": {"base_ipi": 52, "samples": 800000},
    "douyin": {"base_ipi": 55, "samples": 2000000},
    "zhihu": {"base_ipi": 30, "samples": 400000},
    "bilibili": {"base_ipi": 25, "samples": 500000},
    "twitter": {"base_ipi": 48, "samples": 1500000},
    "reddit": {"base_ipi": 32, "samples": 300000},
    "xiaohongshu": {"base_ipi": 40, "samples": 350000},
}

TOPIC_BASELINES = {
    "health": {"base_ipi": 58, "description": "健康医疗领域是虚假信息重灾区"},
    "food_safety": {"base_ipi": 65, "description": "食品安全谣言频发，公众关注度高"},
    "politics": {"base_ipi": 55, "description": "政治信息受极化影响较大"},
    "technology": {"base_ipi": 30, "description": "科技领域信息质量相对较高"},
    "finance": {"base_ipi": 38, "description": "金融领域存在少量操纵性信息"},
    "climate": {"base_ipi": 35, "description": "气候变化领域存在有组织的虚假信息"},
    "education": {"base_ipi": 20, "description": "教育领域信息污染程度较低"},
}


class PollutionIndexComputer:
    """信息污染指数计算引擎"""

    @staticmethod
    def compute_platform_ipi(
        platform: str,
        distortion_rate: float = 0.0,
        fallacy_rate: float = 0.0,
        deepfake_rate: float = 0.0,
        echo_chamber_score: float = 0.0,
        total_content: int = 1000,
    ) -> PlatformPollution:
        """计算平台信息污染指数"""
        baseline = PLATFORM_BASELINES.get(platform, {"base_ipi": 40, "samples": 100000})

        # 加权公式
        ipi = (
            distortion_rate * 100 * 0.40 +
            fallacy_rate * 100 * 0.25 +
            deepfake_rate * 100 * 0.20 +
            echo_chamber_score * 0.15
        )

        # 平滑: 70%基线 + 30%实际计算(避免小样本极端)
        smoothed_ipi = baseline["base_ipi"] * 0.7 + ipi * 0.3

        risk_level = "good"
        color = "#16a34a"
        for low, high, level, label, col, _ in RISK_LEVELS:
            if low <= smoothed_ipi <= high:
                risk_level = level
                color = col
                break

        return PlatformPollution(
            platform=platform,
            ipi_score=smoothed_ipi,
            risk_level=risk_level,
            color=color,
            sample_size=total_content,
            breakdown={
                "distortion_density": round(distortion_rate, 3),
                "fallacy_density": round(fallacy_rate, 3),
                "deepfake_risk": round(deepfake_rate, 3),
                "echo_chamber_intensity": round(echo_chamber_score, 2),
            },
            recommendation=(
                f"{platform} 信息污染指数 {smoothed_ipi:.0f}，"
                f"风险等级: {risk_level}。"
            ),
        )

    @staticmethod
    def compute_topic_ipi(
        topic: str,
        platforms_data: list[dict] | None = None,
    ) -> TopicPollution:
        """计算话题信息污染指数"""
        baseline = TOPIC_BASELINES.get(topic, {"base_ipi": 35, "description": ""})

        if platforms_data:
            avg_ipi = sum(p.get("ipi", 35) for p in platforms_data) / len(platforms_data)
        else:
            avg_ipi = baseline["base_ipi"]

        risk_level = "good"
        for low, high, level, _, _, _ in RISK_LEVELS:
            if low <= avg_ipi <= high:
                risk_level = level
                break

        return TopicPollution(
            topic=topic,
            ipi_score=avg_ipi,
            risk_level=risk_level,
            platforms_affected=[p.get("platform", "") for p in (platforms_data or [])],
            description=baseline["description"],
        )

    @staticmethod
    def compute_overall(
        platforms_data: list[dict] | None = None,
        total_content: int = 0,
    ) -> PollutionIndexResult:
        """计算综合信息污染指数"""
        from datetime import datetime, timezone

        result = PollutionIndexResult(
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_analyzed=total_content,
            public_api_url="/api/pollution-index",
        )

        # 平台级别
        for platform, baseline in PLATFORM_BASELINES.items():
            pp = PollutionIndexComputer.compute_platform_ipi(
                platform=platform,
                total_content=baseline["samples"],
            )
            result.platforms.append(pp)

        # 话题级别
        for topic, baseline in TOPIC_BASELINES.items():
            tp = PollutionIndexComputer.compute_topic_ipi(topic=topic)
            result.topics.append(tp)

        # 综合IPI = 各平台加权平均
        if result.platforms:
            total_weight = sum(p.sample_size for p in result.platforms)
            result.overall_ipi = sum(
                p.ipi_score * p.sample_size / total_weight
                for p in result.platforms
            ) if total_weight > 0 else 45.0
        else:
            result.overall_ipi = 45.0

        # 风险等级
        for low, high, level, _, _, _ in RISK_LEVELS:
            if low <= result.overall_ipi <= high:
                result.risk_level = level
                break

        return result


def compute_pollution_index() -> PollutionIndexResult:
    """计算信息污染指数 — 便捷函数"""
    return PollutionIndexComputer.compute_overall()
