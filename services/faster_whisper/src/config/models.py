from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FasterWhisperSettings:
    host: str
    port: int
    reload: bool
    log_level: str
    model_path: str
    device: str
    compute_type: str
    beam_size: int
    language: str | None
