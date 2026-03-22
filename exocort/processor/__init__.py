"""Processor: reads vault records and builds derived artifacts."""

from __future__ import annotations

from .engine import run_once
from .models import ProcessorConfig

__all__ = ["ProcessorConfig", "run_once"]
