from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .common import MediaInput

OcrFormat = Literal["ocr", "llm"]


@dataclass(slots=True, frozen=True)
class OcrRequest:
    media: MediaInput
    model: str
    format: OcrFormat = "llm"
    prompt: str | None = None


@dataclass(slots=True, frozen=True)
class OcrPage:
    index: int
    text: str


@dataclass(slots=True, frozen=True)
class OcrResult:
    text: str
    pages: tuple[OcrPage, ...] = ()
    raw: dict[str, object] | None = None
