from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import re
from typing import Any

import yaml

from exocort.capturer.audio.vad import AudioVADConfig

from .models import (
    AudioSettings,
    CapturerSettings,
    ContentFilterRule,
    ContentFilterSettings,
    EndpointSettings,
    ExocortSettings,
    NotesSettings,
    ProcessorSettings,
    ScreenSettings,
)

def load_config(path: Path) -> ExocortSettings:
    config_dir = path.expanduser().resolve().parent
    data = yaml.safe_load(path.read_text())
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ValueError("Config file must contain a YAML mapping at the top level.")
    capturer = _as_mapping(data.get("capturer", {}), "capturer")
    return ExocortSettings(
        capturer=CapturerSettings(
            audio=_parse_audio_settings(capturer.get("audio", data.get("audio", {})), config_dir),
            screen=_parse_screen_settings(capturer.get("screen", data.get("screen", {})), config_dir),
        ),
        processor=_parse_processor_settings(data.get("processor", {}), config_dir),
    )


def _parse_audio_settings(data: object, config_dir: Path) -> AudioSettings:
    mapping = _as_mapping(data, "audio")
    return AudioSettings(
        enabled=bool(mapping.get("enabled", False)),
        chunk_seconds=int(mapping.get("chunk_seconds", 30)),
        sample_rate=int(mapping.get("sample_rate", 16_000)),
        channels=int(mapping.get("channels", 1)),
        output_dir=_resolve_path(mapping.get("output_dir", "captures/audio"), config_dir),
        expired_in=_parse_expired_in(mapping.get("expired_in", 0), "capturer.audio.expired_in"),
        vad=_parse_vad_settings(mapping.get("vad", {})),
    )


def _parse_vad_settings(data: object) -> AudioVADConfig:
    mapping = _as_mapping(data, "audio.vad")
    return AudioVADConfig(
        enabled=bool(mapping.get("enabled", False)),
        aggressiveness=int(mapping.get("aggressiveness", 2)),
        frame_ms=int(mapping.get("frame_ms", 30)),
        pre_roll_seconds=float(mapping.get("pre_roll_seconds", 0.3)),
        min_speech_seconds=float(mapping.get("min_speech_seconds", 0.2)),
        min_silence_seconds=float(mapping.get("min_silence_seconds", 0.8)),
    )


def _parse_screen_settings(data: object, config_dir: Path) -> ScreenSettings:
    mapping = _as_mapping(data, "screen")
    return ScreenSettings(
        enabled=bool(mapping.get("enabled", False)),
        interval_seconds=int(mapping.get("interval_seconds", 5)),
        output_dir=_resolve_path(mapping.get("output_dir", "captures/screen"), config_dir),
        expired_in=_parse_expired_in(mapping.get("expired_in", 0), "capturer.screen.expired_in"),
    )


def _parse_endpoint_settings(data: object, label: str) -> EndpointSettings:
    mapping = _as_mapping(data, "endpoint")
    enabled = mapping.get("enabled")
    if enabled is None:
        enabled = bool(mapping.get("model") and mapping.get("api_base"))
    return EndpointSettings(
        enabled=bool(enabled),
        model=str(mapping.get("model", "")),
        api_base=str(mapping.get("api_base", "")),
        api_key_env=str(mapping.get("api_key_env", "test_key")),
        expired_in=_parse_expired_in(mapping.get("expired_in", 0), label),
    )


def _parse_processor_settings(data: object, config_dir: Path) -> ProcessorSettings:
    mapping = _as_mapping(data, "processor")
    content_filter_data = mapping.get("content_filter", mapping.get("sensitive_data", {}))
    return ProcessorSettings(
        watch_dir=_resolve_path(mapping.get("watch_dir", "captures"), config_dir),
        output_dir=_resolve_path(mapping.get("output_dir", "captures/processed"), config_dir),
        ocr=_parse_endpoint_settings(mapping.get("ocr", {}), "processor.ocr.expired_in"),
        asr=_parse_endpoint_settings(mapping.get("asr", {}), "processor.asr.expired_in"),
        content_filter=_parse_content_filter_settings(content_filter_data),
        notes=_parse_notes_settings(mapping.get("notes", {}), config_dir),
    )


def _parse_notes_settings(data: object, config_dir: Path) -> NotesSettings:
    mapping = _as_mapping(data, "processor.notes")
    max_concurrent_batch = mapping.get("max_concurrent_batch", mapping.get("max_cocurrent_batch", 4))
    return NotesSettings(
        enabled=bool(mapping.get("enabled", False)),
        interval_seconds=int(mapping.get("interval_seconds", 60)),
        max_input_tokens=int(mapping.get("max_input_tokens", 10_000)),
        max_concurrent_batch=int(max_concurrent_batch),
        vault_dir=_resolve_path(mapping.get("vault_dir", "captures/vault"), config_dir),
        state_dir=_resolve_path(mapping.get("state_dir", "captures/processed/notes"), config_dir),
        model=str(mapping.get("model", "")),
        api_base=str(mapping.get("api_base", "")),
        api_key_env=str(mapping.get("api_key_env", "test_key")),
        temperature=float(mapping.get("temperature", 0.0)),
        max_tool_iterations=int(mapping.get("max_tool_iterations", 8)),
        system_prompt=str(mapping.get("system_prompt", "")),
    )


def _parse_content_filter_settings(data: object) -> ContentFilterSettings:
    mapping = _as_mapping(data, "processor.content_filter")
    rules_value = mapping.get("rules", [])
    if not isinstance(rules_value, list):
        raise ValueError("processor.content_filter.rules must be a list.")

    rules: list[ContentFilterRule] = []
    for index, item in enumerate(rules_value, start=1):
        rule = _as_mapping(item, f"processor.content_filter.rules[{index}]")
        keywords = _parse_string_list(
            rule.get("keywords", []),
            f"processor.content_filter.rules[{index}].keywords",
        )
        regexes = _parse_string_list(
            rule.get("regexes", []),
            f"processor.content_filter.rules[{index}].regexes",
        )
        if not keywords and not regexes:
            raise ValueError(
                f"processor.content_filter.rules[{index}] must define keywords or regexes."
            )
        for regex in regexes:
            try:
                re.compile(regex)
            except re.error as exc:
                raise ValueError(
                    f"processor.content_filter.rules[{index}].regexes contains an invalid regex: {exc}"
                ) from exc
        name = str(rule.get("name", f"rule_{index}")).strip() or f"rule_{index}"
        rules.append(
            ContentFilterRule(
                name=name,
                keywords=tuple(keywords),
                regexes=tuple(regexes),
            )
        )

    return ContentFilterSettings(
        enabled=bool(mapping.get("enabled", False)),
        rules=tuple(rules),
    )


def _as_mapping(data: object, label: str) -> dict[str, Any]:
    if isinstance(data, Mapping):
        return dict(data)
    raise ValueError(f"{label} section must be a mapping.")


def _resolve_path(value: object, config_dir: Path) -> Path:
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path
    return (config_dir / path).resolve()


def _parse_expired_in(value: object, label: str) -> int:
    seconds = int(value)
    if seconds < 0:
        raise ValueError(f"{label} must be greater than or equal to 0.")
    return seconds


def _parse_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list.")
    items: list[str] = []
    for item in value:
        text = str(item).strip()
        if not text:
            raise ValueError(f"{label} must not contain empty values.")
        items.append(text)
    return items
