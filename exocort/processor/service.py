from __future__ import annotations

from dataclasses import asdict, is_dataclass
import json
import os
from pathlib import Path
import time
from typing import Any

from exocort.config import EndpointSettings, FileProcessorSettings

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".mp4", ".mpeg", ".mpga", ".webm", ".ogg"}


def processing_loop(config: FileProcessorSettings) -> None:
    config.watch_dir.mkdir(parents=True, exist_ok=True)
    config.output.root_path.mkdir(parents=True, exist_ok=True)

    print(
        f"[processor] watching {config.watch_dir} every "
        f"{config.poll_interval_seconds}s -> {config.output.root_path}"
    )

    while True:
        processed = process_pending_files(config)
        if processed:
            print(f"[processor] processed {processed} file(s)")
        time.sleep(config.poll_interval_seconds)


def process_pending_files(config: FileProcessorSettings) -> int:
    processed = 0
    for file_path in _iter_supported_files(config.watch_dir):
        endpoint = _get_endpoint_config(config, file_path)
        if endpoint is None:
            continue
        output_path = _build_output_path(config, file_path)
        if output_path.exists():
            continue
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            response = _process_file(file_path, endpoint)
        except Exception as exc:
            error_path = output_path.with_suffix(".error.txt")
            error_path.write_text(str(exc), encoding="utf-8")
            print(f"[processor] failed {file_path} -> {error_path}: {exc}")
            continue
        output_path.write_text(
            json.dumps(_serialize_response(response), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[processor] saved {file_path} -> {output_path}")
        processed += 1
    return processed


def _iter_supported_files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS | AUDIO_EXTENSIONS
    )


def _get_endpoint_config(
    config: FileProcessorSettings,
    file_path: Path,
) -> EndpointSettings | None:
    suffix = file_path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS and config.ocr.model and config.ocr.api_base:
        return config.ocr
    if suffix in AUDIO_EXTENSIONS and config.asr.model and config.asr.api_base:
        return config.asr
    return None


def _build_output_path(config: FileProcessorSettings, file_path: Path) -> Path:
    relative_path = file_path.relative_to(config.watch_dir)
    return config.output.root_path / relative_path.parent / f"{relative_path.name}.json"


def _process_file(file_path: Path, endpoint: EndpointSettings) -> Any:
    api_key = os.getenv(endpoint.api_key_env, "test_key") if endpoint.api_key_env else "test_key"

    if file_path.suffix.lower() in IMAGE_EXTENSIONS:
        from litellm import ocr

        return ocr(
            model=endpoint.model,
            document={"type": "file", "file": str(file_path)},
            api_base=endpoint.api_base,
            api_key=api_key,
        )

    from litellm import transcription

    with file_path.open("rb") as audio_file:
        return transcription(
            model=endpoint.model,
            file=audio_file,
            api_base=endpoint.api_base,
            api_key=api_key,
        )


def _serialize_response(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _serialize_response(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_response(item) for item in value]
    return value
