"""Project settings loaded from a shared config file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import (
    config_path as _config_path,
    get_value,
    load_root_config,
    project_root,
)

_PROJECT_ROOT = project_root()


def _data() -> dict[str, Any]:
    return load_root_config()


def _str(*path: str, default: str = "") -> str:
    value = get_value(_data(), *path, default=default)
    if value is None:
        return default
    return str(value).strip()


def _bool(*path: str, default: bool = False) -> bool:
    value = get_value(_data(), *path, default=default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return bool(value) if value is not None else default


def _int(*path: str, default: int = 0) -> int:
    value = get_value(_data(), *path, default=default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(*path: str, default: float = 0.0) -> float:
    value = get_value(_data(), *path, default=default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _latency(*path: str) -> str | float | None:
    raw = _str(*path)
    if not raw:
        return None
    lowered = raw.lower()
    if lowered in ("low", "high"):
        return lowered
    try:
        return float(raw)
    except ValueError:
        return None


def _path(*path: str, default: Path | None = None) -> Path:
    raw = get_value(_data(), *path, default=None)
    if raw in (None, ""):
        return (default or Path.cwd()).expanduser().resolve()
    value = Path(str(raw)).expanduser()
    if value.is_absolute():
        return value.resolve()
    return (_config_path().parent / value).resolve()


def config_path() -> Path:
    return _config_path()


def log_level() -> str:
    return _str("runtime", "log_level", default="INFO")


def audio_capturer_enabled() -> bool:
    return _bool("runtime", "enable_audio_capturer", default=False)


def audio_capturer_spool_dir() -> Path:
    return _path(
        "capturer", "audio", "spool_dir", default=_PROJECT_ROOT / "tmp" / "audio"
    )

def audio_capturer_max_upload_per_cycle() -> int:
    return _int("capturer", "audio", "max_upload_per_cycle", default=5)


def audio_capturer_min_rms() -> int:
    return _int("capturer", "audio", "min_rms", default=0)


def audio_capturer_reconnect_delay_s() -> float:
    return _float("capturer", "audio", "reconnect_delay_s", default=5.0)


def audio_capturer_sample_rate() -> int:
    return _int("capturer", "audio", "sample_rate", default=8000)


def audio_capturer_target_sample_rate() -> int:
    return _int("capturer", "audio", "target_sample_rate", default=8000)


def audio_capturer_frame_ms() -> int:
    return _int("capturer", "audio", "frame_ms", default=20)


def audio_capturer_vad_mode() -> int:
    return _int("capturer", "audio", "vad_mode", default=2)


def audio_capturer_start_rms() -> int:
    return _int("capturer", "audio", "start_rms", default=150)


def audio_capturer_continue_rms() -> int:
    return _int("capturer", "audio", "continue_rms", default=100)


def audio_capturer_start_trigger_ms() -> int:
    return _int("capturer", "audio", "start_trigger_ms", default=120)


def audio_capturer_start_window_ms() -> int:
    return _int("capturer", "audio", "start_window_ms", default=400)


def audio_capturer_end_silence_ms() -> int:
    return _int("capturer", "audio", "end_silence_ms", default=700)


def audio_capturer_pre_roll_ms() -> int:
    return _int("capturer", "audio", "pre_roll_ms", default=300)


def audio_capturer_min_segment_ms() -> int:
    return _int("capturer", "audio", "min_segment_ms", default=500)


def audio_capturer_max_segment_ms() -> int:
    return _int("capturer", "audio", "max_segment_ms", default=30_000)


def audio_capturer_input_device() -> str | None:
    raw = _str("capturer", "audio", "input_device")
    return raw or None


def audio_capturer_latency() -> str | float | None:
    return _latency("capturer", "audio", "latency")


def audio_capturer_gain_db() -> float:
    return _float("capturer", "audio", "gain_db", default=0.0)


def audio_capturer_diagnostic_s() -> float:
    return max(0.0, _float("capturer", "audio", "diagnostic_s", default=0.0))


def audio_capturer_low_speech_ratio() -> float:
    return max(
        0.0, min(1.0, _float("capturer", "audio", "low_speech_ratio", default=0.2))
    )


def audio_capturer_low_speech_max_ms() -> int:
    return max(0, _int("capturer", "audio", "low_speech_max_ms", default=1600))


def screen_capturer_enabled() -> bool:
    return _bool("runtime", "enable_screen_capturer", default=False)


def screen_capturer_fps() -> float:
    return _float("capturer", "screen", "fps", default=0.5)


def screen_capturer_prompt_permission() -> bool:
    return _bool("capturer", "screen", "prompt_permission", default=False)


def screen_capturer_dedup_window_s() -> float:
    return max(60.0, _float("capturer", "screen", "dedup_window_s", default=300.0))


def screen_capturer_dedup_threshold() -> int:
    return _int("capturer", "screen", "dedup_threshold", default=5)


def vault_dir() -> Path:
    return _path("storage", "vault_dir", default=_PROJECT_ROOT / "vault" / "raw")
