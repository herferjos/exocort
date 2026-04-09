from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FasterWhisperSettings:
    host: str
    port: int
    model_path: str
    device: str
    compute_type: str
    beam_size: int
    language: str | None
