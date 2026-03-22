"""Unit tests for the event -> timeline -> notes processor pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from exocort.collector.vault import normalize_vault_response
from exocort.processor import ProcessorConfig, run_once
from exocort.processor.models import CollectionDefinition, PipelineDefinition, StageDefinition


pytestmark = pytest.mark.unit


class FakeProcessorLLMClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete_json(self, prompt_key: str, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(prompt_key)

        if prompt_key == "l1_event":
            events = payload.get("events") if isinstance(payload.get("events"), list) else []
            return {
                "events": [
                    {
                        "event_id": str(event.get("raw_event_id") or "event"),
                        "timestamp": str(event.get("timestamp") or "2026-03-19T10:00:00+00:00"),
                        "title": f"Event {event.get('raw_event_id')}",
                        "description": f"Observed activity for {event.get('raw_event_id')}.",
                        "content": str(event.get("raw_text") or ""),
                        "meta": event.get("meta") or {},
                    }
                    for event in events
                    if isinstance(event, dict)
                ]
            }

        if prompt_key == "l2_timeline":
            events = payload.get("events") if isinstance(payload.get("events"), list) else []
            if not events:
                return {"cleaned_timeline": [], "super_events": []}

            first = events[0] if isinstance(events[0], dict) else {}
            last = events[-1] if isinstance(events[-1], dict) else first
            event_ids = [str(event.get("event_id") or "") for event in events if isinstance(event, dict)]
            start_ts = str(first.get("timestamp") or "2026-03-19T10:00:00+00:00")
            end_ts = str(last.get("timestamp") or start_ts)

            if len(events) >= 2:
                return {
                    "cleaned_timeline": [
                        {
                            "timeline_event_id": "timeline_focus_block",
                            "title": "OCR parser work",
                            "description": "Focused work block on OCR parser improvements.",
                            "timestamp_start": start_ts,
                            "timestamp_end": end_ts,
                            "source_event_ids": event_ids,
                            "super_event_id": "super_focus_block",
                        }
                    ],
                    "super_events": [
                        {
                            "super_event_id": "super_focus_block",
                            "title": "OCR parser work",
                            "description": "Grouped OCR parser work session.",
                            "timestamp_start": start_ts,
                            "timestamp_end": end_ts,
                            "source_event_ids": event_ids,
                            "timeline_event_ids": ["timeline_focus_block"],
                            "grouping_dimensions": ["topic", "process"],
                            "category": "work",
                            "subject": "ocr-parser",
                        }
                    ],
                }

            return {
                "cleaned_timeline": [
                    {
                        "timeline_event_id": f"timeline_{event_ids[0]}",
                        "title": "Single activity",
                        "description": "Single event preserved in the cleaned timeline.",
                        "timestamp_start": start_ts,
                        "timestamp_end": end_ts,
                        "source_event_ids": event_ids,
                        "super_event_id": f"super_{event_ids[0]}",
                    }
                ],
                "super_events": [
                    {
                        "super_event_id": f"super_{event_ids[0]}",
                        "title": "Single activity",
                        "description": "Single event converted into a super event.",
                        "timestamp_start": start_ts,
                        "timestamp_end": end_ts,
                        "source_event_ids": event_ids,
                        "timeline_event_ids": [f"timeline_{event_ids[0]}"],
                        "grouping_dimensions": ["topic"],
                        "category": "activity",
                        "subject": event_ids[0],
                    }
                ],
            }

        if prompt_key == "l3_notes":
            super_events = payload.get("super_events") if isinstance(payload.get("super_events"), list) else []
            notes: list[dict[str, object]] = []
            for super_event in super_events:
                if not isinstance(super_event, dict):
                    continue
                super_event_id = str(super_event.get("super_event_id") or "super_event")
                notes.append(
                    {
                        "note_id": f"note_{super_event_id}",
                        "timestamp": str(super_event.get("timestamp_start") or ""),
                        "date": str(super_event.get("date") or "2026-03-19"),
                        "title": str(super_event.get("title") or "Untitled note"),
                        "description": str(super_event.get("description") or ""),
                        "content": f"Derived note for {super_event_id}.",
                        "category": str(super_event.get("category") or ""),
                        "subject": str(super_event.get("subject") or ""),
                        "super_event_id": super_event_id,
                        "source_event_ids": super_event.get("source_event_ids") or [],
                    }
                )
            return {"notes": notes}

        raise AssertionError(f"unexpected prompt key {prompt_key!r}")


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_raw_record(
    vault_dir: Path,
    *,
    date: str,
    timestamp_iso: str,
    event_id: str,
    raw_text: str,
) -> Path:
    day_dir = vault_dir / date
    day_dir.mkdir(parents=True, exist_ok=True)
    safe_ts = timestamp_iso.replace(":", "-")
    path = day_dir / f"{safe_ts}_screen_{event_id}.json"
    path.write_text(
        json.dumps(
            {
                "timestamp": timestamp_iso,
                "type": "screen",
                "id": event_id,
                "meta": {"app": {"name": "Cursor"}, "window": {"title": "openai.py"}},
                "responses": [
                    normalize_vault_response(
                        "http://127.0.0.1:9093/ocr",
                        "openai",
                        True,
                        200,
                        raw_text,
                        raw_text,
                    )
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize("execution_mode", ["per_stage_worker", "single_loop"])
def test_processor_creates_super_events_and_notes_from_related_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    execution_mode: str,
) -> None:
    vault_dir = tmp_path / "vault"
    out_dir = tmp_path / "processed"
    monkeypatch.setenv("COLLECTOR_VAULT_DIR", str(vault_dir))

    record_a = write_raw_record(
        vault_dir,
        date="2026-03-19",
        timestamp_iso="2026-03-19T10:00:00+00:00",
        event_id="screen_event_a",
        raw_text="raw OCR text A",
    )
    record_b = write_raw_record(
        vault_dir,
        date="2026-03-19",
        timestamp_iso="2026-03-19T10:01:00+00:00",
        event_id="screen_event_b",
        raw_text="raw OCR text B",
    )

    config = ProcessorConfig(
        vault_dir=vault_dir,
        out_dir=out_dir,
        state_dir=out_dir / "state",
        write_notes=True,
        dry_run=False,
        execution_mode=execution_mode,
        l1_batch_events=2,
        l2_batch_events=2,
        l3_batch_events=1,
    )
    client = FakeProcessorLLMClient()

    processed = run_once(config, client=client)

    assert processed == 5
    assert not record_a.exists()
    assert not record_b.exists()
    assert client.calls == ["l1_event", "l2_timeline", "l3_notes"]

    timeline_path = out_dir / "timeline" / "2026-03-19.jsonl"
    super_event_path = out_dir / "l2" / "2026-03-19" / "super_focus_block.json"
    note_path = out_dir / "notes" / "inbox" / "2026-03-19" / "note_super_focus_block.md"
    note_json_path = out_dir / "notes" / "2026-03-19" / "note_super_focus_block.json"
    l1_archive_a = out_dir / "l1_processed" / "2026-03-19" / "screen_event_a.json"
    l1_archive_b = out_dir / "l1_processed" / "2026-03-19" / "screen_event_b.json"

    assert timeline_path.exists()
    assert super_event_path.exists()
    assert note_path.exists()
    assert note_json_path.exists()
    assert l1_archive_a.exists()
    assert l1_archive_b.exists()

    timeline_lines = [json.loads(line) for line in timeline_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(timeline_lines) == 1
    assert timeline_lines[0]["super_event_id"] == "super_focus_block"
    assert timeline_lines[0]["source_event_ids"] == ["screen_event_a", "screen_event_b"]

    super_event = load_json(super_event_path)
    assert super_event["payload"]["grouping_dimensions"] == ["topic", "process"]
    assert super_event["payload"]["category"] == "work"

    note_text = note_path.read_text(encoding="utf-8")
    assert "Derived note for super_focus_block." in note_text
    assert "super_focus_block" in note_text


def test_processor_flushes_single_event_into_super_event_when_upstream_is_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    vault_dir = tmp_path / "vault"
    out_dir = tmp_path / "processed"
    monkeypatch.setenv("COLLECTOR_VAULT_DIR", str(vault_dir))

    record = write_raw_record(
        vault_dir,
        date="2026-03-19",
        timestamp_iso="2026-03-19T12:00:00+00:00",
        event_id="screen_event_single",
        raw_text="raw OCR text single",
    )

    config = ProcessorConfig(
        vault_dir=vault_dir,
        out_dir=out_dir,
        state_dir=out_dir / "state",
        write_notes=True,
        dry_run=False,
        l1_batch_events=1,
        l2_batch_events=3,
        l3_batch_events=2,
    )
    client = FakeProcessorLLMClient()

    processed = run_once(config, client=client)

    assert processed == 4
    assert not record.exists()

    timeline_path = out_dir / "timeline" / "2026-03-19.jsonl"
    super_event_path = out_dir / "l2" / "2026-03-19" / "super_screen_event_single.json"
    note_path = out_dir / "notes" / "inbox" / "2026-03-19" / "note_super_screen_event_single.md"

    assert timeline_path.exists()
    assert super_event_path.exists()
    assert note_path.exists()

    timeline_lines = [json.loads(line) for line in timeline_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(timeline_lines) == 1
    assert timeline_lines[0]["source_event_ids"] == ["screen_event_single"]


def test_processor_levels_progress_across_runs_without_reprocessing_old_super_events(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    vault_dir = tmp_path / "vault"
    out_dir = tmp_path / "processed"
    monkeypatch.setenv("COLLECTOR_VAULT_DIR", str(vault_dir))

    write_raw_record(
        vault_dir,
        date="2026-03-19",
        timestamp_iso="2026-03-19T10:00:00+00:00",
        event_id="screen_event_a",
        raw_text="raw OCR text A",
    )
    write_raw_record(
        vault_dir,
        date="2026-03-19",
        timestamp_iso="2026-03-19T10:01:00+00:00",
        event_id="screen_event_b",
        raw_text="raw OCR text B",
    )
    write_raw_record(
        vault_dir,
        date="2026-03-19",
        timestamp_iso="2026-03-19T10:02:00+00:00",
        event_id="screen_event_c",
        raw_text="raw OCR text C",
    )

    config = ProcessorConfig(
        vault_dir=vault_dir,
        out_dir=out_dir,
        state_dir=out_dir / "state",
        write_notes=True,
        dry_run=False,
        l1_batch_events=2,
        l2_batch_events=2,
        l3_batch_events=1,
    )
    client = FakeProcessorLLMClient()

    first_pass = run_once(config, client=client)
    second_pass = run_once(config, client=client)

    assert first_pass == 5
    assert second_pass == 4

    note_dir = out_dir / "notes" / "inbox" / "2026-03-19"
    notes = sorted(path.name for path in note_dir.glob("*.md"))
    assert notes == ["note_super_focus_block.md", "note_super_screen_event_c.md"]

    state_l3 = load_json(out_dir / "state" / "state_l3.json")
    assert state_l3["last_l2_event_id"] == "super_screen_event_c"


def test_processor_supports_generic_llm_pipeline_with_free_payload(
    tmp_path: Path,
) -> None:
    vault_dir = tmp_path / "vault"
    out_dir = tmp_path / "processed"
    write_raw_record(
        vault_dir,
        date="2026-03-19",
        timestamp_iso="2026-03-19T09:00:00+00:00",
        event_id="screen_event_generic",
        raw_text="generic payload text",
    )

    class GenericClient:
        def complete_json(self, prompt_key: str, payload: dict[str, object]) -> dict[str, object]:
            assert prompt_key == "generic_prompt"
            return {
                "items": [
                    {
                        "id": "generic_item",
                        "date": "2026-03-19",
                        "timestamp": "2026-03-19T09:00:00+00:00",
                        "title": "Custom title",
                        "description": "Custom description",
                    }
                ]
            }

    config = ProcessorConfig(
        vault_dir=vault_dir,
        out_dir=out_dir,
        state_dir=out_dir / "state",
        pipeline=PipelineDefinition(
            execution_mode="single_loop",
            collections={
                "vault": CollectionDefinition(name="vault", base_dir="vault", path="."),
                "custom": CollectionDefinition(name="custom", path="custom"),
            },
            stages=[
                StageDefinition(
                    name="generic_stage",
                    type="llm_map",
                    input_collection="vault",
                    outputs=[{"name": "items", "collection": "custom"}],
                    prompt_key="generic_prompt",
                    batch_size=1,
                    flush_threshold=1,
                    transform_adapter="llm_map",
                    transform_options={
                        "input_mode": "raw",
                        "input_key": "records",
                        "result_key": "items",
                        "kind": "custom_summary",
                        "id_field": "id",
                        "date_field": "date",
                        "timestamp_field": "timestamp",
                    },
                )
            ],
        ),
    )

    processed = run_once(config, client=GenericClient())

    assert processed == 1
    artifact = load_json(out_dir / "custom" / "2026-03-19" / "generic_item.json")
    assert artifact["kind"] == "custom_summary"
    assert artifact["payload"]["title"] == "Custom title"
