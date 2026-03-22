"""Collector: receives audio/screen uploads and forwards to processing APIs via the shared config."""

from .config import CollectorConfig, EndpointConfig
from . import vault

__all__ = ["app", "main", "CollectorConfig", "EndpointConfig", "vault"]


def __getattr__(name: str):
    if name in ("app", "main"):
        from .app import app, main
        return app if name == "app" else main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
