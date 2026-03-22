"""Stage L1: raw vault events -> enriched events."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..llm import SupportsLLMClient
from ..models import ProcessorConfig
from ..storage import load_state, save_state
from ..utils import (
    atomic_write_json,
    canonical_path,
    date_from_timestamp,
    ensure_parent,
    extract_record_text,
    iter_json_files_recursive,
    load_json,
    parse_meta,
    safe_id,
    utc_date,
)


def raw_event_id(record: dict[str, Any], path: Path) -> str:
    return safe_id(str(record.get("id") or path.stem))


def build_l1_payload(record: dict[str, Any], path: Path) -> dict[str, Any]:
    meta = parse_meta(record.get("meta") or {})
    return {
        "raw_event_id": raw_event_id(record, path),
        "timestamp": str(record.get("timestamp") or ""),
        "type": str(record.get("type") or "unknown"),
        "id": str(record.get("id") or ""),
        "meta": meta,
        "responses": record.get("responses") or [],
        "raw_text": extract_record_text(record),
        "source_path": str(path),
    }


def fallback_event_title(payload: dict[str, Any]) -> str:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    app = meta.get("app") if isinstance(meta, dict) else {}
    app_name = app.get("name") if isinstance(app, dict) else None
    type_name = str(payload.get("type") or "event").strip() or "event"
    if app_name:
        return f"{type_name.title()} in {app_name}"
    return type_name.title()


def normalize_l1_output(result: dict[str, Any], record: dict[str, Any], path: Path) -> dict[str, Any]:
    payload = build_l1_payload(record, path)
    timestamp = str(result.get("timestamp") or payload["timestamp"] or "")
    event_id = safe_id(str(result.get("event_id") or result.get("l1_event_id") or payload["raw_event_id"]))
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else payload["meta"]
    context = result.get("context") if isinstance(result.get("context"), dict) else {}
    title = str(result.get("title") or "").strip() or fallback_event_title(payload)
    description = str(result.get("description") or payload["raw_text"] or "").strip()
    content = str(result.get("content") or result.get("clean_text") or description).strip()
    app_name = ""
    if isinstance(meta.get("app"), dict):
        app_name = str(meta["app"].get("name") or "")
    return {
        "kind": "event",
        "event_id": event_id,
        "timestamp": timestamp,
        "date": date_from_timestamp(timestamp),
        "source_type": str(result.get("source_type") or payload["type"] or "unknown"),
        "source_raw_event_id": payload["raw_event_id"],
        "title": title,
        "description": description,
        "content": content,
        "app_name": str(result.get("app_name") or app_name),
        "context": context,
        "meta": meta,
        "source_path": str(path),
    }


def extract_l1_results(result: dict[str, Any], records: list[dict[str, Any]], paths: list[Path]) -> list[dict[str, Any]]:
    raw_items = result.get("events") or result.get("items") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    if len(records) == 1 and isinstance(result, dict) and not raw_items:
        raw_items = [result]
    if not isinstance(raw_items, list) or len(raw_items) != len(records):
        raise ValueError("L1 response must return one result per input event")
    return [normalize_l1_output(item, record, path) for item, record, path in zip(raw_items, records, paths, strict=False)]


def run_l1_once(config: ProcessorConfig, client: SupportsLLMClient) -> int:
    raw_paths = iter_json_files_recursive(config.vault_dir)
    if not raw_paths:
        return 0

    batch_paths = raw_paths[: config.l1_batch_events]
    records = [load_json(path) for path in batch_paths]
    result = client.complete_json(
        "l1_event",
        {"events": [build_l1_payload(record, path) for record, path in zip(records, batch_paths, strict=False)]},
    )
    events = extract_l1_results(result, records, batch_paths)

    state = load_state(config, "l1")
    processed = 0
    for path, event in zip(batch_paths, events, strict=False):
        date = str(event.get("date") or utc_date())
        event_path = config.out_dir / "l1" / date / f"{event['event_id']}.json"
        archive_path = config.out_dir / "l0_processed_raw" / date / path.name
        if not config.dry_run:
            atomic_write_json(event_path, event)
            ensure_parent(archive_path)
            path.replace(archive_path)
        state.last_raw_event_id = str(event["event_id"])
        state.last_raw_path = canonical_path(path)
        processed += 1

    save_state(config, "l1", state)
    return processed
