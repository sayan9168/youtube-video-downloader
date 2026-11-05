"""Application configuration.

Everything is configurable through environment variables so the app can be
deployed locally, on a VPS or inside Docker without touching the source.

Example:
    DOWNLOAD_DIR=/data MAX_CONCURRENT_DOWNLOADS=3 uvicorn app:app
"""

from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent

APP_NAME = "YouTube Downloader"
APP_VERSION = "2.0.0"


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return max(minimum, int(raw.strip()))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


_ffmpeg_cache: Optional[str] = None
_ffmpeg_resolved = False


def detect_ffmpeg() -> Optional[str]:
    """Return a path to an ffmpeg binary, or None when unavailable.

    Order of preference:
      1. FFMPEG_LOCATION environment variable
      2. ffmpeg on PATH
      3. the binary shipped by the optional ``imageio-ffmpeg`` package

    When only the bundled binary is available its directory is prepended to
    ``PATH``: yt-dlp shells out to a plain ``ffmpeg`` command for slicing,
    merging and converting, so it has to be discoverable there too.
    """
    global _ffmpeg_cache, _ffmpeg_resolved
    if _ffmpeg_resolved:
        return _ffmpeg_cache
    _ffmpeg_resolved = True

    configured = os.getenv("FFMPEG_LOCATION", "").strip()
    if configured:
        candidate = Path(configured)
        if candidate.is_dir():
            for name in ("ffmpeg", "ffmpeg.exe"):
                if (candidate / name).exists():
                    _ffmpeg_cache = str(candidate / name)
                    break
        elif candidate.exists():
            _ffmpeg_cache = str(candidate)
        if _ffmpeg_cache:
            _expose_on_path(_ffmpeg_cache)
            return _ffmpeg_cache

    found = shutil.which("ffmpeg")
    if found:
        _ffmpeg_cache = found
        return found

    try:  # pragma: no cover - depends on optional dependency
        import imageio_ffmpeg

        executable = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        executable = None
    if executable:
        _ffmpeg_cache = executable
        _expose_on_path(executable)
    return _ffmpeg_cache


def _expose_on_path(executable: str) -> None:
    exe_path = Path(executable).resolve()
    directory = exe_path.parent

    # imageio-ffmpeg ships versioned binaries (ffmpeg-linux-x86_64-v...), while
    # yt-dlp looks for a command literally called "ffmpeg". Create an alias.
    if exe_path.stem.lower() not in {"ffmpeg", "ffmpeg.exe"}:
        alias_dir = Path(tempfile.gettempdir()) / "ytd-ffmpeg-bin"
        alias_dir.mkdir(parents=True, exist_ok=True)
        alias = alias_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if not alias.exists():
            try:
                alias.symlink_to(exe_path)
            except OSError:  # e.g. Windows without symlink rights
                shutil.copy2(exe_path, alias)
                alias.chmod(0o755)
        directory = alias_dir

    directory_str = str(directory)
    current = os.environ.get("PATH", "")
    if directory_str not in current.split(os.pathsep):
        os.environ["PATH"] = f"{directory_str}{os.pathsep}{current}" if current else directory_str


@dataclass(frozen=True)
class Settings:
    app_name: str = APP_NAME
    version: str = APP_VERSION
    base_dir: Path = BASE_DIR
    download_dir: Path = field(
        default_factory=lambda: Path(_env_str("DOWNLOAD_DIR", str(BASE_DIR / "downloads"))).resolve()
    )
    templates_dir: Path = BASE_DIR / "templates"
    static_dir: Path = BASE_DIR / "static"

    # Housekeeping
    max_file_age_seconds: int = field(default_factory=lambda: _env_int("MAX_FILE_AGE_SECONDS", 3600, 60))
    cleanup_interval_seconds: int = field(default_factory=lambda: _env_int("CLEANUP_INTERVAL_SECONDS", 60, 5))

    # Downloads
    max_concurrent_downloads: int = field(default_factory=lambda: _env_int("MAX_CONCURRENT_DOWNLOADS", 2, 1))
    max_queue_size: int = field(default_factory=lambda: _env_int("MAX_QUEUE_SIZE", 50, 1))
    max_playlist_entries: int = field(default_factory=lambda: _env_int("MAX_PLAYLIST_ENTRIES", 100, 1))
    max_filename_length: int = field(default_factory=lambda: _env_int("MAX_FILENAME_LENGTH", 120, 16))
    socket_timeout: int = field(default_factory=lambda: _env_int("YTDLP_SOCKET_TIMEOUT", 30, 5))
    retries: int = field(default_factory=lambda: _env_int("YTDLP_RETRIES", 3, 0))

    # Rate limiting (helps when the app is deployed publicly)
    rate_limit_enabled: bool = field(default_factory=lambda: _env_bool("RATE_LIMIT_ENABLED", True))
    rate_limit_per_minute: int = field(default_factory=lambda: _env_int("RATE_LIMIT_PER_MINUTE", 120, 1))
    rate_limit_downloads_per_minute: int = field(
        default_factory=lambda: _env_int("RATE_LIMIT_DOWNLOADS_PER_MINUTE", 30, 1)
    )
    trust_proxy_headers: bool = field(default_factory=lambda: _env_bool("TRUST_PROXY_HEADERS", False))

    # Demo / offline showcase mode (no network calls to YouTube)
    demo_mode: bool = field(default_factory=lambda: _env_bool("DEMO_MODE", False))

    # Optional CORS origins for embedding the API elsewhere
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip()
            for origin in _env_str("CORS_ORIGINS", "").split(",")
            if origin.strip()
        )
    )

    @property
    def archives_dir(self) -> Path:
        return self.download_dir / ".archives"

    @property
    def ffmpeg_location(self) -> Optional[str]:
        return detect_ffmpeg()

    @property
    def ffmpeg_available(self) -> bool:
        return self.ffmpeg_location is not None

    def ensure_dirs(self) -> None:
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.archives_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()

# Hosts we are willing to proxy thumbnails from (prevents SSRF abuse).
ALLOWED_THUMBNAIL_HOSTS = (
    "i.ytimg.com",
    "i9.ytimg.com",
    "img.youtube.com",
    "yt3.ggpht.com",
    "yt3.googleusercontent.com",
    "lh3.googleusercontent.com",
    "webp.ytimg.com",
)
