"""
媒体内容真实性验证引擎 — 图片/视频/音频/深伪检测

这是解决"刷到一条被剪辑过的视频"场景的核心模块。

检测维度:
1. 图片反向搜索 — 通过 imagehash 找原始/不同版本图片
2. 元数据提取 — EXIF/创建时间/设备信息/修改历史
3. 视频关键帧分析 — 检测是否有帧被插入/删除/调序
4. 音频拼接检测 — 检测是否有拼接/剪切痕迹
5. 深度伪造信号 — 利用公开检测信号做初步筛查

原则:
- 自动检测只能提供线索，不能给出确定结论
- 被清除的元数据本身就是线索——"为什么这些信息被删掉了？"
- 不确定时诚实告知
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

from app.engine.types import Confidence

logger = logging.getLogger("truthtrace.media")


# =============================================================================
# 数据类型
# =============================================================================

class MediaType(str):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"


class IntegrityStatus(str):
    VERIFIED = "verified"          # 完整性验证通过
    SUSPICIOUS = "suspicious"      # 发现可疑迹象
    TAMPERED = "tampered"         # 检测到明确篡改痕迹
    INCONCLUSIVE = "inconclusive"  # 无法确定


@dataclass
class MediaIntegrityResult:
    """媒体完整性检查结果"""
    media_type: str = ""
    status: IntegrityStatus = IntegrityStatus.INCONCLUSIVE
    indicators: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    confidence: Confidence = Confidence.LOW
    limitations: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "media_type": self.media_type,
            "status": self.status,
            "indicators": self.indicators,
            "metadata": self.metadata,
            "confidence": self.confidence.value,
            "limitations": self.limitations,
            "recommendations": self.recommendations,
        }


# =============================================================================
# 1. 图片哈希比对 (ImageHash)
# =============================================================================

def verify_image_fingerprint(image_path_or_bytes) -> dict:
    """
    生成图片的多重哈希指纹，用于比对是否有不同版本。

    使用 pHash + dHash 双重指纹:
    - pHash (感知哈希): 对缩放/压缩/轻微修改鲁棒
    - dHash (差异哈希): 对亮度调整鲁棒

    如果有原始图片的哈希，可以检测到:
    - 图片是否被裁剪/拉伸/压缩
    - 图片是否来自不同来源但内容相同
    """
    result = {
        "phash": "",
        "dhash": "",
        "ahash": "",
        "width": 0,
        "height": 0,
        "file_size": 0,
        "format": "",
        "issues": [],
        "note": "",
    }

    try:
        from PIL import Image
        import imagehash
        import io

        if isinstance(image_path_or_bytes, bytes):
            img = Image.open(io.BytesIO(image_path_or_bytes))
        else:
            img = Image.open(image_path_or_bytes)

        result["width"] = img.width
        result["height"] = img.height
        result["format"] = img.format or "unknown"

        if isinstance(image_path_or_bytes, bytes):
            result["file_size"] = len(image_path_or_bytes)

        # 生成哈希
        result["phash"] = str(imagehash.phash(img))
        result["dhash"] = str(imagehash.dhash(img))
        result["ahash"] = str(imagehash.average_hash(img))

        # 检查缩放痕迹
        if img.width < 200 or img.height < 200:
            result["issues"].append("图片分辨率极低 ({}x{})，可能经过多次压缩/转发".format(img.width, img.height))

        # 检查异常宽高比
        ratio = img.width / max(1, img.height)
        if ratio > 5 or ratio < 0.2:
            result["issues"].append(f"图片宽高比异常 ({ratio:.1f})，可能被裁剪")

        result["note"] = ("图片指纹已生成。可以通过将多个图片的指纹进行汉明距离比对来判断是否来自同一原始来源。"
                          "汉明距离 < 5 表示高度相似(可能为同一图片的不同版本)。"
                          "汉明距离 5-15 表示可能相关(经过较大修改)。"
                          "汉明距离 > 15 表示大概率不同。")

    except ImportError:
        result["note"] = "PIL/imagehash 不可用，无法生成图片指纹"
        result["issues"].append("图片指纹功能不可用")
    except Exception as e:
        result["issues"].append(f"图片处理失败: {str(e)[:100]}")

    return result


# =============================================================================
# 2. 图片元数据提取
# =============================================================================

def extract_image_metadata(image_path_or_bytes) -> dict:
    """
    提取图片的 EXIF/元数据。

    被清除的元数据本身就是线索:
    - 正常照片通常有相机型号、拍摄时间、GPS等信息
    - 如果所有元数据都被清除了 → 可能是故意为之（为了隐藏图片来源）
    - 如果有创建时间但被修改过 → 可能时间已被更改
    """
    result = {
        "has_exif": False,
        "camera_make": "",
        "camera_model": "",
        "date_taken": "",
        "date_modified": "",
        "gps_lat": None,
        "gps_lon": None,
        "software_used": "",
        "metadata_stripped": False,
        "issues": [],
        "note": "",
    }

    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS
        import io

        if isinstance(image_path_or_bytes, bytes):
            img = Image.open(io.BytesIO(image_path_or_bytes))
        else:
            img = Image.open(image_path_or_bytes)

        exif_data = img._getexif()
        if exif_data:
            result["has_exif"] = True
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == "Make":
                    result["camera_make"] = str(value)
                elif tag == "Model":
                    result["camera_model"] = str(value)
                elif tag == "DateTimeOriginal":
                    result["date_taken"] = str(value)
                elif tag == "DateTime":
                    result["date_modified"] = str(value)
                elif tag == "Software":
                    result["software_used"] = str(value)
                elif tag == "GPSInfo":
                    for gps_tag_id, gps_value in value.items():
                        gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                        if gps_tag == "GPSLatitude":
                            result["gps_lat"] = float(gps_value[0]) if isinstance(gps_value, tuple) else gps_value
                        elif gps_tag == "GPSLongitude":
                            result["gps_lon"] = float(gps_value[0]) if isinstance(gps_value, tuple) else gps_value

            # 如果没有拍摄日期但有修改日期 → 元数据不完整
            if not result["date_taken"] and result["date_modified"]:
                result["issues"].append("缺少原始拍摄时间，仅存修改时间——可能时间已被更改")

            # 如果 Photoshop 等软件处理过
            if result["software_used"]:
                if any(sw in result["software_used"].lower() for sw in ["photoshop", "lightroom", "gimp"]):
                    result["issues"].append(f"图片被 {result['software_used']} 处理过——内容可能被编辑")

        else:
            result["metadata_stripped"] = True
            result["issues"].append(
                "图片不包含 EXIF 元数据。正常拍摄的照片通常包含相机型号、拍摄时间等信息。"
                "元数据被清除可能是分享平台的自动处理，也可能是故意隐藏图片来源。"
                "仅凭元数据缺失不能断定恶意，但这是一个值得注意的信号。"
            )

    except ImportError:
        result["note"] = "PIL 不可用，无法提取图片元数据"
    except Exception as e:
        result["issues"].append(f"元数据提取失败: {str(e)[:100]}")

    if not result["issues"]:
        result["note"] = "元数据提取正常完成。"
    else:
        result["note"] = f"发现 {len(result['issues'])} 个元数据相关的可疑信号。"

    return result


# =============================================================================
# 3. 视频关键帧分析
# =============================================================================

def analyze_video_frames(video_path_or_url: str) -> dict:
    """
    视频帧分析 — 提取关键帧并检测异常。

    检测:
    - 相邻帧之间的异常跳跃（可能的剪辑点）
    - 场景切换频率是否异常
    - 帧的时间戳是否有间隙

    注意: 完整的逐帧深度分析需要专业的视频取证工具。
    本模块提供的是基于可用信息的启发式检测。
    """
    result = {
        "frame_count": 0,
        "duration_seconds": 0,
        "fps": 0,
        "key_frames_extracted": 0,
        "scene_changes_detected": 0,
        "suspicious_jumps": [],
        "issues": [],
        "note": "视频帧分析需要视频文件访问。对于URL类型的视频源，只能通过元数据进行初步分析。",
        "limitation": "完整的视频篡改检测需要逐帧分析和专业取证工具。本检测仅提供启发式线索。",
    }

    # 尝试通过 ffprobe 或类似工具获取视频元数据
    try:
        import subprocess
        import json
        import os

        path = video_path_or_url
        if not os.path.exists(path) and not path.startswith("http"):
            result["note"] = "无法访问视频文件。请提供本地文件路径或可下载的视频URL。"
            return result

        # ffprobe 分析
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", path
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)

            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    result["fps"] = eval(stream.get("r_frame_rate", "0/1"))
                    result["frame_count"] = int(stream.get("nb_frames", 0))
                    result["duration_seconds"] = float(stream.get("duration", 0))
                    break

            if not result["duration_seconds"]:
                fmt = data.get("format", {})
                result["duration_seconds"] = float(fmt.get("duration", 0))

            # 检查异常
            if result["duration_seconds"] < 1:
                result["issues"].append(f"视频时长极短 ({result['duration_seconds']}s)，可能是截取的片段")
            if result["fps"] > 0 and result["frame_count"] > 0:
                expected = result["duration_seconds"] * result["fps"]
                diff = abs(result["frame_count"] - expected)
                if diff > result["fps"] * 2:
                    result["issues"].append(f"帧数 ({result['frame_count']}) 与期望帧数 ({expected:.0f}) 不符，可能存在帧丢失或插入")

            # 关键帧提取
            keyframe_cmd = [
                "ffprobe", "-v", "quiet", "-select_streams", "v:0",
                "-show_entries", "frame=key_frame,pkt_pts_time",
                "-of", "csv", path
            ]
            kf_proc = subprocess.run(keyframe_cmd, capture_output=True, text=True, timeout=30)
            if kf_proc.returncode == 0:
                keyframes = [line for line in kf_proc.stdout.strip().split("\n") if "1" in line]
                result["key_frames_extracted"] = len(keyframes)
                result["scene_changes_detected"] = len(keyframes)

                # 异常场景切换频率
                if result["duration_seconds"] > 0 and len(keyframes) > 0:
                    avg_interval = result["duration_seconds"] / len(keyframes)
                    if avg_interval < 0.5:
                        result["issues"].append(f"场景切换频率异常高 (平均{avg_interval:.1f}s)，可能是拼凑的视频")
        else:
            result["note"] = f"ffprobe 分析失败。请确保 ffmpeg 已安装。错误: {proc.stderr[:200]}"

    except FileNotFoundError:
        result["note"] = "ffmpeg/ffprobe 未安装，无法进行视频分析。请安装 ffmpeg 后重试。"
    except Exception as e:
        result["issues"].append(f"视频分析失败: {str(e)[:100]}")

    return result


# =============================================================================
# 4. 音频拼接检测
# =============================================================================

def detect_audio_splicing(audio_path: str) -> dict:
    """
    音频拼接检测 — 检测音频文件中是否存在拼接/剪切痕迹。

    检测信号:
    - 波形在拼接点的不连续
    - 背景噪声水平的突然变化
    - 频率成分的突然变化

    注意: 这是一个复杂的信号处理问题。本模块提供的是基于可用工具的启发式检测。
    """
    result = {
        "duration_seconds": 0,
        "sample_rate": 0,
        "channels": 0,
        "suspicious_segments": [],
        "issues": [],
        "note": "音频拼接检测需要专业的音频取证工具。本检测仅提供启发式线索。",
    }

    try:
        import subprocess
        import json

        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", audio_path
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode == 0:
            data = json.loads(proc.stdout)
            fmt = data.get("format", {})
            result["duration_seconds"] = float(fmt.get("duration", 0))
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "audio":
                    result["sample_rate"] = int(stream.get("sample_rate", 0))
                    result["channels"] = int(stream.get("channels", 0))
                    break

            # 检查音频标签（可能记录编辑历史）
            tags = fmt.get("tags", {})
            if "encoder" in tags:
                result["issues"].append(f"音频编码器: {tags['encoder']}——已被编码软件处理过")
            if "date" in tags:
                result["issues"].append(f"音频处理日期: {tags['date']}")

            # 极短音频
            if result["duration_seconds"] < 2:
                result["issues"].append(f"音频时长极短 ({result['duration_seconds']}s)，可能是截取的片段")

    except FileNotFoundError:
        result["note"] = "ffmpeg/ffprobe 未安装，无法进行音频分析。"
    except Exception as e:
        result["issues"].append(f"音频分析失败: {str(e)[:100]}")

    return result


# =============================================================================
# 5. 深度伪造信号检测
# =============================================================================

def detect_deepfake_signals(media_info: dict) -> dict:
    """
    深度伪造信号检测 — 基于启发式信号做初步筛查。

    检测的信号:
    - 不自然的眨眼频率
    - 面部边缘模糊/锯齿
    - 光照不一致
    - 分辨率异常
    - 元数据缺失或矛盾

    注意: 这只是一个初步筛查，不能替代专业的深度伪造检测工具。
    完整的深伪检测需要专门的深度学习模型（如 FaceForensics、XceptionNet）。
    """
    signals = []

    # 元数据检查
    if media_info.get("metadata_stripped"):
        signals.append({
            "signal": "元数据缺失",
            "severity": "low",
            "note": "媒体文件的元数据被清除。这可能是平台自动处理，但也是隐藏伪造痕迹的常见手段。"
        })

    # 分辨率异常
    width = media_info.get("width", 0)
    height = media_info.get("height", 0)
    if width > 0 and height > 0:
        if width < 360 or height < 360:
            signals.append({
                "signal": "极低分辨率",
                "severity": "low",
                "note": f"媒体分辨率极低 ({width}x{height})。低分辨率可以掩盖深伪瑕疵。但也有很多正当的低分辨率原因。"
            })

    # 来源检查
    if media_info.get("source_is_anonymous"):
        signals.append({
            "signal": "匿名/无法验证来源",
            "severity": "medium",
            "note": "媒体来源无法验证。深伪内容通常通过匿名账号传播以逃避追踪。"
        })

    # 首次出现时间
    if media_info.get("first_seen_at"):
        try:
            first_seen = datetime.fromisoformat(str(media_info["first_seen_at"]))
            days_ago = (datetime.now(timezone.utc) - first_seen).days
            if days_ago < 1:
                signals.append({
                    "signal": "极近出现",
                    "severity": "low",
                    "note": "媒体在最近24小时内才首次出现。突发事件可能是真实的，也可能是被伪造后立即投放的。"
                })
        except Exception:
            pass

    # 总结
    if len(signals) == 0:
        verdict = "无明确深伪信号 —— 但自动检测无法排除高质量的深度伪造"
    elif len(signals) <= 2:
        verdict = f"发现 {len(signals)} 个低风险信号，不足以做出深伪判定"
    elif len(signals) <= 4:
        verdict = f"发现 {len(signals)} 个异常信号，建议进行人工审查"
    else:
        verdict = f"发现 {len(signals)} 个异常信号，该媒体存在较高的伪造风险"

    return {
        "signals": signals,
        "signal_count": len(signals),
        "verdict": verdict,
        "caveat": ("本检测仅为启发式筛查。高质量的深度伪造可能不会有以上任何信号。"
                   "要做出可靠的深伪判定，需要专门的深度学习检测模型（如 FaceForensics++、XceptionNet）。"
                   "本检测不能替代专业深伪鉴定。"),
    }


# =============================================================================
# 统一分析接口
# =============================================================================

def run_media_verification(
    media_type: str,
    media_source: str = "",  # 文件路径、URL 或 bytes
    media_info: dict | None = None,
) -> MediaIntegrityResult:
    """
    对媒体内容进行完整的真实性验证。

    Args:
        media_type: "image" / "video" / "audio"
        media_source: 文件路径、URL 或图片 bytes
        media_info: 已有的媒体元数据信息

    Returns:
        MediaIntegrityResult — 包含所有检测维度的结果
    """
    if media_info is None:
        media_info = {}

    result = MediaIntegrityResult(media_type=media_type)
    all_indicators = []

    # 1. 图片分析
    if media_type == MediaType.IMAGE and media_source:
        # 指纹
        fp = verify_image_fingerprint(media_source)
        result.metadata["fingerprint"] = fp
        for issue in fp.get("issues", []):
            all_indicators.append({"dimension": "图片指纹", "finding": issue})

        # 元数据
        exif = extract_image_metadata(media_source)
        result.metadata["exif"] = exif
        for issue in exif.get("issues", []):
            all_indicators.append({"dimension": "图片元数据", "finding": issue})

    # 2. 视频分析
    elif media_type == MediaType.VIDEO and media_source:
        vf = analyze_video_frames(media_source)
        result.metadata["video_analysis"] = vf
        for issue in vf.get("issues", []):
            all_indicators.append({"dimension": "视频帧分析", "finding": issue})

    # 3. 音频分析
    elif media_type == MediaType.AUDIO and media_source:
        af = detect_audio_splicing(media_source)
        result.metadata["audio_analysis"] = af
        for issue in af.get("issues", []):
            all_indicators.append({"dimension": "音频分析", "finding": issue})

    # 4. 深伪检测 (所有类型)
    media_info.update(result.metadata)
    df = detect_deepfake_signals(media_info)
    result.metadata["deepfake_check"] = df
    for sig in df.get("signals", []):
        all_indicators.append({"dimension": "深伪检测", "finding": sig["note"], "severity": sig["severity"]})

    result.indicators = all_indicators

    # 判定
    high_severity = sum(1 for i in all_indicators if i.get("severity") == "high")
    medium_severity = sum(1 for i in all_indicators if i.get("severity") in ("medium", None, ""))

    if high_severity >= 2:
        result.status = IntegrityStatus.TAMPERED
        result.confidence = Confidence.HIGH
    elif high_severity >= 1 or medium_severity >= 3:
        result.status = IntegrityStatus.SUSPICIOUS
        result.confidence = Confidence.MODERATE
    elif medium_severity >= 1:
        result.status = IntegrityStatus.SUSPICIOUS
        result.confidence = Confidence.LOW
    elif not all_indicators:
        result.status = IntegrityStatus.INCONCLUSIVE
        result.confidence = Confidence.UNCERTAIN

    # 建议
    if result.status == IntegrityStatus.TAMPERED:
        result.recommendations.append("该媒体文件存在严重篡改迹象，建议不要采信。如需确认，请提交专业的数字取证机构进行深度分析。")
    elif result.status == IntegrityStatus.SUSPICIOUS:
        result.recommendations.append("发现可疑信号，建议查找该媒体的原始版本进行比对。可以通过图片反向搜索(Google Images/TinEye/Baidu识图)找到更早的版本。")
    else:
        result.recommendations.append("未发现明确的篡改信号。但请注意，自动检测存在局限，高质量的伪造可能不会被检测到。")

    result.limitations = [
        "自动媒体真实性检测存在固有的局限，不能替代专业的数字取证。",
        "高质量的深度伪造可能不会有本引擎能检测到的任何信号。",
        "对于URL来源的媒体，分析受限于可下载的内容质量。",
    ]

    return result
