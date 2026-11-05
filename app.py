"""YouTube Video Downloader - FastAPI backend.

Endpoints
---------
GET  /                          -> single page app
POST /api/info                  -> video / playlist metadata (+ formats, subtitles)
POST /api/jobs                  -> queue one download
POST /api/jobs/batch            -> queue several downloads at once
GET  /api/jobs                  -> queue snapshot (polled by the UI)
GET  /api/jobs/{id}             -> one job
POST /api/jobs/{id}/cancel      -> cancel a queued/running job
DELETE /api/jobs/{id}           -> forget a job and delete its files
GET  /api/jobs/{id}/file        -> download the finished file (or zip)
GET  /api/thumbnail             -> save a thumbnail as a file
GET  /api/config                -> capability + limit discovery
POST /api/download              -> legacy synchronous download

IMPORTANT: This tool is for personal, educational and fair-use purposes only.
Always respect YouTube's Terms of Service and copyright laws.
"""

from __future__ import annotations

import asyncio
import json
import mimetypes
import re
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Literal, Optional
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

import downloader
from config import settings
from jobs import JobManager
from ratelimit import limiter

manager = JobManager()

templates = Jinja2Templates(directory=str(settings.templates_dir))

QUALITY_VALUES = {"best", "best_mp4", "worst", "custom", "144", "240", "360", "480", "720", "1080", "1440", "2160"}
MODE_VALUES = {"video", "audio", "subtitles"}


# ==================== LIFESPAN ====================
@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.ensure_dirs()
    await manager.start()
    manager.cleanup(force=True)
    print(f"✅ {settings.app_name} v{settings.version} ready")
    print(f"📁 Downloads: {settings.download_dir}")
    print(f"🎛  ffmpeg: {'found' if settings.ffmpeg_available else 'NOT FOUND (mp3/trim disabled)'}")
    if settings.demo_mode:
        print("🧪 DEMO_MODE is enabled - no requests are sent to YouTube")
    yield
    await manager.stop()


app = FastAPI(
    title="YouTube Video Downloader",
    description="Modern, self-hosted YouTube downloader with queue, progress, playlists and more.",
    version=settings.version,
    lifespan=lifespan,
)

if settings.cors_origins or settings.cors_origin_regex:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_origin_regex=settings.cors_origin_regex or None,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")


