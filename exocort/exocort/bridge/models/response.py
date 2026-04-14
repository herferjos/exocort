from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class ToolCall:
    id: str | None
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True, frozen=True)
class ResponseRequest:
    model: str
    messages: tuple[dict[str, Any], ...]
    tools: tuple[dict[str, Any], ...] = ()
    tool_choice: str | dict[str, Any] | None = None
    temperature: float | None = None


@dataclass(slots=True, frozen=True)
class ResponseResult:
    message: dict[str, Any]
    text: str
    tool_calls: tuple[ToolCall, ...] = ()
    raw: dict[str, Any] | None = None
