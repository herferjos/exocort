from __future__ import annotations

import json
from typing import Any

from ..client import HttpClient
from ..models.ocr import OcrRequest, OcrResult
from ..models.response import ResponseRequest, ResponseResult, ToolCall
from ..utils.media import guess_mime_type, media_to_base64
from ..utils.messages import text_from_content
from ..utils.provider import split_model_provider
from .common import (
    api_key_json_headers,
    content_as_text_blocks,
    normalize_function_arguments,
    require_payload,
    single_page_ocr_result,
)

DEFAULT_OCR_PROMPT = "Extract the readable text from this image. Return only the extracted text."
ANTHROPIC_VERSION = "2023-06-01"


def ocr(
    client: HttpClient,
    api_base: str,
    api_key: str,
    req: OcrRequest,
    extra_headers: dict[str, str],
) -> OcrResult:
    prompt = req.prompt or DEFAULT_OCR_PROMPT
    result = response(
        client,
        api_base,
        api_key,
        ResponseRequest(
            model=req.model,
            messages=(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image", "media": req.media},
                    ],
                },
            ),
        ),
        extra_headers,
    )
    return single_page_ocr_result(result.text, result.raw or {}, "OCR page markdown")


def response(
    client: HttpClient,
    api_base: str,
    api_key: str,
    req: ResponseRequest,
    extra_headers: dict[str, str],
) -> ResponseResult:
    _, model = split_model_provider(req.model)
    headers = {
        **api_key_json_headers("x-api-key", api_key, extra_headers),
        "anthropic-version": ANTHROPIC_VERSION,
    }
    system_prompt, messages = _messages_for_anthropic(req.messages)
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": 2048,
        "messages": messages,
    }
    if system_prompt:
        payload["system"] = system_prompt
    if req.temperature is not None:
        payload["temperature"] = req.temperature
    if req.tools:
        payload["tools"] = [_tool_to_anthropic(tool) for tool in req.tools]
    response = client.post_json(_messages_url(api_base), headers=headers, payload=payload)
    payload_json = require_payload(response.json, "Anthropic")
    message, tool_calls = _message_from_response(payload_json)
    return ResponseResult(
        message=message,
        text=text_from_content(message.get("content")),
        tool_calls=tool_calls,
        raw=payload_json,
    )


def _messages_for_anthropic(messages: tuple[dict[str, Any], ...]) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    converted: list[dict[str, Any]] = []
    for message in messages:
        role = str(message.get("role", "user"))
        if role == "system":
            system_parts.append(text_from_content(message.get("content")))
            continue
        if role == "tool":
            converted.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": str(message.get("tool_call_id", "")),
                            "content": str(message.get("content", "")),
                        }
                    ],
                }
            )
            continue
        content = _content_blocks(message)
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list):
            for tool_call in tool_calls:
                if not isinstance(tool_call, dict):
                    continue
                function = tool_call.get("function")
                if not isinstance(function, dict):
                    continue
                arguments = normalize_function_arguments(function.get("arguments", "{}"))
                content.append(
                    {
                        "type": "tool_use",
                        "id": str(tool_call.get("id", "")),
                        "name": str(function.get("name", "")),
                        "input": arguments,
                    }
                )
        converted.append({"role": "assistant" if role == "assistant" else "user", "content": content})
    return "\n\n".join(part for part in system_parts if part).strip(), converted


def _content_blocks(message: dict[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content")
    blocks = content_as_text_blocks(content)
    if not isinstance(content, list):
        return blocks
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type", "text"))
        if item_type == "image":
            media = item.get("media")
            if media is None:
                continue
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": guess_mime_type(media),
                        "data": media_to_base64(media),
                    },
                }
            )
    return blocks


def _tool_to_anthropic(tool: dict[str, Any]) -> dict[str, Any]:
    function = tool.get("function")
    if not isinstance(function, dict):
        raise ValueError("Anthropic tools must use function specs.")
    return {
        "name": function.get("name"),
        "description": function.get("description"),
        "input_schema": function.get("parameters", {"type": "object"}),
    }


def _message_from_response(payload: dict[str, Any]) -> tuple[dict[str, Any], tuple[ToolCall, ...]]:
    content = payload.get("content")
    if not isinstance(content, list):
        raise ValueError("Anthropic response must include content blocks.")
    text_parts: list[dict[str, Any]] = []
    tool_calls: list[ToolCall] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "text":
            text = item.get("text")
            if isinstance(text, str) and text:
                text_parts.append({"type": "text", "text": text})
        elif item_type == "tool_use":
            input_payload = item.get("input", {})
            if not isinstance(input_payload, dict):
                input_payload = {}
            tool_calls.append(
                ToolCall(
                    id=str(item.get("id")) if item.get("id") is not None else None,
                    name=str(item.get("name", "")),
                    arguments=input_payload,
                )
            )
    message = {
        "role": "assistant",
        "content": text_parts if text_parts else "",
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.name,
                    "arguments": json.dumps(tool_call.arguments, ensure_ascii=False),
                },
            }
            for tool_call in tool_calls
        ]
        or None,
    }
    return message, tuple(tool_calls)


def _messages_url(api_base: str) -> str:
    stripped = api_base.rstrip("/")
    if stripped.endswith("/messages"):
        return stripped
    if stripped.endswith("/v1"):
        return f"{stripped}/messages"
    return f"{stripped}/v1/messages"
