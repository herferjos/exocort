from __future__ import annotations

from common import EnvReader

from .models import FasterWhisperSettings


def load_settings() -> FasterWhisperSettings:
    env = EnvReader()
    language = env.str("FASTER_WHISPER_LANGUAGE", "") or None
    if language and language.lower() == "auto":
        language = None

    return FasterWhisperSettings(
        host=env.str("FASTER_WHISPER_HOST", "127.0.0.1"),
        port=env.int("FASTER_WHISPER_PORT", 9000),
        reload=env.bool("FASTER_WHISPER_RELOAD", True),
        model_path=env.str("FASTER_WHISPER_MODEL_PATH", "medium"),
        device=env.str("FASTER_WHISPER_DEVICE", "cpu"),
        compute_type=env.str("FASTER_WHISPER_COMPUTE_TYPE", "int8"),
        beam_size=env.int("FASTER_WHISPER_BEAM_SIZE", 5),
        language=language,
    )


__all__ = ["FasterWhisperSettings", "load_settings"]
