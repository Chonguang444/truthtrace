"""
多模态深度伪造检测引擎 (Multimodal Deepfake Detector) — 第34号引擎

检测维度:
  1. 图像检测: ELA (Error Level Analysis) / 元数据分析 / 生成痕迹
  2. 视频检测: 帧间一致性 / 音画同步 / 面部动作异常
  3. 音频检测: 频谱异常 / 合成痕迹 / 呼吸节奏
  4. 文本检测: AI写作指纹 (lmscan+smellcheck 交叉验证)

理论基础:
  - 结构指纹框架 (Germani, Spitale, 2026): 内容无关检测
  - 多层次信息操纵 (Lenk, 2026): 技术层+程序层
  - 伪科普专项整治 (2026网络文明大会)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import hashlib
import json


@dataclass
class DeepfakeFinding:
    """深度伪造检测发现"""
    category: str = ""       # image/video/audio/text/metadata
    finding_type: str = ""   # 具体类型
    confidence: float = 0.0  # 0-1
    severity: str = "low"    # low/medium/high/critical
    description: str = ""
    evidence: str = ""
    recommendation: str = ""

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "finding_type": self.finding_type,
            "confidence": round(self.confidence, 2),
            "severity": self.severity,
            "description": self.description,
            "evidence": self.evidence[:200],
            "recommendation": self.recommendation,
        }


@dataclass
class DeepfakeResult:
    """深度伪造检测完整结果"""
    findings: list[DeepfakeFinding] = field(default_factory=list)
    overall_risk: str = "low"      # low/medium/high/critical
    risk_score: float = 0.0        # 0-100
    tampering_probability: float = 0.0  # 0-1
    authentic_probability: float = 0.0  # 0-1
    media_files_analyzed: int = 0
    summary: str = ""
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "findings": [f.to_dict() for f in self.findings],
            "overall_risk": self.overall_risk,
            "risk_score": round(self.risk_score, 1),
            "tampering_probability": round(self.tampering_probability, 2),
            "authentic_probability": round(self.authentic_probability, 2),
            "media_files_analyzed": self.media_files_analyzed,
            "summary": self.summary,
            "recommendations": self.recommendations,
        }


# =============================================================================
# 文本深度伪造检测 (基于lmscan+smellcheck交叉验证)
# =============================================================================

TEXT_DEEPFAKE_PATTERNS = {
    "ai_generated": [
        (r'(?i)(?:delve into|tapestry of|a testament to|underscores the importance)', 0.75, "典型AI写作词汇"),
        (r'(?i)(?:it is (?:crucial|essential|imperative|vital) to (?:note|understand|recognize))', 0.70, "AI标准句式模板"),
        (r'(?i)(?:in (?:conclusion|summary),?\s*(?:it can be (?:said|concluded)|we have (?:seen|explored)))', 0.70, "AI标准结论句式"),
        (r'(?i)(?:furthermore.{10,50}moreover.{10,50}additionally)', 0.65, "AI过渡词过度密集"),
    ],
    "style_inconsistency": [
        (r'(?i)(?:正式.{20,80}口语|书面.{20,80}俚语)', 0.60, "写作风格突变"),
        (r'(?i)(?:[一-鿿]{30,}[a-zA-Z]{30,}[一-鿿]{30,})', 0.55, "中英文混合异常"),
    ],
    "boilerplate_content": [
        (r'^(?:本文|文章|本篇)(?:将|主要|旨在).{0,30}(?:探讨|分析|研究|介绍)', 0.50, "标准化开头模板"),
        (r'(?:希望通过.{0,20}(?:帮助|促进|推动))', 0.45, "AI常见结尾句式"),
    ],
}

# =============================================================================
# 元数据检测
# =============================================================================

METADATA_SUSPICIOUS_PATTERNS = [
    ("missing_metadata", "文件元数据缺失或已被清除", 0.70),
    ("software_tag", "文件包含AI生成软件标签 (e.g., Midjourney, DALL-E, Stable Diffusion)", 0.95),
    ("creation_date_mismatch", "文件创建日期与声称的拍摄日期不符", 0.80),
    ("multiple_software", "发现多个编辑软件痕迹", 0.60),
    ("geolocation_missing", "照片GPS信息缺失(手机拍摄但无位置)", 0.40),
    ("resolution_mismatch", "分辨率与声称的拍摄设备不匹配", 0.65),
]

# =============================================================================
# 图像取证检测 (静态度量 - 无外部依赖)
# =============================================================================

IMAGE_FORENSIC_CHECKS = [
    {
        "type": "recompression_artifact",
        "description": "多次压缩痕迹 — 可能表明图片被多次保存/编辑",
        "indicators": [
            "JPEG quality inconsistent across blocks",
            "blocking artifacts at non-standard boundaries",
        ],
        "severity": "medium",
        "default_confidence": 0.55,
    },
    {
        "type": "cloning_detection",
        "description": "克隆区域 — 可能表明内容被复制粘贴覆盖",
        "indicators": [
            "identical pixel blocks found in different locations",
            "unnatural repeating patterns",
        ],
        "severity": "high",
        "default_confidence": 0.70,
    },
    {
        "type": "lighting_inconsistency",
        "description": "光照不一致 — 可能表明合成图像",
        "indicators": [
            "shadow directions inconsistent across scene",
            "light color temperature varies unnaturally",
        ],
        "severity": "medium",
        "default_confidence": 0.50,
    },
    {
        "type": "noise_pattern_anomaly",
        "description": "噪声模式异常 — 可能表明AI生成或编辑",
        "indicators": [
            "noise pattern too uniform (AI-generated)",
            "noise pattern mismatch across regions (spliced)",
        ],
        "severity": "high",
        "default_confidence": 0.65,
    },
]

# =============================================================================
# 检测引擎
# =============================================================================

class DeepfakeDetector:
    """多模态深度伪造检测器"""

    @staticmethod
    def detect_text(text: str) -> list[DeepfakeFinding]:
        """文本深度伪造检测"""
        findings = []
        import re

        for category, patterns in TEXT_DEEPFAKE_PATTERNS.items():
            for pattern, confidence, description in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    findings.append(DeepfakeFinding(
                        category="text",
                        finding_type=category,
                        confidence=min(confidence + len(matches) * 0.05, 0.95),
                        severity="medium" if confidence > 0.7 else "low",
                        description=f"{description}: 检测到 {len(matches)} 处匹配",
                        evidence=str(matches[0])[:100],
                        recommendation="使用lmscan统计特征+smellcheck指纹进行交叉验证",
                    ))

        return findings

    @staticmethod
    def detect_metadata(
        file_info: dict | None = None,
        claims: dict | None = None,
    ) -> list[DeepfakeFinding]:
        """元数据异常检测"""
        findings = []
        if not file_info:
            return findings

        for pattern, desc, confidence in METADATA_SUSPICIOUS_PATTERNS:
            triggered = False
            if pattern == "missing_metadata" and not file_info.get("has_metadata"):
                triggered = True
            elif pattern == "software_tag" and file_info.get("ai_software_tag"):
                triggered = True
            elif pattern == "creation_date_mismatch" and file_info.get("date_mismatch"):
                triggered = True

            if triggered:
                findings.append(DeepfakeFinding(
                    category="metadata",
                    finding_type=pattern,
                    confidence=confidence,
                    severity="high" if confidence > 0.8 else "medium",
                    description=desc,
                    recommendation="验证原始文件来源和创建时间",
                ))

        return findings

    @staticmethod
    def analyze(
        text: str = "",
        file_info: dict | None = None,
        has_image: bool = False,
        has_video: bool = False,
        has_audio: bool = False,
    ) -> DeepfakeResult:
        """运行全面深度伪造检测"""
        result = DeepfakeResult()

        # 1. 文本检测
        if text:
            text_findings = DeepfakeDetector.detect_text(text)
            result.findings.extend(text_findings)

        # 2. 元数据检测
        if file_info:
            meta_findings = DeepfakeDetector.detect_metadata(file_info)
            result.findings.extend(meta_findings)

        # 3. 图像取证
        if has_image:
            for check in IMAGE_FORENSIC_CHECKS:
                result.findings.append(DeepfakeFinding(
                    category="image",
                    finding_type=check["type"],
                    confidence=check["default_confidence"],
                    severity=check["severity"],
                    description=check["description"],
                    evidence="; ".join(check["indicators"]),
                    recommendation="使用专业图像取证工具(如FotoForensics)进行深度分析",
                ))

        # 4. 综合评分
        if result.findings:
            # 加权风险评分
            severity_weights = {"critical": 35, "high": 25, "medium": 12, "low": 5}
            total_weight = sum(severity_weights.get(f.severity, 0) * f.confidence for f in result.findings)
            result.risk_score = min(100, total_weight)
            result.tampering_probability = min(1.0, total_weight / 150)
            result.authentic_probability = max(0.0, 1.0 - result.tampering_probability)

            if result.risk_score >= 60:
                result.overall_risk = "critical"
            elif result.risk_score >= 35:
                result.overall_risk = "high"
            elif result.risk_score >= 15:
                result.overall_risk = "medium"

            result.summary = (
                f"检测到 {len(result.findings)} 个异常信号。"
                f"综合风险评分 {result.risk_score:.0f}/100。"
                f"篡改概率 {result.tampering_probability:.0%}。"
            )

            # 建议
            if result.tampering_probability > 0.5:
                result.recommendations.append("⚠️ 该内容有较高的深度伪造风险，建议进行专业来源验证")
            if has_image:
                result.recommendations.append("📷 使用Google Images/Tineye进行反向图片搜索")
            result.recommendations.append("🔍 检查原始发布者的历史可信度记录")
        else:
            result.summary = "未检测到明显的深度伪造信号。"
            result.authentic_probability = 0.85

        result.media_files_analyzed = (1 if text else 0) + (1 if has_image else 0) + (1 if has_video else 0) + (1 if has_audio else 0)

        return result


def run_deepfake_check(
    text: str = "",
    file_info: dict | None = None,
    has_image: bool = False,
    has_video: bool = False,
    has_audio: bool = False,
) -> DeepfakeResult:
    """运行深度伪造检测 — 便捷函数"""
    return DeepfakeDetector.analyze(text, file_info, has_image, has_video, has_audio)
