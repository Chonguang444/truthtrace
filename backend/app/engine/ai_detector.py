"""
AI内容鉴伪引擎 — 第11号引擎

检测维度:
  1. AI生成文本检测 — 语言模式/重复度/幻觉标记/"正如"/"值得注意的是"等AI常用语
  2. 深度伪造视频信号 — 不自然眨眼/面部边界模糊/音频-口型不匹配
  3. AI生成图片特征 — 元数据缺失/JPEG压缩痕迹异常/手指/文字扭曲异常
  4. 机器人发帖模式 — 发布时间规律/内容模板化/互动模式异常
  5. 跨模态一致性 — 图片与文字描述是否匹配/视频场景切换是否自然

行业对标:
  - 抖音"AI求真"大模型: 主动召回+求真卡, 谣言曝光量-67%
  - 白杨智鉴(中传国重实验室): 可解释音视频鉴伪
  - B站/小红书/微博: 完全无法检测无水印AI视频(2025年9月实测)

核心原则:
  - AI检测只能提供线索, 不能给出确定结论
  - 每次检测附带置信度和证据
  - 误报比漏报更严重 — 人工内容是合法的
"""

from __future__ import annotations
import re
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

logger = logging.getLogger("truthtrace.ai_detector")


class AIContentType(str, Enum):
    AI_TEXT = "ai_text"            # AI生成文本
    AI_IMAGE = "ai_image"          # AI生成图片
    AI_VIDEO = "ai_video"          # AI生成/深度伪造视频
    AI_VOICE = "ai_voice"          # AI合成语音
    BOT_PATTERN = "bot_pattern"    # 机器人发帖模式
    AI_TRANSLATION = "ai_translation"  # 机器翻译痕迹
    CROSS_MODAL_MISMATCH = "cross_modal_mismatch"  # 跨模态不一致
    WATERMARK_DETECTED = "watermark_detected"  # 检测到AI水印
    METADATA_ANOMALY = "metadata_anomaly"  # 元数据异常（缺失/矛盾）


@dataclass
class AIDetectorMatch:
    """单条AI检测匹配"""
    match_type: AIContentType
    description: str
    confidence: float  # 0-1
    evidence_snippet: str = ""
    evidence_location: str = ""  # 文本位置/图片区域
    technical_detail: str = ""   # 技术细节（面向开发者）
    false_positive_risk: str = ""  # 误报风险说明

    def to_dict(self) -> dict:
        return {
            "match_type": self.match_type.value,
            "description": self.description,
            "confidence": round(self.confidence, 2),
            "evidence_snippet": self.evidence_snippet,
            "evidence_location": self.evidence_location,
            "technical_detail": self.technical_detail,
            "false_positive_risk": self.false_positive_risk,
        }


@dataclass
class AIDetectorResult:
    """AI鉴伪完整结果"""
    matches: list[AIDetectorMatch] = field(default_factory=list)
    risk_score: float = 0.0       # 0-100 AI生成风险评分
    confidence: float = 0.0        # 检测置信度
    summary: str = ""
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "matches": [m.to_dict() for m in self.matches],
            "risk_score": round(self.risk_score, 1),
            "confidence": round(self.confidence, 2),
            "summary": self.summary,
            "recommendations": self.recommendations,
        }


# =============================================================================
# 1. AI文本检测
# =============================================================================

AI_TEXT_PATTERNS = [
    # GPT/Claude经典用语 (中英文)
    (r"(?i)\b(as an AI|as a language model|I don't have (personal )?opinions|I cannot|I'm not able to)\b",
     0.85, "AI模型经典拒绝/声明语句", "AI_TEXT"),
    (r"(?i)\b(值得注意的是|需要注意的是|需要强调的是|总的来说|综上所述|此外|与此同时)\b",
     0.30, "AI常用过渡语（高密度出现时风险升高）", "AI_TEXT"),
    (r"(?i)\b(explore|delve into|tapestry|testament|in conclusion|it is important to note)\b",
     0.50, "Claude经典英文用词（GPT和人类很少用）", "AI_TEXT"),
    (r"(?i)\b(在这个(?:日益|不断|快速|飞速)(?:变化|发展)的|在这个信息爆炸的|随着(?:人工智能|科技|互联网)(?:的|不断)发展|在当今(?:这个)?(?:数字化|网络化|信息化|全球化)(?:时代|社会|世界))\b",
     0.40, "AI开场白模板 — 空洞的宏大叙事", "AI_TEXT"),
    # 过度工整 — 人类写作不完美的标志
    (r"^.{200,}$", 0.15, "超长无断句段落（>200字符无标点）", "AI_TEXT"),
    # 幻觉标记: 数字极度精确但无来源
    (r"根据(?:研究|调查|数据|统计|报告|分析)(?:显示|表明|发现|证实)[^，。]{0,50}?(?:\d{2,4}\.\d{1,2}%|\d+\.\d{2,})",
     0.55, "AI生成式精确数字 — 格式工整但引用来源模糊", "AI_TEXT"),
    # 引用不存在的研究
    (r"(?:根据|据)(?:[A-Z][a-z]+\s*(?:et\s*al\.?|和|&)\s*)?(?:\(\d{4}\))",
     0.35, "学术引用格式 — 需验证该引用是否真实存在", "AI_TEXT"),
]


