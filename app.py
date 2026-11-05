"""
YouTube Video Downloader Web App
A clean, modern, production-ready web application for downloading YouTube videos.
Built with FastAPI + yt-dlp.

IMPORTANT: This tool is for personal, educational, and fair-use purposes only.
Always respect YouTube's Terms of Service and copyright laws.
Do not use for commercial redistribution of copyrighted content.
"""

import os
import re
import uuid
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, HttpUrl, field_validator
import yt_dlp
from yt_dlp.utils import DownloadError

# ==================== CONFIG ====================
app = FastAPI(
    title="YouTube Video Downloader",
    description="Modern web app to download YouTube videos safely and easily",
    version="1.0.0"
)

BASE_DIR = Path(__file__).parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Clean old files periodically (simple approach)
MAX_FILE_AGE_SECONDS = 3600  # 1 hour

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


# ==================== MODELS ====================
class VideoRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        v = v.strip()
        youtube_regex = re.compile(
            r"^(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/|embed/|live/)|youtu\.be/)[\w\-]+"
        )
        if not youtube_regex.search(v):
            raise ValueError("Please provide a valid YouTube URL")
        return v


class FormatInfo(BaseModel):
    format_id: str
    ext: str
    resolution: Optional[str] = None
    filesize: Optional[int] = None
    filesize_approx: Optional[int] = None
    vcodec: Optional[str] = None
    acodec: Optional[str] = None
    format_note: Optional[str] = None
    quality: Optional[str] = None


class VideoInfo(BaseModel):
    id: str
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    uploader: Optional[str] = None
    view_count: Optional[int] = None
    formats: List[Dict[str, Any]] = []


# ==================== HELPERS ====================
def get_ydl_opts(download: bool = False, format_id: Optional[str] = None, outtmpl: Optional[str] = None) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "socket_timeout": 30,
    }
    if download:
        opts["format"] = format_id or "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
        opts["outtmpl"] = outtmpl or str(DOWNLOAD_DIR / "%(id)s.%(ext)s")
        opts["merge_output_format"] = "mp4"
    return opts


def format_filesize(size: Optional[int]) -> str:
    if not size:
        return "Unknown"
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def clean_old_files():
    """Remove files older than MAX_FILE_AGE_SECONDS"""
    import time
    current = time.time()
    for f in DOWNLOAD_DIR.glob("*"):
        if f.is_file() and (current - f.stat().st_mtime) > MAX_FILE_AGE_SECONDS:
            try:
                f.unlink()
            except Exception:
                pass


# ==================== ROUTES ====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/info")
async def get_video_info(req: VideoRequest):
    """Fetch video metadata and available formats"""
    try:
        ydl_opts = get_ydl_opts(download=False)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.url, download=False)

        if not info:
            raise HTTPException(status_code=400, detail="Could not extract video information")

        # Filter and organize formats
        formats = []
        seen = set()

        for f in info.get("formats", []):
            # Prefer progressive or video+audio
            if f.get("vcodec") == "none" and f.get("acodec") == "none":
                continue

            format_id = f.get("format_id")
            if not format_id or format_id in seen:
                continue
            seen.add(format_id)

            height = f.get("height")
            resolution = f"{height}p" if height else f.get("resolution") or f.get("format_note") or "audio"

            formats.append({
                "format_id": format_id,
                "ext": f.get("ext", "mp4"),
                "resolution": resolution,
                "filesize": f.get("filesize") or f.get("filesize_approx"),
                "filesize_str": format_filesize(f.get("filesize") or f.get("filesize_approx")),
                "vcodec": f.get("vcodec"),
                "acodec": f.get("acodec"),
                "format_note": f.get("format_note") or "",
                "fps": f.get("fps"),
                "is_audio": f.get("vcodec") == "none",
            })

        # Sort: video first (higher res), then audio
        def sort_key(x):
            if x["is_audio"]:
                return (1, 0)
            res = 0
            if x["resolution"] and x["resolution"].endswith("p"):
                try:
                    res = int(x["resolution"][:-1])
                except:
                    pass
            return (0, -res)

        formats.sort(key=sort_key)

        return {
            "id": info.get("id"),
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "uploader": info.get("uploader"),
            "view_count": info.get("view_count"),
            "description": (info.get("description") or "")[:300] + "..." if info.get("description") else None,
            "formats": formats[:25],  # Limit to keep response small
        }

    except DownloadError as e:
        raise HTTPException(status_code=400, detail=f"YouTube error: {str(e)[:200]}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch info: {str(e)[:200]}")


@app.post("/api/download")
async def download_video(req: VideoRequest, format_id: Optional[str] = None, background_tasks: BackgroundTasks = None):
    """
    Download the video and return it as a file response.
    For large files this streams the response.
    """
    clean_old_files()

    try:
        # Unique filename
        video_id = str(uuid.uuid4())[:8]
        outtmpl = str(DOWNLOAD_DIR / f"{video_id}.%(ext)s")

        ydl_opts = get_ydl_opts(download=True, format_id=format_id, outtmpl=outtmpl)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.url, download=True)
            filename = ydl.prepare_filename(info)

        # Find the actual file (yt-dlp may change extension)
        path = Path(filename)
        if not path.exists():
            # Try common extensions
            for ext in ["mp4", "webm", "mkv", "m4a", "mp3"]:
                candidate = DOWNLOAD_DIR / f"{video_id}.{ext}"
                if candidate.exists():
                    path = candidate
                    break

        if not path.exists():
            raise HTTPException(status_code=500, detail="Download completed but file not found")

        # Schedule cleanup
        def remove_file(p: Path):
            try:
                if p.exists():
                    p.unlink()
            except Exception:
                pass

        if background_tasks:
            background_tasks.add_task(remove_file, path)

        media_type = "video/mp4"
        if path.suffix in [".m4a", ".mp3", ".webm"]:
            media_type = f"audio/{path.suffix[1:]}"

        return FileResponse(
            path=path,
            media_type=media_type,
            filename=f"{info.get('title', 'video')[:80]}{path.suffix}",
            background=background_tasks
        )

    except DownloadError as e:
        raise HTTPException(status_code=400, detail=f"Download failed: {str(e)[:200]}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)[:200]}")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "YouTube Downloader"}


# ==================== STARTUP ====================
@app.on_event("startup")
async def startup():
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    print("✅ YouTube Downloader started")
    print(f"📁 Downloads directory: {DOWNLOAD_DIR}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
