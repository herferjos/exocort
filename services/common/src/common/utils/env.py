from __future__ import annotations

import os

from dotenv import load_dotenv


class EnvReader:
    def __init__(self) -> None:
        load_dotenv()

    def str(self, key: str, default: str = "") -> str:
        return os.getenv(key, default).strip()

    def int(self, key: str, default: int) -> int:
        raw = self.str(key, str(default))
        try:
            return int(raw)
        except ValueError:
            return default

    def float(self, key: str, default: float) -> float:
        raw = self.str(key, str(default))
        try:
            return float(raw)
        except ValueError:
            return default

    def bool(self, key: str, default: bool) -> bool:
        raw = self.str(key, "true" if default else "false").lower()
        return raw in {"1", "true", "yes", "on"}


__all__ = ["EnvReader"]
