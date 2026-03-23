"""Small shared config loader for LiteLLM-backed services."""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .config import get_value, load_root_config

_FORMAT_PROVIDER_MAP = {
    "claude": "anthropic",
}


def _expand_env(value: str) -> str:
    if "${" not in value:
        return value
    for key, env_value in os.environ.items():
        value = value.replace(f"${{{key}}}", env_value)
    return value


def _expand_object(value: Any) -> Any:
    if isinstance(value, str):
        return _expand_env(value)
    if isinstance(value, list):
        return [_expand_object(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _expand_object(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class ServiceConfig:
    name: str
    endpoint: str
    format: str
    model: str
    prompt: str = ""
    api_key: str = ""
    timeout: float = 30.0
    headers: dict[str, str] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)

    @property
    def provider(self) -> str:
        raw = self.format.strip().lower()
        return _FORMAT_PROVIDER_MAP.get(raw, raw)

    @property
    def model(self) -> str:
        model = self.model.strip()
        if "/" in model:
            return model
        provider = self.provider
        return f"{provider}/{model}" if provider else model

    @property
    def base_url(self) -> str:
        parts = urlsplit(self.endpoint)
        if not parts.scheme or not parts.netloc:
            return self.endpoint.rstrip("/")
        return urlunsplit((parts.scheme, parts.netloc, "", "", "")).rstrip("/")


def load_service_config(name: str) -> ServiceConfig | None:
    data = load_root_config()
    block = get_value(data, "services", name, default={})
    if not isinstance(block, dict) or not block:
        return None

    raw_headers = block.get("headers") or {}
    headers = {str(key): _expand_env(str(value)) for key, value in raw_headers.items()}
    raw_options = block.get("options") or {}
    options = (
        _expand_object(copy.deepcopy(raw_options))
        if isinstance(raw_options, dict)
        else {}
    )

    endpoint = _expand_env(str(block.get("endpoint", "")).strip())
    format_name = _expand_env(str(block.get("format", "")).strip())
    model = _expand_env(str(block.get("model", "")).strip())
    if not endpoint or not format_name or not model:
        raise ValueError(f"[services.{name}] requires endpoint, format and model")

    return ServiceConfig(
        name=name,
        endpoint=endpoint,
        format=format_name,
        model=model,
        prompt=_expand_env(str(block.get("prompt", "")).strip()),
        api_key=_expand_env(str(block.get("api_key", "")).strip()),
        timeout=float(block.get("timeout", 30)),
        headers=headers,
        options=options,
    )
