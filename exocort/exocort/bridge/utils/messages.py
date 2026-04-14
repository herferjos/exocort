from __future__ import annotations

from typing import Any

def text_from_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
        return "\n".join(parts).strip()
    return ""


def collect_tool_calls(message: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list):
        return ()

    normalized: list[dict[str, Any]] = []
    for item in tool_calls:
        if isinstance(item, dict):
            normalized.append(item)
    return tuple(normalized)
