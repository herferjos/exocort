from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MacAsrSettings:
    host: str
    port: int
    locale: str
    default_locale: str
    transcription_timeout_s: float
    prompt_permission: bool
    log_level: int
    detect_model: str
    detect_device: str
    detect_compute_type: str
    detect_discard_min_prob: float
    detect_default_min_prob: float
