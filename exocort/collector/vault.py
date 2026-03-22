"""Persistence helpers for collector records."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from exocort import settings


def _vault_dir() -> Path:
    return settings.collector_vault_dir()


def write_vault_record(
    id_: str,
    text: str,
) -> Path:
    """Write one JSON record to vault/raw/{id}.json."""
    root = _vault_dir()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{id_}.json"
    record = {
        "id": id_,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "text": text,
    }
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return path


def new_record_id() -> str:
    return uuid4().hex
