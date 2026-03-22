"""Stage adapters for the declarative processor runtime."""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import uuid

from .models import ArtifactEnvelope, OutputDefinition, ProcessorConfig, StageDefinition
from .utils import date_from_timestamp, extract_record_text, normalize_list, safe_id, utc_iso

logger = logging.getLogger(__name__)


@dataclass
class InputItem:
    path: Path
    raw: dict[str, Any]
    envelope: ArtifactEnvelope | None = None


def _require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _require_str(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    out = value.strip()
    if not out:
        raise ValueError(f"{label} must not be empty")
    return out


def _input_payload(item: InputItem, mode: str) -> Any:
    if mode == "raw":
        return item.raw
    if mode == "payload":
        if item.envelope is None:
            raise ValueError("payload input_mode requires artifact inputs")
        return item.envelope.to_dict()
    if mode == "envelope":
        if item.envelope is None:
            raise ValueError("envelope input_mode requires artifact inputs")
        return item.envelope.to_dict()
    raise ValueError(f"Unsupported input_mode {mode!r}")


def _lookup_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
            continue
        if isinstance(current, list):
            try:
                index = int(part)
            except ValueError:
                return None
            if index < 0 or index >= len(current):
                return None
            current = current[index]
            continue
        return None
    return current


def _assign_path(target: dict[str, Any], path: str, value: Any) -> None:
    current = target
    parts = path.split(".")
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value


def _project_input_value(item: InputItem, mode: str, options: dict[str, Any], label: str) -> Any:
    value = _input_payload(item, mode)
    projection = options.get("input_projection")
    if projection is None:
        return value
    if isinstance(projection, str):
        projection = projection.strip()
    if not projection or projection == "none":
        return value
    if projection == "record_text":
        record = _require_dict(value, f"{label}.input")
        return extract_record_text(record)
    if projection == "field":
        field_path = _require_str(options.get("input_field"), f"{label}.transform_options.input_field")
        return copy.deepcopy(_lookup_path(value, field_path))
    if isinstance(projection, dict):
        projected: dict[str, Any] = {}
        for target_key, source_path in projection.items():
            source_expr = _require_str(source_path, f"{label}.input_projection[{target_key}]")
            if source_expr == "record_text":
                record = _require_dict(value, f"{label}.input")
                projected[str(target_key)] = extract_record_text(record)
                continue
            projected[str(target_key)] = copy.deepcopy(_lookup_path(value, source_expr))
        return projected
    raise ValueError(f"Unsupported input_projection {projection!r} for stage {label}")


def _mapping_source(item: InputItem, mode: str) -> Any:
    return _input_payload(item, mode)


def _matched_batch_items(
    row: dict[str, Any],
    batch_source: list[Any],
    ids_path: str,
    match_id_path: str,
) -> list[Any]:
    wanted_ids = [str(value).strip() for value in normalize_list(_lookup_path(row, ids_path)) if str(value).strip()]
    index: dict[str, Any] = {}
    for candidate in batch_source:
        if not isinstance(candidate, dict):
            continue
        candidate_id = _lookup_path(candidate, match_id_path)
        candidate_key = str(candidate_id).strip() if candidate_id is not None else ""
        if candidate_key:
            index[candidate_key] = candidate
    matched: list[Any] = []
    for wanted_id in wanted_ids:
        candidate = index.get(wanted_id)
        if candidate is not None:
            matched.append(candidate)
    return matched


def _project_fields(value: Any, fields: Any, label: str) -> Any:
    if isinstance(fields, dict):
        projected: dict[str, Any] = {}
        for target_key, source_path in fields.items():
            projected[str(target_key)] = copy.deepcopy(_lookup_path(value, _require_str(source_path, f"{label}.{target_key}")))
        return projected
    if isinstance(fields, list):
        projected = {}
        for field in fields:
            field_name = _require_str(field, label)
            projected[field_name] = copy.deepcopy(_lookup_path(value, field_name))
        return projected
    return copy.deepcopy(value)


def _resolve_mapping_value(expression: Any, source: Any, row: dict[str, Any], batch_source: list[Any]) -> Any:
    if isinstance(expression, list):
        return [_resolve_mapping_value(item, source, row, batch_source) for item in expression]
    if not isinstance(expression, str):
        if not isinstance(expression, dict):
            return copy.deepcopy(expression)
        if "op" not in expression:
            return {
                str(key): _resolve_mapping_value(value, source, row, batch_source)
                for key, value in expression.items()
            }
        op = _require_str(expression.get("op"), "output_map.op")
        if op == "slug":
            from_mode = str(expression.get("from") or "row").strip()
            base = row if from_mode == "row" else source
            value = _lookup_path(base, _require_str(expression.get("path"), "output_map.path"))
            prefix = str(expression.get("prefix") or "")
            suffix = str(expression.get("suffix") or "")
            return f"{prefix}{safe_id(str(value) if value is not None else '')}{suffix}"
        if op == "uuid":
            prefix = str(expression.get("prefix") or "")
            suffix = str(expression.get("suffix") or "")
            return f"{prefix}{uuid.uuid4().hex}{suffix}"
        if op == "now":
            return utc_iso()
        if op == "match_items":
            ids_path = _require_str(expression.get("ids_from_row"), "output_map.ids_from_row")
            match_id_path = _require_str(expression.get("match_id_path"), "output_map.match_id_path")
            matches = _matched_batch_items(row, batch_source, ids_path, match_id_path)
            fields = expression.get("fields")
            return [_project_fields(item, fields, "output_map.fields") for item in matches]
        if op in {"min_path_from_matches", "max_path_from_matches"}:
            ids_path = _require_str(expression.get("ids_from_row"), "output_map.ids_from_row")
            match_id_path = _require_str(expression.get("match_id_path"), "output_map.match_id_path")
            value_path = _require_str(expression.get("value_path"), "output_map.value_path")
            matches = _matched_batch_items(row, batch_source, ids_path, match_id_path)
            values = [str(value).strip() for item in matches for value in [_lookup_path(item, value_path)] if str(value).strip()]
            if not values:
                return ""
            return min(values) if op == "min_path_from_matches" else max(values)
        if op == "date_from_path":
            from_mode = str(expression.get("from") or "row").strip()
            base = row if from_mode == "row" else source
            value = _lookup_path(base, _require_str(expression.get("path"), "output_map.path"))
            return date_from_timestamp(str(value) if value is not None else None)
        raise ValueError(f"Unsupported output_map op {op!r}")
    if expression == "input":
        return copy.deepcopy(source)
    if expression.startswith("input:"):
        return copy.deepcopy(_lookup_path(source, expression[len("input:") :]))
    if expression.startswith("date_from:input:"):
        value = _lookup_path(source, expression[len("date_from:input:") :])
        return date_from_timestamp(str(value) if value is not None else None)
    if expression.startswith("literal:"):
        return expression[len("literal:") :]
    return expression


def _apply_output_map(row: dict[str, Any], item: InputItem, items: list[InputItem], stage: StageDefinition) -> dict[str, Any]:
    output_map = stage.transform_options.get("output_map")
    if not isinstance(output_map, dict) or not output_map:
        return row
    source_mode = str(stage.transform_options.get("output_map_source") or "raw").strip()
    source = _mapping_source(item, source_mode)
    batch_source = [_mapping_source(candidate, source_mode) for candidate in items]
    mapped = copy.deepcopy(row)
    for target_path, expression in output_map.items():
        _assign_path(mapped, str(target_path), _resolve_mapping_value(expression, source, mapped, batch_source))
    return mapped


def _result_rows(result: dict[str, Any], result_key: str, label: str) -> list[dict[str, Any]]:
    values = result.get(result_key)
    if not isinstance(values, list):
        raise ValueError(f"{label} expected response key {result_key!r} to be a list")
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(values):
        rows.append(_require_dict(item, f"{label}.{result_key}[{index}]"))
    return rows


def _build_envelope(
    *,
    stage: StageDefinition,
    output: OutputDefinition,
    row: dict[str, Any],
    index: int,
) -> ArtifactEnvelope:
    artifact_id = safe_id(_require_str(row.get(output.id_field), f"{stage.name}.{output.name}[{index}].{output.id_field}"))
    timestamp = _require_str(
        row.get(output.timestamp_field),
        f"{stage.name}.{output.name}[{index}].{output.timestamp_field}",
    )
    data = copy.deepcopy(row)
    data["id"] = artifact_id
    data["timestamp"] = timestamp
    source_ids = normalize_list(data.get("source_ids"))
    source_ids = [str(value).strip() for value in source_ids if str(value).strip()]
    if not source_ids:
        raise ValueError(f"{stage.name}.{output.name}[{index}] is missing source_ids")
    data["source_ids"] = list(source_ids)
    return ArtifactEnvelope(
        id=artifact_id,
        timestamp=timestamp,
        source_ids=source_ids,
        data=data,
    )


def _execute_llm(
    stage: StageDefinition,
    items: list[InputItem],
    client: Any,
    *,
    expect_per_input: bool,
) -> dict[str, list[ArtifactEnvelope]]:
    if stage.prompt is None:
        raise ValueError(f"Stage {stage.name} requires prompt")
    options = stage.transform_options
    input_mode = _require_str(options.get("input_mode"), f"{stage.name}.transform_options.input_mode")
    input_key = _require_str(options.get("input_key"), f"{stage.name}.transform_options.input_key")
    expect_per_input_option = options.get("expect_per_input")
    if expect_per_input_option is not None:
        if not isinstance(expect_per_input_option, bool):
            raise ValueError(f"{stage.name}.transform_options.expect_per_input must be a boolean")
        expect_per_input = expect_per_input_option
    payload = {input_key: [_project_input_value(item, input_mode, options, stage.name) for item in items]}
    logger.debug(
        "Executing LLM adapter: stage=%s mode=%s input_key=%s items=%s per_input=%s",
        stage.name,
        stage.transform_adapter,
        input_key,
        len(items),
        expect_per_input,
    )
    result = _require_dict(client.complete_json(stage.name, stage.prompt, payload), f"{stage.name}.response")
    logger.info("%s LLM response received: keys=%s", stage.name, sorted(result.keys()))

    outputs: dict[str, list[ArtifactEnvelope]] = {}
    for output in stage.outputs:
        rows = _result_rows(result, output.result_key, stage.name)
        if expect_per_input and len(rows) != len(items):
            raise ValueError(f"Stage {stage.name} expected one row in {output.result_key!r} per input item")
        envelopes: list[ArtifactEnvelope] = []
        for index, row in enumerate(rows):
            item = items[index] if expect_per_input else items[0]
            mapped_row = _apply_output_map(row, item, items, stage)
            envelopes.append(
                _build_envelope(
                    stage=stage,
                    output=output,
                    row=mapped_row,
                    index=index,
                )
            )
        outputs[output.name] = envelopes
    return outputs


def execute_generic_llm_map(
    stage: StageDefinition,
    items: list[InputItem],
    client: Any,
) -> dict[str, list[ArtifactEnvelope]]:
    return _execute_llm(stage, items, client, expect_per_input=True)


def execute_generic_llm_reduce(
    stage: StageDefinition,
    items: list[InputItem],
    client: Any,
) -> dict[str, list[ArtifactEnvelope]]:
    return _execute_llm(stage, items, client, expect_per_input=False)


def execute_stage_adapter(
    stage: StageDefinition,
    config: ProcessorConfig,
    items: list[InputItem],
    client: Any,
) -> dict[str, list[ArtifactEnvelope]]:
    del config
    adapter = stage.transform_adapter
    logger.debug("Dispatching stage adapter: stage=%s adapter=%s items=%s", stage.name, adapter, len(items))
    if adapter == "llm_map":
        return execute_generic_llm_map(stage, items, client)
    if adapter == "llm_reduce":
        return execute_generic_llm_reduce(stage, items, client)
    if adapter == "noop":
        logger.debug("No-op stage adapter: stage=%s", stage.name)
        return {output.name: [] for output in stage.outputs}
    raise ValueError(f"Unsupported stage adapter {adapter!r} for stage {stage.name}")
