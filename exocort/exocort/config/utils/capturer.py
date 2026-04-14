from __future__ import annotations

from pathlib import Path

from exocort.capturer.audio.vad import AudioVADConfig

from ..models.capturer import AudioSettings, ScreenSettings
from .common import as_mapping, parse_expired_in, resolve_path


def parse_vad_settings(data: object) -> AudioVADConfig:
    mapping = as_mapping(data, "capturer.audio.vad")
    return AudioVADConfig(
        enabled=bool(mapping.get("enabled", False)),
        aggressiveness=int(mapping.get("aggressiveness", 2)),
        frame_ms=int(mapping.get("frame_ms", 30)),
        pre_roll_seconds=float(mapping.get("pre_roll_seconds", 0.3)),
        min_speech_seconds=float(mapping.get("min_speech_seconds", 0.2)),
        min_silence_seconds=float(mapping.get("min_silence_seconds", 0.8)),
    )


def parse_audio_settings(data: object, config_dir: Path) -> AudioSettings:
    mapping = as_mapping(data, "capturer.audio")
    return AudioSettings(
        enabled=bool(mapping.get("enabled", False)),
        chunk_seconds=int(mapping.get("chunk_seconds", 30)),
        sample_rate=int(mapping.get("sample_rate", 16_000)),
        channels=int(mapping.get("channels", 1)),
        output_dir=resolve_path(mapping.get("output_dir", "captures/audio"), config_dir),
        expired_in=parse_expired_in(mapping.get("expired_in", 0), "capturer.audio.expired_in"),
        vad=parse_vad_settings(mapping.get("vad", {})),
    )


def parse_screen_settings(data: object, config_dir: Path) -> ScreenSettings:
    mapping = as_mapping(data, "capturer.screen")
    return ScreenSettings(
        enabled=bool(mapping.get("enabled", False)),
        interval_seconds=int(mapping.get("interval_seconds", 5)),
        output_dir=resolve_path(mapping.get("output_dir", "captures/screen"), config_dir),
        expired_in=parse_expired_in(mapping.get("expired_in", 0), "capturer.screen.expired_in"),
    )
