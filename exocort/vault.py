"""Persistence helpers for direct capturer outputs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from exocort import settings


def vault_dir() -> Path:
    root = settings.vault_dir()
    root.mkdir(parents=True, exist_ok=True)
    return root


def new_record_id() -> str:
    return uuid4().hex


def write_vault_record(
    id_: str,
    text: str,
    *,
    stream: str,
    model: str,
    metadata: dict[str, Any] | None = None,
) -> Path:
    path = vault_dir() / f"{id_}.json"
    record = {
        "id": id_,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stream": stream,
        "model": model,
        "text": text,
    }
    if metadata:
        record["metadata"] = metadata
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    return path
