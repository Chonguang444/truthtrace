"""
视频音频提取 + 语音转文字 — 深度视频内容分析

技术栈:
  - yt-dlp: 音频下载 (支持 B站/YouTube/抖音/快手等 1000+ 平台)
  - faster-whisper: 本地语音识别 (CTranslate2 加速, 4x faster)
  - ffmpeg: 音频格式转换

流程:
  视频URL → yt-dlp下载音频(m4a/mp3) → ffmpeg转16kHz WAV → Whisper转录 → 送入引擎分析

参考开源项目:
  - bili2text (github.com/lanbinleo/bili2text): B站专属的 Whisper 转写工具
  - juAo12/bilibili-audio-to-text (github.com/juAo12): B站音频→Whisper
  - mcp-video-extraction (github.com/SealinGp): MCP 协议的视频提取
  - AI-Video-Transcriber (github.com/wendy7756): 30+ 平台 Faster-Whisper
"""

from __future__ import annotations
import asyncio
import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("truthtrace.video_transcriber")

# =============================================================================
# 配置
# =============================================================================

TRANSCRIBE_CONFIG = {
    "whisper_model": "medium",       # tiny/base/small/medium/large-v3
    "whisper_device": "cpu",         # cpu / cuda
    "whisper_compute_type": "int8",  # float16 / int8 / int8_float16
    "language": "zh",                # 自动检测或强制指定
    "max_audio_duration": 600,       # 最多处理 10 分钟音频
    "temp_dir": None,                # 临时文件目录 (None=系统默认)
    "keep_audio": False,             # 保留下载的音频文件
    "timeout_download": 120,         # 下载超时
    "timeout_transcribe": 300,       # 转录超时
}


@dataclass
class TranscriptResult:
    """语音转录完整结果"""
    url: str = ""
    platform: str = ""
    video_title: str = ""
    # 转录
    full_text: str = ""
    segments: list[dict] = field(default_factory=list)  # [{start, end, text}]
    language: str = ""
    duration_seconds: float = 0.0
    # 元数据
    word_count: int = 0
    segment_count: int = 0
    # 统计
    download_duration_ms: float = 0.0
    transcribe_duration_ms: float = 0.0
    audio_file: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "platform": self.platform,
            "video_title": self.video_title,
            "full_text": self.full_text,
            "segments": self.segments[:20],
            "language": self.language,
            "duration_seconds": round(self.duration_seconds, 1),
            "word_count": self.word_count,
            "segment_count": self.segment_count,
            "download_duration_ms": round(self.download_duration_ms, 0),
            "transcribe_duration_ms": round(self.transcribe_duration_ms, 0),
            "error": self.error,
        }


# =============================================================================
# 检查依赖
# =============================================================================

def _check_yt_dlp() -> bool:
    """检查 yt-dlp 是否可用"""
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
    except Exception:
        return False


