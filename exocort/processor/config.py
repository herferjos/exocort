"""Load processor configuration from the shared app config."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from exocort.app_config import get_value, load_root_config

from .models import CollectionDefinition, PipelineDefinition, ProcessorConfig, StageDefinition


@dataclass
class LLMConfig:
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)


@dataclass
class AppConfig:
    prompts: dict[str, str]
    llm: LLMConfig


def _processor_data(data: dict[str, Any]) -> dict[str, Any]:
    processor_data = data.get("processor")
    return processor_data if isinstance(processor_data, dict) else {}


def _collect_prompts(processor_data: dict[str, Any]) -> dict[str, str]:
    prompts = processor_data.get("prompts")
    out: dict[str, str] = {}
    if isinstance(prompts, dict):
        out.update({str(key): str(value) for key, value in prompts.items() if str(value).strip()})

    legacy_prompts = {
        "l1_event": processor_data.get("l1_event", "") or processor_data.get("l1_clean", ""),
        "l2_timeline": processor_data.get("l2_timeline", "") or processor_data.get("l2_group", ""),
        "l3_notes": processor_data.get("l3_notes", "") or processor_data.get("l3_profile", "") or processor_data.get("l3_user_model", ""),
        "l4_reserved": processor_data.get("l4_reserved", ""),
    }
    out.update({key: str(value) for key, value in legacy_prompts.items() if str(value).strip()})

    stages = processor_data.get("stages")
    if isinstance(stages, list):
        for raw_stage in stages:
            if not isinstance(raw_stage, dict):
                continue
            prompt_key = str(raw_stage.get("prompt_key") or raw_stage.get("name") or "").strip()
            prompt = str(raw_stage.get("prompt") or "").strip()
            if prompt_key and prompt:
                out[prompt_key] = prompt
    return out


def load_app_config(path: Path | None = None) -> AppConfig:
    if path is None:
        from exocort import settings

        path = settings.collector_config_path()

    if not path.exists():
        raise FileNotFoundError(f"Config file not found at {path}")

    data = load_root_config(path)
    processor_data = _processor_data(data)
    prompts = _collect_prompts(processor_data)

    llm_data = processor_data.get(
        "llm",
        get_value(data, "services", "processor", default={}) or get_value(data, "services", "llm", default={}),
    )
    if not isinstance(llm_data, dict):
        llm_data = {}

    headers = {str(k): str(v) for k, v in llm_data.get("headers", {}).items()}
    llm = LLMConfig(
        url=str(llm_data.get("url", "")),
        headers=headers,
        body=llm_data.get("body", {}),
    )

    return AppConfig(prompts=prompts, llm=llm)


def _parse_collections(processor_data: dict[str, Any]) -> dict[str, CollectionDefinition]:
    raw_collections = processor_data.get("collections")
    collections: dict[str, CollectionDefinition] = {}
    if isinstance(raw_collections, dict):
        for name, raw_value in raw_collections.items():
            if isinstance(raw_value, dict):
                collections[str(name)] = CollectionDefinition(name=str(name), **raw_value)
            else:
                collections[str(name)] = CollectionDefinition(name=str(name), path=str(raw_value))
    return collections


def _parse_stage(raw_stage: dict[str, Any]) -> StageDefinition:
    outputs = raw_stage.get("outputs")
    if not isinstance(outputs, list):
        outputs = []
    kwargs = dict(raw_stage)
    kwargs["outputs"] = outputs
    return StageDefinition(**kwargs)


def load_processor_config(path: Path | None = None) -> ProcessorConfig:
    if path is None:
        from exocort import settings

        path = settings.collector_config_path()

    data = load_root_config(path)
    processor_data = _processor_data(data)

    raw_stages = processor_data.get("stages")
    stages = [_parse_stage(item) for item in raw_stages if isinstance(item, dict)] if isinstance(raw_stages, list) else []
    pipeline = PipelineDefinition(
        execution_mode=str(processor_data.get("execution_mode") or "per_stage_worker"),
        collections=_parse_collections(processor_data),
        stages=stages,
    )

    state_dir_raw = processor_data.get("state_dir")
    out_dir_raw = processor_data.get("out_dir")
    vault_dir_raw = processor_data.get("vault_dir")

    from exocort import settings

    return ProcessorConfig(
        vault_dir=settings._path("processor", "vault_dir", default=settings.processor_vault_dir()) if vault_dir_raw is not None else settings.processor_vault_dir(),
        out_dir=settings._path("processor", "out_dir", default=settings.processor_out_dir()) if out_dir_raw is not None else settings.processor_out_dir(),
        state_dir=settings._path("processor", "state_dir", default=settings.processor_state_dir()) if state_dir_raw is not None else settings.processor_state_dir(),
        poll_interval_seconds=float(processor_data.get("poll_interval_seconds", settings.processor_poll_interval_seconds())),
        max_concurrent_tasks=int(processor_data.get("max_concurrent_tasks", settings.processor_max_concurrent_tasks())),
        write_notes=bool(processor_data.get("write_notes", True)),
        dry_run=bool(processor_data.get("dry_run", False)),
        execution_mode=str(processor_data.get("execution_mode") or "per_stage_worker"),
        pipeline=pipeline,
        stages=stages,
        collections=pipeline.collections,
        l1_batch_events=processor_data.get("l1_trigger_threshold"),
        l2_batch_events=processor_data.get("l2_trigger_threshold"),
        l3_batch_events=processor_data.get("l3_trigger_threshold"),
    )
