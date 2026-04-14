from __future__ import annotations

from ..models.asr import AsrGeminiSettings, AsrMistralSettings, AsrOpenAISettings, AsrSettings
from .common import as_mapping, parse_endpoint_common, parse_format_value


def parse_asr_settings(data: object, label: str) -> AsrSettings:
    mapping = as_mapping(data, label)
    common = parse_endpoint_common(mapping, label)
    provider = common["provider"]
    format_value = parse_format_value(
        mapping.get("format"),
        f"{label}.format",
        allowed=("asr", "llm") if provider == "mistral" else ("llm",) if provider == "gemini" else ("asr",),
        default="asr" if provider in {"openai", "mistral"} else "llm",
    )

    if provider == "openai":
        if format_value != "asr":
            raise ValueError(f"{label} only supports format=asr for provider=openai.")
        return AsrOpenAISettings(
            **common,
            format="asr",
            language=str(mapping.get("language", "") or ""),
            prompt=str(mapping.get("prompt", "") or ""),
        )
    if provider == "gemini":
        if format_value != "llm":
            raise ValueError(f"{label} only supports format=llm for provider=gemini.")
        return AsrGeminiSettings(
            **common,
            format="llm",
            language=str(mapping.get("language", "") or ""),
            prompt=str(mapping.get("prompt", "") or ""),
        )
    if provider == "mistral":
        if format_value in {"asr", "llm"}:
            return AsrMistralSettings(
                **common,
                format=format_value,
                language=str(mapping.get("language", "") or ""),
                prompt=str(mapping.get("prompt", "") or ""),
            )
        raise ValueError(f"{label} only supports format=asr or llm for provider=mistral.")
    raise ValueError(f"{label} does not support provider={provider}.")
