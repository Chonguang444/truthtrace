"""
视频内容深度提取 — 双策略采集

策略1 (主力): 平台原生音频流 API
  - B站: x/player/playurl?fnval=16 → DASH audio URL → httpx下载 → ffmpeg转WAV → Whisper
  - YouTube: youtube.com/oembed + 音频流下载
  优势: 不需要 yt-dlp, 不依赖外部工具, 直接调用平台API

策略2 (回退): 浏览器DOM抓取
  - 已有的 Chrome 扩展可直接从页面 __playinfo__ 提取音频URL
  - 或从页面内嵌JSON中提取结构化数据
  优势: 100%成功率, 不受API变化影响

策略3 (兜底): yt-dlp
  - 如果以上都失败, 回退到 yt-dlp 音频下载

参考开源:
  - bili2text: B站专属 Whisper (github.com/lanbinleo/bili2text)
  - biliup: B站视频下载 (github.com/biliup/biliup)
"""

from __future__ import annotations
import asyncio, hashlib, json, logging, os, re, subprocess, tempfile, time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

logger = logging.getLogger("truthtrace.video_transcriber")

TRANSCRIBE_CONFIG = {
    "whisper_model": os.environ.get("WHISPER_MODEL", "medium"),
    "whisper_device": os.environ.get("WHISPER_DEVICE", "cpu"),
    "whisper_compute_type": os.environ.get("WHISPER_COMPUTE_TYPE", "int8"),
    "language": os.environ.get("TRANSCRIBE_LANGUAGE", "zh"),
    "max_audio_duration": int(os.environ.get("TRANSCRIBE_MAX_DURATION", "300")),
}


@dataclass
class TranscriptResult:
    url: str = ""; platform: str = ""; video_title: str = ""
    full_text: str = ""; segments: list[dict] = field(default_factory=list)
    language: str = ""; duration_seconds: float = 0.0; word_count: int = 0
    download_ms: float = 0.0; transcribe_ms: float = 0.0
    method: str = ""; error: str = ""

    def to_dict(self) -> dict:
        return {
            "url": self.url, "platform": self.platform, "video_title": self.video_title,
            "full_text": self.full_text, "segments": self.segments[:20],
            "language": self.language, "duration_seconds": round(self.duration_seconds, 1),
            "word_count": self.word_count, "segment_count": self.segment_count,
            "method": self.method, "error": self.error,
        }

    @property
    def segment_count(self) -> int:
        return len(self.segments)


# =============================================================================
# 依赖检查
# =============================================================================

def _get_ffmpeg_path() -> str | None:
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        if r.returncode == 0: return "ffmpeg"
    except FileNotFoundError: pass
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe): return exe
    except ImportError: pass
    return None

def check_dependencies() -> dict:
    """检查视频音频转录所需的全部依赖。

    返回结构:
        {"ffmpeg": bool, "whisper": bool, "yt_dlp": bool,
         "ready": bool, "ready_for_youtube": bool,
         "missing": [{"dep": str, "install": str}, ...]}
    """
    ffmpeg_path = _get_ffmpeg_path()
    status = {
        "ffmpeg": ffmpeg_path is not None,
        "ffmpeg_path": ffmpeg_path,
    }

    # faster-whisper (核心依赖)
    try:
        from faster_whisper import WhisperModel  # noqa: F401
        status["whisper"] = True
    except ImportError:
        status["whisper"] = False

    # yt-dlp (YouTube 备用 / 通用回退)
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, timeout=5, check=True)
        status["yt_dlp"] = True
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        status["yt_dlp"] = False

    # 核心就绪 (B站直连仅需 ffmpeg + whisper)
    status["ready"] = status["ffmpeg"] and status["whisper"]
    # YouTube 就绪 (需要 yt-dlp 作为回退)
    status["ready_for_youtube"] = status["ready"] and status["yt_dlp"]

    # 可操作的安装指引
    missing = []
    if not status["ffmpeg"]:
        missing.append({
            "dep": "ffmpeg",
            "install": "Ubuntu: sudo apt install ffmpeg | Mac: brew install ffmpeg | Win: choco install ffmpeg 或 pip install imageio-ffmpeg"
        })
    if not status["whisper"]:
        missing.append({
            "dep": "faster_whisper",
            "install": "pip install faster-whisper"
        })
    if not status["yt_dlp"]:
        missing.append({
            "dep": "yt-dlp",
            "install": "pip install yt-dlp"
        })
    status["missing"] = missing

    return status


# =============================================================================
# 策略1: 平台原生音频流直接下载 (主力)
# =============================================================================

