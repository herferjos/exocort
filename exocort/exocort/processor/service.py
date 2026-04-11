from __future__ import annotations

import json
import os
import queue
import threading
from datetime import datetime, timezone
from pathlib import Path

from watchdog.events import (
    FileCreatedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from exocort.config import EndpointSettings, ProcessorSettings
from exocort.logs import get_logger
from litellm import ocr, transcription

from .asr.service import asr_text
from .notes import run_notes_loop
from .ocr.service import ocr_text

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".mpeg", ".mpga", ".webm", ".ogg"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | AUDIO_EXTENSIONS
QUEUE_TIMEOUT_SECONDS = 0.5
log = get_logger("processor")


def processing_loop(config: ProcessorSettings) -> None:
    threads = [
        threading.Thread(
            target=_run_file_processor_loop,
            args=(config,),
            name="file-processor-loop",
        )
    ]
    if config.notes.enabled:
        threads.append(
            threading.Thread(
                target=run_notes_loop,
                args=(config,),
                name="notes-processor-loop",
            )
        )

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def _run_file_processor_loop(config: ProcessorSettings) -> None:
    config.watch_dir.mkdir(parents=True, exist_ok=True)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    log.info(
        "watching %s -> %s with filesystem events",
        config.watch_dir,
        config.output_dir,
    )

    processed = process_existing_files(config)
    if processed:
        log.info("processed %s existing file(s)", processed)

    event_queue: queue.Queue[Path] = queue.Queue()
    event_handler = _QueuedPathHandler(event_queue)
    observer = Observer()
    observer.schedule(event_handler, str(config.watch_dir), recursive=True)
    observer.start()

    try:
        while True:
            try:
                file_path = event_queue.get(timeout=QUEUE_TIMEOUT_SECONDS)
            except queue.Empty:
                continue

            _process_file_if_supported(config, file_path)
            event_handler.mark_done(file_path)
            _drain_queue(config, event_queue, event_handler)
    finally:
        observer.stop()
        observer.join()


def process_existing_files(config: ProcessorSettings) -> int:
    processed = 0
    for file_path in _iter_supported_files(config.watch_dir):
        if _process_file_if_supported(config, file_path):
            processed += 1
    return processed


def _drain_queue(
    config: ProcessorSettings,
    event_queue: queue.Queue[Path],
    event_handler: "_QueuedPathHandler",
) -> None:
    while True:
        try:
            file_path = event_queue.get_nowait()
        except queue.Empty:
            return
        _process_file_if_supported(config, file_path)
        event_handler.mark_done(file_path)


def _iter_supported_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def _process_file_if_supported(config: ProcessorSettings, file_path: Path) -> bool:
    endpoint = _get_endpoint_config(config, file_path)
    if endpoint is None:
        return False

    output_path = _build_output_path(config, file_path)
    if output_path.exists():
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        text = _process_file(file_path, endpoint)
    except Exception as exc:
        if _is_empty_text_error(exc):
            text = ""
            log.info("saved empty result for %s because OCR/ASR returned no text", file_path)
        else:
            error_path = output_path.with_suffix(".error.txt")
            error_path.write_text(str(exc), encoding="utf-8")
            log.error("failed %s -> %s: %s", file_path, error_path, exc)
            return False

    output_path.write_text(
        json.dumps(_build_output_payload(config, file_path, text), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("saved %s -> %s", file_path, output_path)
    return True


def _get_endpoint_config(
    config: ProcessorSettings,
    file_path: Path,
) -> EndpointSettings | None:
    suffix = file_path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS and config.ocr.model and config.ocr.api_base:
        return config.ocr
    if suffix in AUDIO_EXTENSIONS and config.asr.model and config.asr.api_base:
        return config.asr
    return None


def _build_output_path(config: ProcessorSettings, file_path: Path) -> Path:
    relative_path = file_path.relative_to(config.watch_dir)
    return config.output_dir / relative_path.parent / f"{relative_path.stem}.json"


def _process_file(file_path: Path, endpoint: EndpointSettings) -> str:
    api_key = os.getenv(endpoint.api_key_env, "test_key") if endpoint.api_key_env else "test_key"

    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        return _process_ocr_file(file_path, endpoint, api_key)

    return _process_asr_file(file_path, endpoint, api_key)


def _build_output_payload(config: ProcessorSettings, file_path: Path, text: str) -> dict[str, object]:
    source_kind = "ocr" if file_path.suffix.lower() in IMAGE_EXTENSIONS else "asr"
    relative_path = file_path.relative_to(config.watch_dir)
    return {
        "schema_version": 2,
        "source_kind": source_kind,
        "source_file": str(file_path.resolve()),
        "source_relpath": str(relative_path),
        "captured_at": _captured_at_from_path(file_path).isoformat().replace("+00:00", "Z"),
        "text": text,
    }


def _is_empty_text_error(exc: Exception) -> bool:
    return str(exc) in {
        "ASR response text is empty.",
        "OCR page markdown is empty.",
        "OCR response must include a non-empty `pages` list.",
    }


def _captured_at_from_path(file_path: Path) -> datetime:
    timestamp = file_path.stem
    return datetime.strptime(timestamp, "%Y%m%dT%H%M%S%f").replace(tzinfo=timezone.utc)


def _process_ocr_file(file_path: Path, endpoint: EndpointSettings, api_key: str) -> str:
    response = ocr(
        model=endpoint.model,
        document={"type": "file", "file": str(file_path)},
        api_base=endpoint.api_base,
        api_key=api_key,
    )
    return ocr_text(response)


def _process_asr_file(file_path: Path, endpoint: EndpointSettings, api_key: str) -> str:
    with file_path.open("rb") as audio_file:
        response = transcription(
            model=endpoint.model,
            file=audio_file,
            api_base=endpoint.api_base,
            api_key=api_key,
        )
    return asr_text(response)


class _QueuedPathHandler(FileSystemEventHandler):
    def __init__(self, event_queue: queue.Queue[Path]) -> None:
        super().__init__()
        self._event_queue = event_queue
        self._queued: set[Path] = set()

    def on_created(self, event: FileCreatedEvent) -> None:  # type: ignore[override]
        self._queue_event(event)

    def on_modified(self, event: FileModifiedEvent) -> None:  # type: ignore[override]
        self._queue_event(event)

    def on_moved(self, event: FileMovedEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        self._queue_path(Path(event.dest_path))

    def mark_done(self, file_path: Path) -> None:
        resolved = file_path.resolve()
        self._queued.discard(resolved)

    def _queue_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._queue_path(Path(event.src_path))

    def _queue_path(self, file_path: Path) -> None:
        resolved = file_path.expanduser().resolve()
        if resolved.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return
        if resolved in self._queued:
            return
        self._queued.add(resolved)
        self._event_queue.put(resolved)
