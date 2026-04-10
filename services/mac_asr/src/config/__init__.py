from __future__ import annotations

from common import EnvReader

from .models import MacAsrSettings


def _probability(env: EnvReader, key: str, default: float) -> float:
    return max(0.0, min(1.0, env.float(key, default)))


def load_settings() -> MacAsrSettings:
    env = EnvReader()
    return MacAsrSettings(
        host=env.str("MAC_ASR_HOST", "127.0.0.1"),
        port=env.int("MAC_ASR_PORT", 9092),
        reload=env.bool("MAC_ASR_RELOAD", True),
        locale=env.str("MAC_ASR_LOCALE", "auto"),
        default_locale=env.str("MAC_ASR_DEFAULT_LOCALE", "es"),
        transcription_timeout_s=max(3.0, env.float("MAC_ASR_TRANSCRIPTION_TIMEOUT_S", 30.0)),
        prompt_permission=env.bool("MAC_ASR_PROMPT_PERMISSION", True),
        log_level=env.str("MAC_ASR_LOG_LEVEL", "info").lower(),
        detect_model=env.str("MAC_ASR_DETECT_MODEL", "tiny"),
        detect_device=env.str("MAC_ASR_DETECT_DEVICE", "cpu"),
        detect_compute_type=env.str("MAC_ASR_DETECT_COMPUTE_TYPE", "int8"),
        detect_discard_min_prob=_probability(
            env,
            "MAC_ASR_DETECT_DISCARD_MIN_PROB",
            env.float("MAC_ASR_DETECT_MIN_PROB", 0.5),
        ),
        detect_default_min_prob=_probability(env, "MAC_ASR_DETECT_DEFAULT_MIN_PROB", 0.7),
    )


__all__ = ["MacAsrSettings", "load_settings"]
