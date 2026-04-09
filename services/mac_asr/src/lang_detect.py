from __future__ import annotations

import logging
from pathlib import Path

from faster_whisper import WhisperModel

from .config import load_settings

log = logging.getLogger("mac_asr.lang_detect")
_detector_model: WhisperModel | None = None


def get_detector_model() -> WhisperModel:
    global _detector_model
    if _detector_model is not None:
        return _detector_model

    settings = load_settings()
    _detector_model = WhisperModel(
        settings.detect_model,
        device=settings.detect_device,
        compute_type=settings.detect_compute_type,
    )
    return _detector_model


def detect_language(path: Path) -> tuple[str | None, float | None]:
    try:
        _, info = get_detector_model().transcribe(
            str(path),
            beam_size=1,
            language=None,
        )
    except Exception as exc:
        log.warning("Language detection failed: %s", exc)
        return None, None

    language = getattr(info, "language", None)
    probability = getattr(info, "language_probability", None)
    if isinstance(language, str):
        language = language.strip().lower() or None
    else:
        language = None
    try:
        probability = float(probability) if probability is not None else None
    except (TypeError, ValueError):
        probability = None
    if probability is not None and probability < load_settings().detect_discard_min_prob:
        return None, probability

    if language:
        log.info(
            "Language detected | language=%s | prob=%.3f",
            language,
            probability if probability is not None else -1.0,
        )
    else:
        log.info("Language not detected")

    return language, probability


__all__ = ["detect_language", "get_detector_model"]
