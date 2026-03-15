"""Provider format adapters: build requests and parse responses per endpoint format."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BuiltRequest, FormatAdapter, ParsedResponse
from .default import DefaultAdapter
from .openai import OpenAIAdapter

if TYPE_CHECKING:
    from exocort.collector.config import EndpointConfig

_REGISTRY: dict[str, FormatAdapter] = {
    "default": DefaultAdapter(),
    "openai": OpenAIAdapter(),
}


def get_adapter(format_code: str) -> FormatAdapter:
    """Return the adapter for the given format code (e.g. 'default', 'openai')."""
    code = (format_code or "default").strip().lower()
    adapter = _REGISTRY.get(code)
    if adapter is None:
        return _REGISTRY["default"]
    return adapter
