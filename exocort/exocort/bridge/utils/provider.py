from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

Provider = Literal["openai", "gemini", "anthropic", "mistral"]

KNOWN_PROVIDERS: tuple[Provider, ...] = ("openai", "gemini", "anthropic", "mistral")


def split_model_provider(model: str) -> tuple[Provider | None, str]:
    raw_model = model.strip()
    if "/" not in raw_model:
        return None, raw_model

    prefix, suffix = raw_model.split("/", 1)
    provider = prefix.strip().lower()
    if provider in KNOWN_PROVIDERS and suffix.strip():
        return provider, suffix.strip()  # type: ignore[return-value]
    return None, raw_model


def infer_provider(model: str, api_base: str, configured_provider: str = "") -> Provider:
    value = configured_provider.strip().lower()
    if value in KNOWN_PROVIDERS:
        return value  # type: ignore[return-value]

    provider, _ = split_model_provider(model)
    if provider is not None:
        return provider

    host = urlparse(api_base).netloc.lower()
    path = urlparse(api_base).path.lower()
    combined = f"{host}{path}"
    if "googleapis.com" in combined or "generativelanguage" in combined or "gemini" in combined:
        return "gemini"
    if "anthropic.com" in combined:
        return "anthropic"
    if "mistral.ai" in combined or "voxtral" in combined:
        return "mistral"
    return "openai"
