"""In-memory deduplication for screen and audio.
Screen: by content hash (SHA-1 of image bytes = pixel-level identity). No OCR/text comparison.
Audio: by segment_id (one id per recorded segment)."""

from __future__ import annotations

import logging
import time
from threading import Lock

log = logging.getLogger("collector.dedup")


def _dedup_window_s() -> float:
    import os
    try:
        return max(60.0, float(os.environ.get("COLLECTOR_DEDUP_WINDOW_S", "300")))
    except ValueError:
        return 300.0


class DedupStore:
    """Thread-safe store of recently seen keys. Keys expire after window_seconds."""

    def __init__(self, window_seconds: float | None = None) -> None:
        self._window = window_seconds if window_seconds is not None else _dedup_window_s()
        self._seen: dict[str, float] = {}
        self._lock = Lock()

    def _prune(self) -> None:
        now = time.monotonic()
        expired = [k for k, t in self._seen.items() if (now - t) > self._window]
        for k in expired:
            del self._seen[k]

    def is_duplicate(self, key: str) -> bool:
        with self._lock:
            self._prune()
            return key in self._seen

    def mark_seen(self, key: str) -> None:
        with self._lock:
            self._prune()
            self._seen[key] = time.monotonic()


# Module-level store shared by screen and audio endpoints
_dedup: DedupStore | None = None


def get_dedup() -> DedupStore:
    global _dedup
    if _dedup is None:
        _dedup = DedupStore()
    return _dedup
