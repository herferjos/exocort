"""Shared helpers for format adapters: placeholder rendering and file replacements."""

from __future__ import annotations

import base64
from typing import Any


def render_placeholders(value: Any, replacements: dict[str, Any]) -> Any:
    """Recursively replace {{key}} placeholders in dict/list/string values."""
    if isinstance(value, dict):
        return {k: render_placeholders(v, replacements) for k, v in value.items()}
    if isinstance(value, list):
        return [render_placeholders(v, replacements) for v in value]
    if isinstance(value, str):
        if value.startswith("{{") and value.endswith("}}"):
            key = value[2:-2].strip()
            return replacements.get(key, value)
        out = value
        for key, replacement in replacements.items():
            out = out.replace(f"{{{{{key}}}}}", str(replacement))
        return out
    return value


def _audio_format_from_content_type(content_type: str) -> str:
    """Map content type to audio format (e.g. for Gemini input_audio)."""
    ct = (content_type or "").lower()
    if "wav" in ct:
        return "wav"
    if "mp3" in ct or "mpeg" in ct:
        return "mp3"
    if "webm" in ct:
        return "webm"
    if "ogg" in ct:
        return "ogg"
    if "flac" in ct:
        return "flac"
    return "wav"


def file_replacements(
    file_content: bytes,
    filename: str,
    content_type: str,
    stream_type: str | None = None,
) -> dict[str, Any]:
    """Build placeholder dict for file: base64, data_url, mime_type, filename, optional stream_type and audio_format."""
    b64 = base64.standard_b64encode(file_content).decode("ascii")
    mime = content_type or "application/octet-stream"
    out: dict[str, Any] = {
        "file.base64": b64,
        "file.data_url": f"data:{mime};base64,{b64}",
        "file.mime_type": mime,
        "file.filename": filename,
        "file.audio_format": _audio_format_from_content_type(content_type),
    }
    if stream_type is not None:
        out["file.stream_type"] = stream_type
    return out
