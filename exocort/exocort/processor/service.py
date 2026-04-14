from __future__ import annotations

import json
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

from exocort.config import EndpointSettings, ExocortSettings, ProcessorSettings
from exocort.logs import get_logger
from exocort.bridge import AsrRequest, MediaInput, OcrRequest, ProviderBridge, ProviderConfig

from .asr.service import asr_text
from .notes import run_notes_loop
from .ocr.service import ocr_text
from .retention import schedule_file_deletion
from .sensitive import ContentMatch, detect_content_match

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".mpeg", ".mpga", ".webm", ".ogg"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | AUDIO_EXTENSIONS
QUEUE_TIMEOUT_SECONDS = 0.5
log = get_logger("processor")


def processing_loop(config: ExocortSettings) -> None:
    processor = config.processor
    threads: list[threading.Thread] = []
    log.info(
        "processor loop starting watch_dir=%s output_dir=%s ocr_enabled=%s asr_enabled=%s notes_enabled=%s",
        processor.watch_dir,
        processor.output_dir,
        processor.ocr.enabled,
        processor.asr.enabled,
        processor.notes.enabled,
    )
    if processor.ocr.enabled or processor.asr.enabled:
        threads.append(
            threading.Thread(
                target=_run_file_processor_loop,
                args=(config,),
                name="file-processor-loop",
            )
        )
    if processor.notes.enabled:
        threads.append(
            threading.Thread(
                target=run_notes_loop,
                args=(processor,),
                name="notes-processor-loop",
            )
        )

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def _run_file_processor_loop(config: ExocortSettings) -> None:
    processor = config.processor
    processor.watch_dir.mkdir(parents=True, exist_ok=True)
    processor.output_dir.mkdir(parents=True, exist_ok=True)

    log.info(
        "watching %s -> %s with filesystem events",
        processor.watch_dir,
        processor.output_dir,
    )

    event_queue: queue.Queue[Path] = queue.Queue()
    event_handler = _QueuedPathHandler(event_queue)
    worker_queues = _start_processing_workers(config, event_handler)

    queued_existing = queue_existing_files(config, event_handler, worker_queues)
    if queued_existing:
        log.info("queued %s existing file(s) for processing", queued_existing)
    else:
        log.debug("no existing files found to process on startup")

    observer = Observer()
    observer.schedule(event_handler, str(processor.watch_dir), recursive=True)
    observer.start()

    try:
        while True:
            try:
                file_path = event_queue.get(timeout=QUEUE_TIMEOUT_SECONDS)
            except queue.Empty:
                continue

            _dispatch_file_path(config, file_path, worker_queues, source="filesystem")
    finally:
        observer.stop()
        observer.join()


def queue_existing_files(
    config: ExocortSettings,
    event_handler: "_QueuedPathHandler",
    worker_queues: dict[str, queue.Queue[Path]],
) -> int:
    queued = 0
    for file_path in _iter_supported_files(config.processor.watch_dir):
        if event_handler.track_existing(file_path):
            _dispatch_file_path(config, file_path, worker_queues, source="startup")
            queued += 1
    return queued


def _iter_supported_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if _is_supported_visible_file(path)
    )


