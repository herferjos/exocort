from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from common.utils.yaml import load_yaml_config

from .models import FasterWhisperSettings


@lru_cache(maxsize=1)
def load_settings() -> FasterWhisperSettings:
    config = load_yaml_config(Path(__file__).resolve().parents[2] / "config.yaml")
    language = str(config.get("language", "")).strip() or None
    if language and language.lower() == "auto":
        language = None
    model_size = str(config.get("model_size", "medium")).strip() or "medium"
    model_path = resolve_config_path(config_dir, config.get("model_path"), "models")

    return FasterWhisperSettings(
        host=str(config.get("host", "127.0.0.1")).strip(),
        port=int(config.get("port", 9000)),
        reload=bool(config.get("reload", True)),
        log_level=str(config.get("log_level", "info")).lower().strip(),
        model_size=model_size,
        model_path=model_path,
        device=str(config.get("device", "cpu")).strip(),
        compute_type=str(config.get("compute_type", "int8")).strip(),
        beam_size=int(config.get("beam_size", 5)),
        language=language,
    )
