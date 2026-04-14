from __future__ import annotations

from pathlib import Path

import yaml

from .models.capturer import CapturerSettings
from .models.common import ExocortSettings
from .utils.capturer import parse_audio_settings, parse_screen_settings
from .utils.common import as_mapping, parse_log_level
from .utils.processor import parse_processor_settings

def load_config(path: Path) -> ExocortSettings:
    config_dir = path.expanduser().resolve().parent
    data = yaml.safe_load(path.read_text())
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("Config file must contain a YAML mapping at the top level.")
    capturer = as_mapping(data.get("capturer", {}), "capturer")
    return ExocortSettings(
        log_level=parse_log_level(data.get("log_level", "INFO")),
        capturer=CapturerSettings(
            audio=parse_audio_settings(capturer.get("audio", data.get("audio", {})), config_dir),
            screen=parse_screen_settings(capturer.get("screen", data.get("screen", {})), config_dir),
        ),
        processor=parse_processor_settings(data.get("processor", {}), config_dir),
    )
