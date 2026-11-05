"""In-memory download queue with progress tracking.

Jobs are processed by a small pool of async workers (each download runs in a
worker thread so the event loop stays responsive).  Every job owns a directory
inside ``settings.download_dir`` that holds its output files; those files are
removed automatically once they are older than ``MAX_FILE_AGE_SECONDS``.
"""

from __future__ import annotations

import asyncio
import shutil
import threading
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import downloader
from config import settings

TERMINAL_STATUSES = {"completed", "failed", "canceled"}
MODE_LABELS = {"video": "video", "audio": "audio", "subtitles": "subtitles"}


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Job:
    url: str
    mode: str
    options: Dict[str, Any]
    id: str = field(default_factory=_new_id)
    status: str = "queued"
    stage: str = "queued"
    message: str = ""
    progress: float = 0.0
    speed_str: Optional[str] = None
    eta_str: Optional[str] = None
    downloaded_bytes: Optional[int] = None
    total_bytes: Optional[int] = None
    entry_index: Optional[int] = None
    entry_count: Optional[int] = None
    title: Optional[str] = None
    thumbnail: Optional[str] = None
    duration: Optional[int] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    files: List[Dict[str, Any]] = field(default_factory=list)
    result_name: Optional[str] = None
    result_size: Optional[int] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    cancel_requested: bool = False
    is_playlist: bool = False

    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    # -- lifecycle ------------------------------------------------------
    @property
    def dir(self) -> Path:
        return settings.download_dir / self.id

    @property
    def is_active(self) -> bool:
        return self.status in {"queued", "running"}

    def is_cancelled(self) -> bool:
        return self.cancel_requested

    def report_progress(self, update: Dict[str, Any]) -> None:
        with self._lock:
            if self.cancel_requested:
                raise downloader.JobCancelled()
            if self.status == "queued":
                self.status = "running"
            for key in (
                "progress",
                "stage",
                "message",
                "speed_str",
                "eta_str",
                "downloaded_bytes",
                "total_bytes",
                "entry_index",
                "entry_count",
            ):
                if key in update and update[key] is not None:
                    setattr(self, key, update[key])

    # -- serialisation --------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            total = self.result_size or sum(int(f.get("size") or 0) for f in self.files)
            return {
                "id": self.id,
                "url": self.url,
                "mode": self.mode,
                "status": self.status,
                "stage": self.stage,
                "message": self.message,
                "progress": round(float(self.progress or 0), 1),
                "speed_str": self.speed_str,
                "eta_str": self.eta_str,
                "downloaded_bytes": self.downloaded_bytes,
                "downloaded_str": downloader.format_filesize(self.downloaded_bytes),
                "total_bytes": self.total_bytes,
                "total_str": downloader.format_filesize(self.total_bytes),
                "entry_index": self.entry_index,
                "entry_count": self.entry_count,
                "title": self.title or self.options.get("title") or None,
                "thumbnail": self.thumbnail,
                "duration": self.duration,
                "error": self.error,
                "error_code": self.error_code,
                "result_name": self.result_name,
                "result_size": total or None,
                "result_size_str": downloader.format_filesize(total) if total else None,
                "file_count": len(self.files),
                "files": [
                    {
                        "name": entry.get("name"),
                        "size": entry.get("size"),
                        "size_str": downloader.format_filesize(entry.get("size")),
                    }
                    for entry in self.files
                ],
                "is_playlist": self.is_playlist,
                "created_at": self.created_at,
                "started_at": self.started_at,
                "finished_at": self.finished_at,
                "download_url": f"/api/jobs/{self.id}/file" if self.status == "completed" else None,
                "options": dict(self.options),
            }

    # -- state transitions ----------------------------------------------
    def mark_running(self) -> None:
        with self._lock:
            self.status = "running"
            self.stage = "preparing"
            self.started_at = time.time()
            self.message = ""

    def mark_completed(self, title: Optional[str], files: List[Dict[str, Any]], result_name: str, result_size: int) -> None:
        with self._lock:
            self.status = "completed"
            self.stage = "completed"
            self.progress = 100.0
            self.title = title or self.title
            self.files = files
            self.result_name = result_name
            self.result_size = result_size
            self.finished_at = time.time()
            self.message = ""
            self.speed_str = None
            self.eta_str = None

    def mark_failed(self, code: str, message: str) -> None:
        with self._lock:
            self.status = "failed"
            self.stage = "failed"
            self.error = message
            self.error_code = code
            self.finished_at = time.time()
            self.speed_str = None
            self.eta_str = None

    def mark_canceled(self) -> None:
        with self._lock:
            self.status = "canceled"
            self.stage = "canceled"
            self.cancel_requested = True
            self.finished_at = time.time()
            self.speed_str = None
            self.eta_str = None