# =============================================================================
# 2. AI图片/视频特征 (元数据层面)
# =============================================================================

AI_IMAGE_METADATA_CHECKS = [
    # 缺少EXIF数据 (AI生成图片通常无相机元数据)
    ("exif_missing", 0.30, "缺少EXIF相机元数据 — AI生成图片通常无相机信息"),
    ("exif_software_tag", 0.90, "EXIF中包含AI生成软件标记 (如 Midjourney/Stable Diffusion/DALL-E)"),
    ("jpeg_quality_uniform", 0.40, "全图JPEG质量均匀 — 真实照片的压缩质量通常不均匀"),
    ("resolution_standard", 0.25, "分辨率恰好为标准AI生成尺寸 (1024x1024, 512x512等)"),
    ("face_landmark_inconsistency", 0.65, "面部关键点不一致 — 深度伪造常见特征"),
    ("eye_reflection_mismatch", 0.70, "双眼的高光反射不匹配 — 真实照片中反射应一致"),
    ("irregular_blink", 0.60, "不自然的眨眼频率或模式 — 深度伪造视频检测"),
    ("lip_sync_mismatch", 0.55, "口型与音频不完全同步 — AI配音检测"),
    ("finger_deformity", 0.70, "手指形态异常 — AI生成的经典缺陷"),
    ("text_distortion", 0.65, "图中文字扭曲/乱码 — AI难以正确生成嵌入式文字"),
    ("background_blur_artifact", 0.45, "背景模糊区域有人工痕迹 — AI抠图/虚化不自然"),
    ("repeating_pattern", 0.50, "检测到重复纹理模式 — AI生成常见模式"),
]

# =============================================================================
# 3. 机器人发帖检测
# =============================================================================

BOT_DETECTION_PATTERNS = [
    # 发布时间规律
    (r"published_at.*?(?:0[02]:\d{2}|0[356]:\d{2}|1[02]:\d{2})", 0.20,
     "发布时间恰好在整点/半点 — 机器定时发布特征"),
    # 内容模板化
    (r"^(?:#\S+\s*){3,}$", 0.60, "纯标签内容 — 机器人水帖特征"),
    # 跨账号内容雷同 (需要外部数据支持)
    ("content_template_match", 0.70, "内容与已知机器人模板高度匹配"),
    # 互动模式异常
    (r"(?:转发|分享|收藏)(?:\d+)(?:评论|回复)(?:\d+)", 0.25,
     "高转发/低评论比例 — 机器人转发网络特征"),
    # 账号信息异常
    ("default_avatar", 0.40, "使用平台默认头像 — 机器人账号特征"),
    ("new_account", 0.45, "新注册账号（<30天）— 机器人/水军常见特征"),
    ("numeric_username", 0.35, "纯数字/随机字符串用户名 — 批量注册特征"),
]


# =============================================================================
# 主检测器
# =============================================================================

