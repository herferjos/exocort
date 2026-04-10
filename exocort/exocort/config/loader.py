from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from exocort.capturer.audio.vad import AudioVADConfig

from .models import AudioSettings, EndpointSettings, ExocortSettings, ProcessorSettings, ScreenSettings

def load_config(path: Path) -> ExocortSettings:
    config_dir = path.expanduser().resolve().parent
    data = yaml.safe_load(path.read_text())
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("Config file must contain a YAML mapping at the top level.")
    return ExocortSettings(
        audio=_parse_audio_settings(data.get("audio", {}), config_dir),
        screen=_parse_screen_settings(data.get("screen", {}), config_dir),
        processor=_parse_processor_settings(data.get("processor", {}), config_dir),
    )


def _parse_audio_settings(data: object, config_dir: Path) -> AudioSettings:
    mapping = _as_mapping(data, "audio")
    return AudioSettings(
        enabled=bool(mapping.get("enabled", False)),
        chunk_seconds=int(mapping.get("chunk_seconds", 30)),
        sample_rate=int(mapping.get("sample_rate", 16_000)),
        channels=int(mapping.get("channels", 1)),
        output_dir=_resolve_path(mapping.get("output_dir", "captures/audio"), config_dir),
        vad=_parse_vad_settings(mapping.get("vad", {})),
    )


def _parse_vad_settings(data: object) -> AudioVADConfig:
    mapping = _as_mapping(data, "audio.vad")
    return AudioVADConfig(
        enabled=bool(mapping.get("enabled", False)),
        aggressiveness=int(mapping.get("aggressiveness", 2)),
        frame_ms=int(mapping.get("frame_ms", 30)),
        pre_roll_seconds=float(mapping.get("pre_roll_seconds", 0.3)),
        min_speech_seconds=float(mapping.get("min_speech_seconds", 0.2)),
        min_silence_seconds=float(mapping.get("min_silence_seconds", 0.8)),
    )


def _parse_screen_settings(data: object, config_dir: Path) -> ScreenSettings:
    mapping = _as_mapping(data, "screen")
    return ScreenSettings(
        enabled=bool(mapping.get("enabled", False)),
        interval_seconds=int(mapping.get("interval_seconds", 5)),
        output_dir=_resolve_path(mapping.get("output_dir", "captures/screen"), config_dir),
    )


def _parse_endpoint_settings(data: object) -> EndpointSettings:
    mapping = _as_mapping(data, "endpoint")
    return EndpointSettings(
        model=str(mapping.get("model", "")),
        api_base=str(mapping.get("api_base", "")),
        api_key_env=str(mapping.get("api_key_env", "")),
    )


def _parse_processor_settings(data: object, config_dir: Path) -> ProcessorSettings:
    mapping = _as_mapping(data, "processor")
    return ProcessorSettings(
        enabled=bool(mapping.get("enabled", False)),
        watch_dir=_resolve_path(mapping.get("watch_dir", "captures"), config_dir),
        output_dir=_resolve_path(mapping.get("output_dir", "captures/processed"), config_dir),
        ocr=_parse_endpoint_settings(mapping.get("ocr", {})),
        asr=_parse_endpoint_settings(mapping.get("asr", {})),
    )


def _as_mapping(data: object, label: str) -> dict[str, Any]:
    if isinstance(data, Mapping):
        return dict(data)
    raise ValueError(f"{label} section must be a mapping.")


def _resolve_path(value: object, config_dir: Path) -> Path:
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path
    return (config_dir / path).resolve()
