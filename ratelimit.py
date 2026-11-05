"""Tiny dependency-free sliding-window rate limiter.

Used to protect a publicly deployed instance from abuse.  It keeps counters in
memory (per process), which is all a single-node deployment needs.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple


class SlidingWindowLimiter:
    def __init__(self, window_seconds: int = 60, max_keys: int = 10_000):
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._hits: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int) -> Tuple[bool, int]:
        """Register a hit for ``key``.

        Returns ``(allowed, retry_after_seconds)``.  When the limit is exceeded
        ``retry_after`` says how long the caller should wait.
        """
        if limit <= 0:
            return True, 0
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            if len(self._hits) > self.max_keys:
                self._prune_all(cutoff)
            bucket = self._hits[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, round(self.window_seconds - (now - bucket[0])))
                return False, retry_after
            bucket.append(now)
            return True, 0

    def _prune_all(self, cutoff: float) -> None:
        for key in list(self._hits):
            bucket = self._hits[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if not bucket:
                self._hits.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter(window_seconds=60)
