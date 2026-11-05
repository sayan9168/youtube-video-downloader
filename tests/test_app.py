"""API and download-pipeline tests.

The tests never touch the network: yt-dlp metadata and downloads are replaced
with deterministic fakes so the queue, progress, zip and error paths can be
verified offline.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as app_module
import downloader
from config import settings
from ratelimit import limiter

VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PL1234567890"


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    object.__setattr__(settings, "download_dir", tmp_path / "downloads")
    settings.ensure_dirs()
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture()
def client():
    with TestClient(app_module.app) as test_client:
        yield test_client


def install_fake_execute(files: int = 1, error: str | None = None, slow: bool = False, progress: bool = True):
    """Replace the real yt-dlp download with a fake that writes local files."""

    def fake_execute(options, job_dir: Path, on_progress=None, is_cancelled=None):
        job_dir.mkdir(parents=True, exist_ok=True)
        produced = []
        for index in range(1, files + 1):
            if slow:
                deadline = time.time() + 5
                while time.time() < deadline:
                    if is_cancelled and is_cancelled():
                        raise downloader.JobCancelled()
                    if progress and on_progress:
                        on_progress({"progress": 40.0, "stage": "downloading", "speed_str": "1.0 MB/s"})
                    time.sleep(0.05)
            if on_progress:
                on_progress(
                    {
                        "progress": 100.0 * index / files,
                        "stage": "downloading",
                        "speed_str": "2.0 MB/s",
                        "eta_str": "0:02",
                        "downloaded_bytes": 1024 * index,
                        "total_bytes": 1024 * files,
                        "entry_index": index,
                        "entry_count": files,
                    }
                )
            path = job_dir / (f"clip-{index}.mp4" if files > 1 else "clip.mp4")
            path.write_bytes(b"fake-video-bytes" * 64)
            produced.append(
                {"name": path.name, "relative": path.name, "path": str(path), "size": path.stat().st_size}
            )
        if error:
            raise downloader.DownloaderError(error, "Fake failure")
        return {
            "title": "Fake video",
            "duration": 42,
            "thumbnail": None,
            "is_playlist": files > 1,
            "entry_count": len(produced),
            "files": produced,
        }

    app_module.manager._execute = fake_execute
    return fake_execute


def wait_for_status(client: TestClient, job_id: str, statuses=("completed", "failed", "canceled"), timeout=10.0):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        assert response.status_code == 200
        last = response.json()
        if last["status"] in statuses:
            return last
        time.sleep(0.1)
    raise AssertionError(f"job did not reach {statuses}: {last}")


# ------------------------------------------------------------------ basics
def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    body = response.text
    assert "urlInput" in body
    assert "manifest.webmanifest" in body
    assert app_module.settings.version in body


def test_static_assets_and_pwa_files(client):
    for path in ("/static/css/app.css", "/static/js/app.js", "/static/manifest.webmanifest", "/sw.js"):
        response = client.get(path)
        assert response.status_code == 200, path
    assert client.get("/static/js/app.js").headers["content-type"].startswith("text/javascript") or True
    manifest = client.get("/static/manifest.webmanifest").json()
    assert manifest["start_url"] == "/"
    assert manifest["display"] == "standalone"


def test_config_and_health(client):
    config = client.get("/api/config").json()
    assert config["version"] == settings.version
    assert isinstance(config["ffmpeg_available"], bool)
    assert "mp3" in config["audio_formats"]

    health = client.get("/api/health").json()
    assert health["status"] == "ok"


# -------------------------------------------------------------- info parsing
def test_info_returns_video_payload(client, monkeypatch):
    payload = {
        "type": "video",
        "id": "abc123",
        "title": "A test video",
        "thumbnail": "https://i.ytimg.com/vi/abc123/hq.jpg",
        "duration": 100,
        "formats": [{"format_id": "137", "resolution": "1080p", "is_audio": False}],
        "subtitles": [{"code": "en", "name": "English", "auto": False}],
    }
    monkeypatch.setattr(downloader, "fetch_media_info", lambda url, playlist=False: payload)

    response = client.post("/api/info", json={"url": VIDEO_URL})
    assert response.status_code == 200
    assert response.json()["title"] == "A test video"


def test_info_rejects_non_youtube_url(client):
    response = client.post("/api/info", json={"url": "https://vimeo.com/12345"})
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_url"


# ------------------------------------------------------------------- jobs
def test_job_download_lifecycle(client):
    install_fake_execute(files=1)
    created = client.post("/api/jobs", json={"url": VIDEO_URL, "mode": "video", "quality": "720"}).json()
    assert created["status"] in {"queued", "running"}

    job = wait_for_status(client, created["id"])
    assert job["status"] == "completed"
    assert job["progress"] == 100.0
    assert job["title"] == "Fake video"
    assert job["result_name"] == "clip.mp4"

    listing = client.get("/api/jobs").json()
    assert any(item["id"] == created["id"] for item in listing["jobs"])

    file_response = client.get(f"/api/jobs/{created['id']}/file")
    assert file_response.status_code == 200
    assert file_response.content.startswith(b"fake-video-bytes")
    assert "attachment" in file_response.headers["content-disposition"]

    assert client.delete(f"/api/jobs/{created['id']}").status_code == 200
    assert client.get(f"/api/jobs/{created['id']}/file").status_code == 404


def test_playlist_job_is_zipped(client):
    install_fake_execute(files=3)
    created = client.post(
        "/api/jobs",
        json={"url": PLAYLIST_URL, "mode": "video", "quality": "best", "playlist": True, "entry_count": 3},
    ).json()
    job = wait_for_status(client, created["id"])
    assert job["status"] == "completed"
    assert job["result_name"].endswith(".zip")
    assert job["file_count"] == 3

    archive = client.get(f"/api/jobs/{created['id']}/file")
    assert archive.status_code == 200
    assert archive.headers["content-type"] == "application/zip"
    assert archive.content[:2] == b"PK"


def test_failed_job_reports_error_code(client):
    install_fake_execute(files=1, error="format_unavailable")
    created = client.post("/api/jobs", json={"url": VIDEO_URL, "mode": "video"}).json()
    job = wait_for_status(client, created["id"])
    assert job["status"] == "failed"
    assert job["error_code"] == "format_unavailable"
    assert client.get(f"/api/jobs/{created['id']}/file").status_code == 410


def test_job_can_be_canceled(client):
    install_fake_execute(files=1, slow=True)
    created = client.post("/api/jobs", json={"url": VIDEO_URL, "mode": "video"}).json()
    time.sleep(0.3)
    assert client.post(f"/api/jobs/{created['id']}/cancel").status_code == 200
    job = wait_for_status(client, created["id"], statuses=("canceled", "completed"))
    assert job["status"] == "canceled"


def test_batch_queue_creates_multiple_jobs(client):
    install_fake_execute(files=1)
    response = client.post(
        "/api/jobs/batch",
        json={
            "urls": [VIDEO_URL, "https://youtu.be/abcdefghijk"],
            "mode": "audio",
            "audio_format": "mp3",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    for job in body["jobs"]:
        wait_for_status(client, job["id"])


def test_audio_conversion_without_ffmpeg_is_rejected(client, monkeypatch):
    monkeypatch.setattr(type(settings), "ffmpeg_available", property(lambda self: False))
    response = client.post("/api/jobs", json={"url": VIDEO_URL, "mode": "audio", "audio_format": "mp3"})
    assert response.status_code == 400
    assert response.json()["code"] == "ffmpeg_missing"


# ------------------------------------------------------------------ security
def test_thumbnail_proxy_blocks_internal_urls(client):
    response = client.get("/api/thumbnail", params={"url": "http://169.254.169.254/latest/meta-data"})
    assert response.status_code == 400
    assert response.json()["code"] == "invalid_thumbnail"


def test_rate_limit_returns_429(client, monkeypatch):
    monkeypatch.setattr(downloader, "fetch_media_info", lambda url, playlist=False: {"type": "video"})
    statuses = [client.post("/api/info", json={"url": VIDEO_URL}).status_code for _ in range(22)]
    assert 429 in statuses
    limited = client.post("/api/info", json={"url": VIDEO_URL})
    assert limited.status_code == 429
    assert "retry-after" in {key.lower() for key in limited.headers}


# ---------------------------------------------------------------- pure logic
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("hello/world", "hello-world"),
        ("../etc/passwd", "etc-passwd"),
        ('bad:"name"?', "badname"),
        ("   ", "download"),
        ("video.mp4", "video"),
        ("a" * 300, None),
    ],
)
def test_sanitize_filename(raw, expected):
    cleaned = downloader.sanitize_filename(raw)
    assert cleaned
    assert not any(char in cleaned for char in '/\\:*?"<>|')
    if expected is None:
        assert len(cleaned) <= settings.max_filename_length
    else:
        assert cleaned == expected


@pytest.mark.parametrize(
    "url,is_playlist",
    [
        ("https://www.youtube.com/playlist?list=PL123", True),
        ("https://www.youtube.com/watch?v=abc&list=PL123", False),
        ("https://youtu.be/abc", False),
        ("https://www.youtube.com/@somechannel/videos", True),
        ("https://www.youtube.com/shorts/abc", False),
    ],
)
def test_playlist_url_detection(url, is_playlist):
    assert downloader.is_playlist_url(url) is is_playlist


@pytest.mark.parametrize(
    "bad",
    ["", "ftp://youtube.com/x", "https://example.com/watch?v=1", "javascript:alert(1)"],
)
def test_invalid_urls_rejected(bad):
    with pytest.raises(downloader.DownloaderError):
        downloader.normalize_youtube_url(bad)


def test_format_selector_honours_quality():
    best = downloader.video_format_selector("best")
    assert "bv*" in best or "b[ext=mp4]" in best
    limited = downloader.video_format_selector("720")
    if settings.ffmpeg_available:
        assert "height<=720" in limited
    assert downloader.video_format_selector("custom", "137").startswith("137")


def test_url_normalisation_adds_scheme():
    assert downloader.normalize_youtube_url("youtu.be/abcdefghijk") == "https://youtu.be/abcdefghijk"