# ==================== ERRORS ====================
class APIError(Exception):
    """Error carrying a stable code so the UI can translate the message."""

    def __init__(self, status_code: int, code: str, message: str, headers: Optional[Dict[str, str]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers


@app.exception_handler(APIError)
async def api_error_handler(_request: Request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    """Turn pydantic validation failures into the same shape as APIError."""
    code, message = "invalid_request", "Invalid request."
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", []))
        if location.endswith("url") or location.endswith("urls"):
            code, message = "invalid_url", "Please provide a valid YouTube URL."
            break
        if error.get("msg"):
            message = str(error["msg"])
    return JSONResponse(status_code=400, content={"detail": message, "code": code})


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(_request: Request, exc: StarletteHTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": detail, "code": "http_error"},
        headers=getattr(exc, "headers", None),
    )


# ==================== SECURITY HEADERS ====================
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


# ==================== RATE LIMITING ====================
# (pattern, http methods or None for all, requests per minute)
RATE_RULES: List[tuple[re.Pattern[str], Optional[set], int]] = [
    (re.compile(r"^/api/info$"), {"POST"}, 20),
    (re.compile(r"^/api/jobs$"), {"POST"}, 30),
    (re.compile(r"^/api/jobs/batch$"), {"POST"}, 10),
    (re.compile(r"^/api/download$"), {"POST"}, 15),
    (re.compile(r"^/api/thumbnail$"), {"GET"}, 30),
    (re.compile(r"^/api/jobs/[^/]+/file$"), {"GET"}, 120),
    (re.compile(r"^/api/jobs$"), {"GET"}, 900),
    (re.compile(r"^/api/jobs"), None, 600),
]


def _client_key(request: Request) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _limit_for(method: str, path: str) -> int:
    for pattern, methods, limit in RATE_RULES:
        if pattern.match(path) and (methods is None or method in methods):
            return limit
    return settings.rate_limit_per_minute


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    if (
        not settings.rate_limit_enabled
        or request.method == "OPTIONS"
        or not path.startswith("/api/")
        or path == "/api/health"
    ):
        return await call_next(request)

    allowed, retry_after = limiter.hit(
        f"{_client_key(request)}:{request.method}:{path}", _limit_for(request.method, path)
    )
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests. Please slow down and try again in a moment.",
                "code": "rate_limited",
            },
            headers={"Retry-After": str(retry_after)},
        )
    return await call_next(request)


# ==================== MODELS ====================
def _validated_url(value: str) -> str:
    """Normalise a URL and surface bad input as a normal validation error."""
    try:
        return downloader.normalize_youtube_url(value)
    except downloader.DownloaderError as exc:
        raise ValueError(exc.message) from exc


class DownloadOptions(BaseModel):
    mode: Literal["video", "audio", "subtitles"] = "video"
    quality: str = "best"
    format_id: Optional[str] = None
    audio_format: str = "mp3"
    audio_quality: int = 192
    subtitle_langs: List[str] = Field(default_factory=list)
    subtitle_format: str = "srt"
    embed_subtitles: bool = False
    filename: Optional[str] = None
    trim_start: Optional[float] = None
    trim_end: Optional[float] = None
    playlist: bool = False
    playlist_items: Optional[str] = None
    entry_count: Optional[int] = None
    title: Optional[str] = None
    thumbnail: Optional[str] = None

    @field_validator("quality")
    @classmethod
    def _check_quality(cls, value: str) -> str:
        value = (value or "best").strip().lower()
        if value not in QUALITY_VALUES:
            raise ValueError("Unknown quality")
        return value

    @field_validator("format_id")
    @classmethod
    def _check_format_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.\-]{1,40}", value):
            raise ValueError("Invalid format id")
        return value or None

    @field_validator("audio_quality")
    @classmethod
    def _check_audio_quality(cls, value: int) -> int:
        return max(64, min(320, int(value or 192)))

    @field_validator("audio_format")
    @classmethod
    def _check_audio_format(cls, value: str) -> str:
        value = (value or "mp3").lower()
        allowed = {"mp3", "m4a", "opus", "flac", "wav", "best"}
        if value not in allowed:
            raise ValueError("Unsupported audio format")
        return value

    @field_validator("subtitle_langs")
    @classmethod
    def _check_langs(cls, values: List[str]) -> List[str]:
        cleaned = []
        for value in values or []:
            value = value.strip()
            if re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?", value) and value not in cleaned:
                cleaned.append(value)
        return cleaned[:6]

    @field_validator("subtitle_format")
    @classmethod
    def _check_subtitle_format(cls, value: str) -> str:
        value = (value or "srt").lower()
        return value if value in {"srt", "vtt"} else "srt"

    @field_validator("filename")
    @classmethod
    def _check_filename(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        value = downloader.sanitize_filename(value)
        return value or None

    @field_validator("playlist_items")
    @classmethod
    def _check_playlist_items(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        value = value.replace(" ", "")
        if not re.fullmatch(r"[0-9,\-]{1,200}", value):
            raise ValueError("Invalid playlist selection")
        return value

    @field_validator("trim_start", "trim_end")
    @classmethod
    def _check_trim(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return None
        if value < 0 or value > 24 * 3600:
            raise ValueError("Invalid trim time")
        return round(value, 2)


class InfoRequest(BaseModel):
    url: str
    playlist: Optional[bool] = None

    @field_validator("url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        return _validated_url(value)


class JobRequest(DownloadOptions):
    url: str

    @field_validator("url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        return _validated_url(value)


class BatchJobRequest(DownloadOptions):
    urls: List[str] = Field(min_length=1, max_length=20)

    @field_validator("urls")
    @classmethod
    def _check_urls(cls, values: List[str]) -> List[str]:
        cleaned: List[str] = []
        for value in values:
            url = _validated_url(value)
            if url not in cleaned:
                cleaned.append(url)
        return cleaned


# ==================== HELPERS ====================
def _options_dict(payload: DownloadOptions) -> Dict[str, Any]:
    """Job payload without the request-only fields (url/urls)."""
    return payload.model_dump(exclude={"urls", "url"})


def _create_job(url: str, payload: DownloadOptions) -> Dict[str, Any]:
    if manager.active_count() >= settings.max_queue_size:
        raise APIError(429, "queue_full", "The download queue is full. Please wait for it to finish.")
    options = _options_dict(payload)
    options["url"] = url
    options["playlist"] = bool(options.get("playlist") or downloader.is_playlist_url(url))
    job = manager.create(
        url,
        payload.mode,
        options,
        title=payload.title,
        thumbnail=payload.thumbnail,
    )
    return job.snapshot()


def _validate_ffmpeg(payload: DownloadOptions) -> None:
    if payload.mode == "audio" and payload.audio_format != "best" and not settings.ffmpeg_available:
        raise APIError(
            400,
            "ffmpeg_missing",
            "MP3/M4A conversion needs ffmpeg. Install ffmpeg (or pip install imageio-ffmpeg) and restart the app.",
        )
    if (payload.trim_start or payload.trim_end) and not settings.ffmpeg_available:
        raise APIError(400, "ffmpeg_missing", "Trimming needs ffmpeg, which is not installed on the server.")


# ==================== PAGES ====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "version": settings.version,
            "demo": settings.demo_mode,
            "max_playlist_entries": settings.max_playlist_entries,
            "default_lang": "en",
        },
    )


@app.get("/manifest.webmanifest")
async def manifest():
    return FileResponse(settings.static_dir / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
async def service_worker():
    return FileResponse(
        settings.static_dir / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"},
    )


@app.get("/config.js", include_in_schema=False)
async def runtime_config():
    """Runtime configuration read by the UI before it boots.

    The static build on Cloudflare Pages ships its own copy of this file; when
    the API serves the UI itself the base is normally empty (same origin).
    """
    body = "window.YTD_CONFIG = Object.assign({ apiBase: %s }, window.YTD_CONFIG || {});\n" % json.dumps(
        settings.public_api_base
    )
    return Response(
        content=body,
        media_type="application/javascript",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/favicon.ico")
async def favicon():
    icon = settings.static_dir / "icons" / "favicon.ico"
    if icon.is_file():
        return FileResponse(icon)
    raise APIError(404, "not_found", "Not found")


# ==================== API ====================
@app.post("/api/info")
async def api_info(payload: InfoRequest):
    try:
        return await asyncio.to_thread(downloader.fetch_media_info, payload.url, bool(payload.playlist))
    except downloader.DownloaderError as exc:
        raise APIError(400, exc.code, exc.message) from exc


@app.post("/api/jobs")
async def create_job(payload: JobRequest):
    _validate_ffmpeg(payload)
    return _create_job(payload.url, payload)


@app.post("/api/jobs/batch")
async def create_batch(payload: BatchJobRequest):
    _validate_ffmpeg(payload)
    created = []
    for url in payload.urls:
        if manager.active_count() >= settings.max_queue_size:
            break
        created.append(_create_job(url, payload))
    if not created:
        raise APIError(429, "queue_full", "The download queue is full. Please wait for it to finish.")
    return {"jobs": created, "count": len(created)}


@app.get("/api/jobs")
async def list_jobs(limit: int = 100):
    manager.cleanup()
    jobs = manager.list_jobs()
    return {
        "jobs": jobs[-max(1, min(limit, 200)):],
        "active": manager.active_count(),
        "max_concurrent": manager.max_concurrent,
        "max_queue": settings.max_queue_size,
    }


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str):
    job = manager.get(job_id)
    if not job:
        raise APIError(404, "job_not_found", "This download is no longer available.")
    return job.snapshot()


@app.post("/api/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    if not manager.get(job_id):
        raise APIError(404, "job_not_found", "This download is no longer available.")
    if not manager.cancel(job_id):
        raise APIError(409, "job_not_cancellable", "This download has already finished.")
    return {"ok": True}


@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    job = manager.get(job_id)
    if not job:
        raise APIError(404, "job_not_found", "This download is no longer available.")
    if not manager.remove(job_id):
        raise APIError(409, "job_running", "Cancel the download before removing it.")
    return {"ok": True}


@app.get("/api/jobs/{job_id}/file")
async def job_file(job_id: str):
    job = manager.get(job_id)
    if not job:
        raise APIError(404, "job_not_found", "This download is no longer available.")
    path = manager.result_path(job)
    if not path:
        if job.status in {"queued", "running"}:
            raise APIError(409, "job_not_ready", "This download is still running.")
        raise APIError(
            410,
            "file_expired",
            "This file is no longer available. Temporary files are deleted automatically.",
        )
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if path.suffix.lower() == ".zip":
        media_type = "application/zip"
    return FileResponse(
        path,
        media_type=media_type,
        filename=job.result_name or path.name,
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/thumbnail")
async def download_thumbnail(url: str, name: Optional[str] = None):
    try:
        data = await asyncio.to_thread(downloader.fetch_thumbnail_bytes, url)
    except downloader.DownloaderError as exc:
        raise APIError(400, exc.code, exc.message) from exc

    filename = downloader.sanitize_filename(name or "thumbnail") + ".jpg"
    ascii_name = re.sub(r"[^A-Za-z0-9._ -]", "_", filename) or "thumbnail.jpg"
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}",
            "Cache-Control": "no-store",
        },
    )


@app.get("/api/config")
async def api_config():
    return {
        "version": settings.version,
        "demo_mode": settings.demo_mode,
        "ffmpeg_available": settings.ffmpeg_available,
        "max_concurrent_downloads": settings.max_concurrent_downloads,
        "max_queue_size": settings.max_queue_size,
        "max_playlist_entries": settings.max_playlist_entries,
        "max_file_age_seconds": settings.max_file_age_seconds,
        "rate_limit": {
            "enabled": settings.rate_limit_enabled,
            "per_minute": settings.rate_limit_per_minute,
        },
        "audio_formats": ["mp3", "m4a", "opus", "best"],
        "subtitle_formats": ["srt", "vtt"],
    }


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.version,
        "ffmpeg": settings.ffmpeg_available,
        "demo": settings.demo_mode,
        "active_jobs": manager.active_count(),
        "uptime": int(time.time()),
    }


@app.post("/api/download")
async def legacy_download(payload: JobRequest, format_id: Optional[str] = None, wait: int = 600):
    """Backwards compatible endpoint: queue a job, wait for it, return the file."""
    if format_id:
        payload.format_id = format_id
        payload.quality = "custom"
    _validate_ffmpeg(payload)
    job_payload = _create_job(payload.url, payload)
    job = manager.get(job_payload["id"])
    deadline = time.monotonic() + max(30, min(wait, 1800))
    while job and job.status in {"queued", "running"} and time.monotonic() < deadline:
        await asyncio.sleep(0.4)
    if not job:
        raise APIError(404, "job_not_found", "This download is no longer available.")
    if job.status == "failed":
        raise APIError(400, job.error_code or "download_failed", job.error or "Download failed.")
    if job.status == "canceled":
        raise APIError(409, "job_canceled", "The download was canceled.")
    path = manager.result_path(job)
    if not path:
        raise APIError(504, "job_timeout", "The download took too long. Try the queue API instead.")
    return FileResponse(
        path,
        media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        filename=job.result_name or path.name,
    )
