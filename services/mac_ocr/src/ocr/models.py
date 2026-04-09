from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class OcrLine:
    text: str
    confidence: float
    x: float
    y: float
    width: float
    height: float
