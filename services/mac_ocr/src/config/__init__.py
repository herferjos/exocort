from __future__ import annotations

from common import EnvReader

from .models import MacOcrSettings


def load_settings() -> MacOcrSettings:
    env = EnvReader()
    return MacOcrSettings(
        host=env.str("MAC_OCR_HOST", "127.0.0.1"),
        port=env.int("MAC_OCR_PORT", 9093),
        reload=env.bool("MAC_OCR_RELOAD", True),
        log_level=env.str("MAC_OCR_LOG_LEVEL", "info").lower(),
    )


__all__ = ["MacOcrSettings", "load_settings"]
