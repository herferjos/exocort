from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomllib


@dataclass
class FasterWhisperSettings:
    model_path: str
    device: str
    compute_type: str
    vad_filter: bool
    beam_size: int
    language: str | None


def _default_config_path() -> Path:
    return Path(__file__).with_suffix(".toml")


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Faster Whisper config not found: {path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Faster Whisper config must be a TOML table")
    return data


def load_settings(path: Path | None = None) -> FasterWhisperSettings:
    cfg_path = path or _default_config_path()
    data = _load_toml(cfg_path)

    model_path = str(data.get("model_path") or "medium")
    device = str(data.get("device") or "cpu")
    compute_type = str(data.get("compute_type") or "int8")
    vad_filter = bool(data.get("vad_filter") or False)
    beam_size = int(data.get("beam_size") or 5)
    language = data.get("language")
    if isinstance(language, str):
        language = language.strip() or None
    else:
        language = None

    return FasterWhisperSettings(
        model_path=model_path,
        device=device,
        compute_type=compute_type,
        vad_filter=vad_filter,
        beam_size=beam_size,
        language=language,
    )


__all__ = ["FasterWhisperSettings", "load_settings"]