def _check_ffmpeg() -> bool:
    """检查 ffmpeg 是否可用"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
    except Exception:
        return False


def _check_whisper() -> bool:
    """检查 faster-whisper 是否可用"""
    try:
        from faster_whisper import WhisperModel
        return True
    except ImportError:
        try:
            import whisper
            return True
        except ImportError:
            return False


def check_dependencies() -> dict:
    """检查所有依赖, 返回状态"""
    status = {
        "yt_dlp": _check_yt_dlp(),
        "ffmpeg": _check_ffmpeg(),
        "whisper": _check_whisper(),
    }
    status["ready"] = all(status.values())
    if not status["ready"]:
        missing = [k for k, v in status.items() if not v]
        logger.warning(f"视频转录缺少依赖: {missing}")
        status["missing"] = missing
    return status


# =============================================================================
# 核心: 音频下载 + 转录
# =============================================================================

class VideoTranscriber:
    """
    视频深度转录器 — 下载音频 + Whisper语音转文字
    """

    def __init__(self, model: str = "medium", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model
        self.device = device
        self.compute_type = compute_type
        self._model = None  # 延迟加载

    def _get_model(self):
        """延迟加载 Whisper 模型 (首次转录时才加载, ~1.5GB)"""
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info(f"Whisper 模型已加载: {self.model_size} on {self.device}")
        except ImportError:
            # 回退到 openai-whisper
            import whisper
            self._model = whisper.load_model(self.model_size)
            logger.info(f"openai-whisper 模型已加载: {self.model_size}")
        return self._model

    def transcribe_audio(self, audio_path: str) -> tuple[str, list[dict], str, float]:
        """
        对音频文件执行语音转文字。

        Returns: (full_text, segments, detected_lang, duration)
        """
        model = self._get_model()
        start = time.time()

        try:
            from faster_whisper import WhisperModel
            if isinstance(model, WhisperModel):
                # faster-whisper API
                segments_iter, info = model.transcribe(
                    audio_path,
                    language=TRANSCRIBE_CONFIG["language"] or None,
                    beam_size=5,
                    vad_filter=True,  # 自动跳过静音段
                )
                segments = []
                full_parts = []
                for seg in segments_iter:
                    segments.append({
                        "start": round(seg.start, 1),
                        "end": round(seg.end, 1),
                        "text": seg.text.strip(),
                    })
                    full_parts.append(seg.text.strip())
                return "\n".join(full_parts), segments, info.language, info.duration
            else:
                # openai-whisper API
                result = model.transcribe(
                    audio_path,
                    language=TRANSCRIBE_CONFIG["language"] or None,
                )
                segments = [
                    {"start": round(s["start"], 1), "end": round(s["end"], 1), "text": s["text"].strip()}
                    for s in result.get("segments", [])
                ]
                return result.get("text", ""), segments, result.get("language", "zh"), 0.0

        except Exception as e:
            logger.error(f"Whisper 转录失败: {e}")
            raise

        finally:
            elapsed = (time.time() - start) * 1000
            logger.info(f"转录完成: {elapsed:.0f}ms")

    async def transcribe_video(
        self,
        url: str,
        title_hint: str = "",
        max_duration: int = 300,
    ) -> TranscriptResult:
        """
        完整的视频转录流程: 下载音频 → 转录 → 返回文本

        Args:
            url: 视频 URL (B站/YouTube/抖音/快手等)
            title_hint: 已知标题(可选)
            max_duration: 最大音频时长(秒)

        Returns:
            TranscriptResult 含完整转写文本
        """
        result = TranscriptResult(url=url, video_title=title_hint)

        # Step 0: 检查依赖
        deps = check_dependencies()
        if not deps["ready"]:
            result.error = f"缺少依赖: {deps.get('missing', [])}"
            return result

        # 识别平台
        from app.crawler.video_platforms import identify_video_platform
        result.platform = identify_video_platform(url) or "unknown"

        # Step 1: 下载音频 (yt-dlp)
        with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
            audio_path = tmp.name

        try:
            download_start = time.time()

            # yt-dlp 命令: 提取音频, 限定时长
            cmd = [
                "yt-dlp",
                "-f", "bestaudio[ext=m4a]/bestaudio/best",  # 最佳音频
                "--extract-audio",
                "--audio-format", "wav",                    # 转为 WAV
                "--audio-quality", "0",                      # 最佳质量
                "--max-filesize", "200M",                    # 限制文件大小
                "--no-playlist",
                "--no-warnings",
                "--output", audio_path.replace(".m4a", "%(id)s.%(ext)s"),
                url,
            ]

            if max_duration:
                # yt-dlp 支持按时间段下载 (--download-sections)
                # 但我们用 post-processing 限制，先下载完整音频
                pass

            logger.info(f"[转录] 下载音频: {url[:60]}...")
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=TRANSCRIBE_CONFIG["timeout_download"],
                )
            except asyncio.TimeoutError:
                process.kill()
                result.error = "音频下载超时"
                return result

            result.download_duration_ms = (time.time() - download_start) * 1000

            if process.returncode != 0:
                err_text = stderr.decode()[:200]
                logger.error(f"yt-dlp 失败: {err_text}")
                result.error = f"音频下载失败: {err_text[:100]}"
                return result

            # 查找实际输出的音频文件
            actual_audio = self._find_output_audio(audio_path)
            if not actual_audio:
                result.error = "未找到下载的音频文件"
                return result

            result.audio_file = actual_audio

            # 获取视频标题 (从 yt-dlp 输出)
            title = self._extract_title_from_output(stdout.decode())
            if title and not result.video_title:
                result.video_title = title

            # Step 2: Whisper 转录
            logger.info(f"[转录] Whisper 转写中: {actual_audio}")
            transcribe_start = time.time()

            full_text, segments, lang, duration = self.transcribe_audio(actual_audio)
            result.full_text = full_text
            result.segments = segments[:100]  # 最多保留 100 段
            result.language = lang or TRANSCRIBE_CONFIG["language"] or "zh"
            result.duration_seconds = duration
            result.word_count = len(full_text)
            result.segment_count = len(segments)
            result.transcribe_duration_ms = (time.time() - transcribe_start) * 1000

            logger.info(
                f"[转录] 完成: {result.word_count} 字, "
                f"{result.segment_count} 段, "
                f"下载 {result.download_duration_ms:.0f}ms, "
                f"转录 {result.transcribe_duration_ms:.0f}ms"
            )

        except Exception as e:
            logger.error(f"[转录] 异常: {e}")
            result.error = str(e)[:200]

        finally:
            # 清理临时文件
            if not TRANSCRIBE_CONFIG["keep_audio"] and result.audio_file:
                try:
                    os.unlink(result.audio_file)
                except Exception:
                    pass
            if os.path.exists(audio_path):
                try:
                    os.unlink(audio_path)
                except Exception:
                    pass

        return result

    def _find_output_audio(self, base_path: str) -> str | None:
        """查找 yt-dlp 实际输出的音频文件"""
        import glob

        # yt-dlp 的实际输出路径可能包含视频ID
        base_dir = os.path.dirname(base_path) or "."
        patterns = [
            base_path,
            base_path.replace(".m4a", ".wav"),
            base_path.replace(".m4a", ".mp3"),
            base_path.replace(".m4a", ".m4a"),
            os.path.join(base_dir, "*.wav"),
            os.path.join(base_dir, "*.m4a"),
            os.path.join(base_dir, "*.mp3"),
        ]

        for pat in patterns:
            matches = glob.glob(pat)
            for m in matches:
                if os.path.getsize(m) > 1024:  # >1KB
                    return m
        return None

    @staticmethod
    def _extract_title_from_output(output: str) -> str:
        """从 yt-dlp 输出中提取视频标题"""
        for line in output.split("\n"):
            if "[download] Destination:" in line:
                title = line.split("Destination:")[-1].strip()
                return os.path.splitext(os.path.basename(title))[0]
        return ""


# =============================================================================
# 全局单例
# =============================================================================

_transcriber: VideoTranscriber | None = None


def get_transcriber() -> VideoTranscriber:
    global _transcriber
    if _transcriber is None:
        _transcriber = VideoTranscriber(
            model=TRANSCRIBE_CONFIG["whisper_model"],
            device=TRANSCRIBE_CONFIG["whisper_device"],
            compute_type=TRANSCRIBE_CONFIG["whisper_compute_type"],
        )
    return _transcriber


def get_dependency_status() -> dict:
    """获取外部依赖状态"""
    status = check_dependencies()
    status["whisper_model"] = TRANSCRIBE_CONFIG["whisper_model"]
    status["whisper_device"] = TRANSCRIBE_CONFIG["whisper_device"]
    return status
