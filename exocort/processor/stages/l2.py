"""Stage L2: enriched events -> cleaned timeline + super events."""

from __future__ import annotations

from typing import Any, Iterable

from ..llm import SupportsLLMClient
from ..models import ProcessorConfig
from ..storage import list_l1_paths, load_state, rewrite_timeline_day, save_state
from ..utils import (
    atomic_write_json,
    canonical_path,
    date_from_timestamp,
    ensure_parent,
    iter_json_files_recursive,
    load_json,
    normalize_list,
    safe_id,
    utc_date,
)


def should_flush_pending(pending_paths: list, threshold: int, upstream_pending: bool) -> bool:
    if not pending_paths:
        return False
    if len(pending_paths) >= threshold:
        return True
    return not upstream_pending


def default_cleaned_timeline(inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "timeline_event_id": f"timeline_{event['event_id']}",
            "title": event.get("title"),
            "description": event.get("description"),
            "timestamp_start": event.get("timestamp"),
            "timestamp_end": event.get("timestamp"),
            "source_event_ids": [event.get("event_id")],
        }
        for event in inputs
    ]


def ids_from_indexes(indexes: Iterable[int], inputs: list[dict[str, Any]]) -> list[str]:
    event_ids: list[str] = []
    for index in indexes:
        if 0 <= index < len(inputs):
            event_id = str(inputs[index].get("event_id") or "").strip()
            if event_id:
                event_ids.append(event_id)
    return event_ids


def source_event_ids(raw_item: dict[str, Any], inputs: list[dict[str, Any]], default_indexes: list[int]) -> list[str]:
    raw_ids = raw_item.get("source_event_ids") or raw_item.get("event_ids")
    if isinstance(raw_ids, str):
        return [raw_ids]
    if isinstance(raw_ids, list):
        values = [str(value).strip() for value in raw_ids if str(value).strip()]
        if values:
            return values
    raw_indexes = raw_item.get("source_indexes") or raw_item.get("indexes") or default_indexes
    indexes = raw_indexes if isinstance(raw_indexes, list) else [raw_indexes]
    numeric_indexes = [int(value) for value in indexes if isinstance(value, int) or (isinstance(value, str) and value.isdigit())]
    resolved = ids_from_indexes(numeric_indexes, inputs)
    if resolved:
        return resolved
    return ids_from_indexes(default_indexes, inputs)


def timestamps_for_ids(inputs: list[dict[str, Any]], event_ids: list[str]) -> list[str]:
    lookup = {str(item.get("event_id") or ""): str(item.get("timestamp") or "") for item in inputs}
    return [lookup[event_id] for event_id in event_ids if lookup.get(event_id)]


def normalize_timeline_item(raw_item: dict[str, Any], inputs: list[dict[str, Any]], default_indexes: list[int]) -> dict[str, Any]:
    event_ids = source_event_ids(raw_item, inputs, default_indexes)
    timestamps = timestamps_for_ids(inputs, event_ids)
    start_ts = str(raw_item.get("timestamp_start") or (min(timestamps) if timestamps else ""))
    end_ts = str(raw_item.get("timestamp_end") or (max(timestamps) if timestamps else start_ts))
    title = str(raw_item.get("title") or "").strip()
    description = str(raw_item.get("description") or raw_item.get("summary") or "").strip()
    timeline_event_id = safe_id(str(raw_item.get("timeline_event_id") or raw_item.get("event_id") or f"timeline_{start_ts}_{title or 'event'}"))
    return {
        "kind": "timeline_event",
        "timeline_event_id": timeline_event_id,
        "event_id": timeline_event_id,
        "timestamp_start": start_ts,
        "timestamp_end": end_ts,
        "date": date_from_timestamp(start_ts or end_ts),
        "title": title or "Untitled event",
        "description": description,
        "source_event_ids": event_ids,
        "super_event_id": str(raw_item.get("super_event_id") or "").strip(),
    }


def normalize_super_event(raw_item: dict[str, Any], inputs: list[dict[str, Any]], default_indexes: list[int]) -> dict[str, Any]:
    event_ids = source_event_ids(raw_item, inputs, default_indexes)
    timestamps = timestamps_for_ids(inputs, event_ids)
    start_ts = str(raw_item.get("timestamp_start") or (min(timestamps) if timestamps else ""))
    end_ts = str(raw_item.get("timestamp_end") or (max(timestamps) if timestamps else start_ts))
    title = str(raw_item.get("title") or raw_item.get("name") or "").strip() or "Untitled super event"
    description = str(raw_item.get("description") or raw_item.get("summary") or "").strip()
    super_event_id = safe_id(str(raw_item.get("super_event_id") or raw_item.get("event_id") or f"super_{start_ts}_{title}"))
    timeline_event_ids = [str(item).strip() for item in normalize_list(raw_item.get("timeline_event_ids")) if str(item).strip()]
    dimensions = [str(item).strip() for item in normalize_list(raw_item.get("grouping_dimensions")) if str(item).strip()]
    return {
        "kind": "super_event",
        "super_event_id": super_event_id,
        "timestamp_start": start_ts,
        "timestamp_end": end_ts,
        "date": date_from_timestamp(start_ts or end_ts),
        "title": title,
        "description": description,
        "category": str(raw_item.get("category") or "").strip(),
        "subject": str(raw_item.get("subject") or "").strip(),
        "grouping_dimensions": dimensions,
        "source_event_ids": event_ids,
        "timeline_event_ids": timeline_event_ids,
    }


