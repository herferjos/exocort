"""Configurable orchestration layer for the processor pipeline."""

from __future__ import annotations

import logging
import multiprocessing
import time
from pathlib import Path

from exocort import settings

from .adapters import InputItem, execute_stage_adapter
from .artifacts import render_markdown
from .config import AppConfig, load_app_config
from .llm import ProcessorLLMClient, SemaphoreLLMClient, SupportsLLMClient
from .models import ArtifactEnvelope, CollectionDefinition, OutputDefinition, ProcessorConfig, StageDefinition
from .storage import (
    list_collection_paths,
    load_artifact,
    load_state,
    resolve_collection_dir,
    rewrite_jsonl_day,
    save_state,
)
from .utils import atomic_write_json, atomic_write_text, canonical_path, load_json, pending_paths

logger = logging.getLogger(__name__)


def validate_pipeline(config: ProcessorConfig) -> None:
    execution_mode = config.execution_mode
    if execution_mode not in {"per_stage_worker", "single_loop"}:
        raise ValueError(f"Unsupported processor execution mode: {execution_mode!r}")
    if not config.stages:
        raise ValueError("Processor pipeline must define at least one enabled stage")

    seen_names: set[str] = set()
    for stage in config.stages:
        if stage.name in seen_names:
            raise ValueError(f"Duplicate processor stage name: {stage.name}")
        seen_names.add(stage.name)
        if not stage.outputs:
            raise ValueError(f"Stage {stage.name} must define at least one output")
        if stage.transform_adapter != stage.type and stage.transform_adapter != "noop":
            raise ValueError(
                f"Stage {stage.name} transform_adapter must match type or be 'noop'; got {stage.transform_adapter!r}"
            )
        if stage.type.startswith("llm_") and not stage.prompt:
            raise ValueError(f"Stage {stage.name} requires prompt")
        for output in stage.outputs:
            if output.projection == "jsonl_day" and output.projection_target is None:
                raise ValueError(f"Stage {stage.name} output {output.name} requires projection_target for jsonl_day")
            if output.projection != "jsonl_day" and output.projection_target is not None:
                raise ValueError(f"Stage {stage.name} output {output.name} projection_target is only valid for jsonl_day")


def run_once(
    config: ProcessorConfig,
    client: SupportsLLMClient | None = None,
    app_config: AppConfig | None = None,
) -> int:
    config.out_dir.mkdir(parents=True, exist_ok=True)
    validate_pipeline(config)
    for stage in config.stages:
        for output in stage.outputs:
            resolve_collection_dir(config, output.collection).mkdir(parents=True, exist_ok=True)
        resolve_collection_dir(config, stage.input).mkdir(parents=True, exist_ok=True)

    effective_client = client
    if effective_client is None:
        effective_app_config = app_config or load_app_config()
        effective_client = ProcessorLLMClient(effective_app_config.llm)

    processed = 0
    logger.info(
        "Processor run started: mode=%s stages=%s dry_run=%s",
        config.execution_mode,
        len(config.stages),
        config.dry_run,
    )
    for stage in config.stages:
        processed += run_stage_once(config, stage, effective_client)
    logger.info("Processor run finished: processed=%s", processed)
    return processed


def _collection_paths(config: ProcessorConfig, collection: CollectionDefinition) -> list[Path]:
    return list_collection_paths(config, collection)


def _upstream_pending(config: ProcessorConfig, stage: StageDefinition) -> bool:
    return any(bool(_collection_paths(config, collection)) for collection in stage.upstream)


def _should_flush(pending_count: int, stage: StageDefinition, upstream_pending: bool) -> bool:
    if pending_count <= 0:
        return False
    if pending_count >= stage.flush_threshold:
        return True
    return stage.flush_when_upstream_empty and not upstream_pending


def _load_input_item(config: ProcessorConfig, stage: StageDefinition, path: Path) -> InputItem:
    raw = load_json(path)
    envelope = None
    if stage.input.base_dir != "vault":
        envelope = load_artifact(path)
    return InputItem(path=path, raw=raw if isinstance(raw, dict) else {}, envelope=envelope)


def _artifact_json_path(config: ProcessorConfig, output: OutputDefinition, envelope: ArtifactEnvelope) -> Path:
    root = resolve_collection_dir(config, output.collection)
    return root / f"{envelope.id}.json"


def _write_output_projection(
    config: ProcessorConfig,
    output: OutputDefinition,
    envelopes: list[ArtifactEnvelope],
) -> tuple[list[Path], set[str]]:
    written_paths: list[Path] = []
    touched_dates: set[str] = set()
    if output.projection == "markdown_note":
        for envelope in envelopes:
            path = resolve_collection_dir(config, output.collection) / f"{envelope.id}.md"
            if not config.dry_run:
                atomic_write_text(path, render_markdown(envelope))
            written_paths.append(path)
        return written_paths, touched_dates

    for envelope in envelopes:
        path = _artifact_json_path(config, output, envelope)
        if not config.dry_run:
            atomic_write_json(path, envelope.to_dict())
        written_paths.append(path)
        touched_dates.add(envelope.timestamp[:10] if envelope.timestamp else "")

    if output.projection == "jsonl_day" and not config.dry_run:
        assert output.projection_target is not None
        for date in touched_dates:
            rewrite_jsonl_day(config, output.collection, output.projection_target, date)
    logger.debug(
        "Wrote projection output: output=%s projection=%s files=%s dates=%s dry_run=%s",
        output.name,
        output.projection,
        len(written_paths),
        sorted(touched_dates),
        config.dry_run,
    )
    return written_paths, touched_dates


