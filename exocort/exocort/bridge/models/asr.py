from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .common import MediaInput

AsrFormat = Literal["asr", "llm"]


@dataclass(slots=True, frozen=True)
class AsrRequest:
    media: MediaInput
    model: str
    format: AsrFormat = "asr"
    prompt: str | None = None
    language: str | None = None
    temperature: float | None = None


@dataclass(slots=True, frozen=True)
class AsrResult:
    text: str
    segments: tuple[dict[str, object], ...] = ()
    language: str | None = None
    raw: dict[str, object] | None = None
