"""Shared processor dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


ExecutionMode = Literal["per_stage_worker", "single_loop"]
StageType = Literal["llm_map", "llm_reduce", "noop"]
ProjectionType = Literal["none", "jsonl_day", "markdown_note"]
BaseDirType = Literal["vault", "out"]


@dataclass(frozen=True)
class CollectionDefinition:
    path: str
    base_dir: BaseDirType
    format: str


@dataclass
class OutputDefinition:
    name: str
    collection: CollectionDefinition
    projection: ProjectionType
    result_key: str
    id_field: str
    timestamp_field: str
    projection_target: CollectionDefinition | None = None

    def __post_init__(self) -> None:
        if isinstance(self.collection, dict):
            self.collection = CollectionDefinition(**self.collection)
        if isinstance(self.projection_target, dict):
            self.projection_target = CollectionDefinition(**self.projection_target)


@dataclass
class StageDefinition:
    name: str
    type: StageType
    input: CollectionDefinition
    outputs: list[OutputDefinition]
    enabled: bool
    prompt: str | None
    batch_size: int
    flush_threshold: int
    flush_when_upstream_empty: bool
    upstream: list[CollectionDefinition]
    transform_adapter: str
    transform_options: dict[str, Any]
    concurrency: int

    def __post_init__(self) -> None:
        if isinstance(self.input, dict):
            self.input = CollectionDefinition(**self.input)
        self.upstream = [
            item if isinstance(item, CollectionDefinition) else CollectionDefinition(**item)
            for item in self.upstream
        ]
        self.batch_size = int(self.batch_size)
        self.flush_threshold = int(self.flush_threshold)
        self.concurrency = int(self.concurrency)
        if self.batch_size < 1:
            raise ValueError(f"Stage {self.name} batch_size must be >= 1")
        if self.flush_threshold < 1:
            raise ValueError(f"Stage {self.name} flush_threshold must be >= 1")
        if self.concurrency < 1:
            raise ValueError(f"Stage {self.name} concurrency must be >= 1")
        self.outputs = [
            item if isinstance(item, OutputDefinition) else OutputDefinition(**item)
            for item in self.outputs
        ]
        self.prompt = str(self.prompt).strip() if self.prompt is not None else None


@dataclass
class PipelineDefinition:
    execution_mode: ExecutionMode
    stages: list[StageDefinition]

    def __post_init__(self) -> None:
        self.stages = [
            item if isinstance(item, StageDefinition) else StageDefinition(**item)
            for item in self.stages
        ]


@dataclass
class ArtifactEnvelope:
    id: str
    timestamp: str = ""
    source_ids: list[str] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        record = dict(self.data)
        record["id"] = self.id
        record["timestamp"] = self.timestamp
        record["source_ids"] = list(self.source_ids)
        return record

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtifactEnvelope":
        if not isinstance(data, dict):
            raise ValueError("Artifact must be a JSON object")
        record = dict(data)
        artifact_id = str(record.pop("id"))
        timestamp = str(record.pop("timestamp"))
        source_ids_raw = record.pop("source_ids")
        if not isinstance(source_ids_raw, list):
            raise ValueError("Artifact source_ids must be a list")
        source_ids = [str(value).strip() for value in source_ids_raw if str(value).strip()]
        return cls(
            id=artifact_id,
            timestamp=timestamp,
            source_ids=source_ids,
            data=record,
        )


@dataclass
class ProcessorState:
    cursor_path: str | None = None
    last_run_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cursor_path": self.cursor_path,
            "last_run_at": self.last_run_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProcessorState":
        return cls(
            cursor_path=str(data["cursor_path"]) if data.get("cursor_path") is not None else None,
            last_run_at=str(data["last_run_at"]) if data.get("last_run_at") is not None else None,
        )


@dataclass
class ProcessorConfig:
    vault_dir: Path
    out_dir: Path
    poll_interval_s: float
    max_concurrent_tasks: int
    dry_run: bool
    pipeline: PipelineDefinition

    def __post_init__(self) -> None:
        self.vault_dir = Path(self.vault_dir)
        self.out_dir = Path(self.out_dir)
        self.poll_interval_s = float(self.poll_interval_s)
        self.max_concurrent_tasks = int(self.max_concurrent_tasks)
        if self.poll_interval_s <= 0:
            raise ValueError("Processor poll_interval_s must be > 0")
        if self.max_concurrent_tasks < 1:
            raise ValueError("Processor max_concurrent_tasks must be >= 1")

    @property
    def execution_mode(self) -> ExecutionMode:
        return self.pipeline.execution_mode

    @property
    def stages(self) -> list[StageDefinition]:
        return [stage for stage in self.pipeline.stages if stage.enabled]
