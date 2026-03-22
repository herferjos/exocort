"""Shared processor dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


ExecutionMode = Literal["per_stage_worker", "single_loop"]
StageType = Literal["llm_map", "llm_reduce", "deterministic_map", "deterministic_reduce", "noop"]
ProjectionType = Literal["none", "jsonl_day", "markdown_note"]


@dataclass
class CollectionDefinition:
    name: str
    path: str
    base_dir: str = "out"
    format: str = "json"


@dataclass
class OutputDefinition:
    name: str
    collection: str
    projection: ProjectionType = "none"


@dataclass
class StageDefinition:
    name: str
    type: StageType
    input_collection: str
    outputs: list[OutputDefinition]
    enabled: bool = True
    state_key: str | None = None
    prompt_key: str | None = None
    prompt: str | None = None
    batch_size: int = 1
    flush_threshold: int = 1
    flush_when_upstream_empty: bool = True
    upstream_collections: list[str] = field(default_factory=list)
    archive_collection: str | None = None
    transform_adapter: str = ""
    transform_options: dict[str, Any] = field(default_factory=dict)
    concurrency: int = 1

    def __post_init__(self) -> None:
        self.state_key = self.state_key or self.name
        self.batch_size = max(1, int(self.batch_size or 1))
        self.flush_threshold = max(1, int(self.flush_threshold or self.batch_size))
        self.concurrency = max(1, int(self.concurrency or 1))
        self.upstream_collections = [str(value).strip() for value in self.upstream_collections if str(value).strip()]
        self.outputs = [
            item if isinstance(item, OutputDefinition) else OutputDefinition(**item)
            for item in self.outputs
        ]


@dataclass
class PipelineDefinition:
    execution_mode: ExecutionMode = "per_stage_worker"
    collections: dict[str, CollectionDefinition] = field(default_factory=dict)
    stages: list[StageDefinition] = field(default_factory=list)

    def __post_init__(self) -> None:
        collections: dict[str, CollectionDefinition] = {}
        for name, value in self.collections.items():
            if isinstance(value, CollectionDefinition):
                collection = value
            elif isinstance(value, dict):
                collection = CollectionDefinition(name=name, **value)
            else:
                collection = CollectionDefinition(name=name, path=str(value))
            collections[name] = collection
        self.collections = collections
        self.stages = [
            item if isinstance(item, StageDefinition) else StageDefinition(**item)
            for item in self.stages
        ]


@dataclass
class ArtifactEnvelope:
    kind: str
    stage: str
    item_id: str
    date: str
    payload: dict[str, Any]
    timestamp: str = ""
    source_ids: list[str] = field(default_factory=list)
    source_paths: list[str] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "stage": self.stage,
            "item_id": self.item_id,
            "timestamp": self.timestamp,
            "date": self.date,
            "source_ids": list(self.source_ids),
            "source_paths": list(self.source_paths),
            "trace": dict(self.trace),
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtifactEnvelope":
        payload = data.get("payload")
        if not isinstance(payload, dict):
            payload = {
                key: value
                for key, value in data.items()
                if key not in {"kind", "stage", "item_id", "timestamp", "date", "source_ids", "source_paths", "trace"}
            }
        source_ids = data.get("source_ids")
        source_paths = data.get("source_paths")
        trace = data.get("trace")
        return cls(
            kind=str(data.get("kind") or "artifact"),
            stage=str(data.get("stage") or ""),
            item_id=str(data.get("item_id") or data.get("event_id") or data.get("note_id") or "item"),
            timestamp=str(data.get("timestamp") or data.get("timestamp_start") or ""),
            date=str(data.get("date") or ""),
            source_ids=[str(value).strip() for value in source_ids if str(value).strip()] if isinstance(source_ids, list) else [],
            source_paths=[str(value).strip() for value in source_paths if str(value).strip()] if isinstance(source_paths, list) else [],
            trace=trace if isinstance(trace, dict) else {},
            payload=payload,
        )


@dataclass
class ProcessorState:
    cursor_path: str | None = None
    cursor_id: str | None = None
    last_output_path: str | None = None
    last_output_id: str | None = None
    last_run_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cursor_path": self.cursor_path,
            "cursor_id": self.cursor_id,
            "last_output_path": self.last_output_path,
            "last_output_id": self.last_output_id,
            "last_run_at": self.last_run_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProcessorState":
        metadata = data.get("metadata")
        state = cls(
            cursor_path=data.get("cursor_path") or data.get("last_path") or data.get("last_raw_path") or data.get("last_l1_path") or data.get("last_l2_path"),
            cursor_id=data.get("cursor_id") or data.get("last_event_id") or data.get("last_raw_event_id") or data.get("last_l2_event_id"),
            last_output_path=data.get("last_output_path") or data.get("last_note_path"),
            last_output_id=data.get("last_output_id") or data.get("last_note_id"),
            last_run_at=data.get("last_run_at") or data.get("updated_at"),
            metadata=metadata if isinstance(metadata, dict) else {},
        )
        # Backward-compatible mirrors for existing state readers.
        if state.cursor_id and "last_l2_event_id" not in state.metadata:
            state.metadata["last_l2_event_id"] = state.cursor_id
        return state


@dataclass
class ProcessorConfig:
    vault_dir: Path
    out_dir: Path
    state_dir: Path | None = None
    pipeline: PipelineDefinition | None = None
    poll_interval_s: float | None = None
    poll_interval_seconds: float | None = None
    max_concurrent_tasks: int = 1
    write_notes: bool = True
    dry_run: bool = False
    batch_size: int = 100
    execution_mode: ExecutionMode = "per_stage_worker"
    stages: list[StageDefinition] = field(default_factory=list)
    collections: dict[str, CollectionDefinition] = field(default_factory=dict)
    l1_batch_events: int | None = None
    l2_batch_events: int | None = None
    l3_batch_events: int | None = None
    l1_trigger_threshold: int | None = None
    l2_trigger_threshold: int | None = None
    l3_trigger_threshold: int | None = None
    l4_enabled: bool = False
    l4_interval_h: float = 24.0
    l4_interval_hours: float | None = None

    def __post_init__(self) -> None:
        self.vault_dir = Path(self.vault_dir)
        self.out_dir = Path(self.out_dir)
        self.state_dir = Path(self.state_dir) if self.state_dir is not None else self.out_dir / "state"
        self.poll_interval_s = float(
            self.poll_interval_s
            if self.poll_interval_s is not None
            else self.poll_interval_seconds
            if self.poll_interval_seconds is not None
            else 10.0
        )
        self.max_concurrent_tasks = max(1, int(self.max_concurrent_tasks or 1))
        self.l4_interval_h = float(self.l4_interval_h if self.l4_interval_h else self.l4_interval_hours or 24.0)
        explicit_pipeline = self.pipeline is not None or bool(self.stages) or bool(self.collections)
        if self.pipeline is None:
            self.pipeline = PipelineDefinition(
                execution_mode=self.execution_mode,
                collections=self.collections,
                stages=self.stages,
            )
        if not explicit_pipeline:
            self.pipeline = build_default_pipeline(self)
        self.execution_mode = self.pipeline.execution_mode
        self.collections = self.pipeline.collections
        self.stages = [stage for stage in self.pipeline.stages if stage.enabled]


def build_default_pipeline(config: ProcessorConfig) -> PipelineDefinition:
    l1_batch = max(1, int(config.l1_batch_events or config.l1_trigger_threshold or config.batch_size or 1))
    l2_batch = max(1, int(config.l2_batch_events or config.l2_trigger_threshold or config.batch_size or 1))
    l3_batch = max(1, int(config.l3_batch_events or config.l3_trigger_threshold or config.batch_size or 1))
    collections = {
        "vault": CollectionDefinition(name="vault", base_dir="vault", path="."),
        "l1": CollectionDefinition(name="l1", path="l1"),
        "l0_processed_raw": CollectionDefinition(name="l0_processed_raw", path="l0_processed_raw"),
        "timeline_events": CollectionDefinition(name="timeline_events", path="timeline_events"),
        "timeline": CollectionDefinition(name="timeline", path="timeline"),
        "l2": CollectionDefinition(name="l2", path="l2"),
        "l1_processed": CollectionDefinition(name="l1_processed", path="l1_processed"),
        "notes": CollectionDefinition(name="notes", path="notes"),
        "note_docs": CollectionDefinition(name="note_docs", path="notes/inbox", format="markdown"),
    }
    stages = [
        StageDefinition(
            name="l1",
            type="llm_map",
            input_collection="vault",
            outputs=[OutputDefinition(name="events", collection="l1")],
            archive_collection="l0_processed_raw",
            batch_size=l1_batch,
            flush_threshold=l1_batch,
            transform_adapter="legacy_l1",
            prompt_key="l1_event",
        ),
        StageDefinition(
            name="l2",
            type="llm_reduce",
            input_collection="l1",
            outputs=[
                OutputDefinition(name="timeline_events", collection="timeline_events", projection="jsonl_day"),
                OutputDefinition(name="super_events", collection="l2"),
            ],
            archive_collection="l1_processed",
            upstream_collections=["vault"],
            batch_size=l2_batch,
            flush_threshold=l2_batch,
            transform_adapter="legacy_l2",
            prompt_key="l2_timeline",
        ),
        StageDefinition(
            name="l3",
            type="llm_reduce",
            input_collection="l2",
            outputs=[
                OutputDefinition(name="notes", collection="notes"),
                OutputDefinition(name="note_docs", collection="note_docs", projection="markdown_note"),
            ],
            upstream_collections=["l1"],
            batch_size=l3_batch,
            flush_threshold=l3_batch,
            transform_adapter="legacy_l3",
            prompt_key="l3_notes",
            enabled=config.write_notes,
        ),
    ]
    return PipelineDefinition(execution_mode=config.execution_mode, collections=collections, stages=stages)
