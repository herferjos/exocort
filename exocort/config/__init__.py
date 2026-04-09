from __future__ import annotations

from pathlib import Path
from typing import Any
import tomllib

from exocort.capturer.audio.vad import AudioVADConfig

from .models import (
    AudioCaptureSettings,
    AudioRunnerSettings,
    CaptureOutputSettings,
    EndpointSettings,
    ExocortSettings,
    FileProcessorSettings,
    ProcessingOutputSettings,
    ScreenCaptureSettings,
    ScreenRunnerSettings,
)


def load_config(path: str | Path) -> ExocortSettings:
    config_path = Path(path)
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    return parse_config(raw, base_dir=config_path.parent)


def parse_config(raw: dict[str, Any], base_dir: Path | None = None) -> ExocortSettings:
    base_dir = base_dir or Path.cwd()
    capturer_raw = _get_table(raw, "capturer")
    audio_raw = _get_table(capturer_raw, "audio")
    vad_raw = _get_table(audio_raw, "vad")
    screen_raw = _get_table(capturer_raw, "screen")
    processor_raw = _get_table(raw, "processor")
    processor_output_raw = _get_table(processor_raw, "output")
    processor_ocr_raw = _get_table(processor_raw, "ocr")
    processor_asr_raw = _get_table(processor_raw, "asr")

    capture_root = _resolve_path(
        capturer_raw.get("path"),
        base_dir,
        base_dir / "captures",
    )

    return ExocortSettings(
        capture=CaptureOutputSettings(root_path=capture_root),
        audio=AudioRunnerSettings(
            enabled=bool(audio_raw.get("enabled", False)),
            chunk_seconds=int(audio_raw.get("chunk_seconds", AudioCaptureSettings.chunk_seconds)),
            sample_rate=int(audio_raw.get("sample_rate", AudioCaptureSettings.sample_rate)),
            channels=int(audio_raw.get("channels", AudioCaptureSettings.channels)),
            vad=AudioVADConfig(
                enabled=bool(vad_raw.get("enabled", AudioVADConfig.enabled)),
                aggressiveness=int(vad_raw.get("aggressiveness", AudioVADConfig.aggressiveness)),
                frame_ms=int(vad_raw.get("frame_ms", AudioVADConfig.frame_ms)),
                pre_roll_seconds=float(
                    vad_raw.get("pre_roll_seconds", AudioVADConfig.pre_roll_seconds)
                ),
                min_speech_seconds=float(
                    vad_raw.get("min_speech_seconds", AudioVADConfig.min_speech_seconds)
                ),
                min_silence_seconds=float(
                    vad_raw.get("min_silence_seconds", AudioVADConfig.min_silence_seconds)
                ),
            ),
        ),
        screen=ScreenRunnerSettings(
            enabled=bool(screen_raw.get("enabled", False)),
            interval_seconds=int(
                screen_raw.get("interval_seconds", ScreenCaptureSettings.interval_seconds)
            ),
        ),
        processor=FileProcessorSettings(
            enabled=bool(processor_raw.get("enabled", False)),
            watch_dir=_resolve_path(
                processor_raw.get("watch_dir"),
                base_dir,
                capture_root,
            ),
            poll_interval_seconds=int(
                processor_raw.get(
                    "poll_interval_seconds",
                    FileProcessorSettings.poll_interval_seconds,
                )
            ),
            output=ProcessingOutputSettings(
                root_path=_resolve_path(
                    processor_output_raw.get("path"),
                    base_dir,
                    capture_root / "processed",
                )
            ),
            ocr=EndpointSettings(
                model=str(processor_ocr_raw.get("model", "")),
                api_base=str(processor_ocr_raw.get("api_base", "")),
                api_key_env=str(processor_ocr_raw.get("api_key_env", "")),
            ),
            asr=EndpointSettings(
                model=str(processor_asr_raw.get("model", "")),
                api_base=str(processor_asr_raw.get("api_base", "")),
                api_key_env=str(processor_asr_raw.get("api_key_env", "")),
            ),
        ),
    )


def _get_table(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"Config section '{key}' must be a table/object.")
    return value


def _resolve_path(value: Any | None, base_dir: Path, default: Path) -> Path:
    if value is None:
        resolved = default
    else:
        resolved = Path(value)
        if not resolved.is_absolute():
            resolved = base_dir / resolved
    return resolved.expanduser()


__all__ = [
    "AudioCaptureSettings",
    "AudioRunnerSettings",
    "CaptureOutputSettings",
    "EndpointSettings",
    "ExocortSettings",
    "FileProcessorSettings",
    "ProcessingOutputSettings",
    "ScreenCaptureSettings",
    "ScreenRunnerSettings",
    "load_config",
    "parse_config",
]
