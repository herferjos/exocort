"""Environment-based settings."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")


def _str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key, "").strip().lower()
    if not val:
        return default
    return val in ("1", "true", "yes", "on")


def _int(key: str, default: int = 0) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


def _float(key: str, default: float = 0.0) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default


def _latency(key: str) -> str | float | None:
    raw = _str(key)
    if not raw:
        return None
    lowered = raw.lower()
    if lowered in ("low", "high"):
        return lowered
    try:
        return float(raw)
    except ValueError:
        return None


def _path(key: str, default: Path | None = None) -> Path:
    raw = _str(key)
    if not raw:
        return default or Path.cwd()
    return Path(raw).expanduser().resolve()


def log_level() -> str:
    """Log level for all components (audio, screen, collector)."""
    return _str("LOG_LEVEL", "INFO")


# -----------------------------------------------------------------------------
# Audio capture
# -----------------------------------------------------------------------------


def audio_capture_enabled() -> bool:
    return _bool("AUDIO_CAPTURE_ENABLED", False)


def audio_capture_spool_dir() -> Path:
    return _path("AUDIO_CAPTURE_SPOOL_DIR", _project_root / "tmp" / "audio")


def audio_capture_request_timeout_s() -> float:
    return _float("AUDIO_CAPTURE_REQUEST_TIMEOUT_S", 30.0)


def audio_capture_max_upload_per_cycle() -> int:
    return _int("AUDIO_CAPTURE_MAX_UPLOAD_PER_CYCLE", 5)


def audio_capture_min_rms() -> int:
    return _int("AUDIO_CAPTURE_MIN_RMS", 0)


def audio_capture_reconnect_delay_s() -> float:
    return _float("AUDIO_CAPTURE_RECONNECT_DELAY_S", 5.0)


def audio_capture_sample_rate() -> int:
    return _int("AUDIO_CAPTURE_SAMPLE_RATE", 16000)


def audio_capture_target_sample_rate() -> int:
    return _int("AUDIO_CAPTURE_TARGET_SAMPLE_RATE", 16000)


def audio_capture_frame_ms() -> int:
    return _int("AUDIO_CAPTURE_FRAME_MS", 20)


def audio_capture_vad_mode() -> int:
    return _int("AUDIO_CAPTURE_VAD_MODE", 2)


def audio_capture_start_rms() -> int:
    return _int("AUDIO_CAPTURE_START_RMS", 150)


def audio_capture_continue_rms() -> int:
    return _int("AUDIO_CAPTURE_CONTINUE_RMS", 100)


def audio_capture_start_trigger_ms() -> int:
    return _int("AUDIO_CAPTURE_START_TRIGGER_MS", 120)


def audio_capture_start_window_ms() -> int:
    return _int("AUDIO_CAPTURE_START_WINDOW_MS", 400)


def audio_capture_end_silence_ms() -> int:
    return _int("AUDIO_CAPTURE_END_SILENCE_MS", 700)


def audio_capture_pre_roll_ms() -> int:
    return _int("AUDIO_CAPTURE_PRE_ROLL_MS", 300)


def audio_capture_min_segment_ms() -> int:
    return _int("AUDIO_CAPTURE_MIN_SEGMENT_MS", 500)


def audio_capture_max_segment_ms() -> int:
    return _int("AUDIO_CAPTURE_MAX_SEGMENT_MS", 30_000)


def audio_capture_input_device() -> str | None:
    raw = _str("AUDIO_CAPTURE_INPUT_DEVICE")
    return raw or None


def audio_capture_latency() -> str | float | None:
    return _latency("AUDIO_CAPTURE_LATENCY")


def audio_capture_gain_db() -> float:
    return _float("AUDIO_CAPTURE_GAIN_DB", 0.0)


def audio_capture_mac_helper_path() -> str | None:
    raw = _str("AUDIO_CAPTURE_MAC_HELPER_PATH")
    return raw or None


def audio_capture_diagnostic_s() -> float:
    return max(0.0, _float("AUDIO_CAPTURE_DIAGNOSTIC_S", 0.0))


def audio_capture_system_enabled() -> bool:
    return _bool("AUDIO_CAPTURE_SYSTEM_ENABLED", False)


def audio_capture_system_input_device() -> str | None:
    raw = _str("AUDIO_CAPTURE_SYSTEM_INPUT_DEVICE")
    return raw or None


def audio_capture_system_channels() -> int:
    return max(1, _int("AUDIO_CAPTURE_SYSTEM_CHANNELS", 2))


def audio_capture_system_latency() -> str | float | None:
    return _latency("AUDIO_CAPTURE_SYSTEM_LATENCY")


def audio_capture_system_vad_mode() -> int:
    return _int("AUDIO_CAPTURE_SYSTEM_VAD_MODE", 2)


def audio_capture_system_start_rms() -> int:
    return _int("AUDIO_CAPTURE_SYSTEM_START_RMS", 150)


def audio_capture_system_continue_rms() -> int:
    return _int("AUDIO_CAPTURE_SYSTEM_CONTINUE_RMS", 100)


def audio_capture_system_start_trigger_ms() -> int:
    return _int("AUDIO_CAPTURE_SYSTEM_START_TRIGGER_MS", 120)


def audio_capture_system_start_window_ms() -> int:
    return _int("AUDIO_CAPTURE_SYSTEM_START_WINDOW_MS", 400)


def audio_capture_system_end_silence_ms() -> int:
    return _int("AUDIO_CAPTURE_SYSTEM_END_SILENCE_MS", 700)


def audio_capture_system_pre_roll_ms() -> int:
    return _int("AUDIO_CAPTURE_SYSTEM_PRE_ROLL_MS", 300)


def audio_capture_system_min_segment_ms() -> int:
    return _int("AUDIO_CAPTURE_SYSTEM_MIN_SEGMENT_MS", 500)


def audio_capture_system_max_segment_ms() -> int:
    return _int("AUDIO_CAPTURE_SYSTEM_MAX_SEGMENT_MS", 30_000)


# -----------------------------------------------------------------------------
# Screen capture
# -----------------------------------------------------------------------------


def screen_capture_enabled() -> bool:
    return _bool("SCREEN_CAPTURE_ENABLED", False)


def screen_capture_tmp_dir() -> Path:
    return _path("SCREEN_CAPTURE_TMP_DIR", _project_root / "tmp" / "screen")


def screen_capture_fps() -> float:
    return _float("SCREEN_CAPTURE_FPS", 1.0)


def screen_capture_request_timeout_s() -> float:
    return _float("SCREEN_CAPTURE_REQUEST_TIMEOUT_S", 30.0)


def screen_capture_prompt_permission() -> bool:
    return _bool("SCREEN_CAPTURE_PROMPT_PERMISSION", False)


def screen_capture_dedup_window_s() -> float:
    """Don't re-upload the same screen hash within this many seconds."""
    return max(60.0, _float("SCREEN_CAPTURE_DEDUP_WINDOW_S", 300.0))


# -----------------------------------------------------------------------------
# Collector
# -----------------------------------------------------------------------------


def collector_enabled() -> bool:
    return _bool("COLLECTOR_ENABLED", True)


def collector_audio_url() -> str:
    return _str("COLLECTOR_AUDIO_URL", "http://127.0.0.1:8000/api/audio")


def collector_screen_url() -> str:
    return _str("COLLECTOR_SCREEN_URL", "http://127.0.0.1:8000/api/screen")


def collector_tmp_dir() -> Path:
    return _path("COLLECTOR_TMP_DIR", _project_root / "tmp" / "collector")


def collector_vault_dir() -> Path:
    return _path("COLLECTOR_VAULT_DIR", _project_root / "vault")
