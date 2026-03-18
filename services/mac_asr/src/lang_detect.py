from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .config import (
    DETECT_COMPUTE_TYPE,
    DETECT_DEVICE,
    DETECT_MIN_PROB,
    DETECT_MODEL,
)

log = logging.getLogger("mac_asr.lang_detect")

_model = None


def _create_model():
    from faster_whisper import WhisperModel

    return WhisperModel(
        DETECT_MODEL,
        device=DETECT_DEVICE,
        compute_type=DETECT_COMPUTE_TYPE,
    )


def get_detector_model():
    global _model
    if _model is None:
        _model = _create_model()
    return _model


def detect_language(path: Path) -> tuple[str | None, float | None]:
    try:
        _, info = get_detector_model().transcribe(
            str(path),
            beam_size=1,
            language=None,
            vad_filter=True,
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

    if probability is not None and probability < DETECT_MIN_PROB:
        log.info(
            "Language detection below threshold | language=%s | prob=%.3f",
            language,
            probability,
        )
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
