from __future__ import annotations

import os

from dotenv import load_dotenv

from .models import FasterWhisperSettings


def _str(key: str, default: str) -> str:
    return os.getenv(key, default).strip()


def _int(key: str, default: int) -> int:
    raw = _str(key, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


def load_settings() -> FasterWhisperSettings:
    load_dotenv()
    language = _str("FASTER_WHISPER_LANGUAGE", "") or None
    if language and language.lower() == "auto":
        language = None

    return FasterWhisperSettings(
        host=_str("FASTER_WHISPER_HOST", "127.0.0.1"),
        port=_int("FASTER_WHISPER_PORT", 9000),
        model_path=_str("FASTER_WHISPER_MODEL_PATH", "medium"),
        device=_str("FASTER_WHISPER_DEVICE", "cpu"),
        compute_type=_str("FASTER_WHISPER_COMPUTE_TYPE", "int8"),
        beam_size=_int("FASTER_WHISPER_BEAM_SIZE", 5),
        language=language,
    )


__all__ = ["FasterWhisperSettings", "load_settings"]