def _process_file_if_supported(config: ExocortSettings, file_path: Path) -> bool:
    if not _is_supported_visible_file(file_path):
        log.debug("skipping path=%s reason=hidden_or_missing", file_path.name)
        return False

    processor = config.processor
    endpoint = _get_endpoint_config(processor, file_path)
    if endpoint is None:
        log.debug("skipping path=%s reason=unsupported_or_disabled", file_path.name)
        return False

    output_path = _build_output_path(processor, file_path)
    sensitive_marker_path = _build_sensitive_marker_path(output_path)
    if output_path.exists() or sensitive_marker_path.exists():
        log.debug("skipping path=%s reason=already_processed", file_path.name)
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        log.debug(
            "processing path=%s kind=%s model=%s",
            file_path.name,
            _source_kind_for_path(file_path),
            endpoint.model,
        )
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

    content_match = detect_content_match(processor.content_filter, text)
    if content_match is not None:
        sensitive_marker_path.write_text(
            json.dumps(
                _build_sensitive_marker_payload(processor, file_path, content_match),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        log.warning(
            "blocked sensitive %s output for %s with rule=%s match_type=%s",
            _source_kind_for_path(file_path),
            file_path,
            content_match.rule_name,
            content_match.match_type,
        )
        schedule_file_deletion(
            file_path,
            expired_in=0,
            reason="sensitive content detected in processed capture",
        )
        return True

    output_path.write_text(
        json.dumps(_build_output_payload(processor, file_path, text), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("saved %s -> %s", file_path, output_path)
    schedule_file_deletion(
        file_path,
        expired_in=_raw_expired_in(config, file_path),
        reason="raw capture consumed by processor",
    )
    return True


def _start_processing_workers(
    config: ExocortSettings,
    event_handler: "_QueuedPathHandler",
) -> dict[str, queue.Queue[Path]]:
    worker_queues: dict[str, queue.Queue[Path]] = {}
    processor = config.processor

    if processor.ocr.enabled:
        ocr_queue: queue.Queue[Path] = queue.Queue()
        worker_queues["ocr"] = ocr_queue
        threading.Thread(
            target=_processing_worker_loop,
            args=(config, ocr_queue, event_handler, "ocr"),
            name="ocr-worker",
            daemon=True,
        ).start()

    if processor.asr.enabled:
        asr_queue: queue.Queue[Path] = queue.Queue()
        worker_queues["asr"] = asr_queue
        threading.Thread(
            target=_processing_worker_loop,
            args=(config, asr_queue, event_handler, "asr"),
            name="asr-worker",
            daemon=True,
        ).start()

    return worker_queues


def _dispatch_file_path(
    config: ExocortSettings,
    file_path: Path,
    worker_queues: dict[str, queue.Queue[Path]],
    *,
    source: str,
) -> None:
    kind = _source_kind_for_processing(config.processor, file_path)
    if kind is None:
        log.debug("skipping queued path=%s source=%s reason=unsupported_or_disabled", file_path.name, source)
        return
    log.debug("dispatching path=%s source=%s kind=%s", file_path.name, source, kind)
    worker_queues[kind].put(file_path)


def _processing_worker_loop(
    config: ExocortSettings,
    work_queue: queue.Queue[Path],
    event_handler: "_QueuedPathHandler",
    kind: str,
) -> None:
    while True:
        file_path = work_queue.get()
        try:
            log.debug("worker=%s processing path=%s", kind, file_path.name)
            _process_file_if_supported(config, file_path)
        finally:
            event_handler.mark_done(file_path)


def _get_endpoint_config(
    config: ProcessorSettings,
    file_path: Path,
) -> EndpointSettings | None:
    kind = _source_kind_for_processing(config, file_path)
    if kind == "ocr" and config.ocr.model and config.ocr.api_base:
        return config.ocr
    if kind == "asr" and config.asr.model and config.asr.api_base:
        return config.asr
    return None


def _source_kind_for_processing(config: ProcessorSettings, file_path: Path) -> str | None:
    suffix = file_path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS and config.ocr.enabled:
        return "ocr"
    if suffix in AUDIO_EXTENSIONS and config.asr.enabled:
        return "asr"
    return None


def _build_output_path(config: ProcessorSettings, file_path: Path) -> Path:
    relative_path = file_path.relative_to(config.watch_dir)
    return config.output_dir / relative_path.parent / f"{relative_path.stem}.json"


def _process_file(file_path: Path, endpoint: EndpointSettings) -> str:
    log.debug(
        "dispatching path=%s suffix=%s model=%s",
        file_path.name,
        file_path.suffix.lower(),
        endpoint.model,
    )

    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        return _process_ocr_file(file_path, endpoint)

    return _process_asr_file(file_path, endpoint)


def _build_output_payload(config: ProcessorSettings, file_path: Path, text: str) -> dict[str, object]:
    source_kind = _source_kind_for_path(file_path)
    relative_path = file_path.relative_to(config.watch_dir)
    return {
        "schema_version": 2,
        "source_kind": source_kind,
        "source_file": str(file_path.resolve()),
        "source_relpath": str(relative_path),
        "captured_at": _captured_at_from_path(file_path).isoformat().replace("+00:00", "Z"),
        "text": text,
    }


def _build_sensitive_marker_payload(
    config: ProcessorSettings,
    file_path: Path,
    content_match: ContentMatch,
) -> dict[str, object]:
    relative_path = file_path.relative_to(config.watch_dir)
    return {
        "schema_version": 1,
        "source_kind": _source_kind_for_path(file_path),
        "source_file": str(file_path.resolve()),
        "source_relpath": str(relative_path),
        "captured_at": _captured_at_from_path(file_path).isoformat().replace("+00:00", "Z"),
        "status": "blocked_sensitive",
        "content_rule": content_match.rule_name,
        "content_match_type": content_match.match_type,
        "content_pattern": content_match.pattern,
    }


def _raw_expired_in(config: ExocortSettings, file_path: Path) -> int:
    suffix = file_path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return config.capturer.screen.expired_in
    if suffix in AUDIO_EXTENSIONS:
        return config.capturer.audio.expired_in
    return 0


def _source_kind_for_path(file_path: Path) -> str:
    return "ocr" if file_path.suffix.lower() in IMAGE_EXTENSIONS else "asr"


def _build_sensitive_marker_path(output_path: Path) -> Path:
    return output_path.with_suffix(".sensitive.json")


def _is_empty_text_error(exc: Exception) -> bool:
    return str(exc) in {
        "ASR response text is empty.",
        "OCR page markdown is empty.",
        "OCR response must include a non-empty `pages` list.",
    }


def _captured_at_from_path(file_path: Path) -> datetime:
    timestamp = file_path.stem
    return datetime.strptime(timestamp, "%Y%m%dT%H%M%S%f").replace(tzinfo=timezone.utc)


def _is_supported_visible_file(file_path: Path) -> bool:
    return (
        file_path.is_file()
        and not file_path.name.startswith(".")
        and file_path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def _process_ocr_file(file_path: Path, endpoint: EndpointSettings) -> str:
    log.debug("sending request kind=ocr path=%s", file_path.name)
    language = getattr(endpoint, "language", "")
    prompt = _prompt_with_language(endpoint.prompt, language)
    bridge = ProviderBridge(
        ProviderConfig(
            provider=endpoint.provider,
            api_base=endpoint.api_base,
            api_key_env=endpoint.api_key_env,
            timeout_s=endpoint.timeout_s,
            retries=endpoint.retries,
        )
    )
    response = bridge.ocr(
        OcrRequest(
            model=endpoint.model,
            format=endpoint.format,
            media=MediaInput(file_path=file_path),
            prompt=prompt or None,
        )
    )
    return ocr_text({"pages": [{"index": page.index, "markdown": page.text} for page in response.pages]})


def _process_asr_file(file_path: Path, endpoint: EndpointSettings) -> str:
    log.debug("sending request kind=asr path=%s", file_path.name)
    language = getattr(endpoint, "language", "")
    prompt = _prompt_with_language(endpoint.prompt, language)
    bridge = ProviderBridge(
        ProviderConfig(
            provider=endpoint.provider,
            api_base=endpoint.api_base,
            api_key_env=endpoint.api_key_env,
            timeout_s=endpoint.timeout_s,
            retries=endpoint.retries,
        )
    )
    response = bridge.asr(
        AsrRequest(
            model=endpoint.model,
            format=endpoint.format,
            media=MediaInput(file_path=file_path),
            language=language.strip() or None,
            prompt=prompt or None,
        )
    )
    return asr_text({"text": response.text})


def _prompt_with_language(prompt: str, language: str) -> str:
    return prompt.replace("{{language}}", language.strip() or "English").strip()


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
        log.debug("marked done path=%s", resolved.name)

    def track_existing(self, file_path: Path) -> bool:
        resolved = file_path.expanduser().resolve()
        if resolved in self._queued:
            return False
        self._queued.add(resolved)
        return True

    def _queue_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._queue_path(Path(event.src_path))

    def _queue_path(self, file_path: Path) -> None:
        resolved = file_path.expanduser().resolve()
        if resolved.name.startswith("."):
            return
        if resolved.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return
        if resolved in self._queued:
            log.debug("ignoring duplicate event path=%s", resolved.name)
            return
        self._queued.add(resolved)
        log.debug("queued event path=%s", resolved.name)
        self._event_queue.put(resolved)