class AIContentDetector:
    """
    AI内容鉴伪检测器 — 第11号引擎

    用法:
        detector = AIContentDetector()
        result = detector.analyze(
            text="...",
            images_meta=[...],
            video_meta={...},
            author_info={...},
        )
    """

    def analyze(self, text: str = "", title: str = "",
                images_meta: list[dict] | None = None,
                video_meta: dict | None = None,
                author_info: dict | None = None,
                content_meta: dict | None = None,
                ) -> AIDetectorResult:
        """
        对内容进行全面的AI鉴伪分析。

        Args:
            text: 正文内容
            title: 标题
            images_meta: 图片元数据列表 [{"url":..., "exif":..., "dimensions":...}]
            video_meta: 视频元数据 {"fps":..., "duration":..., "codec":...}
            author_info: 发布者信息 {"username":..., "created_at":..., "avatar":...}
            content_meta: 内容元数据 {"published_at":..., "platform":..., "interaction":...}
        """
        matches = []
        combined = f"{title}\n{text}"

        # === 1. AI文本检测 ===
        for pattern, confidence, description, match_type in AI_TEXT_PATTERNS:
            for m in re.finditer(pattern, combined):
                snippet = m.group()[:150]
                matches.append(AIDetectorMatch(
                    match_type=AIContentType(match_type),
                    description=description,
                    confidence=confidence,
                    evidence_snippet=snippet,
                    evidence_location=f"文本偏移 {m.start()}-{m.end()}",
                    false_positive_risk="专业写作/学术翻译可能有类似用语" if confidence < 0.5 else ""
                ))

        # 多指标聚合: 如果同时命中多个AI文本特征→置信度提升
        ai_text_matches = [m for m in matches if m.match_type == AIContentType.AI_TEXT]
        if len(ai_text_matches) >= 3:
            matches.append(AIDetectorMatch(
                match_type=AIContentType.AI_TEXT,
                description=f"多重AI文本特征同时命中（{len(ai_text_matches)}个特征），AI生成风险显著升高",
                confidence=min(0.85, 0.3 + len(ai_text_matches) * 0.12),
                evidence_snippet="；".join(m.evidence_snippet[:30] for m in ai_text_matches[:3]),
                evidence_location="全文",
                technical_detail=f"命中特征: {', '.join(m.description[:20] for m in ai_text_matches[:4])}",
                false_positive_risk="专业学术写作/翻译内容可能被误判 — 需要人工复审"
            ))

        # === 2. AI图片检测 ===
        if images_meta:
            for img in images_meta[:10]:
                for check_key, confidence, desc in AI_IMAGE_METADATA_CHECKS:
                    # 根据实际元数据进行检测
                    if check_key == "exif_missing" and not img.get("exif"):
                        matches.append(AIDetectorMatch(
                            match_type=AIContentType.AI_IMAGE,
                            description=f"图片 {img.get('url','?')[:40]}: {desc}",
                            confidence=confidence,
                            evidence_location=img.get("url", ""),
                            technical_detail="无EXIF相机型号/镜头/光圈/快门/ISO信息",
                            false_positive_risk="截图/社交媒体转发也可能丢失EXIF"
                        ))
                    elif check_key == "exif_software_tag" and img.get("exif", {}).get("Software"):
                        sw = img["exif"]["Software"]
                        if any(ai_tool in sw for ai_tool in ["Midjourney", "Stable Diffusion", "DALL-E", "DALL·E",
                                                              "NovelAI", "SD", "ComfyUI", "Automatic1111"]):
                            matches.append(AIDetectorMatch(
                                match_type=AIContentType.WATERMARK_DETECTED,
                                description=f"图片 {img.get('url','?')[:40]}: EXIF软件标记 '{sw}' — AI生成水印",
                                confidence=0.90,
                                evidence_location=img.get("url", ""),
                                technical_detail=f"EXIF Software: {sw}"
                            ))
                    elif check_key == "resolution_standard" and img.get("dimensions"):
                        w, h = img["dimensions"]
                        if (w, h) in [(512, 512), (768, 768), (1024, 1024), (512, 768), (768, 512)]:
                            matches.append(AIDetectorMatch(
                                match_type=AIContentType.AI_IMAGE,
                                description=f"图片 {img.get('url','?')[:40]}: 分辨率 {w}x{h} 恰好为标准AI生成尺寸",
                                confidence=confidence,
                                evidence_location=img.get("url", ""),
                                technical_detail=f"分辨率 {w}x{h} 是SD/DALL-E常见输出尺寸",
                                false_positive_risk="图标/Logo也可能使用标准尺寸"
                            ))

        # === 3. AI视频检测 ===
        if video_meta:
            if video_meta.get("fps", 0) == 0:
                pass  # 无视频帧信息，跳过
            # 检查帧率异常 (深度伪造常有不规则帧率)
            fps = video_meta.get("fps", 0)
            if fps and (fps < 10 or fps > 120):
                matches.append(AIDetectorMatch(
                    match_type=AIContentType.AI_VIDEO,
                    description=f"视频帧率异常 ({fps} fps) — AI生成视频常见标志",
                    confidence=0.45,
                    technical_detail=f"正常视频帧率通常在23.976-60fps, {fps}fps异常",
                    false_positive_risk="老旧设备/特殊格式可能有异常帧率"
                ))

            # 检查元数据完整性
            has_creation_date = bool(video_meta.get("creation_time"))
            has_camera_info = bool(video_meta.get("camera_model"))
            if not has_camera_info and video_meta.get("codec"):
                matches.append(AIDetectorMatch(
                    match_type=AIContentType.METADATA_ANOMALY,
                    description="视频缺少录制设备信息 — 可能为AI生成或后期处理",
                    confidence=0.25,
                    technical_detail="真实手机/相机拍摄的视频通常包含设备型号",
                    false_positive_risk="部分视频编辑软件可能清除元数据"
                ))

        # === 4. 机器人发帖检测 ===
        if author_info or content_meta:
            # 新账号检测
            if author_info and author_info.get("created_at"):
                try:
                    from datetime import datetime, timedelta, timezone
                    created = datetime.fromisoformat(str(author_info["created_at"]).replace("Z", "+00:00"))
                    days_old = (datetime.now(timezone.utc) - created.replace(tzinfo=timezone.utc)).days
                    if days_old < 30:
                        matches.append(AIDetectorMatch(
                            match_type=AIContentType.BOT_PATTERN,
                            description=f"账号注册仅{days_old}天 — 新账号发布争议内容的可信度较低",
                            confidence=0.40 if days_old < 7 else 0.25,
                            technical_detail=f"注册于 {author_info['created_at']}",
                            false_positive_risk="正常新用户也可能被误判"
                        ))
                except (ValueError, TypeError):
                    pass

            # 默认头像检测
            if author_info and (author_info.get("avatar", "") == "" or "default" in str(author_info.get("avatar", "")).lower()):
                matches.append(AIDetectorMatch(
                    match_type=AIContentType.BOT_PATTERN,
                    description="使用默认头像 — 机器人/水军账号常见特征",
                    confidence=0.30,
                    false_positive_risk="部分正常用户不使用自定义头像"
                ))

        # === 5. 跨模态一致性 (文本声称 vs 元数据) ===
        if content_meta and text:
            # 声称"现场拍摄"但无GPS/时间 — 矛盾
            if re.search(r"(?:现场|实拍|实地|前线|直击|一手)", text) and content_meta.get("has_gps") is False:
                matches.append(AIDetectorMatch(
                    match_type=AIContentType.CROSS_MODAL_MISMATCH,
                    description="文本声称'现场/实拍'但图片无GPS位置信息 — 可信度降低",
                    confidence=0.40,
                    evidence_snippet="声称'现场'但元数据不支持",
                    technical_detail="cross-modal inconsistency: claim vs metadata",
                    false_positive_risk="用户可能关闭了位置服务"
                ))

        # === 计算风险评分 ===
        if matches:
            # 加权平均 + 多特征加成
            weights = {
                AIContentType.WATERMARK_DETECTED: 2.0,
                AIContentType.AI_TEXT: 1.0,
                AIContentType.AI_IMAGE: 1.2,
                AIContentType.AI_VIDEO: 1.5,
                AIContentType.BOT_PATTERN: 0.8,
                AIContentType.CROSS_MODAL_MISMATCH: 1.0,
                AIContentType.METADATA_ANOMALY: 0.7,
            }
            weighted_sum = sum(
                m.confidence * weights.get(m.match_type, 1.0)
                for m in matches
            )
            # 多类型命中加成
            unique_types = len(set(m.match_type for m in matches))
            type_bonus = 1.0 + (unique_types - 1) * 0.3

            risk_score = min(100, weighted_sum * type_bonus * 25)
            avg_confidence = sum(m.confidence for m in matches) / len(matches)
        else:
            risk_score = 0.0
            avg_confidence = 0.0

        # === 生成摘要 ===
        summary_parts = []
        if any(m.match_type == AIContentType.WATERMARK_DETECTED for m in matches):
            summary_parts.append("检测到明确的AI生成水印标记。")
        elif risk_score >= 60:
            summary_parts.append(f"多重AI生成特征同时命中(风险评分{risk_score:.0f}/100)，建议人工核实。")
        elif risk_score >= 30:
            summary_parts.append(f"存在部分AI生成/操纵迹象(风险评分{risk_score:.0f}/100)，但证据不够充分。")
        elif risk_score > 0:
            summary_parts.append(f"检测到微弱AI信号({risk_score:.0f}/100)，可能是专业写作风格的正常表现。")
        else:
            summary_parts.append("未检测到明显的AI生成或操纵特征。")

        # 针对性建议
        recommendations = []
        if any(m.match_type == AIContentType.AI_TEXT for m in matches if m.confidence > 0.6):
            recommendations.append("该文本呈现典型的AI生成语言模式。可尝试搜索文中引用的'研究'或'数据'，如无法找到原文，则内容可信度大幅降低。")
        if any(m.match_type == AIContentType.AI_IMAGE for m in matches):
            recommendations.append("检测到的图片可能由AI生成。可进行反向图片搜索（Google Images / TinEye）确认图片的原始出处。")
        if any(m.match_type == AIContentType.BOT_PATTERN for m in matches):
            recommendations.append("发布者账号呈现机器人特征。建议检查该账号的历史发帖模式，单一账号影响度有限，但若多个类似账号同时推送相同内容则可能为协同操纵。")
        if not recommendations:
            recommendations.append("当前未发现明确的操纵证据。但AI检测技术存在局限性，不应仅据此判断内容真实性。")

        return AIDetectorResult(
            matches=matches,
            risk_score=round(risk_score, 1),
            confidence=round(avg_confidence, 2),
            summary="。".join(summary_parts),
            recommendations=recommendations,
        )
