from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from datetime import datetime, timezone

from exocort.config import ProcessorSettings
from exocort.logs import get_logger

from .agent import run_notes_agent, touched_note_paths
from .batching import build_batch_candidates, discover_unprocessed_artifacts
from .models import BatchCandidate, BatchRunResult
from .state import ensure_state_dirs, write_batch_error, write_batch_manifest

log = get_logger("processor", "notes")


def run_notes_loop(config: ProcessorSettings) -> None:
    notes = config.notes
    if not notes.enabled:
        return

    notes.vault_dir.mkdir(parents=True, exist_ok=True)
    ensure_state_dirs(notes.state_dir)
    log.info(
        "running notes loop every %ss from %s into %s",
        notes.interval_seconds,
        config.output_dir,
        notes.vault_dir,
    )

    while True:
        try:
            process_notes_once(config)
        except Exception as exc:
            log.error("notes loop failed: %s", exc)
        time.sleep(notes.interval_seconds)


def process_notes_once(config: ProcessorSettings) -> bool:
    notes = config.notes
    artifacts = discover_unprocessed_artifacts(config)
    if not artifacts:
        return False

    candidates = build_batch_candidates(config.notes, artifacts)
    if not candidates:
        return False

    log.info(
        "notes check found %s artifact(s) and will run %s batch(es)",
        len(artifacts),
        len(candidates),
    )

    failures: list[Exception] = []
    max_workers = max(1, min(notes.max_concurrent_batch, len(candidates)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_run_notes_batch, config, candidate): candidate
            for candidate in candidates
        }
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as exc:
                failures.append(exc)

    if failures:
        raise failures[0]

    return True


def _run_notes_batch(config: ProcessorSettings, candidate: BatchCandidate) -> BatchRunResult:
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    try:
        result = run_notes_agent(config.notes, candidate)
    except Exception as exc:
        error_text = str(exc)
        write_batch_error(config.notes.state_dir, batch_id, error_text)
        write_batch_manifest(
            config.notes.state_dir,
            batch_id=batch_id,
            status="failed",
            artifact_ids=[artifact.artifact_id for artifact in candidate.artifacts],
            input_tokens=candidate.input_tokens,
            note_paths=[],
            assistant_message="",
            tool_results=[],
            error=error_text,
        )
        raise

    note_paths = touched_note_paths(result)
    write_batch_manifest(
        config.notes.state_dir,
        batch_id=batch_id,
        status="completed",
        artifact_ids=[artifact.artifact_id for artifact in candidate.artifacts],
        input_tokens=candidate.input_tokens,
        note_paths=note_paths,
        assistant_message=result.assistant_message,
        tool_results=[
            {
                "tool_name": tool_result.tool_name,
                "summary": tool_result.summary,
                "note_path": tool_result.note_path,
            }
            for tool_result in result.tool_results
        ],
        error=None,
    )
    log.info(
        "notes batch %s completed with %s artifact(s), %s token(s), %s note change(s)",
        batch_id,
        len(candidate.artifacts),
        candidate.input_tokens,
        len(note_paths),
    )
    return result