def extract_l2_outputs(result: dict[str, Any], inputs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_timeline = result.get("cleaned_timeline") or result.get("timeline") or []
    raw_super_events = result.get("super_events") or result.get("groups") or []
    if isinstance(raw_timeline, dict):
        raw_timeline = [raw_timeline]
    if isinstance(raw_super_events, dict):
        raw_super_events = [raw_super_events]
    if not raw_timeline:
        raw_timeline = default_cleaned_timeline(inputs)

    timeline_items = [
        normalize_timeline_item(item if isinstance(item, dict) else {}, inputs, [index])
        for index, item in enumerate(raw_timeline)
    ]
    super_events = [
        normalize_super_event(item if isinstance(item, dict) else {}, inputs, [index])
        for index, item in enumerate(raw_super_events)
    ]

    if not super_events:
        super_events = []
        for item in timeline_items:
            super_events.append(
                {
                    "kind": "super_event",
                    "super_event_id": safe_id(f"super_{item['timeline_event_id']}"),
                    "timestamp_start": item["timestamp_start"],
                    "timestamp_end": item["timestamp_end"],
                    "date": item["date"],
                    "title": item["title"],
                    "description": item["description"],
                    "category": "",
                    "subject": "",
                    "grouping_dimensions": ["topic"],
                    "source_event_ids": item["source_event_ids"],
                    "timeline_event_ids": [item["timeline_event_id"]],
                }
            )

    for item in timeline_items:
        if item["super_event_id"]:
            continue
        matching = next(
            (
                super_event
                for super_event in super_events
                if set(item["source_event_ids"]) & set(super_event["source_event_ids"])
            ),
            None,
        )
        if matching is None:
            matching = {
                "kind": "super_event",
                "super_event_id": safe_id(f"super_{item['timeline_event_id']}"),
                "timestamp_start": item["timestamp_start"],
                "timestamp_end": item["timestamp_end"],
                "date": item["date"],
                "title": item["title"],
                "description": item["description"],
                "category": "",
                "subject": "",
                "grouping_dimensions": ["topic"],
                "source_event_ids": item["source_event_ids"],
                "timeline_event_ids": [],
            }
            super_events.append(matching)
        item["super_event_id"] = matching["super_event_id"]
        if item["timeline_event_id"] not in matching["timeline_event_ids"]:
            matching["timeline_event_ids"].append(item["timeline_event_id"])

    return timeline_items, super_events


def run_l2_once(config: ProcessorConfig, client: SupportsLLMClient) -> int:
    pending_l1 = list_l1_paths(config)
    if not should_flush_pending(pending_l1, config.l2_batch_events, upstream_pending=bool(iter_json_files_recursive(config.vault_dir))):
        return 0

    batch_paths = pending_l1[: config.l2_batch_events] if len(pending_l1) >= config.l2_batch_events else pending_l1
    inputs = [load_json(path) for path in batch_paths]
    payload = {
        "events": inputs,
        "grouping_axes": ["time", "topic", "process", "intention", "app", "context"],
        "expectations": {
            "cleaned_timeline": "ordered events with timestamps and source_event_ids",
            "super_events": "grouped events that may represent one or many timeline items",
        },
    }
    result = client.complete_json("l2_timeline", payload)
    timeline_items, super_events = extract_l2_outputs(result, inputs)

    touched_dates: set[str] = set()
    for item in timeline_items:
        date = str(item.get("date") or utc_date())
        touched_dates.add(date)
        item_path = config.out_dir / "timeline_events" / date / f"{item['timeline_event_id']}.json"
        if not config.dry_run:
            atomic_write_json(item_path, item)

    for super_event in super_events:
        date = str(super_event.get("date") or utc_date())
        super_path = config.out_dir / "l2" / date / f"{super_event['super_event_id']}.json"
        if not config.dry_run:
            atomic_write_json(super_path, super_event)

    state = load_state(config, "l2")
    for path in batch_paths:
        date = path.parent.name
        archive_path = config.out_dir / "l1_processed" / date / path.name
        if not config.dry_run:
            ensure_parent(archive_path)
            path.replace(archive_path)
        state.last_l1_path = canonical_path(path)

    if super_events:
        last_super = super_events[-1]
        state.last_l2_event_id = str(last_super.get("super_event_id") or "")
        state.last_l2_path = canonical_path(config.out_dir / "l2" / last_super["date"] / f"{last_super['super_event_id']}.json")

    if not config.dry_run:
        for date in touched_dates:
            rewrite_timeline_day(config.out_dir, date)
    save_state(config, "l2", state)
    return len(timeline_items) + len(super_events)