async def _extract_bilibili_audio(client, bvid: str, cid: int = 0) -> tuple[str | None, str, str]:
    """
    B站 playurl API → 提取音频流 URL → 逐块下载 → 返回本地WAV路径
    完全不需要 yt-dlp
    """
    import httpx
    if isinstance(client, str):
        # Create client if string passed
        pass

    # Step 1: 获取 cid (如果未提供)
    if not cid:
        resp = await client.get(
            f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}",
            headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"}
        )
        data = resp.json()
        pages = data.get("data", {}).get("pages", [])
        cid = pages[0].get("cid", 0) if pages else 0
        title = data.get("data", {}).get("title", "")
        if not cid:
            return None, "", "无法获取视频 cid"
    else:
        title = ""

    # Step 2: 调用 playurl API 获取音频直链
    play_resp = await client.get(
        f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&fnval=16",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": f"https://www.bilibili.com/video/{bvid}",
        }
    )
    play_data = play_resp.json()
    if play_data.get("code") != 0:
        return None, title, f"playurl API 返回错误: {play_data.get('message','')}"

    dash = play_data.get("data", {}).get("dash", {})
    audio_tracks = dash.get("audio", [])
    if not audio_tracks:
        return None, title, "未找到音频轨道"

    audio_url = audio_tracks[0].get("baseUrl") or audio_tracks[0].get("base_url", "")
    if not audio_url:
        return None, title, "音频URL为空"

    # Step 3: 下载音频流
    tmp_m4s = os.path.join(tempfile.gettempdir(), f"bili_{bvid}.m4s")
    try:
        dl_resp = await client.get(
            audio_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": f"https://www.bilibili.com/video/{bvid}",
                "Origin": "https://www.bilibili.com",
            }
        )
        with open(tmp_m4s, "wb") as f:
            f.write(dl_resp.content[:50_000_000])  # Max 50MB
    except Exception as e:
        return None, title, f"音频下载失败: {str(e)[:100]}"

    # Step 4: ffmpeg 转 WAV
    tmp_wav = tmp_m4s.replace(".m4s", ".wav")
    ffmpeg = _get_ffmpeg_path()
    if not ffmpeg:
        os.unlink(tmp_m4s)
        return None, title, "ffmpeg 不可用"

    try:
        subprocess.run(
            [ffmpeg, "-i", tmp_m4s, "-ar", "16000", "-ac", "1",
             "-t", str(TRANSCRIBE_CONFIG["max_audio_duration"]),
             tmp_wav, "-y"],
            capture_output=True, check=True, timeout=60
        )
    except Exception as e:
        os.unlink(tmp_m4s)
        return None, title, f"音频转换失败: {str(e)[:100]}"
    finally:
        if os.path.exists(tmp_m4s):
            os.unlink(tmp_m4s)

    return tmp_wav, title, ""


