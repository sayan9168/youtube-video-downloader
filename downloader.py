"""yt-dlp integration layer.

This module contains every interaction with yt-dlp: fetching metadata,
building format selectors, running downloads with progress reporting and
collecting the resulting files.  It is intentionally free of FastAPI imports so
it can be reused (CLI, tests, workers) and so the download logic stays easy to
reason about.
"""

from __future__ import annotations

import copy
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlsplit

import httpx
import yt_dlp
from yt_dlp.utils import DownloadError, PostProcessingError

from config import ALLOWED_THUMBNAIL_HOSTS, settings

ProgressCallback = Callable[[Dict[str, Any]], None]
CancelCheck = Callable[[], bool]

YOUTUBE_HOSTS = {
    "youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "gaming.youtube.com",
}
SHORT_HOSTS = {"youtu.be"}

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class JobCancelled(Exception):
    """Raised from inside a yt-dlp progress hook to abort a download."""


class DownloaderError(Exception):
    """A user facing download error with a stable machine readable code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


def normalize_url(raw: str) -> str:
    url = (raw or "").strip()
    if not url:
        return ""
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        url = "https://" + url.lstrip("/")
    return url


def _host_of(url: str) -> str:
    try:
        host = (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def is_youtube_url(url: str) -> bool:
    url = normalize_url(url)
    if not url:
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme not in {"http", "https"}:
        return False
    host = _host_of(url)
    if host in SHORT_HOSTS:
        return bool(parts.path.strip("/"))
    if host not in YOUTUBE_HOSTS:
        return False
    path = parts.path or "/"
    if host == "music.youtube.com":
        return True
    if path in {"/", ""}:
        return "list" in parse_qs(parts.query)
    return True


def is_playlist_url(url: str) -> bool:
    """True when the URL points at a collection rather than a single video."""
    url = normalize_url(url)
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    host = _host_of(url)
    query = parse_qs(parts.query)
    path = parts.path or "/"

    if host in SHORT_HOSTS:
        return False
    if "v" in query:
        # /watch?v=...&list=... -> the user asked for one video
        return False
    if "list" in query:
        return True
    if path.startswith(("/playlist", "/embed/playlist")):
        return True
    if re.match(r"^/(@[^/]+|c/[^/]+|user/[^/]+|channel/[^/]+|results)(/|$)", path):
        return True
    if path.rstrip("/").endswith(("/videos", "/shorts", "/streams", "/playlists")):
        return True
    return False


def normalize_youtube_url(raw: str) -> str:
    url = normalize_url(raw)
    if not is_youtube_url(url):
        raise DownloaderError("invalid_url", "Please provide a valid YouTube URL")
    return url


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_filesize(size: Optional[float]) -> str:
    if not size:
        return "—"
    size = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


def format_duration(seconds: Optional[float]) -> str:
    if not seconds:
        return ""
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_speed(speed: Optional[float]) -> Optional[str]:
    if not speed:
        return None
    return f"{format_filesize(speed)}/s"


def format_eta(eta: Optional[float]) -> Optional[str]:
    if eta is None:
        return None
    return format_duration(eta)


def sanitize_filename(name: str, max_length: Optional[int] = None) -> str:
    """Make a user supplied filename safe for the filesystem and HTTP headers."""
    max_length = max_length or settings.max_filename_length
    name = unicodedata.normalize("NFC", (name or "").strip())
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = name.replace("/", "-").replace("\\", "-")
    name = re.sub(r'[<>:"|?*]', "", name)
    name = re.sub(r"\s+", " ", name).strip(" .-")
    if name.lower().endswith((".mp4", ".webm", ".mkv", ".mp3", ".m4a", ".opus", ".srt", ".vtt", ".zip")):
        name = name.rsplit(".", 1)[0]
    name = name.strip(" .-")
    if len(name) > max_length:
        name = name[:max_length].rstrip(" .-")
    return name or "download"


# ---------------------------------------------------------------------------
# yt-dlp option factories
# ---------------------------------------------------------------------------


def _base_opts() -> Dict[str, Any]:
    opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "socket_timeout": settings.socket_timeout,
        "retries": settings.retries,
        "fragment_retries": settings.retries,
        "extractor_retries": 1,
        "cachedir": False,
    }
    ffmpeg = settings.ffmpeg_location
    if ffmpeg:
        opts["ffmpeg_location"] = ffmpeg
    return opts


def fetch_media_info(url: str, force_playlist: bool = False) -> Dict[str, Any]:
    """Extract metadata for a video or playlist URL."""
    if settings.demo_mode:
        from demo import demo_media_info

        return demo_media_info(url, force_playlist=force_playlist)

    url = normalize_youtube_url(url)
    playlist = force_playlist or is_playlist_url(url)
    opts = _base_opts()
    opts["noplaylist"] = not playlist
    opts["skip_download"] = True
    if playlist:
        opts["extract_flat"] = "in_playlist"
        opts["playlistend"] = settings.max_playlist_entries
        opts["ignoreerrors"] = True

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as exc:
        raise _map_extract_error(exc) from exc
    except Exception as exc:  # pragma: no cover - network / extractor surprises
        raise DownloaderError("extract_failed", "Could not read this video. Please try again.") from exc

    if not info:
        raise DownloaderError("extract_failed", "Could not extract video information.")

    if playlist:
        return _playlist_payload(info, url)
    return _video_payload(info, url)


def _video_payload(info: Dict[str, Any], url: str) -> Dict[str, Any]:
    formats = _build_formats(info)
    heights = sorted({f["height"] for f in formats if f.get("height") and not f["is_audio"]}, reverse=True)
    return {
        "type": "video",
        "url": url,
        "id": info.get("id"),
        "title": info.get("title") or "Untitled video",
        "thumbnail": _pick_thumbnail(info),
        "duration": info.get("duration"),
        "duration_str": format_duration(info.get("duration")),
        "uploader": info.get("uploader") or info.get("channel"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "upload_date": info.get("upload_date"),
        "is_live": bool(info.get("is_live")),
        "description": (info.get("description") or "").strip()[:400] or None,
        "formats": formats,
        "available_qualities": [h for h in heights if h >= 144][:8],
        "subtitles": _build_subtitles(info),
        "playlist": None,
    }


def _playlist_payload(info: Dict[str, Any], url: str) -> Dict[str, Any]:
    raw_entries = info.get("entries") or []
    entries: List[Dict[str, Any]] = []
    for position, entry in enumerate(raw_entries, start=1):
        if not entry or not entry.get("id"):
            continue
        entries.append(
            {
                "index": position,
                "id": entry.get("id"),
                "url": entry.get("webpage_url")
                or entry.get("url")
                or f"https://www.youtube.com/watch?v={entry.get('id')}",
                "title": entry.get("title") or f"Video {position}",
                "thumbnail": _pick_thumbnail(entry),
                "duration": entry.get("duration"),
                "duration_str": format_duration(entry.get("duration")),
                "uploader": entry.get("uploader") or entry.get("channel"),
            }
        )
    total = info.get("playlist_count") or len(entries)
    return {
        "type": "playlist",
        "url": url,
        "id": info.get("id"),
        "title": info.get("title") or "Playlist",
        "thumbnail": entries[0]["thumbnail"] if entries else _pick_thumbnail(info),
        "uploader": info.get("uploader") or info.get("channel"),
        "count": total,
        "entries": entries,
        "truncated": bool(total and len(entries) < total),
        "max_entries": settings.max_playlist_entries,
        "formats": [],
        "available_qualities": [],
        "subtitles": [],
    }


def _pick_thumbnail(info: Dict[str, Any]) -> Optional[str]:
    if info.get("thumbnail"):
        return info["thumbnail"]
    thumbnails = info.get("thumbnails") or []
    for thumb in reversed(thumbnails):
        if thumb.get("url"):
            return thumb["url"]
    if info.get("id"):
        return f"https://i.ytimg.com/vi/{info['id']}/hqdefault.jpg"
    return None


def _build_formats(info: Dict[str, Any]) -> List[Dict[str, Any]]:
    formats: List[Dict[str, Any]] = []
    seen = set()
    for raw in info.get("formats") or []:
        format_id = raw.get("format_id")
        if not format_id or format_id in seen:
            continue
        seen.add(format_id)
        vcodec = raw.get("vcodec")
        acodec = raw.get("acodec")
        if vcodec == "none" and acodec == "none":
            continue
        is_audio = vcodec == "none"
        height = raw.get("height")
        size = raw.get("filesize") or raw.get("filesize_approx")
        if is_audio:
            label = f"Audio {raw.get('abr') or raw.get('tbr') or ''}".strip()
            resolution = "audio"
        else:
            resolution = f"{height}p" if height else (raw.get("resolution") or "video")
            label = resolution
            if raw.get("fps") and raw["fps"] >= 50:
                label += f"{int(raw['fps'])}"
        formats.append(
            {
                "format_id": format_id,
                "ext": raw.get("ext") or "mp4",
                "resolution": resolution,
                "label": label,
                "height": height,
                "fps": raw.get("fps"),
                "filesize": size,
                "filesize_str": format_filesize(size),
                "vcodec": vcodec,
                "acodec": acodec,
                "format_note": raw.get("format_note") or "",
                "dynamic_range": raw.get("dynamic_range") or "SDR",
                "tbr": raw.get("tbr"),
                "is_audio": is_audio,
                "is_video_only": acodec == "none" and vcodec != "none",
                "is_progressive": vcodec != "none" and acodec != "none",
            }
        )

    def sort_key(item: Dict[str, Any]):
        if item["is_audio"]:
            return (2, -(item.get("tbr") or 0), item["format_id"])
        return (1 if item["is_video_only"] else 0, -(item.get("height") or 0), -(item.get("tbr") or 0))

    formats.sort(key=sort_key)
    return formats[:60]


SUBTITLE_LANG_NAMES: Dict[str, str] = {
    "en": "English",
    "bn": "বাংলা (Bengali)",
    "hi": "हिन्दी (Hindi)",
    "ur": "اردو (Urdu)",
    "ar": "العربية (Arabic)",
    "es": "Español",
    "pt": "Português",
    "fr": "Français",
    "de": "Deutsch",
    "it": "Italiano",
    "ru": "Русский",
    "ja": "日本語",
    "ko": "한국어",
    "zh": "中文",
    "id": "Bahasa Indonesia",
    "ms": "Bahasa Melayu",
    "ta": "தமிழ் (Tamil)",
    "te": "తెలుగు (Telugu)",
    "ml": "മലയാളം (Malayalam)",
    "kn": "ಕನ್ನಡ (Kannada)",
    "gu": "ગુજરાતી (Gujarati)",
    "mr": "मराठी (Marathi)",
    "pa": "ਪੰਜਾਬੀ (Punjabi)",
    "ne": "नेपाली (Nepali)",
    "si": "සිංහල (Sinhala)",
    "th": "ไทย",
    "vi": "Tiếng Việt",
    "tr": "Türkçe",
    "pl": "Polski",
    "nl": "Nederlands",
    "uk": "Українська",
    "fa": "فارسی",
    "he": "עברית",
    "sw": "Kiswahili",
    "fil": "Filipino",
}


def subtitle_language_name(code: str) -> str:
    base = code.split("-")[0].lower()
    return SUBTITLE_LANG_NAMES.get(base, code)


def _build_subtitles(info: Dict[str, Any]) -> List[Dict[str, Any]]:
    manual = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    result: List[Dict[str, Any]] = []
    for code in set(manual) | set(automatic):
        name = subtitle_language_name(code)
        result.append({"code": code, "name": name, "auto": code not in manual})
    priority = {"en": 0, "bn": 1}

    def sort_key(item: Dict[str, Any]):
        base = item["code"].split("-")[0]
        return (1 if item["auto"] else 0, priority.get(base, 5), base, item["code"])

    result.sort(key=sort_key)
    return result[:40]


def _map_extract_error(exc: Exception) -> DownloaderError:
    message = str(exc).lower()
    if "private" in message or "sign in" in message or "login" in message or "members-only" in message:
        return DownloaderError("private_video", "This video is private or requires sign-in.")
    if "age" in message and ("restrict" in message or "confirm" in message):
        return DownloaderError("age_restricted", "This video is age restricted and cannot be downloaded.")
    if "removed" in message or "unavailable" in message or "does not exist" in message:
        return DownloaderError("unavailable", "This video is unavailable or was removed.")
    if "timed out" in message or "timeout" in message or "getaddrinfo" in message or "connection" in message:
        return DownloaderError("network", "Could not reach YouTube. Please check your connection.")
    if "unsupported url" in message or "no video" in message:
        return DownloaderError("invalid_url", "This URL is not supported.")
    if "live" in message and "not" in message:
        return DownloaderError("live_unsupported", "Live streams cannot be downloaded yet.")
    return DownloaderError("extract_failed", "Could not read this video. It may be restricted.")


# ---------------------------------------------------------------------------
# Format selection
# ---------------------------------------------------------------------------


def video_format_selector(quality: str, format_id: Optional[str] = None) -> str:
    """Translate a friendly quality preset into a yt-dlp format selector."""
    quality = (quality or "best").lower()
    can_merge = settings.ffmpeg_available

    if quality == "custom" and format_id:
        if not can_merge:
            return format_id
        return f"{format_id}+bestaudio/{format_id}"

    if not can_merge:
        # Without ffmpeg yt-dlp can only deliver progressive (video+audio) files.
        if quality in {"best", "best_mp4"}:
            return "b[ext=mp4]/b"
        if quality == "worst":
            return "w[ext=mp4]/w"
        if quality.isdigit():
            return f"b[height<={quality}][ext=mp4]/b[height<={quality}]/b[ext=mp4]/b"
        return "b[ext=mp4]/b"

    if quality == "best":
        return "bv*+ba/b"
    if quality == "best_mp4":
        return "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b"
    if quality == "worst":
        return "wv*+wa/w"
    if quality.isdigit():
        height = int(quality)
        return (
            f"bv*[height<={height}][ext=mp4]+ba[ext=m4a]/"
            f"bv*[height<={height}]+ba/b[height<={height}]/b"
        )
    return "bv*+ba/b"


AUDIO_CODECS = {"mp3", "m4a", "opus", "flac", "wav", "best"}


def _audio_postprocessors(audio_format: str, audio_quality: int) -> List[Dict[str, Any]]:
    audio_format = (audio_format or "mp3").lower()
    if audio_format not in AUDIO_CODECS:
        audio_format = "mp3"
    if audio_format == "best":
        return []
    codec = audio_format
    postprocessor: Dict[str, Any] = {"key": "FFmpegExtractAudio", "preferredcodec": codec}
    if codec in {"mp3", "m4a"}:
        postprocessor["preferredquality"] = str(max(64, min(320, int(audio_quality or 192))))
    return [postprocessor]


# ---------------------------------------------------------------------------
# Download execution
# ---------------------------------------------------------------------------

IGNORED_SUFFIXES = {".part", ".ytdl", ".temp", ".tmp", ".json", ".description"}


def _emit(on_progress: Optional[ProgressCallback], **update: Any) -> None:
    if on_progress is None:
        return
    try:
        on_progress(update)
    except JobCancelled:
        raise
    except Exception:  # never let a UI callback break the download
        pass


def execute_job(
    options: Dict[str, Any],
    job_dir: Path,
    on_progress: Optional[ProgressCallback] = None,
    is_cancelled: Optional[CancelCheck] = None,
) -> Dict[str, Any]:
    """Download ``options['url']`` into ``job_dir`` and report progress.

    Returns a dict describing the produced files.  Raises ``DownloaderError``
    for expected failures and ``JobCancelled`` when the user cancels.
    """
    if settings.demo_mode:
        from demo import execute_demo_job

        return execute_demo_job(options, job_dir, on_progress, is_cancelled)

    url = normalize_youtube_url(options.get("url", ""))
    mode = (options.get("mode") or "video").lower()
    job_dir.mkdir(parents=True, exist_ok=True)

    playlist_mode = bool(options.get("playlist")) or is_playlist_url(url)
    subtitle_langs = [lang for lang in (options.get("subtitle_langs") or []) if isinstance(lang, str)]
    trim_start = _as_float(options.get("trim_start"))
    trim_end = _as_float(options.get("trim_end"))
    audio_format = (options.get("audio_format") or "mp3").lower()

    if trim_start is not None or trim_end is not None:
        if not settings.ffmpeg_available:
            raise DownloaderError("ffmpeg_missing", "Trimming needs ffmpeg, which is not installed on the server.")
        if trim_start is not None and trim_end is not None and trim_end <= trim_start:
            raise DownloaderError("invalid_trim", "The end time must be after the start time.")

    if mode == "audio" and audio_format != "best" and not settings.ffmpeg_available:
        raise DownloaderError(
            "ffmpeg_missing",
            f"Converting to {audio_format.upper()} needs ffmpeg, which is not installed on the server.",
        )
    if mode == "subtitles" and subtitle_langs and not settings.ffmpeg_available:
        # yt-dlp can still write .vtt files without ffmpeg
        pass

    custom_name = options.get("filename")
    template = _output_template(custom_name, playlist_mode)
    total_entries = int(options.get("entry_count") or 1)

    ydl_opts = _base_opts()
    ydl_opts.update(
        {
            "outtmpl": {"default": template},
            "paths": {"home": str(job_dir), "temp": str(job_dir / ".tmp")},
            "trim_file_name": settings.max_filename_length,
            "overwrites": True,
            "continuedl": True,
            "noplaylist": not playlist_mode,
            "ignoreerrors": False,
            "concurrent_fragment_downloads": 4,
        }
    )

    if playlist_mode:
        if options.get("playlist_items"):
            ydl_opts["playlist_items"] = str(options["playlist_items"])
        else:
            # Never start an unbounded crawl of a channel or playlist.
            ydl_opts["playlistend"] = settings.max_playlist_entries

    progress_state = {"finished": set(), "total": max(1, total_entries)}

    def progress_hook(status: Dict[str, Any]) -> None:
        if is_cancelled and is_cancelled():
            raise JobCancelled()
        info = status.get("info_dict") or {}
        entry_index = info.get("playlist_index") or 1
        playlist_count = info.get("playlist_count") or info.get("n_entries")
        if playlist_count:
            progress_state["total"] = max(progress_state["total"], int(playlist_count))

        if status.get("status") == "downloading":
            total_bytes = status.get("total_bytes") or status.get("total_bytes_estimate")
            downloaded = status.get("downloaded_bytes") or 0
            fraction: Optional[float]
            if total_bytes:
                fraction = min(downloaded / total_bytes, 1.0)
            else:
                fragment_index = status.get("fragment_index")
                fragment_count = status.get("fragment_count")
                fraction = (fragment_index / fragment_count) if fragment_index and fragment_count else 0.0
            overall = ((entry_index - 1) + fraction) / progress_state["total"]
            _emit(
                on_progress,
                progress=round(min(overall, 0.999) * 100, 1),
                stage="downloading",
                speed=status.get("speed"),
                speed_str=format_speed(status.get("speed")),
                eta=status.get("eta"),
                eta_str=format_eta(status.get("eta")),
                downloaded_bytes=downloaded,
                total_bytes=total_bytes,
                entry_index=entry_index,
                entry_count=progress_state["total"],
            )
        elif status.get("status") == "finished":
            progress_state["finished"].add(entry_index)
            overall = len(progress_state["finished"]) / progress_state["total"]
            _emit(
                on_progress,
                progress=round(min(overall, 1.0) * 100, 1),
                stage="processing",
                speed=None,
                speed_str=None,
                eta=None,
                eta_str=None,
                entry_index=entry_index,
                entry_count=progress_state["total"],
            )

    def postprocessor_hook(status: Dict[str, Any]) -> None:
        if is_cancelled and is_cancelled():
            raise JobCancelled()
        if status.get("status") == "started":
            name = (status.get("postprocessor") or "").replace("FFmpeg", "")
            _emit(on_progress, stage="processing", message=name)

    ydl_opts["progress_hooks"] = [progress_hook]
    ydl_opts["postprocessor_hooks"] = [postprocessor_hook]

    if mode == "subtitles":
        if not subtitle_langs:
            raise DownloaderError("no_subtitles", "No subtitle language was selected.")
        ydl_opts.update(
            {
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": subtitle_langs,
                "subtitlesformat": _subtitle_format(options.get("subtitle_format")),
            }
        )
        if playlist_mode:
            ydl_opts["ignoreerrors"] = True
    elif mode == "audio":
        ydl_opts["format"] = options.get("format_id") or "bestaudio/best"
        ydl_opts["postprocessors"] = _audio_postprocessors(audio_format, int(options.get("audio_quality") or 192))
    else:
        ydl_opts["format"] = video_format_selector(options.get("quality") or "best", options.get("format_id"))
        ydl_opts["merge_output_format"] = "mp4/mkv"
        if subtitle_langs:
            embed = bool(options.get("embed_subtitles")) and settings.ffmpeg_available
            ydl_opts.update(
                {
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": subtitle_langs,
                    "subtitlesformat": _subtitle_format(options.get("subtitle_format")),
                    "embedsubtitles": embed,
                }
            )

    if trim_start is not None or trim_end is not None:
        start = trim_start or 0
        end = trim_end

        def download_ranges(_info: Dict[str, Any], _ydl: Any = None) -> List[Dict[str, Any]]:
            return [{"start_time": start, "end_time": end}]

        ydl_opts["download_ranges"] = download_ranges
        ydl_opts["force_keyframes_at_cuts"] = True

    _emit(on_progress, progress=0.0, stage="preparing", message="Fetching video information")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except JobCancelled:
        raise
    except DownloadError as exc:
        if _contains_cancel(exc):
            raise JobCancelled() from exc
        raise _map_download_error(exc) from exc
    except PostProcessingError as exc:
        raise DownloaderError(
            "processing_failed", f"Post-processing failed: {str(exc)[:200]}"
        ) from exc
    except Exception as exc:  # pragma: no cover - unexpected yt-dlp internals
        if _contains_cancel(exc):
            raise JobCancelled() from exc
        raise DownloaderError("download_failed", f"Download failed: {str(exc)[:200]}") from exc
    finally:
        shutil.rmtree(job_dir / ".tmp", ignore_errors=True)

    files = _collect_files(job_dir)
    if not files:
        raise DownloaderError("no_file", "The download finished but no file was produced.")

    title = (info or {}).get("title") if isinstance(info, dict) else None
    if not title and playlist_mode and isinstance(info, dict):
        entries = [entry for entry in (info.get("entries") or []) if entry]
        title = info.get("title") or (entries[0].get("title") if entries else None)

    _emit(on_progress, progress=100.0, stage="processing", message="Finishing up")

    return {
        "title": title or "download",
        "duration": (info or {}).get("duration") if isinstance(info, dict) else None,
        "thumbnail": _pick_thumbnail(info) if isinstance(info, dict) else None,
        "is_playlist": playlist_mode,
        "entry_count": len(files),
        "files": [_file_entry(path, job_dir) for path in files],
    }


def _output_template(custom_name: Optional[str], playlist_mode: bool) -> str:
    if custom_name:
        base = sanitize_filename(custom_name)
        if playlist_mode:
            return f"{base} - %(playlist_index)03d.%(ext)s"
        return f"{base}.%(ext)s"
    if playlist_mode:
        return "%(playlist_index)03d - %(title).100s [%(id)s].%(ext)s"
    return "%(title).120s [%(id)s].%(ext)s"


def _subtitle_format(requested: Optional[str]) -> str:
    requested = (requested or "srt").lower()
    if requested not in {"srt", "vtt", "ass", "lrc", "best"}:
        requested = "srt"
    if requested == "srt" and not settings.ffmpeg_available:
        return "vtt"
    return requested


def _as_float(value: Any) -> Optional[float]:
    if value in (None, "", False):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _contains_cancel(exc: Exception) -> bool:
    seen = set()
    current: Optional[BaseException] = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, JobCancelled):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def _map_download_error(exc: Exception) -> DownloaderError:
    message = str(exc)
    lowered = message.lower()
    if "ffmpeg" in lowered and ("not installed" in lowered or "not found" in lowered):
        return DownloaderError("ffmpeg_missing", "This download needs ffmpeg, which is not installed on the server.")
    if "requested format is not available" in lowered:
        return DownloaderError("format_unavailable", "That quality is not available for this video.")
    if "private" in lowered or "sign in" in lowered:
        return DownloaderError("private_video", "This video is private or requires sign-in.")
    if "403" in lowered or "forbidden" in lowered:
        return DownloaderError("forbidden", "YouTube refused this download. Please try again later.")
    return _map_extract_error(exc)


def _file_entry(path: Path, job_dir: Path) -> Dict[str, Any]:
    try:
        relative = str(path.relative_to(job_dir))
    except ValueError:
        relative = path.name
    return {
        "name": path.name,
        "relative": relative,
        "path": str(path),
        "size": path.stat().st_size,
        "size_str": format_filesize(path.stat().st_size),
    }


def _collect_files(job_dir: Path) -> List[Path]:
    files: List[Path] = []
    for path in sorted(job_dir.rglob("*")):
        if not path.is_file():
            continue
        if ".tmp" in path.parts:
            continue
        if path.name.startswith("."):
            continue
        if path.suffix.lower() in IGNORED_SUFFIXES:
            continue
        files.append(path)
    return files


# ---------------------------------------------------------------------------
# Thumbnails
# ---------------------------------------------------------------------------


def is_allowed_thumbnail_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme not in {"http", "https"}:
        return False
    host = (parts.hostname or "").lower()
    return any(host == allowed or host.endswith("." + allowed) for allowed in ALLOWED_THUMBNAIL_HOSTS)


def fetch_thumbnail_bytes(url: str) -> bytes:
    if not is_allowed_thumbnail_url(url):
        raise DownloaderError("invalid_thumbnail", "Unsupported thumbnail URL.")
    try:
        with httpx.Client(timeout=20, follow_redirects=True) as client:
            response = client.get(url)
        if response.status_code != 200 or not response.content:
            raise DownloaderError("thumbnail_failed", "Could not fetch the thumbnail.")
        return response.content
    except httpx.HTTPError as exc:
        raise DownloaderError("thumbnail_failed", "Could not fetch the thumbnail.") from exc


def best_thumbnail_url(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"


def clone_options(options: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-ish copy used when a job is retried from the UI."""
    return copy.deepcopy(options)
