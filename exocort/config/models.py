from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from exocort.capturer.audio.vad import AudioVADConfig


@dataclass(slots=True, frozen=True)
class AudioCaptureSettings:
    chunk_seconds: int = 30
    sample_rate: int = 16_000
    channels: int = 1
    output_dir: Path = field(default_factory=lambda: Path("captures") / "audio")
    vad: AudioVADConfig = field(default_factory=AudioVADConfig)


@dataclass(slots=True, frozen=True)
class ScreenCaptureSettings:
    interval_seconds: int = 5
    output_dir: Path = field(default_factory=lambda: Path("captures") / "screen")


@dataclass(slots=True, frozen=True)
class EndpointSettings:
    model: str = ""
    api_base: str = ""
    api_key_env: str = ""


@dataclass(slots=True, frozen=True)
class ProcessingOutputSettings:
    root_path: Path = field(default_factory=lambda: Path("captures") / "processed")


@dataclass(slots=True, frozen=True)
class FileProcessorSettings:
    enabled: bool = False
    watch_dir: Path = field(default_factory=lambda: Path("captures"))
    poll_interval_seconds: int = 5
    output: ProcessingOutputSettings = field(default_factory=ProcessingOutputSettings)
    ocr: EndpointSettings = field(default_factory=EndpointSettings)
    asr: EndpointSettings = field(default_factory=EndpointSettings)


@dataclass(slots=True, frozen=True)
class AudioRunnerSettings:
    enabled: bool = False
    chunk_seconds: int = 30
    sample_rate: int = 16_000
    channels: int = 1
    vad: AudioVADConfig = field(default_factory=AudioVADConfig)


@dataclass(slots=True, frozen=True)
class ScreenRunnerSettings:
    enabled: bool = False
    interval_seconds: int = 5


@dataclass(slots=True, frozen=True)
class CaptureOutputSettings:
    root_path: Path = Path("captures")

    @property
    def audio_dir(self) -> Path:
        return self.root_path / "audio"

    @property
    def screen_dir(self) -> Path:
        return self.root_path / "screen"


@dataclass(slots=True, frozen=True)
class ExocortSettings:
    capture: CaptureOutputSettings = field(default_factory=CaptureOutputSettings)
    audio: AudioRunnerSettings = field(default_factory=AudioRunnerSettings)
    screen: ScreenRunnerSettings = field(default_factory=ScreenRunnerSettings)
    processor: FileProcessorSettings = field(default_factory=FileProcessorSettings)

    @property
    def audio_capture(self) -> AudioCaptureSettings:
        return AudioCaptureSettings(
            chunk_seconds=self.audio.chunk_seconds,
            sample_rate=self.audio.sample_rate,
            channels=self.audio.channels,
            output_dir=self.capture.audio_dir,
            vad=self.audio.vad,
        )

    @property
    def screen_capture(self) -> ScreenCaptureSettings:
        return ScreenCaptureSettings(
            interval_seconds=self.screen.interval_seconds,
            output_dir=self.capture.screen_dir,
        )
