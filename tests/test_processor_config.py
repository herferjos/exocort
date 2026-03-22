"""Unit tests for processor config loading from shared TOML."""

from __future__ import annotations

from pathlib import Path

import pytest

from exocort.processor.config import load_app_config, load_processor_config
from exocort.processor.engine import build_worker_specs, validate_pipeline
from exocort.processor.models import CollectionDefinition, PipelineDefinition, ProcessorConfig, StageDefinition


pytestmark = pytest.mark.unit


def test_load_app_config_from_toml(tmp_path: Path) -> None:
    path = tmp_path / "exocort.toml"
    path.write_text(
        """
[processor.prompts]
l1_event = "Clean event prompt"

[[processor.stages]]
name = "summaries"
enabled = true
type = "llm_reduce"
input_collection = "events"
prompt_key = "summary_prompt"
prompt = "Summarize the events"

[services.processor]
url = "http://localhost:9100/v1/chat/completions"
headers = { Authorization = "Bearer test-key" }
body = { model = "gpt-4o-mini" }
""",
        encoding="utf-8",
    )

    config = load_app_config(path)

    assert config.prompts["l1_event"] == "Clean event prompt"
    assert config.prompts["summary_prompt"] == "Summarize the events"
    assert config.llm.url == "http://localhost:9100/v1/chat/completions"
    assert config.llm.headers == {"Authorization": "Bearer test-key"}
    assert config.llm.body == {"model": "gpt-4o-mini"}


def test_load_processor_config_from_toml(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "exocort.toml"
    path.write_text(
        """
[processor]
vault_dir = "vault"
out_dir = "processed"
state_dir = "state"
execution_mode = "single_loop"
poll_interval_seconds = 3
max_concurrent_tasks = 2

[processor.collections.vault]
base_dir = "vault"
path = "."

[processor.collections.events]
path = "events"

[[processor.stages]]
name = "l1"
enabled = true
type = "llm_map"
input_collection = "vault"
state_key = "raw_to_events"
prompt_key = "l1_event"
batch_size = 4
flush_threshold = 2
transform_adapter = "llm_map"
outputs = [{ name = "events", collection = "events" }]
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("EXOCORT_CONFIG", str(path))

    config = load_processor_config(path)

    assert config.execution_mode == "single_loop"
    assert config.max_concurrent_tasks == 2
    assert config.collections["events"].path == "events"
    assert config.stages[0].name == "l1"
    assert config.stages[0].state_key == "raw_to_events"
    assert config.stages[0].batch_size == 4


def test_validate_pipeline_rejects_invalid_configs(tmp_path: Path) -> None:
    config = ProcessorConfig(
        vault_dir=tmp_path / "vault",
        out_dir=tmp_path / "out",
        state_dir=tmp_path / "state",
        pipeline=PipelineDefinition(
            execution_mode="bogus",  # type: ignore[arg-type]
            collections={"vault": CollectionDefinition(name="vault", base_dir="vault", path=".")},
            stages=[],
        ),
    )

    with pytest.raises(ValueError, match="Unsupported processor execution mode"):
        validate_pipeline(config)


def test_validate_pipeline_rejects_duplicate_stage_names(tmp_path: Path) -> None:
    config = ProcessorConfig(
        vault_dir=tmp_path / "vault",
        out_dir=tmp_path / "out",
        state_dir=tmp_path / "state",
        pipeline=PipelineDefinition(
            execution_mode="per_stage_worker",
            collections={
                "vault": CollectionDefinition(name="vault", base_dir="vault", path="."),
                "events": CollectionDefinition(name="events", path="events"),
            },
            stages=[
                StageDefinition(name="dup", type="llm_map", input_collection="vault", outputs=[{"name": "events", "collection": "events"}]),
                StageDefinition(name="dup", type="llm_map", input_collection="vault", outputs=[{"name": "events", "collection": "events"}]),
            ],
        ),
    )

    with pytest.raises(ValueError, match="Duplicate processor stage name"):
        validate_pipeline(config)


def test_build_worker_specs_respects_execution_mode(tmp_path: Path) -> None:
    config = ProcessorConfig(
        vault_dir=tmp_path / "vault",
        out_dir=tmp_path / "out",
        state_dir=tmp_path / "state",
        pipeline=PipelineDefinition(
            execution_mode="single_loop",
            collections={
                "vault": CollectionDefinition(name="vault", base_dir="vault", path="."),
                "events": CollectionDefinition(name="events", path="events"),
            },
            stages=[
                StageDefinition(name="l1", type="llm_map", input_collection="vault", outputs=[{"name": "events", "collection": "events"}]),
            ],
        ),
    )

    specs = build_worker_specs(config)

    assert specs == [{"mode": "single_loop", "name": "processor-single-loop"}]