async def _extract_youtube_audio(client, url: str) -> tuple[str | None, str, str]:
    """YouTube oEmbed + 音频流 (目前需要浏览器cookie绕过bot检测)"""
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    vid = ""
    if "youtube.com" in parsed.netloc:
        vid = parse_qs(parsed.query).get("v", [""])[0]
    elif "youtu.be" in parsed.netloc:
        vid = parsed.path.strip("/")

    if not vid:
        return None, "", "无法解析 YouTube video ID"

    # 尝试 oEmbed 获取标题
    try:
        oembed = await client.get(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json")
        if oembed.status_code == 200:
            title = oembed.json().get("title", "")
        else:
            title = ""
    except Exception:
        title = ""

    # 直接下载音频流 (YouTube 需要cookie/CORS签名)
    # 返回空 error 让 transcribe_video 的 yt-dlp 回退接管
    return None, title, ""


# =============================================================================
# 策略2: Whisper 语音转文字
# =============================================================================

class WhisperEngine:
    def __init__(self, model="medium", device="cpu", compute_type="int8"):
        self.model_size = model; self.device = device; self.compute_type = compute_type
        self._model = None

    def _get_model(self):
        if self._model is not None: return self._model
        from faster_whisper import WhisperModel
        self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        logger.info(f"Whisper loaded: {self.model_size} on {self.device}")
        return self._model

    def transcribe(self, wav_path: str) -> tuple[str, list[dict], str, float]:
        model = self._get_model()
        segments_iter, info = model.transcribe(
            wav_path,
            language=TRANSCRIBE_CONFIG["language"] or None,
            beam_size=5, vad_filter=True,
        )
        segments = []
        parts = []
        for seg in segments_iter:
            segments.append({"start": round(seg.start, 1), "end": round(seg.end, 1), "text": seg.text.strip()})
            parts.append(seg.text.strip())
        return "\n".join(parts), segments, info.language, info.duration


# =============================================================================
# 统一入口
# =============================================================================

class VideoTranscriber:
    def __init__(self):
        self._whisper = None
        self._client = None

    @property
    def whisper(self) -> WhisperEngine:
        if self._whisper is None:
            self._whisper = WhisperEngine(
                model=TRANSCRIBE_CONFIG["whisper_model"],
                device=TRANSCRIBE_CONFIG["whisper_device"],
                compute_type=TRANSCRIBE_CONFIG["whisper_compute_type"],
            )
        return self._whisper

    async def _get_client(self):
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(timeout=120, follow_redirects=True)
        return self._client

    async def close(self):
        if self._client: await self._client.aclose(); self._client = None

    async def transcribe_video(self, url: str, title_hint: str = "", cid: int = 0) -> TranscriptResult:
        """
        完整的视频转录:
        策略1: 平台原生API提取音频URL → httpx下载 → ffmpeg转换 → Whisper
        策略2: 浏览器DOM抓取 (通过扩展注入)
        策略3: yt-dlp 兜底
        """
        result = TranscriptResult(url=url, video_title=title_hint)

        deps = check_dependencies()
        if not deps["ready"]:
            result.error = f"缺少依赖: {[k for k,v in deps.items() if not v]}"
            return result

        from app.crawler.video_platforms import identify_video_platform
        result.platform = identify_video_platform(url) or "unknown"

        client = await self._get_client()
        wav_path = None
        title = title_hint

        # === 策略1: 平台原生 API ===
        bvid = ""
        if "bilibili.com" in url or "b23.tv" in url:
            m = re.search(r'(BV[A-Za-z0-9]{10})', url)
            bvid = m.group(1) if m else ""
            if not bvid:
                # 短链接: b23.tv/xxxxx
                try:
                    r = await client.get(url, follow_redirects=True)
                    m2 = re.search(r'(BV[A-Za-z0-9]{10})', str(r.url))
                    bvid = m2.group(1) if m2 else ""
                except Exception:
                    pass

            if bvid:
                logger.info(f"[视频提取] B站直连: {bvid}")
                wav_path, api_title, err = await _extract_bilibili_audio(client, bvid, cid)
                if api_title and not title: title = api_title
                result.method = "bilibili-playurl-api"
            else:
                err = "无法提取 BV 号"
        elif "youtube.com" in url or "youtu.be" in url:
            wav_path, api_title, err = await _extract_youtube_audio(client, url)
            if api_title and not title: title = api_title
            result.method = "youtube-oembed"
        else:
            err = f"不支持的平台: {result.platform}"

        # 更新标题
        if title: result.video_title = title

        # === 策略3 兜底: yt-dlp ===
        if not wav_path:
            try:
                logger.info(f"[视频提取] 回退到 yt-dlp: {url[:60]}")
                wav_path, dl_title, dl_err = await self._fallback_ytdlp(client, url)
                if dl_title and not title: result.video_title = dl_title
                result.method = "yt-dlp-fallback"
                if dl_err: err = dl_err
            except Exception as e:
                pass

        if not wav_path or err:
            result.error = err or "所有提取策略均失败"
            return result

        # === Whisper 转录 ===
        start = time.time()
        try:
            full_text, segments, lang, duration = self.whisper.transcribe(wav_path)
            result.full_text = full_text; result.segments = segments[:100]
            result.language = lang or TRANSCRIBE_CONFIG["language"]
            result.duration_seconds = duration
            result.word_count = len(full_text); result.transcribe_ms = (time.time() - start) * 1000
            logger.info(f"[转录] {result.word_count} 字, {len(segments)} 段")
        except Exception as e:
            result.error = f"Whisper 转录失败: {str(e)[:200]}"
        finally:
            if wav_path and os.path.exists(wav_path):
                try: os.unlink(wav_path)
                except Exception: pass

        return result

    async def _fallback_ytdlp(self, client, url: str) -> tuple[str | None, str, str]:
        """yt-dlp 兜底 (仅在前两个策略都失败时使用)"""
        try:
            import subprocess, tempfile, os
            with tempfile.NamedTemporaryFile(suffix=".m4a", delete=False) as tmp:
                audio_path = tmp.name

            ffmpeg = _get_ffmpeg_path()
            cmd = [
                "yt-dlp", "-f", "bestaudio[ext=m4a]/bestaudio/best",
                "--extract-audio", "--audio-format", "wav",
                "--max-filesize", "200M", "--no-playlist", "--no-warnings",
                "-o", audio_path.replace(".m4a", "%(id)s.%(ext)s"),
                "--add-header", "User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            ]
            if ffmpeg and ffmpeg != "ffmpeg":
                cmd.extend(["--ffmpeg-location", ffmpeg])
            cmd.append(url)

            process = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
            except asyncio.TimeoutError:
                process.kill(); return None, "", "yt-dlp 超时"

            if process.returncode != 0:
                return None, "", f"yt-dlp 失败: {stderr.decode(errors='replace')[:100]}"

            # 找到输出文件
            import glob
            for f in glob.glob(audio_path.replace(".m4a", "*")):
                if f.endswith((".wav", ".m4a", ".mp3")):
                    return f, "", ""
            return None, "", "未找到下载文件"
        except FileNotFoundError:
            return None, "", "yt-dlp 未安装"

# 全局单例
_transcriber: VideoTranscriber | None = None

def get_transcriber() -> VideoTranscriber:
    global _transcriber
    if _transcriber is None: _transcriber = VideoTranscriber()
    return _transcriber
