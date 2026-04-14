from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .common import EndpointSettings

OcrFormat = Literal["ocr", "llm"]


@dataclass(slots=True, frozen=True)
class OcrEndpointSettings(EndpointSettings):
    format: OcrFormat = "llm"
    language: str = ""
    prompt: str = ""


@dataclass(slots=True, frozen=True)
class OcrOpenAISettings(OcrEndpointSettings):
    provider: Literal["openai"] = "openai"
    format: Literal["llm"] = "llm"


@dataclass(slots=True, frozen=True)
class OcrGeminiSettings(OcrEndpointSettings):
    provider: Literal["gemini"] = "gemini"
    format: Literal["llm"] = "llm"


@dataclass(slots=True, frozen=True)
class OcrAnthropicSettings(OcrEndpointSettings):
    provider: Literal["anthropic"] = "anthropic"
    format: Literal["llm"] = "llm"


@dataclass(slots=True, frozen=True)
class OcrMistralSettings(OcrEndpointSettings):
    provider: Literal["mistral"] = "mistral"
    format: Literal["ocr", "llm"] = "ocr"


OcrSettings = OcrOpenAISettings | OcrGeminiSettings | OcrAnthropicSettings | OcrMistralSettings
