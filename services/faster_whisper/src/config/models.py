from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FasterWhisperSettings:
    host: str
    port: int
    reload: bool
    log_level: str
    model_size: str
    model_path: Path
    device: str
    compute_type: str
    beam_size: int
    language: str | None
