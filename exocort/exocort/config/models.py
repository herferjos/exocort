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
    expired_in: int = 0
    vad: AudioVADConfig = field(default_factory=AudioVADConfig)


@dataclass(slots=True, frozen=True)
class ScreenSettings:
    enabled: bool = False
    interval_seconds: int = 5
    output_dir: Path = field(default_factory=lambda: Path("captures") / "screen")
    expired_in: int = 0


@dataclass(slots=True, frozen=True)
class CapturerSettings:
    audio: AudioSettings = field(default_factory=AudioSettings)
    screen: ScreenSettings = field(default_factory=ScreenSettings)


@dataclass(slots=True, frozen=True)
class EndpointSettings:
    enabled: bool = False
    model: str = ""
    api_base: str = ""
    api_key_env: str = "test_key"
    expired_in: int = 0


@dataclass(slots=True, frozen=True)
class ContentFilterRule:
    name: str
    keywords: tuple[str, ...] = ()
    regexes: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class ContentFilterSettings:
    enabled: bool = False
    rules: tuple[ContentFilterRule, ...] = ()


@dataclass(slots=True, frozen=True)
class NotesSettings:
    enabled: bool = False
    interval_seconds: int = 60
    max_input_tokens: int = 10_000
    max_concurrent_batch: int = 4
    vault_dir: Path = field(default_factory=lambda: Path("captures") / "vault")
    state_dir: Path = field(default_factory=lambda: Path("captures") / "processed" / "notes")
    model: str = ""
    api_base: str = ""
    api_key_env: str = "test_key"
    temperature: float = 0.0
    max_tool_iterations: int = 8
    system_prompt: str = ""


@dataclass(slots=True, frozen=True)
class ProcessorSettings:
    watch_dir: Path = field(default_factory=lambda: Path("captures"))
    output_dir: Path = field(default_factory=lambda: Path("captures") / "processed")
    ocr: EndpointSettings = field(default_factory=EndpointSettings)
    asr: EndpointSettings = field(default_factory=EndpointSettings)
    content_filter: ContentFilterSettings = field(default_factory=ContentFilterSettings)
    notes: NotesSettings = field(default_factory=NotesSettings)


@dataclass(slots=True, frozen=True)
class ExocortSettings:
    capturer: CapturerSettings = field(default_factory=CapturerSettings)
    processor: ProcessorSettings = field(default_factory=ProcessorSettings)
