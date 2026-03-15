"""Persist incoming files to tmp, write API responses to vault, then remove tmp."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any


def normalize_vault_response(
    url: str,
    provider: str,
    ok: bool,
    status: int,
    raw_body: str,
    parsed_text: str | None = None,
) -> dict[str, Any]:
    """Build a single response dict for vault so every record has the same shape."""
    return {
        "url": url,
        "provider": provider,
        "ok": ok,
        "status": status,
        "text": parsed_text if parsed_text is not None else None,
        "raw": raw_body,
    }

try:
    from exocort import settings

    def _tmp_dir() -> Path:
        return settings.collector_tmp_dir()

    def _vault_dir() -> Path:
        return settings.collector_vault_dir()
except ImportError:
    def _tmp_dir() -> Path:
        return Path(os.environ.get("COLLECTOR_TMP_DIR", "tmp/collector")).resolve()

    def _vault_dir() -> Path:
        return Path(os.environ.get("COLLECTOR_VAULT_DIR", "vault")).resolve()


def _date_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_content_keys_from_vault(days_back: int = 2) -> set[str]:
    """Scan vault for screen (meta.hash) and audio (meta.segment_id); return set of 'screen:<hash>' and 'audio:<segment_id>'."""
    root = _vault_dir()
    if not root.exists():
        return set()
    keys: set[str] = set()
    today = datetime.now(timezone.utc).date()
    for d in range(days_back + 1):
        date_dir = root / (today - timedelta(days=d)).strftime("%Y-%m-%d")
        if not date_dir.is_dir():
            continue
        for path in date_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            t = data.get("type")
            meta = data.get("meta") or {}
            if t == "screen" and meta.get("hash"):
                keys.add(f"screen:{meta['hash']}")
            elif t == "audio" and meta.get("segment_id"):
                keys.add(f"audio:{meta['segment_id']}")
    return keys


class VaultIndex:
    """Set of content keys already in vault; loaded from disk on init, updated on write."""

    def __init__(self, days_back: int = 2) -> None:
        self._keys: set[str] = set()
        self._lock = Lock()
        self._days_back = days_back
        self._load()

    def _load(self) -> None:
        self._keys = _load_content_keys_from_vault(self._days_back)

    def contains(self, key: str) -> bool:
        with self._lock:
            return key in self._keys

    def add(self, key: str) -> None:
        with self._lock:
            self._keys.add(key)

    def __len__(self) -> int:
        with self._lock:
            return len(self._keys)


def _timestamp_id() -> str:
    """Filesystem-safe ISO timestamp (no colons)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S.%f")[:-3]


def save_to_tmp(
    content: bytes,
    subdir: str,
    date: str,
    base_name: str,
    suffix: str,
) -> Path:
    """Save content under tmp/collector/{subdir}/{date}/{base_name}{suffix}. Returns path."""
    root = _tmp_dir() / subdir / date
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{base_name}{suffix}"
    path.write_bytes(content)
    return path


def write_vault_record(
    date: str,
    timestamp_iso: str,
    type_: str,
    id_: str,
    meta: dict[str, Any],
    responses: list[dict[str, Any]],
) -> Path:
    """Write one JSON record to vault/{date}/{timestamp}_{type}_{id}.json.
    Each item in responses should be normalized (e.g. via normalize_vault_response).
    """
    root = _vault_dir() / date
    root.mkdir(parents=True, exist_ok=True)
    safe_ts = timestamp_iso.replace(":", "-")
    name = f"{safe_ts}_{type_}_{id_}.json"
    path = root / name
    record = {
        "timestamp": timestamp_iso,
        "type": type_,
        "id": id_,
        "meta": meta,
        "responses": responses,
    }
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def remove_tmp(path: Path) -> None:
    path.unlink(missing_ok=True)
