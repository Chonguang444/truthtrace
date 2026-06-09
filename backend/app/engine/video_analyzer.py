"""
视频内容深度分析引擎 — 解读视频本身而非仅依赖评论和播放量

分析维度:
1. OCR文字提取 — 视频画面中出现的文字(标题/字幕/水印)
2. 语音转文字 — 将视频对话/旁白转为可分析的文本
3. 关键帧场景分析 — 提取关键帧, 分析场景变化
4. 视觉情感检测 — 画面色调/构图暗示的情感倾向
5. 内容-标题一致性 — 检测标题党(标题与视频内容不匹配)

将以上维度提取的文本送入10引擎推理分析。

依赖: ffmpeg (关键帧提取, 音频提取)
"""

from __future__ import annotations
import logging
import os
import tempfile
import subprocess
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("truthtrace.video_analyzer")


# =============================================================================
# 数据类型
# =============================================================================

@dataclass
class VideoContentAnalysis:
    """视频内容深度分析结果"""
    # OCR
    ocr_text: str = ""              # 从画面提取的所有文字
    ocr_keywords: list[str] = field(default_factory=list)

    # 语音/字幕
    transcript: str = ""            # 语音转文字结果
    transcript_language: str = ""   # 检测到的语言
    subtitle_text: str = ""         # 内嵌字幕文本

    # 关键帧
    keyframe_count: int = 0
    scene_changes: int = 0          # 场景切换次数
    avg_scene_duration: float = 0.0 # 平均场景时长(秒)
    rapid_cuts: int = 0             # 快速剪辑次数(<1秒的场景)

    # 视觉
    dominant_colors: list[str] = field(default_factory=list)
    brightness_avg: float = 0.0
    has_text_overlay: bool = False
    has_face: bool = False

    # 一致性
    title_content_match: float = 0.0    # 标题与视频内容匹配度(0-1)
    is_clickbait: bool = False          # 是否为标题党

    # 文本汇总(送入引擎分析的完整文本)
    combined_text: str = ""

    # 元数据
    duration_seconds: float = 0.0
    resolution: str = ""
    codec: str = ""
    file_size_mb: float = 0.0

    def to_dict(self) -> dict:
        return {
            "ocr_text": self.ocr_text[:500],
            "ocr_keywords": self.ocr_keywords,
            "transcript": self.transcript[:500],
            "transcript_language": self.transcript_language,
            "subtitle_text": self.subtitle_text[:500],
            "keyframe_count": self.keyframe_count,
            "scene_changes": self.scene_changes,
            "avg_scene_duration": round(self.avg_scene_duration, 1),
            "rapid_cuts": self.rapid_cuts,
            "dominant_colors": self.dominant_colors,
            "brightness_avg": round(self.brightness_avg, 1),
            "has_text_overlay": self.has_text_overlay,
            "has_face": self.has_face,
            "title_content_match": round(self.title_content_match, 2),
            "is_clickbait": self.is_clickbait,
            "combined_text": self.combined_text[:1000],
            "duration_seconds": self.duration_seconds,
            "resolution": self.resolution,
            "codec": self.codec,
            "file_size_mb": round(self.file_size_mb, 1),
        }


# =============================================================================
# ffmpeg 工具
# =============================================================================

def _check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _extract_audio(video_path: str, output_path: str) -> bool:
    """从视频中提取音频"""
    try:
        subprocess.run([
            "ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1", output_path,
            "-y", "-loglevel", "quiet"
        ], check=True, timeout=120)
        return True
    except Exception as e:
        logger.warning(f"音频提取失败: {e}")
        return False


def _extract_keyframes(video_path: str, output_dir: str, interval: float = 2.0) -> int:
    """每N秒提取一帧"""
    try:
        subprocess.run([
            "ffmpeg", "-i", video_path, "-vf", f"fps=1/{interval}",
            f"{output_dir}/frame_%04d.jpg",
            "-y", "-loglevel", "quiet"
        ], check=True, timeout=120)
        import glob
        return len(glob.glob(f"{output_dir}/frame_*.jpg"))
    except Exception as e:
        logger.warning(f"关键帧提取失败: {e}")
        return 0


