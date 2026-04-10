from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MacOcrSettings:
    host: str
    port: int
    reload: bool
    log_level: str