def run_stage_once(config: ProcessorConfig, stage: StageDefinition, client: SupportsLLMClient) -> int:
    state = load_state(config, stage.name)
    all_input_paths = _collection_paths(config, stage.input)
    batch_candidates = pending_paths(all_input_paths, state.cursor_path)
    upstream_pending = _upstream_pending(config, stage)
    logger.debug(
        "Stage scan: stage=%s candidates=%s cursor=%s upstream_pending=%s batch_size=%s flush_threshold=%s",
        stage.name,
        len(batch_candidates),
        state.cursor_path,
        upstream_pending,
        stage.batch_size,
        stage.flush_threshold,
    )
    if not _should_flush(len(batch_candidates), stage, upstream_pending):
        logger.debug("Stage idle: stage=%s pending=%s", stage.name, len(batch_candidates))
        return 0

    batch_paths = batch_candidates[: stage.batch_size] if len(batch_candidates) >= stage.batch_size else batch_candidates
    items = [_load_input_item(config, stage, path) for path in batch_paths]
    logger.info(
        "Stage executing: stage=%s type=%s inputs=%s batch=%s dry_run=%s",
        stage.name,
        stage.type,
        len(items),
        len(batch_paths),
        config.dry_run,
    )
    outputs_by_name = execute_stage_adapter(stage, config, items, client)

    processed_items: set[tuple[str, str]] = set()
    for output in stage.outputs:
        envelopes = outputs_by_name.get(output.name, [])
        written_paths, _ = _write_output_projection(config, output, envelopes)
        processed_items.update((output.name, envelope.id) for envelope in envelopes)
        logger.info(
            "Stage output complete: stage=%s output=%s envelopes=%s written=%s projection=%s",
            stage.name,
            output.name,
            len(envelopes),
            len(written_paths),
            output.projection,
        )

    if batch_paths:
        state.cursor_path = canonical_path(batch_paths[-1])
    save_state(config, stage.name, state)
    logger.info(
        "Stage finished: stage=%s processed=%s cursor=%s",
        stage.name,
        len(processed_items),
        state.cursor_path,
    )
    return len(processed_items)


def _worker_loop(name: str, config: ProcessorConfig, stage: StageDefinition, client: SupportsLLMClient) -> None:
    logger.info("Worker started: %s", name)
    while True:
        try:
            processed = run_stage_once(config, stage, client)
            if processed:
                logger.info("%s worker processed %s items", name, processed)
            else:
                logger.debug("%s worker idle", name)
        except Exception:
            logger.exception("%s worker failed", name)
        time.sleep(config.poll_interval_s)


def _configure_worker_logging() -> None:
    level_name = settings.log_level()
    logging.getLogger().setLevel(level_name)
    logger.debug("Worker logging configured at level=%s", level_name)


def _build_worker_client(app_config: AppConfig, semaphore: multiprocessing.Semaphore) -> SupportsLLMClient:
    return SemaphoreLLMClient(ProcessorLLMClient(app_config.llm), semaphore)


def _stage_worker(config: ProcessorConfig, app_config: AppConfig, semaphore: multiprocessing.Semaphore, stage_name: str) -> None:
    _configure_worker_logging()
    stage = next(stage for stage in config.stages if stage.name == stage_name)
    logger.info("Launching stage worker: %s", stage_name)
    client = _build_worker_client(app_config, semaphore)
    _worker_loop(stage.name, config, stage, client)


def _single_loop_worker(config: ProcessorConfig, app_config: AppConfig, semaphore: multiprocessing.Semaphore) -> None:
    _configure_worker_logging()
    logger.info("Launching single-loop worker")
    client = _build_worker_client(app_config, semaphore)
    while True:
        try:
            processed = 0
            for stage in config.stages:
                processed += run_stage_once(config, stage, client)
            if processed:
                logger.info("processor single loop processed %s items", processed)
            else:
                logger.debug("processor single loop idle")
        except Exception:
            logger.exception("processor single loop failed")
        time.sleep(config.poll_interval_s)


def build_worker_specs(config: ProcessorConfig) -> list[dict[str, str]]:
    validate_pipeline(config)
    if config.execution_mode == "single_loop":
        return [{"mode": "single_loop", "name": "processor-single-loop"}]
    return [{"mode": "per_stage_worker", "name": stage.name} for stage in config.stages]


def run_worker_spec(
    config: ProcessorConfig,
    app_config: AppConfig,
    semaphore: multiprocessing.Semaphore,
    spec: dict[str, str],
) -> None:
    if spec["mode"] == "single_loop":
        _single_loop_worker(config, app_config, semaphore)
        return
    _stage_worker(config, app_config, semaphore, spec["name"])
