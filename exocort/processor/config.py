"""Load processor configuration from the shared app config."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any

from exocort.app_config import config_path, load_root_config

from .models import CollectionDefinition, PipelineDefinition, ProcessorConfig, StageDefinition

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)


@dataclass
class AppConfig:
    llm: LLMConfig


def _require_table(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Missing required table [{key}]")
    return value


def _require_subtable(data: dict[str, Any], *path: str) -> dict[str, Any]:
    current: Any = data
    for part in path:
        if not isinstance(current, dict) or part not in current:
            dotted = ".".join(path)
            raise ValueError(f"Missing required table [{dotted}]")
        current = current[part]
    if not isinstance(current, dict):
        dotted = ".".join(path)
        raise ValueError(f"Expected table at [{dotted}]")
    return current


def _require_value(data: dict[str, Any], *path: str) -> Any:
    current: Any = data
    for part in path:
        if not isinstance(current, dict) or part not in current:
            dotted = ".".join(path)
            raise ValueError(f"Missing required config value '{dotted}'")
        current = current[part]
    return current


def _as_str(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Config value '{label}' must be a string")
    out = value.strip()
    if not out:
        raise ValueError(f"Config value '{label}' must not be empty")
    return out


def _as_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"Config value '{label}' must be a boolean")
    return value


def _as_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Config value '{label}' must be an integer")
    return value


def _as_float(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Config value '{label}' must be numeric")
    return float(value)


def _as_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Config value '{label}' must be a table/object")
    return value


def _as_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"Config value '{label}' must be a list")
    return value


def _resolve_path(raw: Any, label: str, root: Path) -> Path:
    value = _as_str(raw, label)
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _load_data(path: Path | None) -> tuple[Path, dict[str, Any]]:
    resolved = (path or config_path()).resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Config file not found at {resolved}")
    logger.debug("Loading config file: %s", resolved)
    return resolved, load_root_config(resolved)


def _parse_collection(raw: Any, label: str) -> CollectionDefinition:
    block = _as_dict(raw, label)
    return CollectionDefinition(
        path=_as_str(_require_value(block, "path"), f"{label}.path"),
        base_dir=_as_str(_require_value(block, "base_dir"), f"{label}.base_dir"),  # type: ignore[arg-type]
        format=_as_str(_require_value(block, "format"), f"{label}.format"),
    )


def load_app_config(path: Path | None = None) -> AppConfig:
    config_path_resolved, data = _load_data(path)
    llm_data = _require_subtable(data, "services", "processor")
    headers_raw = _as_dict(_require_value(llm_data, "headers"), "services.processor.headers")
    body = _as_dict(_require_value(llm_data, "body"), "services.processor.body")
    llm = LLMConfig(
        url=_as_str(_require_value(llm_data, "url"), "services.processor.url"),
        headers={str(k): str(v) for k, v in headers_raw.items()},
        body=body,
    )
    logger.info(
        "Loaded processor app config: path=%s url=%s headers=%s body_keys=%s",
        config_path_resolved,
        llm.url,
        len(llm.headers),
        sorted(llm.body.keys()),
    )

    return AppConfig(llm=llm)


def _parse_stage(raw_stage: dict[str, Any], index: int) -> StageDefinition:
    label = f"processor.stages[{index}]"
    outputs_raw = _as_list(_require_value(raw_stage, "outputs"), f"{label}.outputs")
    outputs = [_as_dict(item, f"{label}.outputs[{output_index}]") for output_index, item in enumerate(outputs_raw)]
    upstream_raw = raw_stage.get("upstream", [])
    upstream_values = _as_list(upstream_raw, f"{label}.upstream")
    transform_options = _as_dict(_require_value(raw_stage, "transform_options"), f"{label}.transform_options")
    prompt = raw_stage.get("prompt")
    parsed_outputs: list[dict[str, Any]] = []
    for output_index, raw_output in enumerate(outputs):
        output_label = f"{label}.outputs[{output_index}]"
        projection_target = raw_output.get("projection_target")
        parsed_outputs.append(
            {
                "name": _as_str(_require_value(raw_output, "name"), f"{output_label}.name"),
                "collection": _parse_collection(_require_value(raw_output, "collection"), f"{output_label}.collection"),
                "projection": _as_str(_require_value(raw_output, "projection"), f"{output_label}.projection"),
                "result_key": _as_str(_require_value(raw_output, "result_key"), f"{output_label}.result_key"),
                "id_field": _as_str(_require_value(raw_output, "id_field"), f"{output_label}.id_field"),
                "timestamp_field": _as_str(_require_value(raw_output, "timestamp_field"), f"{output_label}.timestamp_field"),
                "projection_target": _parse_collection(projection_target, f"{output_label}.projection_target")
                if projection_target is not None
                else None,
            }
        )
    return StageDefinition(
        name=_as_str(_require_value(raw_stage, "name"), f"{label}.name"),
        type=_as_str(_require_value(raw_stage, "type"), f"{label}.type"),  # type: ignore[arg-type]
        input=_parse_collection(_require_value(raw_stage, "input"), f"{label}.input"),
        outputs=parsed_outputs,
        enabled=_as_bool(_require_value(raw_stage, "enabled"), f"{label}.enabled"),
        prompt=_as_str(prompt, f"{label}.prompt") if prompt is not None else None,
        batch_size=_as_int(_require_value(raw_stage, "batch_size"), f"{label}.batch_size"),
        flush_threshold=_as_int(_require_value(raw_stage, "flush_threshold"), f"{label}.flush_threshold"),
        flush_when_upstream_empty=_as_bool(
            _require_value(raw_stage, "flush_when_upstream_empty"),
            f"{label}.flush_when_upstream_empty",
        ),
        upstream=[_parse_collection(value, f"{label}.upstream[{upstream_index}]") for upstream_index, value in enumerate(upstream_values)],
        transform_adapter=_as_str(_require_value(raw_stage, "transform_adapter"), f"{label}.transform_adapter"),
        transform_options=transform_options,
        concurrency=_as_int(_require_value(raw_stage, "concurrency"), f"{label}.concurrency"),
    )


def load_processor_config(path: Path | None = None) -> ProcessorConfig:
    resolved_path, data = _load_data(path)
    processor_data = _require_table(data, "processor")

    raw_stages = _as_list(_require_value(processor_data, "stages"), "processor.stages")
    stages = [_parse_stage(_as_dict(item, f"processor.stages[{index}]"), index) for index, item in enumerate(raw_stages)]
    pipeline = PipelineDefinition(
        execution_mode=_as_str(_require_value(processor_data, "execution_mode"), "processor.execution_mode"),  # type: ignore[arg-type]
        stages=stages,
    )

    config_root = resolved_path.parent
    config = ProcessorConfig(
        vault_dir=_resolve_path(_require_value(processor_data, "vault_dir"), "processor.vault_dir", config_root),
        out_dir=_resolve_path(_require_value(processor_data, "out_dir"), "processor.out_dir", config_root),
        poll_interval_s=_as_float(_require_value(processor_data, "poll_interval_seconds"), "processor.poll_interval_seconds"),
        max_concurrent_tasks=_as_int(_require_value(processor_data, "max_concurrent_tasks"), "processor.max_concurrent_tasks"),
        dry_run=_as_bool(_require_value(processor_data, "dry_run"), "processor.dry_run"),
        pipeline=pipeline,
    )
    logger.info(
        "Loaded processor config: path=%s mode=%s stages=%s vault_dir=%s out_dir=%s dry_run=%s",
        resolved_path,
        config.execution_mode,
        len(config.stages),
        config.vault_dir,
        config.out_dir,
        config.dry_run,
    )
    return config
