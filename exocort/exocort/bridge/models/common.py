from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ..utils.provider import Provider

Mode = Literal["asr", "ocr", "response"]


@dataclass(slots=True, frozen=True)
class MediaInput:
    file_path: Path | None = None
    url: str | None = None
    base64: str | None = None
    mime_type: str | None = None


@dataclass(slots=True, frozen=True)
class ProviderConfig:
    provider: Provider
    api_base: str
    api_key_env: str
    timeout_s: float = 30.0
    retries: int = 2
    format: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)
