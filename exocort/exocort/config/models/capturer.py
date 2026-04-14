from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from exocort.capturer.audio.vad import AudioVADConfig


@dataclass(slots=True, frozen=True)
class AudioSettings:
    enabled: bool = False
    chunk_seconds: int = 30
    sample_rate: int = 16_000
    channels: int = 1
    output_dir: Path = field(default_factory=lambda: Path("captures") / "audio")
    expired_in: int | bool = 0
    vad: AudioVADConfig = field(default_factory=AudioVADConfig)


@dataclass(slots=True, frozen=True)
class ScreenSettings:
    enabled: bool = False
    interval_seconds: int = 5
    output_dir: Path = field(default_factory=lambda: Path("captures") / "screen")
    expired_in: int | bool = 0


@dataclass(slots=True, frozen=True)
class CapturerSettings:
    audio: AudioSettings = field(default_factory=AudioSettings)
    screen: ScreenSettings = field(default_factory=ScreenSettings)