class JobManager:
    def __init__(
        self,
        execute: Optional[Callable[..., Dict[str, Any]]] = None,
        max_concurrent: Optional[int] = None,
    ):
        self._jobs: Dict[str, Job] = {}
        self._order: List[str] = []
        self._queue: Optional[asyncio.Queue] = None
        self._queue_loop: Optional[asyncio.AbstractEventLoop] = None
        self._workers: List[asyncio.Task] = []
        self._execute = execute or downloader.execute_job
        self._max_concurrent = max(1, max_concurrent or settings.max_concurrent_downloads)
        self._last_cleanup = 0.0
        self._lock = threading.RLock()

    # -- lifecycle ------------------------------------------------------
    def _get_queue(self) -> asyncio.Queue:
        """Queue bound to the currently running event loop.

        asyncio primitives are tied to one loop; re-creating the queue when the
        loop changes keeps the manager usable in tests and after reloads.
        """
        try:
            loop: Optional[asyncio.AbstractEventLoop] = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if self._queue is None or (loop is not None and self._queue_loop is not loop):
            self._queue = asyncio.Queue()
            self._queue_loop = loop
        return self._queue

    async def start(self) -> None:
        settings.ensure_dirs()
        loop = asyncio.get_running_loop()
        alive = [
            task
            for task in self._workers
            if not task.done() and getattr(task, "get_loop", lambda: None)() is loop
        ]
        if len(alive) >= self._max_concurrent:
            return
        for task in self._workers:
            task.cancel()
        self._workers = [asyncio.create_task(self._worker(i)) for i in range(self._max_concurrent)]

    async def stop(self) -> None:
        workers, self._workers = self._workers, []
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)
        for job in self.list_jobs_raw():
            if job.is_active:
                job.cancel_requested = True

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    def active_count(self) -> int:
        return sum(1 for job in self._jobs.values() if job.is_active)

    # -- public API -----------------------------------------------------
    def create(
        self,
        url: str,
        mode: str,
        options: Dict[str, Any],
        title: Optional[str] = None,
        thumbnail: Optional[str] = None,
    ) -> Job:
        options = dict(options)
        options["url"] = url
        options["mode"] = mode
        job = Job(url=url, mode=mode, options=options, is_playlist=bool(options.get("playlist")))
        job.title = title
        job.thumbnail = thumbnail
        job.dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._jobs[job.id] = job
            self._order.append(job.id)
        self._get_queue().put_nowait(job.id)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list_jobs_raw(self) -> List[Job]:
        with self._lock:
            return [self._jobs[job_id] for job_id in self._order if job_id in self._jobs]

    def list_jobs(self) -> List[Dict[str, Any]]:
        jobs = [job.snapshot() for job in self.list_jobs_raw()]
        jobs.sort(key=lambda item: item["created_at"])
        return jobs

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if not job:
            return False
        if job.status == "queued":
            job.mark_canceled()
            shutil.rmtree(job.dir, ignore_errors=True)
            return True
        if job.status == "running":
            job.cancel_requested = True
            job.message = "Cancelling"
            return True
        return False

    def remove(self, job_id: str) -> bool:
        job = self.get(job_id)
        if not job:
            return False
        if job.status == "running":
            job.cancel_requested = True
            return False
        with self._lock:
            self._jobs.pop(job_id, None)
            if job_id in self._order:
                self._order.remove(job_id)
        shutil.rmtree(job.dir, ignore_errors=True)
        return True

    def result_path(self, job: Job) -> Optional[Path]:
        if job.status != "completed":
            return None
        if job.result_name:
            candidate = job.dir / job.result_name
            if candidate.is_file():
                return candidate
        for entry in job.files:
            candidate = Path(entry.get("path") or "")
            if candidate.is_file():
                return candidate
        return None

    # -- workers --------------------------------------------------------
    async def _worker(self, index: int) -> None:
        while True:
            queue = self._get_queue()
            job_id = await queue.get()
            try:
                await self._process(job_id)
            except asyncio.CancelledError:  # pragma: no cover - shutdown
                raise
            except Exception:  # pragma: no cover - defensive
                pass
            finally:
                queue.task_done()

    async def _process(self, job_id: str) -> None:
        job = self.get(job_id)
        if not job or job.status != "queued":
            return

        job.mark_running()
        try:
            result = await asyncio.to_thread(
                self._execute,
                job.options,
                job.dir,
                job.report_progress,
                job.is_cancelled,
            )
        except downloader.JobCancelled:
            job.mark_canceled()
            self._cleanup_partials(job)
        except downloader.DownloaderError as exc:
            job.mark_failed(exc.code, exc.message)
            self._cleanup_partials(job)
        except Exception as exc:  # pragma: no cover - unexpected
            job.mark_failed("download_failed", f"Unexpected error: {str(exc)[:200]}")
            self._cleanup_partials(job)
        else:
            try:
                # Zipping a big playlist is I/O heavy: keep the event loop free.
                await asyncio.to_thread(self._finalize, job, result)
            except Exception as exc:  # pragma: no cover
                job.mark_failed("finalize_failed", f"Could not prepare the file: {str(exc)[:200]}")
        finally:
            self.cleanup()

    def _finalize(self, job: Job, result: Dict[str, Any]) -> None:
        files = result.get("files") or []
        if not files:
            raise downloader.DownloaderError("no_file", "The download finished but no file was produced.")
        title = result.get("title") or job.title or "download"
        with job._lock:  # single assignment block for consistent snapshots
            job.title = title
            job.thumbnail = result.get("thumbnail") or job.thumbnail
            job.duration = result.get("duration") or job.duration
            job.is_playlist = bool(result.get("is_playlist") or job.is_playlist)

        if len(files) > 1:
            archive_title = job.options.get("filename") or title
            archive = self._make_archive(job, files, archive_title)
            job.mark_completed(title, files, archive.name, archive.stat().st_size)
        else:
            single = Path(files[0]["path"])
            job.mark_completed(title, files, single.name, single.stat().st_size)

    def _make_archive(self, job: Job, files: List[Dict[str, Any]], title: str) -> Path:
        base = downloader.sanitize_filename(title or "download")
        archive = job.dir / f"{base}.zip"
        counter = 1
        while archive.exists():
            archive = job.dir / f"{base} ({counter}).zip"
            counter += 1
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
            for entry in files:
                path = Path(entry["path"])
                if path.is_file() and path.resolve() != archive.resolve():
                    bundle.write(path, arcname=entry.get("name") or path.name)
        return archive

    def _cleanup_partials(self, job: Job) -> None:
        """Drop half-written files after a failure so the disk stays clean."""
        try:
            for path in job.dir.rglob("*"):
                if path.is_file():
                    path.unlink(missing_ok=True)
        except OSError:  # pragma: no cover - best effort
            pass

    # -- housekeeping ---------------------------------------------------
    def cleanup(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_cleanup < settings.cleanup_interval_seconds:
            return
        self._last_cleanup = now
        max_age = settings.max_file_age_seconds

        expired: List[str] = []
        for job in self.list_jobs_raw():
            reference = job.finished_at or job.created_at
            if job.status in TERMINAL_STATUSES and now - reference > max_age:
                expired.append(job.id)
        for job_id in expired:
            with self._lock:
                self._jobs.pop(job_id, None)
                if job_id in self._order:
                    self._order.remove(job_id)
        stale_dirs = [settings.download_dir / job_id for job_id in expired]
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # called outside the event loop (tests, scripts)
            for path in stale_dirs:
                shutil.rmtree(path, ignore_errors=True)
            return
        loop.create_task(self._purge_orphan_dirs(now, max_age, stale_dirs))

    async def _purge_orphan_dirs(self, now: float, max_age: int, stale_dirs: List[Path]) -> None:
        def purge() -> None:
            for path in stale_dirs:
                shutil.rmtree(path, ignore_errors=True)
            try:
                settings.ensure_dirs()
                known = set(self._jobs.keys())
                for path in settings.download_dir.iterdir():
                    if not path.is_dir() or path.name.startswith(".") or path.name in known:
                        continue
                    if now - path.stat().st_mtime > max_age:
                        shutil.rmtree(path, ignore_errors=True)
                archives = settings.archives_dir
                if archives.is_dir():
                    for path in archives.iterdir():
                        if path.is_file() and now - path.stat().st_mtime > max_age:
                            path.unlink(missing_ok=True)
            except OSError:  # pragma: no cover - best effort
                pass

        try:
            await asyncio.to_thread(purge)
        except Exception:  # pragma: no cover - best effort
            pass
