from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from exocort.provider import Provider

if TYPE_CHECKING:
    from .capturer import CapturerSettings
    from .processor import ProcessorSettings


def _default_capturer_settings() -> CapturerSettings:
    from .capturer import CapturerSettings

    return CapturerSettings()


def _default_processor_settings() -> ProcessorSettings:
    from .processor import ProcessorSettings

    return ProcessorSettings()


@dataclass(slots=True, frozen=True)
class ExocortSettings:
    log_level: str = "INFO"
    capturer: CapturerSettings = field(default_factory=_default_capturer_settings)
    processor: ProcessorSettings = field(default_factory=_default_processor_settings)


@dataclass(slots=True, frozen=True)
class ContentFilterRule:
    name: str
    keywords: tuple[str, ...] = ()
    regexes: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class ContentFilterSettings:
    enabled: bool = False
    rules: tuple[ContentFilterRule, ...] = ()


@dataclass(slots=True, frozen=True)
class EndpointSettings:
    enabled: bool = False
    provider: Provider = "openai"
    model: str = ""
    api_base: str = ""
    api_key_env: str = "test_key"
    format: str = ""
    timeout_s: float = 30.0
    retries: int = 2
    expired_in: int | bool = 0
