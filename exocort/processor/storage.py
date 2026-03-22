"""Persistence helpers for processor artifacts and state."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .models import ArtifactEnvelope, CollectionDefinition, ProcessorConfig, ProcessorState
from .utils import (
    atomic_write_json,
    atomic_write_text,
    iter_json_files_flat,
    iter_json_files_recursive,
    load_json,
    utc_iso,
)

logger = logging.getLogger(__name__)


def resolve_collection_dir(config: ProcessorConfig, collection: CollectionDefinition) -> Path:
    base = config.out_dir
    if collection.base_dir == "vault":
        base = config.vault_dir
    path = Path(collection.path)
    if path == Path("."):
        return base
    return base / path


def state_file(config: ProcessorConfig, name: str) -> Path:
    return config.out_dir / name / "state.json"


def load_state(config: ProcessorConfig, name: str) -> ProcessorState:
    path = state_file(config, name)
    if not path.exists():
        logger.debug("State file missing, using default state: name=%s path=%s", name, path)
        return ProcessorState()
    data = load_json(path)
    state = ProcessorState.from_dict(data if isinstance(data, dict) else {})
    logger.debug(
        "Loaded state: name=%s path=%s cursor=%s",
        name,
        path,
        state.cursor_path,
    )
    return state


def save_state(config: ProcessorConfig, name: str, state: ProcessorState) -> None:
    state.last_run_at = utc_iso()
    path = state_file(config, name)
    atomic_write_json(path, state.to_dict())
    logger.debug(
        "Saved state: name=%s path=%s cursor=%s",
        name,
        path,
        state.cursor_path,
    )


def projection_jsonl_path(config: ProcessorConfig, collection: CollectionDefinition, date: str) -> Path:
    return resolve_collection_dir(config, collection) / f"{date}.jsonl"


def _artifact_date(item: dict[str, object]) -> str:
    timestamp = item.get("timestamp")
    if isinstance(timestamp, str) and len(timestamp) >= 10:
        return timestamp[:10]
    return ""


def rewrite_jsonl_day(config: ProcessorConfig, source: CollectionDefinition, target: CollectionDefinition, date: str) -> None:
    source_root = resolve_collection_dir(config, source)
    entries: list[dict[str, object]] = []
    if source_root.exists():
        for path in sorted(source_root.rglob("*.json")):
            if path.name == "state.json":
                continue
            item = load_json(path)
            if _artifact_date(item) == date:
                entries.append(item)
    entries.sort(
        key=lambda item: (
            str(item.get("timestamp") or ""),
            str(item.get("timestamp_end") or ""),
            str(item.get("id") or ""),
        )
    )
    text = ""
    if entries:
        lines = [json.dumps(item, ensure_ascii=False) for item in entries]
        text = "\n".join(lines) + "\n"
    path = projection_jsonl_path(config, target, date)
    atomic_write_text(path, text)
    logger.debug(
        "Rewrote jsonl day: source=%s target=%s date=%s entries=%s path=%s",
        resolve_collection_dir(config, source),
        resolve_collection_dir(config, target),
        date,
        len(entries),
        path,
    )


def list_collection_paths(config: ProcessorConfig, collection: CollectionDefinition) -> list[Path]:
    root = resolve_collection_dir(config, collection)
    if collection.base_dir == "vault":
        return iter_json_files_recursive(root)
    return iter_json_files_flat(root)


def load_artifact(path: Path) -> ArtifactEnvelope:
    data = load_json(path)
    envelope = ArtifactEnvelope.from_dict(data if isinstance(data, dict) else {})
    logger.debug("Loaded artifact: path=%s id=%s", path, envelope.id)
    return envelope
