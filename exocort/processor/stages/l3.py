"""Stage L3: super events -> inbox notes."""

from __future__ import annotations

from typing import Any

from ..artifacts import note_path, render_note
from ..llm import SupportsLLMClient
from ..models import ProcessorConfig
from ..storage import list_l2_paths, load_state, save_state
from ..utils import atomic_write_text, canonical_path, iter_json_files_recursive, load_json, normalize_list, pending_paths, safe_id, utc_date
from .l2 import should_flush_pending


def default_note_from_super_event(super_event: dict[str, Any]) -> dict[str, Any]:
    note_id = safe_id(str(super_event.get("super_event_id") or super_event.get("title") or "note"))
    return {
        "kind": "inbox_note",
        "note_id": note_id,
        "timestamp": str(super_event.get("timestamp_start") or ""),
        "date": str(super_event.get("date") or utc_date()),
        "title": str(super_event.get("title") or "Untitled note"),
        "description": str(super_event.get("description") or ""),
        "content": str(super_event.get("description") or ""),
        "category": str(super_event.get("category") or ""),
        "subject": str(super_event.get("subject") or ""),
        "super_event_id": str(super_event.get("super_event_id") or ""),
        "source_event_ids": normalize_list(super_event.get("source_event_ids")),
    }


def normalize_note(raw_item: dict[str, Any], super_event: dict[str, Any]) -> dict[str, Any]:
    fallback = default_note_from_super_event(super_event)
    note_id = safe_id(str(raw_item.get("note_id") or raw_item.get("id") or fallback["note_id"]))
    return {
        "kind": "inbox_note",
        "note_id": note_id,
        "timestamp": str(raw_item.get("timestamp") or fallback["timestamp"]),
        "date": str(raw_item.get("date") or fallback["date"]),
        "title": str(raw_item.get("title") or fallback["title"]).strip() or fallback["title"],
        "description": str(raw_item.get("description") or fallback["description"]).strip(),
        "content": str(raw_item.get("content") or raw_item.get("body") or fallback["content"]).strip(),
        "category": str(raw_item.get("category") or fallback["category"]).strip(),
        "subject": str(raw_item.get("subject") or fallback["subject"]).strip(),
        "super_event_id": str(raw_item.get("super_event_id") or fallback["super_event_id"]).strip(),
        "source_event_ids": [
            str(item).strip()
            for item in normalize_list(raw_item.get("source_event_ids") or fallback["source_event_ids"])
            if str(item).strip()
        ],
    }


def extract_l3_notes(result: dict[str, Any], super_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_items = result.get("notes") or result.get("items") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]

    notes_by_super_event: dict[str, dict[str, Any]] = {}
    for raw_item in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(raw_item, dict):
            continue
        super_event_id = str(raw_item.get("super_event_id") or "").strip()
        matching = next(
            (item for item in super_events if str(item.get("super_event_id") or "") == super_event_id),
            None,
        )
        if matching is None and len(super_events) == 1:
            matching = super_events[0]
        if matching is None:
            continue
        notes_by_super_event[matching["super_event_id"]] = normalize_note(raw_item, matching)

    notes: list[dict[str, Any]] = []
    for super_event in super_events:
        super_event_id = str(super_event.get("super_event_id") or "")
        notes.append(notes_by_super_event.get(super_event_id) or default_note_from_super_event(super_event))
    return notes


def run_l3_once(config: ProcessorConfig, client: SupportsLLMClient) -> int:
    if not config.write_notes:
        return 0

    all_super_paths = list_l2_paths(config)
    state = load_state(config, "l3")
    pending_super_paths = pending_paths(all_super_paths, state.last_l2_path)
    upstream_pending = bool(iter_json_files_recursive(config.out_dir / "l1"))
    if not should_flush_pending(pending_super_paths, config.l3_batch_events, upstream_pending=upstream_pending):
        return 0

    batch_paths = (
        pending_super_paths[: config.l3_batch_events]
        if len(pending_super_paths) >= config.l3_batch_events
        else pending_super_paths
    )
    super_events = [load_json(path) for path in batch_paths]
    payload = {
        "super_events": super_events,
        "note_schema": {
            "timestamp": "original timestamp for the note",
            "title": "clear inbox note title",
            "description": "one-line summary",
            "content": "full note body",
            "category": "normalized category",
            "subject": "main subject or entity",
            "super_event_id": "traceability to super event",
        },
    }
    result = client.complete_json("l3_notes", payload)
    notes = extract_l3_notes(result, super_events)

    for note in notes:
        path = note_path(config.out_dir, note)
        if not config.dry_run:
            atomic_write_text(path, render_note(note))

    if notes:
        last_note = notes[-1]
        state.last_note_id = str(last_note.get("note_id") or "")
        state.last_note_path = canonical_path(note_path(config.out_dir, last_note))
    if batch_paths:
        state.last_l2_path = canonical_path(batch_paths[-1])
        state.last_l2_event_id = batch_paths[-1].stem
    save_state(config, "l3", state)
    return len(notes)
