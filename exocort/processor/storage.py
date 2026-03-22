"""Persistence helpers for processor artifacts and state."""

from __future__ import annotations

import json
from pathlib import Path

from .models import ArtifactEnvelope, CollectionDefinition, ProcessorConfig, ProcessorState
from .utils import atomic_write_json, atomic_write_text, iter_json_files_recursive, load_json, utc_iso


def resolve_collection_dir(config: ProcessorConfig, collection: CollectionDefinition) -> Path:
    base = config.out_dir
    if collection.base_dir == "vault":
        base = config.vault_dir
    elif collection.base_dir == "state":
        assert config.state_dir is not None
        base = config.state_dir
    path = Path(collection.path)
    if path == Path("."):
        return base
    return base / path


def collection_dir(config: ProcessorConfig, name: str) -> Path:
    collection = config.collections[name]
    return resolve_collection_dir(config, collection)


def state_file(config: ProcessorConfig, name: str) -> Path:
    assert config.state_dir is not None
    return config.state_dir / f"state_{name}.json"


def load_state(config: ProcessorConfig, name: str) -> ProcessorState:
    path = state_file(config, name)
    if not path.exists():
        return ProcessorState()
    data = load_json(path)
    return ProcessorState.from_dict(data if isinstance(data, dict) else {})


def save_state(config: ProcessorConfig, name: str, state: ProcessorState) -> None:
    state.last_run_at = utc_iso()
    payload = state.to_dict()
    metadata = payload.setdefault("metadata", {})
    if state.cursor_id:
        metadata.setdefault("last_l2_event_id", state.cursor_id)
        payload.setdefault("last_l2_event_id", state.cursor_id)
    atomic_write_json(state_file(config, name), payload)


def timeline_jsonl_path(out_dir: Path, date: str) -> Path:
    return out_dir / "timeline" / f"{date}.jsonl"


def rewrite_timeline_day(out_dir: Path, date: str) -> None:
    source_dir = out_dir / "timeline_events" / date
    entries = [load_json(path) for path in sorted(source_dir.glob("*.json"))] if source_dir.exists() else []
    entries.sort(
        key=lambda item: (
            str(item.get("timestamp") or ""),
            str(item.get("payload", {}).get("timestamp_end") or ""),
            str(item.get("item_id") or ""),
        )
    )
    text = ""
    if entries:
        lines = [json.dumps(item.get("payload", item), ensure_ascii=False) for item in entries]
        text = "\n".join(lines) + "\n"
    atomic_write_text(timeline_jsonl_path(out_dir, date), text)


def list_collection_paths(config: ProcessorConfig, name: str) -> list[Path]:
    return iter_json_files_recursive(collection_dir(config, name))


def load_artifact(path: Path) -> ArtifactEnvelope:
    data = load_json(path)
    return ArtifactEnvelope.from_dict(data if isinstance(data, dict) else {})
