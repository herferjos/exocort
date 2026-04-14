from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .asr import AsrOpenAISettings, AsrSettings
from .common import ContentFilterSettings
from .ocr import OcrMistralSettings, OcrSettings
from .notes import NotesSettings

@dataclass(slots=True, frozen=True)
class ProcessorSettings:
    watch_dir: Path = field(default_factory=lambda: Path("captures"))
    output_dir: Path = field(default_factory=lambda: Path("captures") / "processed")
    ocr: OcrSettings = field(default_factory=lambda: OcrMistralSettings())
    asr: AsrSettings = field(default_factory=lambda: AsrOpenAISettings())
    content_filter: ContentFilterSettings = field(default_factory=ContentFilterSettings)
    notes: NotesSettings = field(default_factory=NotesSettings)
