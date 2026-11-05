"""Demo / offline showcase mode.

When ``DEMO_MODE=1`` the app never talks to YouTube.  It serves realistic fake
metadata and "downloads" bundled sample files, which makes it possible to try
the whole UI (progress bars, queue, playlist zipping, PWA, ...) on a machine
without internet access - for example inside a sandbox or during a demo.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from config import settings
from downloader import DownloaderError, JobCancelled, sanitize_filename

DEMO_DIR = settings.static_dir / "demo"
DEMO_VIDEO_ID = "dQw4w9WgXcQ"
DEMO_TITLE = "Demo Video — Big Buck Bunny Sample Clip"

DEMO_FORMATS: List[Dict[str, Any]] = [
    {
        "format_id": "demo-2160",
        "ext": "mp4",
        "resolution": "2160p",
        "label": "2160p",
        "height": 2160,
        "fps": 60,
        "filesize": 412_000_000,
        "filesize_str": "392.9 MB",
        "vcodec": "av01",
        "acodec": "none",
        "format_note": "2160p60 HDR",
        "dynamic_range": "HDR",
        "tbr": 12000,
        "is_audio": False,
        "is_video_only": True,
        "is_progressive": False,
    },
    {
        "format_id": "demo-1080",
        "ext": "mp4",
        "resolution": "1080p",
        "label": "1080p60",
        "height": 1080,
        "fps": 60,
        "filesize": 96_400_000,
        "filesize_str": "91.9 MB",
        "vcodec": "avc1.64002a",
        "acodec": "none",
        "format_note": "1080p60",
        "dynamic_range": "SDR",
        "tbr": 3600,
        "is_audio": False,
        "is_video_only": True,
        "is_progressive": False,
    },
    {
        "format_id": "demo-720",
        "ext": "mp4",
        "resolution": "720p",
        "label": "720p",
        "height": 720,
        "fps": 30,
        "filesize": 42_100_000,
        "filesize_str": "40.2 MB",
        "vcodec": "avc1.4d401f",
        "acodec": "mp4a.40.2",
        "format_note": "720p",
        "dynamic_range": "SDR",
        "tbr": 1600,
        "is_audio": False,
        "is_video_only": False,
        "is_progressive": True,
    },
    {
        "format_id": "demo-480",
        "ext": "mp4",
        "resolution": "480p",
        "label": "480p",
        "height": 480,
        "fps": 30,
        "filesize": 18_900_000,
        "filesize_str": "18.0 MB",
        "vcodec": "avc1.4d401e",
        "acodec": "mp4a.40.2",
        "format_note": "480p",
        "dynamic_range": "SDR",
        "tbr": 720,
        "is_audio": False,
        "is_video_only": False,
        "is_progressive": True,
    },
    {
        "format_id": "demo-360",
        "ext": "mp4",
        "resolution": "360p",
        "label": "360p",
        "height": 360,
        "fps": 30,
        "filesize": 9_400_000,
        "filesize_str": "9.0 MB",
        "vcodec": "avc1.4d401e",
        "acodec": "mp4a.40.2",
        "format_note": "360p",
        "dynamic_range": "SDR",
        "tbr": 380,
        "is_audio": False,
        "is_video_only": False,
        "is_progressive": True,
    },
    {
        "format_id": "demo-audio-m4a",
        "ext": "m4a",
        "resolution": "audio",
        "label": "Audio 128k",
        "height": None,
        "fps": None,
        "filesize": 3_400_000,
        "filesize_str": "3.2 MB",
        "vcodec": "none",
        "acodec": "mp4a.40.2",
        "format_note": "medium",
        "dynamic_range": None,
        "tbr": 128,
        "is_audio": True,
        "is_video_only": False,
        "is_progressive": False,
    },
]

DEMO_SUBTITLES = [
    {"code": "en", "name": "English", "auto": False},
    {"code": "bn", "name": "বাংলা (Bengali)", "auto": False},
    {"code": "hi", "name": "हिन्दी (Hindi)", "auto": True},
    {"code": "es", "name": "Español", "auto": True},
]

DEMO_THUMBNAIL = "/static/demo/thumbnail.jpg"


def _video_payload(url: str, index: int = 1) -> Dict[str, Any]:
    title = DEMO_TITLE if index == 1 else f"Demo Playlist Item #{index}"
    return {
        "type": "video",
        "url": url,
        "id": f"demo{index:07d}",
        "title": title,
        "thumbnail": DEMO_THUMBNAIL,
        "duration": 214,
        "duration_str": "3:34",
        "uploader": "Arena Demo Channel",
        "view_count": 1_284_930,
        "like_count": 24_120,
        "upload_date": "20260101",
        "is_live": False,
        "description": (
            "This is demo mode: no request ever leaves your machine. "
            "Start a download to preview the progress bar, queue, history and PWA."
        ),
        "formats": [dict(item) for item in DEMO_FORMATS],
        "available_qualities": [2160, 1080, 720, 480, 360],
        "subtitles": [dict(item) for item in DEMO_SUBTITLES],
        "playlist": None,
    }


def demo_media_info(url: str, force_playlist: bool = False) -> Dict[str, Any]:
    lowered = url.lower()
    if force_playlist or "list=" in lowered or "playlist" in lowered:
        return {
            "type": "playlist",
            "url": url,
            "id": "demo-playlist",
            "title": "Demo Playlist — Learn YouTube Downloader",
            "thumbnail": DEMO_THUMBNAIL,
            "uploader": "Arena Demo Channel",
            "count": 3,
            "entries": [
                {
                    "index": index,
                    "id": f"demo{index:07d}",
                    "url": f"https://www.youtube.com/watch?v=demo{index:07d}",
                    "title": f"Demo playlist item #{index}",
                    "thumbnail": DEMO_THUMBNAIL,
                    "duration": 214 if index == 1 else 96 + index * 10,
                    "duration_str": "3:34" if index == 1 else f"1:{36 + index * 10}",
                    "uploader": "Arena Demo Channel",
                }
                for index in range(1, 4)
            ],
            "truncated": False,
            "max_entries": settings.max_playlist_entries,
            "formats": [],
            "available_qualities": [],
            "subtitles": [],
        }
    return _video_payload(url)


def _emit(callback: Optional[Callable[[Dict[str, Any]], None]], **update: Any) -> None:
    if callback:
        callback(update)


def _copy_asset(name: str, destination: Path) -> bool:
    source = DEMO_DIR / name
    if source.is_file():
        shutil.copyfile(source, destination)
        return True
    return False


def execute_demo_job(
    options: Dict[str, Any],
    job_dir: Path,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> Dict[str, Any]:
    job_dir.mkdir(parents=True, exist_ok=True)
    mode = (options.get("mode") or "video").lower()
    is_playlist = bool(options.get("playlist"))
    entry_count = _demo_entry_count(options) if is_playlist else 1
    title = DEMO_TITLE if not is_playlist else "Demo Playlist — Learn YouTube Downloader"

    if mode == "subtitles" and not options.get("subtitle_langs"):
        raise DownloaderError("no_subtitles", "No subtitle language was selected.")

    total_bytes = 58_000_000 if mode == "video" else 3_400_000
    _emit(on_progress, progress=0.0, stage="preparing", message="Demo mode")

    steps = 36
    for step in range(1, steps + 1):
        if is_cancelled and is_cancelled():
            raise JobCancelled()
        fraction = step / steps
        entry_index = min(entry_count, int(fraction * entry_count) + 1)
        _emit(
            on_progress,
            progress=round(fraction * 100, 1),
            stage="downloading",
            speed_str=f"{round(6.4 + step * 0.12, 1)} MB/s",
            eta_str=f"0:{max(0, 3 - step // 12):02d}",
            downloaded_bytes=int(total_bytes * fraction),
            total_bytes=total_bytes,
            entry_index=entry_index,
            entry_count=entry_count,
        )
        time.sleep(0.06)

    _emit(on_progress, progress=100.0, stage="processing", speed_str=None, eta_str=None)

    files: List[Path] = []
    requested_name = options.get("filename")
    subtitle_langs = [lang for lang in (options.get("subtitle_langs") or []) if isinstance(lang, str)]
    subtitle_format = (options.get("subtitle_format") or "srt").lower()

    if mode == "subtitles":
        for lang in subtitle_langs or ["en"]:
            base = sanitize_filename(requested_name) if requested_name and len(subtitle_langs) == 1 else sanitize_filename(
                f"{title} [{lang}]"
            )
            extension = "srt" if subtitle_format != "vtt" else "vtt"
            target = job_dir / f"{base}.{extension}"
            if not _copy_asset(f"subtitle.{lang}.{extension}", target) and not _copy_asset(
                f"subtitle.en.{extension}", target
            ):
                target.write_text(_fallback_subtitle(lang), encoding="utf-8")
            files.append(target)
    else:
        for index in range(1, entry_count + 1):
            if is_playlist:
                base = sanitize_filename(f"{index:03d} - Demo playlist item #{index} [demo{index:07d}]")
            elif requested_name:
                base = sanitize_filename(requested_name)
            else:
                base = sanitize_filename(f"{DEMO_TITLE} [demo0000001]")

            if mode == "audio":
                audio_format = (options.get("audio_format") or "mp3").lower()
                extension = {"mp3": "mp3", "m4a": "m4a", "opus": "opus", "wav": "wav", "flac": "flac"}.get(
                    audio_format, "mp3"
                )
                target = job_dir / f"{base}.{extension}"
                if not _copy_asset(f"sample.{extension}", target):
                    _copy_asset("sample.mp3", target) or _copy_asset("sample.mp4", job_dir / f"{base}.mp4")
            else:
                target = job_dir / f"{base}.mp4"
                _copy_asset("sample.mp4", target)
            if target.exists():
                files.append(target)

    if not files:
        raise DownloaderError("no_file", "Demo assets are missing. Reinstall the app to restore them.")

    _emit(on_progress, progress=100.0, stage="processing")
    return {
        "title": title,
        "duration": 214,
        "thumbnail": DEMO_THUMBNAIL,
        "is_playlist": is_playlist,
        "entry_count": len(files),
        "files": [
            {
                "name": path.name,
                "relative": path.name,
                "path": str(path),
                "size": path.stat().st_size,
                "size_str": f"{path.stat().st_size / 1024:.1f} KB",
            }
            for path in files
        ],
    }


def _demo_entry_count(options: Dict[str, Any]) -> int:
    """How many sample playlist entries this job should produce (demo has 3)."""
    requested = options.get("entry_count")
    if isinstance(requested, int) and requested > 0:
        return min(3, requested)
    items = str(options.get("playlist_items") or "")
    if items:
        total = 0
        for part in items.split(","):
            if not part:
                continue
            if "-" in part:
                try:
                    start, end = part.split("-", 1)
                    total += max(0, int(end) - int(start) + 1)
                except ValueError:
                    total += 1
            else:
                total += 1
        if total:
            return min(3, total)
    return 3


def _fallback_subtitle(lang: str) -> str:
    return (
        "1\n"
        "00:00:00,000 --> 00:00:03,000\n"
        f"[Demo subtitle - {lang}]\n\n"
        "2\n"
        "00:00:03,000 --> 00:00:06,000\n"
        "This is a sample subtitle file generated in demo mode.\n"
    )
