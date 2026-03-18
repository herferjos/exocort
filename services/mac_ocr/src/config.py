from __future__ import annotations

import logging
import os


def _env(key: str, default: str) -> str:
    raw = os.getenv(key)
    return raw.strip() if raw else default


def _env_float(key: str, default: float) -> float:
    try:
        return float(_env(key, str(default)))
    except ValueError:
        return default


HOST = _env("MAC_OCR_HOST", "127.0.0.1")
PORT = int(_env_float("MAC_OCR_PORT", 9093))
LOG_LEVEL = getattr(logging, _env("MAC_OCR_LOG_LEVEL", "INFO").upper(), logging.INFO)

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s | %(levelname)s | %(message)s")
