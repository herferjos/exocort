"""Built-in stage adapters for the configurable processor runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import ArtifactEnvelope, ProcessorConfig, StageDefinition
from .utils import (
    date_from_timestamp,
    extract_record_text,
    normalize_list,
    parse_meta,
    safe_id,
    utc_date,
)


@dataclass
class InputItem:
    path: Path
    raw: dict[str, Any]
    envelope: ArtifactEnvelope | None = None


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
        for item in timeline_items:
            super_events.append(
                {
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


def ids_from_indexes(indexes: list[int], inputs: list[dict[str, Any]]) -> list[str]:
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


def default_note_from_super_event(super_event: dict[str, Any]) -> dict[str, Any]:
    note_id = safe_id(str(super_event.get("super_event_id") or super_event.get("title") or "note"))
    return {
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


def build_envelope(
    *,
    stage: str,
    kind: str,
    item_id: str,
    date: str,
    payload: dict[str, Any],
    timestamp: str = "",
    source_ids: list[str] | None = None,
    source_paths: list[str] | None = None,
    trace: dict[str, Any] | None = None,
) -> ArtifactEnvelope:
    return ArtifactEnvelope(
        kind=kind,
        stage=stage,
        item_id=item_id,
        date=date,
        payload=payload,
        timestamp=timestamp,
        source_ids=source_ids or [],
        source_paths=source_paths or [],
        trace=trace or {},
    )


def execute_legacy_l1(
    stage: StageDefinition,
    items: list[InputItem],
    client: Any,
) -> dict[str, list[ArtifactEnvelope]]:
    records = [item.raw for item in items]
    payload = {"events": [build_l1_payload(item.raw, item.path) for item in items]}
    result = client.complete_json(stage.prompt_key or stage.name, payload)
    raw_items = result.get("events") or result.get("items") or []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    if len(records) == 1 and isinstance(result, dict) and not raw_items:
        raw_items = [result]
    if not isinstance(raw_items, list) or len(raw_items) != len(records):
        raise ValueError("L1 response must return one result per input event")

    envelopes = []
    for raw_result, input_item in zip(raw_items, items, strict=False):
        normalized = normalize_l1_output(raw_result if isinstance(raw_result, dict) else {}, input_item.raw, input_item.path)
        envelopes.append(
            build_envelope(
                stage=stage.name,
                kind="event",
                item_id=str(normalized["event_id"]),
                date=str(normalized["date"]),
                payload=normalized,
                timestamp=str(normalized.get("timestamp") or ""),
                source_ids=[str(normalized.get("source_raw_event_id") or "")],
                source_paths=[str(input_item.path)],
                trace={"adapter": "legacy_l1"},
            )
        )
    return {"events": envelopes}


def execute_legacy_l2(
    stage: StageDefinition,
    items: list[InputItem],
    client: Any,
) -> dict[str, list[ArtifactEnvelope]]:
    inputs = [item.envelope.payload if item.envelope is not None else item.raw for item in items]
    payload = {
        "events": inputs,
        "grouping_axes": ["time", "topic", "process", "intention", "app", "context"],
        "expectations": {
            "cleaned_timeline": "ordered events with timestamps and source_event_ids",
            "super_events": "grouped events that may represent one or many timeline items",
        },
    }
    result = client.complete_json(stage.prompt_key or stage.name, payload)
    timeline_items, super_events = extract_l2_outputs(result, inputs)

    timeline_envelopes = [
        build_envelope(
            stage=stage.name,
            kind="timeline_event",
            item_id=str(item["timeline_event_id"]),
            date=str(item["date"]),
            payload=item,
            timestamp=str(item.get("timestamp_start") or ""),
            source_ids=[str(value) for value in item.get("source_event_ids") or [] if str(value).strip()],
            source_paths=[str(input_item.path) for input_item in items],
            trace={"adapter": "legacy_l2", "output": "timeline_events"},
        )
        for item in timeline_items
    ]
    super_event_envelopes = [
        build_envelope(
            stage=stage.name,
            kind="super_event",
            item_id=str(item["super_event_id"]),
            date=str(item["date"]),
            payload=item,
            timestamp=str(item.get("timestamp_start") or ""),
            source_ids=[str(value) for value in item.get("source_event_ids") or [] if str(value).strip()],
            source_paths=[str(input_item.path) for input_item in items],
            trace={"adapter": "legacy_l2", "output": "super_events"},
        )
        for item in super_events
    ]
    return {"timeline_events": timeline_envelopes, "super_events": super_event_envelopes}


def execute_legacy_l3(
    stage: StageDefinition,
    items: list[InputItem],
    client: Any,
) -> dict[str, list[ArtifactEnvelope]]:
    super_events = [item.envelope.payload if item.envelope is not None else item.raw for item in items]
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
    result = client.complete_json(stage.prompt_key or stage.name, payload)
    notes = extract_l3_notes(result, super_events)
    envelopes = [
        build_envelope(
            stage=stage.name,
            kind="inbox_note",
            item_id=str(note["note_id"]),
            date=str(note["date"]),
            payload=note,
            timestamp=str(note.get("timestamp") or ""),
            source_ids=[str(value) for value in note.get("source_event_ids") or [] if str(value).strip()],
            source_paths=[str(input_item.path) for input_item in items],
            trace={"adapter": "legacy_l3"},
        )
        for note in notes
    ]
    return {"notes": envelopes, "note_docs": envelopes}


def _input_payload(item: InputItem, mode: str) -> Any:
    if mode == "raw":
        return item.raw
    if mode == "payload" and item.envelope is not None:
        return item.envelope.payload
    if mode == "envelope" and item.envelope is not None:
        return item.envelope.to_dict()
    return item.raw


def _result_list(result: dict[str, Any], result_key: str | None) -> list[dict[str, Any]]:
    if result_key:
        values = result.get(result_key)
    else:
        values = result.get("items", result)
    if isinstance(values, dict):
        return [values]
    if isinstance(values, list):
        return [item for item in values if isinstance(item, dict)]
    return []


def execute_generic_llm_map(
    stage: StageDefinition,
    items: list[InputItem],
    client: Any,
) -> dict[str, list[ArtifactEnvelope]]:
    options = stage.transform_options
    input_mode = str(options.get("input_mode") or "payload")
    input_key = str(options.get("input_key") or "items")
    result_key = str(options.get("result_key") or "items") or None
    payload = {input_key: [_input_payload(item, input_mode) for item in items]}
    result = client.complete_json(stage.prompt_key or stage.name, payload)
    rows = _result_list(result, result_key)
    if len(rows) != len(items):
        raise ValueError(f"Stage {stage.name} expected one output per input item")

    output_name = stage.outputs[0].name
    kind = str(options.get("kind") or output_name.rstrip("s") or "artifact")
    id_field = str(options.get("id_field") or "id")
    date_field = str(options.get("date_field") or "date")
    timestamp_field = str(options.get("timestamp_field") or "timestamp")
    source_id_field = str(options.get("source_id_field") or "")
    envelopes: list[ArtifactEnvelope] = []
    for row, item in zip(rows, items, strict=False):
        item_id = safe_id(str(row.get(id_field) or item.path.stem))
        timestamp = str(row.get(timestamp_field) or "")
        date = str(row.get(date_field) or date_from_timestamp(timestamp))
        source_ids = []
        if source_id_field:
            source_ids = [str(value).strip() for value in normalize_list(row.get(source_id_field)) if str(value).strip()]
        envelopes.append(
            build_envelope(
                stage=stage.name,
                kind=kind,
                item_id=item_id,
                date=date,
                payload=row,
                timestamp=timestamp,
                source_ids=source_ids,
                source_paths=[str(item.path)],
                trace={"adapter": "generic_llm_map"},
            )
        )
    return {output_name: envelopes}


def execute_generic_llm_reduce(
    stage: StageDefinition,
    items: list[InputItem],
    client: Any,
) -> dict[str, list[ArtifactEnvelope]]:
    options = stage.transform_options
    input_mode = str(options.get("input_mode") or "payload")
    input_key = str(options.get("input_key") or "items")
    result_key = str(options.get("result_key") or "items") or None
    payload = {input_key: [_input_payload(item, input_mode) for item in items]}
    result = client.complete_json(stage.prompt_key or stage.name, payload)
    rows = _result_list(result, result_key)
    output_name = stage.outputs[0].name
    kind = str(options.get("kind") or output_name.rstrip("s") or "artifact")
    id_field = str(options.get("id_field") or "id")
    date_field = str(options.get("date_field") or "date")
    timestamp_field = str(options.get("timestamp_field") or "timestamp")
    source_id_field = str(options.get("source_id_field") or "")
    source_paths = [str(item.path) for item in items]
    envelopes = []
    for row in rows:
        item_id = safe_id(str(row.get(id_field) or f"{stage.name}_{len(envelopes)}"))
        timestamp = str(row.get(timestamp_field) or "")
        date = str(row.get(date_field) or date_from_timestamp(timestamp))
        source_ids = []
        if source_id_field:
            source_ids = [str(value).strip() for value in normalize_list(row.get(source_id_field)) if str(value).strip()]
        envelopes.append(
            build_envelope(
                stage=stage.name,
                kind=kind,
                item_id=item_id,
                date=date,
                payload=row,
                timestamp=timestamp,
                source_ids=source_ids,
                source_paths=source_paths,
                trace={"adapter": "generic_llm_reduce"},
            )
        )
    return {output_name: envelopes}


def execute_stage_adapter(
    stage: StageDefinition,
    config: ProcessorConfig,
    items: list[InputItem],
    client: Any,
) -> dict[str, list[ArtifactEnvelope]]:
    del config
    adapter = stage.transform_adapter or stage.type
    if adapter == "legacy_l1":
        return execute_legacy_l1(stage, items, client)
    if adapter == "legacy_l2":
        return execute_legacy_l2(stage, items, client)
    if adapter == "legacy_l3":
        return execute_legacy_l3(stage, items, client)
    if adapter == "llm_map":
        return execute_generic_llm_map(stage, items, client)
    if adapter == "llm_reduce":
        return execute_generic_llm_reduce(stage, items, client)
    if adapter == "deterministic_map":
        return execute_deterministic_map(stage, items)
    if adapter == "deterministic_reduce":
        return execute_deterministic_reduce(stage, items)
    if adapter == "noop":
        return {output.name: [] for output in stage.outputs}
    raise ValueError(f"Unsupported stage adapter {adapter!r} for stage {stage.name}")


def execute_deterministic_map(
    stage: StageDefinition,
    items: list[InputItem],
) -> dict[str, list[ArtifactEnvelope]]:
    options = stage.transform_options
    input_mode = str(options.get("input_mode") or "payload")
    output_name = stage.outputs[0].name
    kind = str(options.get("kind") or output_name.rstrip("s") or "artifact")
    id_field = str(options.get("id_field") or "id")
    date_field = str(options.get("date_field") or "date")
    timestamp_field = str(options.get("timestamp_field") or "timestamp")
    source_id_field = str(options.get("source_id_field") or "")

    envelopes: list[ArtifactEnvelope] = []
    for item in items:
        payload = _input_payload(item, input_mode)
        if not isinstance(payload, dict):
            raise ValueError(f"Stage {stage.name} deterministic_map expects dict inputs")
        item_id = safe_id(str(payload.get(id_field) or item.path.stem))
        timestamp = str(payload.get(timestamp_field) or "")
        date = str(payload.get(date_field) or date_from_timestamp(timestamp))
        source_ids = []
        if source_id_field:
            source_ids = [str(value).strip() for value in normalize_list(payload.get(source_id_field)) if str(value).strip()]
        envelopes.append(
            build_envelope(
                stage=stage.name,
                kind=kind,
                item_id=item_id,
                date=date,
                payload=payload,
                timestamp=timestamp,
                source_ids=source_ids,
                source_paths=[str(item.path)],
                trace={"adapter": "deterministic_map"},
            )
        )
    return {output_name: envelopes}


def execute_deterministic_reduce(
    stage: StageDefinition,
    items: list[InputItem],
) -> dict[str, list[ArtifactEnvelope]]:
    options = stage.transform_options
    input_mode = str(options.get("input_mode") or "payload")
    output_name = stage.outputs[0].name
    kind = str(options.get("kind") or output_name.rstrip("s") or "artifact")
    payload_key = str(options.get("payload_key") or "items")
    item_id = safe_id(str(options.get("item_id") or f"{stage.name}_{items[-1].path.stem if items else 'empty'}"))
    timestamp = str(options.get("timestamp") or "")
    date = str(options.get("date") or date_from_timestamp(timestamp))
    payload = {payload_key: [_input_payload(item, input_mode) for item in items]}
    return {
        output_name: [
            build_envelope(
                stage=stage.name,
                kind=kind,
                item_id=item_id,
                date=date,
                payload=payload,
                timestamp=timestamp,
                source_paths=[str(item.path) for item in items],
                trace={"adapter": "deterministic_reduce"},
            )
        ]
    }