def _get_video_metadata(video_path: str) -> dict:
    """使用 ffprobe 获取视频元数据"""
    try:
        import json
        result = subprocess.run([
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", video_path
        ], capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            return {}

        data = json.loads(result.stdout)
        meta = {"duration": 0.0, "width": 0, "height": 0, "codec": "", "size_mb": 0}

        fmt = data.get("format", {})
        meta["duration"] = float(fmt.get("duration", 0))
        meta["size_mb"] = float(fmt.get("size", 0)) / (1024 * 1024)

        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                meta["width"] = stream.get("width", 0)
                meta["height"] = stream.get("height", 0)
                meta["codec"] = stream.get("codec_name", "")
                if meta["width"] and meta["height"]:
                    meta["resolution"] = f"{meta['width']}x{meta['height']}"

            # 检查是否有字幕流
            if stream.get("codec_type") == "subtitle":
                meta["has_subtitle_stream"] = True

        return meta

    except Exception as e:
        logger.warning(f"视频元数据提取失败: {e}")
        return {}


# =============================================================================
# OCR 文字提取
# =============================================================================

def _extract_ocr_text(image_dir: str) -> tuple[str, list[str]]:
    """
    使用 OCR 从关键帧中提取文字。

    尝试顺序: EasyOCR → Tesseract → 手动模式

    EasyOCR 对中文支持较好, Tesseract 需要中文语言包。
    """
    try:
        import glob
        frames = sorted(glob.glob(f"{image_dir}/frame_*.jpg"))

        # EasyOCR (中文优选)
        try:
            import easyocr
            reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
            all_texts = []
            for frame in frames[:10]:  # 最多处理10帧
                results = reader.readtext(frame)
                texts = [r[1] for r in results if r[2] > 0.5]
                all_texts.extend(texts)

            text = " | ".join(all_texts[:50])
            keywords = list(set(all_texts))[:30]
            if text:
                return text, keywords
        except ImportError:
            pass

        # Tesseract 回退
        try:
            import pytesseract
            from PIL import Image
            all_texts = []
            for frame in frames[:10]:
                img = Image.open(frame)
                text = pytesseract.image_to_string(img, lang="chi_sim+eng")
                if text.strip():
                    all_texts.append(text.strip())
            text = " | ".join(all_texts[:50])
            keywords = list(set(" ".join(all_texts).split()))[:30]
            if text:
                return text, keywords
        except ImportError:
            pass

        return "", []

    except Exception as e:
        logger.warning(f"OCR 失败: {e}")
        return "", []


# =============================================================================
# 语音转文字
# =============================================================================

def _transcribe_audio(audio_path: str) -> tuple[str, str]:
    """
    将音频转为文字。

    尝试顺序: whisper(OpenAI) → 内置提示

    whisper 准确性最好, 支持多语言。
    """
    try:
        # OpenAI Whisper
        try:
            import whisper
            model = whisper.load_model("base")  # base 模型, 平衡速度和准确性
            result = model.transcribe(audio_path, language=None)
            text = result.get("text", "")
            lang = result.get("language", "")
            if text.strip():
                return text.strip(), lang
        except ImportError:
            pass

        # 内置提示
        return ("[需要安装 openai-whisper: pip install openai-whisper]", "")
    except Exception as e:
        logger.warning(f"语音转文字失败: {e}")
        return ("", "")


# =============================================================================
# 视觉情感检测
# =============================================================================

def _analyze_visual_emotion(frame_dir: str) -> dict:
    """
    分析关键帧的视觉特征:
    - 色彩: 整体色调偏暖(黄/红)还是偏冷(蓝/灰)
    - 亮度: 暗色调暗示负面/恐惧, 亮色调暗示积极
    """
    try:
        import glob
        from PIL import Image
        import statistics

        frames = sorted(glob.glob(f"{frame_dir}/frame_*.jpg"))
        if not frames:
            return {"dominant_colors": [], "brightness_avg": 0, "has_text_overlay": False, "has_face": False}

        all_brightness = []
        color_counts = {"warm": 0, "cool": 0, "neutral": 0}

        for frame in frames[:5]:
            img = Image.open(frame).convert("RGB")
            # 缩放到小尺寸以加速
            img_small = img.resize((100, 100))

            r_sum, g_sum, b_sum = 0, 0, 0
            for x in range(100):
                for y in range(100):
                    r, g, b = img_small.getpixel((x, y))
                    r_sum += r
                    g_sum += g
                    b_sum += b

            total = 100 * 100
            avg_r, avg_g, avg_b = r_sum / total, g_sum / total, b_sum / total
            brightness = (avg_r + avg_g + avg_b) / 3
            all_brightness.append(brightness)

            # 暖/冷色调
            if avg_r > avg_b * 1.2:
                color_counts["warm"] += 1
            elif avg_b > avg_r * 1.2:
                color_counts["cool"] += 1
            else:
                color_counts["neutral"] += 1

        dominant = "warm" if color_counts["warm"] > color_counts["cool"] else \
                   "cool" if color_counts["cool"] > color_counts["warm"] else "neutral"
        dominant_colors = []
        if color_counts["warm"] >= 3:
            dominant_colors.append("偏暖色调(可能传递温暖/焦虑/愤怒)")
        if color_counts["cool"] >= 3:
            dominant_colors.append("偏冷色调(可能传递冷静/压抑/科技感)")

        return {
            "dominant_colors": dominant_colors,
            "brightness_avg": round(statistics.mean(all_brightness), 1) if all_brightness else 0,
            "has_text_overlay": False,  # 需要专门模型检测
            "has_face": False,          # 需要专门模型检测
        }
    except Exception as e:
        logger.warning(f"视觉分析失败: {e}")
        return {"dominant_colors": [], "brightness_avg": 0, "has_text_overlay": False, "has_face": False}


# =============================================================================
# 标题-内容一致性检测
# =============================================================================

def _check_title_content_match(title: str, ocr_text: str, transcript: str) -> tuple[float, bool]:
    """
    检测标题是否与视频实际内容匹配。

    标题党特征:
    - 标题使用了大量情感词汇但内容平淡
    - 标题承诺的信息在内容中不存在
    - 标题与OCR/转录文本的关键词重叠率极低
    """
    if not title or (not ocr_text and not transcript):
        return 1.0, False

    import re
    # 提取关键词
    title_words = set(re.findall(r'[一-鿿]{2,}', title))
    content_words = set(
        re.findall(r'[一-鿿]{2,}', f"{ocr_text} {transcript}")
    )
    if not title_words:
        return 1.0, False

    overlap = len(title_words & content_words)
    match_ratio = overlap / len(title_words)

    # 标题党检测
    emotional_in_title = bool(re.search(r'(?:震惊|恐怖|吓人|惊人|不敢想|触目|泪目|崩溃)', title))
    is_clickbait = emotional_in_title and match_ratio < 0.3

    return round(match_ratio, 2), is_clickbait


# =============================================================================
# 场景切换分析
# =============================================================================

def _detect_scene_changes(metadata: dict, keyframe_count: int) -> dict:
    """
    通过关键帧密度推断场景切换频率。

    快速剪辑(高密度关键帧)的特征:
    - 平均每场景 < 2秒 → 可能是信息量高或情绪激烈的视频
    - 平均每场景 < 0.5秒 → 可能是视觉冲击/情绪操纵
    """
    duration = metadata.get("duration", 0)
    avg_duration = duration / max(keyframe_count, 1)

    rapid = 1 if keyframe_count > 0 and duration / keyframe_count < 1.0 else 0

    return {
        "keyframe_count": keyframe_count,
        "avg_scene_duration": round(avg_duration, 1),
        "rapid_cuts": rapid,
    }


# =============================================================================
# 主分析入口
# =============================================================================

def analyze_video_content(
    video_path: str,
    title: str = "",
    description: str = "",
) -> VideoContentAnalysis:
    """
    对视频文件进行深度内容分析。

    Args:
        video_path: 视频文件路径(本地文件)
        title: 视频标题
        description: 视频描述

    Returns:
        VideoContentAnalysis — 包含所有分析维度的结果

    使用:
        result = analyze_video_content("/path/to/video.mp4", title="震惊！XX事件")
        if result.combined_text:
            # 送入10引擎分析
            engine_result = await run_reasoning_pipeline(text=result.combined_text, ...)
    """
    analysis = VideoContentAnalysis()

    # ffmpeg 检查
    if not _check_ffmpeg():
        analysis.combined_text = f"{title}\n{description}"
        return analysis

    # 临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.wav")
        frame_dir = os.path.join(tmpdir, "frames")
        os.makedirs(frame_dir, exist_ok=True)

        # 1. 元数据
        meta = _get_video_metadata(video_path)
        analysis.duration_seconds = meta.get("duration", 0)
        analysis.resolution = meta.get("resolution", "")
        analysis.codec = meta.get("codec", "")
        analysis.file_size_mb = meta.get("size_mb", 0)

        # 2. 音频提取 + 语音转文字
        if _extract_audio(video_path, audio_path):
            transcript, lang = _transcribe_audio(audio_path)
            analysis.transcript = transcript
            analysis.transcript_language = lang

        # 3. 关键帧提取
        analysis.keyframe_count = _extract_keyframes(video_path, frame_dir, interval=2.0)

        # 4. OCR 文字提取
        ocr_text, ocr_kw = _extract_ocr_text(frame_dir)
        analysis.ocr_text = ocr_text
        analysis.ocr_keywords = ocr_kw

        # 5. 视觉情感
        visual = _analyze_visual_emotion(frame_dir)
        analysis.dominant_colors = visual["dominant_colors"]
        analysis.brightness_avg = visual["brightness_avg"]

        # 6. 场景分析
        scene = _detect_scene_changes(meta, analysis.keyframe_count)
        analysis.scene_changes = analysis.keyframe_count
        analysis.avg_scene_duration = scene["avg_scene_duration"]
        analysis.rapid_cuts = scene["rapid_cuts"]

        # 7. 标题-内容一致性
        match_ratio, is_clickbait = _check_title_content_match(
            title, analysis.ocr_text, analysis.transcript
        )
        analysis.title_content_match = match_ratio
        analysis.is_clickbait = is_clickbait

    # 合并文本
    combined_parts = []
    if title:
        combined_parts.append(f"视频标题: {title}")
    if description:
        combined_parts.append(f"视频描述: {description}")
    if analysis.ocr_text:
        combined_parts.append(f"画面文字: {analysis.ocr_text[:500]}")
    if analysis.transcript:
        combined_parts.append(f"语音转录: {analysis.transcript[:500]}")
    if analysis.is_clickbait:
        combined_parts.append("⚠️ 该视频被检测为可能标题党(标题与内容匹配度低)")
    analysis.combined_text = "\n".join(combined_parts)

    return analysis
