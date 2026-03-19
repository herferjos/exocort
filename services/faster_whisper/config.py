from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class FasterWhisperSettings:
    model_path: str
    device: str
    compute_type: str
    vad_filter: bool
    beam_size: int
    language: str | None


def load_settings() -> FasterWhisperSettings:
    model_path = os.environ.get("FASTER_WHISPER_MODEL_PATH", "medium")
    device = os.environ.get("FASTER_WHISPER_DEVICE", "cpu")
    compute_type = os.environ.get("FASTER_WHISPER_COMPUTE_TYPE", "int8")
    vad_filter_str = os.environ.get("FASTER_WHISPER_VAD_FILTER", "False")
    vad_filter = vad_filter_str.lower() in ("true", "1", "t")
    beam_size = int(os.environ.get("FASTER_WHISPER_BEAM_SIZE", 5))
    language = os.environ.get("FASTER_WHISPER_LANGUAGE") or None

    if language and language.lower() == "auto":
        language = None

    return FasterWhisperSettings(
        model_path=model_path,
        device=device,
        compute_type=compute_type,
        vad_filter=vad_filter,
        beam_size=beam_size,
        language=language,
    )


__all__ = ["FasterWhisperSettings", "load_settings"]
