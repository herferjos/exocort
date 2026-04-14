from __future__ import annotations

from ..models.ocr import (
    OcrAnthropicSettings,
    OcrGeminiSettings,
    OcrMistralSettings,
    OcrOpenAISettings,
    OcrSettings,
)
from .common import as_mapping, parse_endpoint_common, parse_format_value


def parse_ocr_settings(data: object, label: str) -> OcrSettings:
    mapping = as_mapping(data, label)
    common = parse_endpoint_common(mapping, label)
    provider = common["provider"]
    format_value = parse_format_value(
        mapping.get("format"),
        f"{label}.format",
        allowed=("llm", "ocr") if provider == "mistral" else ("llm",),
        default="ocr" if provider == "mistral" else "llm",
    )

    if provider == "openai":
        if format_value != "llm":
            raise ValueError(f"{label} only supports format=llm for provider=openai.")
        return OcrOpenAISettings(
            **common,
            format="llm",
            language=str(mapping.get("language", "") or ""),
            prompt=str(mapping.get("prompt", "") or ""),
        )
    if provider == "gemini":
        if format_value != "llm":
            raise ValueError(f"{label} only supports format=llm for provider=gemini.")
        return OcrGeminiSettings(
            **common,
            format="llm",
            language=str(mapping.get("language", "") or ""),
            prompt=str(mapping.get("prompt", "") or ""),
        )
    if provider == "anthropic":
        if format_value != "llm":
            raise ValueError(f"{label} only supports format=llm for provider=anthropic.")
        return OcrAnthropicSettings(
            **common,
            format="llm",
            language=str(mapping.get("language", "") or ""),
            prompt=str(mapping.get("prompt", "") or ""),
        )
    if provider == "mistral":
        if format_value in {"ocr", "llm"}:
            return OcrMistralSettings(
                **common,
                format=format_value,
                language=str(mapping.get("language", "") or ""),
                prompt=str(mapping.get("prompt", "") or ""),
            )
        raise ValueError(f"{label} only supports format=ocr or llm for provider=mistral.")
    raise ValueError(f"{label} does not support provider={provider}.")
