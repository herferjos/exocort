from __future__ import annotations

import threading
from pathlib import Path

from faster_whisper import WhisperModel

from common.models.asr import TranscriptionResponse
from common.models.health import HealthResponse
from common.utils.logs import get_logger
from src.config import load_settings

log = get_logger("faster_whisper", "transcription")
_model: WhisperModel | None = None
_model_lock = threading.Lock()


def startup() -> None:
    global _model
    settings = load_settings()
    try:
        _model = WhisperModel(
            settings.model_path,
            device=settings.device,
            compute_type=settings.compute_type,
        )
        log.info(
            "Loaded faster-whisper model | path=%s | device=%s | compute_type=%s",
            settings.model_path,
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
