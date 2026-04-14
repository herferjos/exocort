from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .common import EndpointSettings

AsrFormat = Literal["asr", "llm"]


@dataclass(slots=True, frozen=True)
class AsrEndpointSettings(EndpointSettings):
    format: AsrFormat = "asr"
    language: str = ""
    prompt: str = ""


@dataclass(slots=True, frozen=True)
class AsrOpenAISettings(AsrEndpointSettings):
    provider: Literal["openai"] = "openai"
    format: Literal["asr"] = "asr"


@dataclass(slots=True, frozen=True)
class AsrGeminiSettings(AsrEndpointSettings):
    provider: Literal["gemini"] = "gemini"
    format: Literal["llm"] = "llm"


@dataclass(slots=True, frozen=True)
class AsrMistralSettings(AsrEndpointSettings):
    provider: Literal["mistral"] = "mistral"
    format: AsrFormat = "asr"


AsrSettings = AsrOpenAISettings | AsrGeminiSettings | AsrMistralSettings
