from __future__ import annotations

import logging
import os

from dotenv import load_dotenv

from .models import MacAsrSettings


def _str(key: str, default: str) -> str:
    return os.getenv(key, default).strip()


def _float(key: str, default: float) -> float:
    raw = _str(key, str(default))
    try:
        return float(raw)
    except ValueError:
        return default


def _int(key: str, default: int) -> int:
    raw = _str(key, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


def _bool(key: str, default: bool) -> bool:
    raw = _str(key, "true" if default else "false").lower()
    return raw in {"1", "true", "yes", "on"}


def _probability(key: str, default: float) -> float:
    return max(0.0, min(1.0, _float(key, default)))


def _log_level(key: str, default: str) -> int:
    return getattr(logging, _str(key, default).upper(), logging.INFO)


def load_settings() -> MacAsrSettings:
    load_dotenv()
    return MacAsrSettings(
        host=_str("MAC_ASR_HOST", "127.0.0.1"),
        port=_int("MAC_ASR_PORT", 9092),
        locale=_str("MAC_ASR_LOCALE", "auto"),
        default_locale=_str("MAC_ASR_DEFAULT_LOCALE", "es"),
        transcription_timeout_s=max(3.0, _float("MAC_ASR_TRANSCRIPTION_TIMEOUT_S", 30.0)),
        prompt_permission=_bool("MAC_ASR_PROMPT_PERMISSION", True),
        log_level=_log_level("MAC_ASR_LOG_LEVEL", "INFO"),
        detect_model=_str("MAC_ASR_DETECT_MODEL", "tiny"),
        detect_device=_str("MAC_ASR_DETECT_DEVICE", "cpu"),
        detect_compute_type=_str("MAC_ASR_DETECT_COMPUTE_TYPE", "int8"),
        detect_discard_min_prob=_probability(
            "MAC_ASR_DETECT_DISCARD_MIN_PROB",
            _float("MAC_ASR_DETECT_MIN_PROB", 0.5),
        ),
        detect_default_min_prob=_probability("MAC_ASR_DETECT_DEFAULT_MIN_PROB", 0.7),
    )


__all__ = ["MacAsrSettings", "load_settings"]
