from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import tomllib

from exocort.capturer.audio.config import AudioCaptureConfig
from exocort.capturer.screen.config import ScreenCaptureConfig


@dataclass(slots=True)
class AudioRunnerConfig:
    enabled: bool = False
    chunk_seconds: int = 30
    sample_rate: int = 16_000
    channels: int = 1


@dataclass(slots=True)
class ScreenRunnerConfig:
    enabled: bool = False
    interval_seconds: int = 5


@dataclass(slots=True)
class ExocortConfig:
    audio: AudioRunnerConfig = field(default_factory=AudioRunnerConfig)
    screen: ScreenRunnerConfig = field(default_factory=ScreenRunnerConfig)

    @property
    def audio_capture(self) -> AudioCaptureConfig:
        return AudioCaptureConfig(
            chunk_seconds=self.audio.chunk_seconds,
            sample_rate=self.audio.sample_rate,
            channels=self.audio.channels,
        )

    @property
    def screen_capture(self) -> ScreenCaptureConfig:
        return ScreenCaptureConfig(interval_seconds=self.screen.interval_seconds)


def load_config(path: str | Path) -> ExocortConfig:
    config_path = Path(path)
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    return parse_config(raw)


def parse_config(raw: dict[str, Any]) -> ExocortConfig:
    audio_raw = _get_table(raw, "audio")
    screen_raw = _get_table(raw, "screen")

    return ExocortConfig(
        audio=AudioRunnerConfig(
            enabled=bool(audio_raw.get("enabled", False)),
            chunk_seconds=int(audio_raw.get("chunk_seconds", AudioCaptureConfig.chunk_seconds)),
            sample_rate=int(audio_raw.get("sample_rate", AudioCaptureConfig.sample_rate)),
            channels=int(audio_raw.get("channels", AudioCaptureConfig.channels)),
        ),
        screen=ScreenRunnerConfig(
            enabled=bool(screen_raw.get("enabled", False)),
            interval_seconds=int(
                screen_raw.get("interval_seconds", ScreenCaptureConfig.interval_seconds)
            )
        ),
    )


def _get_table(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"Config section '{key}' must be a table/object.")
    return value
