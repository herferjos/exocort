from __future__ import annotations

import threading
from pathlib import Path

from faster_whisper import WhisperModel
from faster_whisper.utils import download_model

from common.models.asr import TranscriptionResponse
from common.models.health import HealthResponse
from common.utils.logs import get_logger
from src.config.settings import load_settings

log = get_logger("faster_whisper", "transcription")
_model: WhisperModel | None = None
_model_lock = threading.Lock()


def _ensure_model_path(model_size: str, model_path: Path) -> str:
    model_path.mkdir(parents=True, exist_ok=True)
    try:
        return download_model(
            model_size,
            output_dir=str(model_path),
            local_files_only=True,
        )
    except Exception:
        log.info(
            "Downloading faster-whisper model | model_size=%s | model_path=%s",
            model_size,
            model_path,
        )
        return download_model(model_size, output_dir=str(model_path))


def startup() -> None:
    global _model
    settings = load_settings()
    resolved_model_path = _ensure_model_path(settings.model_size, settings.model_path)
    try:
        _model = WhisperModel(
            resolved_model_path,
            device=settings.device,
            compute_type=settings.compute_type,
        )
        log.info(
            "Loaded faster-whisper model | model_size=%s | model_path=%s | resolved_model_path=%s | device=%s | compute_type=%s",
            settings.model_size,
            settings.model_path,
            resolved_model_path,
            settings.device,
            settings.compute_type,
        )
    except Exception:
        log.exception("Failed to load faster-whisper model")
        raise


def health() -> HealthResponse:
    return HealthResponse(ok=_model is not None)


def transcribe_path(
    path: Path,
    *,
    language: str | None,
    prompt: str | None,
) -> TranscriptionResponse | None:
    if _model is None:
        raise RuntimeError("model not loaded")

    settings = load_settings()
    with _model_lock:
        segments, _info = _model.transcribe(
            str(path),
            beam_size=settings.beam_size,
            language=language or settings.language,
            initial_prompt=prompt or None,
        )

    text_parts: list[str] = [segment.text.strip() for segment in segments if segment.text]
    text = " ".join(text_parts).strip()
    if not text:
        return None
    return TranscriptionResponse(
        text=text,
        language=language or settings.language or "",
        duration=None,
    )


__all__ = ["health", "startup", "transcribe_path"]
