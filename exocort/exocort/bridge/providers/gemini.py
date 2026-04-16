from __future__ import annotations

import json
from typing import Any

from ..client import HttpClient
from ..models.asr import AsrRequest, AsrResult
from ..models.ocr import OcrRequest, OcrResult
from ..models.response import ResponseRequest, ResponseResult, ToolCall
from ..utils.media import guess_mime_type, media_to_base64
from ..utils.messages import text_from_content
from ..utils.provider import split_model_provider
from ..utils.urls import join_url
from .common import (
    api_key_json_headers,
    content_as_text_blocks,
    ensure_text,
    normalize_function_arguments,
    require_payload,
    single_page_ocr_result,
)

DEFAULT_ASR_PROMPT = "Transcribe the audio and return only the transcript."
DEFAULT_OCR_PROMPT = "Extract the readable text from this image and return only the extracted text."


def asr(
    client: HttpClient,
    api_base: str,
    api_key: str,
    req: AsrRequest,
    extra_headers: dict[str, str],
) -> AsrResult:
    prompt = req.prompt or DEFAULT_ASR_PROMPT
    payload = _build_generate_content_payload(
        req.model,
        messages=(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "input_audio", "media": req.media},
                ],
            },
        ),
        temperature=req.temperature,
    )
    response = client.post_json(
        _generate_content_url(api_base, req.model),
        headers=_headers(api_key, extra_headers),
        payload=payload,
    )
    payload_json = require_payload(response.json, "ASR")
    text = ensure_text(_candidate_text(payload_json), "ASR response text")
    return AsrResult(text=text, raw=payload_json)


def ocr(
    client: HttpClient,
    api_base: str,
    api_key: str,
    req: OcrRequest,
    extra_headers: dict[str, str],
) -> OcrResult:
    prompt = req.prompt or DEFAULT_OCR_PROMPT
    payload = _build_generate_content_payload(
        req.model,
        messages=(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image", "media": req.media},
                ],
            },
        ),
    )
    response = client.post_json(
        _generate_content_url(api_base, req.model),
        headers=_headers(api_key, extra_headers),
        payload=payload,
    )
    payload_json = require_payload(response.json, "OCR")
    return single_page_ocr_result(_candidate_text(payload_json), payload_json, "OCR page markdown")


def response(
    client: HttpClient,
    api_base: str,
    api_key: str,
    req: ResponseRequest,
    extra_headers: dict[str, str],
) -> ResponseResult:
    payload = _build_generate_content_payload(
        req.model,
        messages=req.messages,
        tools=req.tools,
        tool_choice=req.tool_choice,
        temperature=req.temperature,
    )
    response = client.post_json(
        _generate_content_url(api_base, req.model),
        headers=_headers(api_key, extra_headers),
        payload=payload,
    )
    payload_json = require_payload(response.json, "response")
    message, tool_calls = _message_from_response(payload_json)
    return ResponseResult(
        message=message,
        text=text_from_content(message.get("content")),
        tool_calls=tool_calls,
        raw=payload_json,
    )


def _headers(api_key: str, extra_headers: dict[str, str]) -> dict[str, str]:
    return api_key_json_headers("x-goog-api-key", api_key, extra_headers)


def _generate_content_url(api_base: str, model: str) -> str:
    _, normalized_model = split_model_provider(model)
    stripped = api_base.rstrip("/")
    if ":generateContent" in stripped:
        return stripped
    if stripped.endswith("/v1beta") or stripped.endswith("/v1"):
        return f"{stripped}/models/{normalized_model}:generateContent"
    if stripped.endswith("/models"):
        return f"{stripped}/{normalized_model}:generateContent"
    return join_url(stripped, f"/models/{normalized_model}:generateContent")


def _build_generate_content_payload(
    model: str,
    *,
    messages: tuple[dict[str, Any], ...],
    tools: tuple[dict[str, Any], ...] = (),
    tool_choice: str | dict[str, Any] | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    system_parts: list[dict[str, Any]] = []
    contents: list[dict[str, Any]] = []
    for raw_message in messages:
        role = str(raw_message.get("role", "user"))
        if role == "system":
            system_parts.extend(_parts_from_message(raw_message))
            continue
        if role == "tool":
            contents.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "functionResponse": {
                                "id": str(raw_message.get("tool_call_id", "")) or None,
                                "name": str(raw_message.get("name", "")),
                                "response": _gemini_function_response(raw_message.get("content", "")),
                            }
                        }
                    ],
                }
            )
            continue
        raw_parts = raw_message.get("_gemini_parts")
        if role == "assistant" and isinstance(raw_parts, list):
            parts = [part for part in raw_parts if isinstance(part, dict)]
        else:
            parts = _parts_from_message(raw_message)
            if role == "assistant":
                tool_calls = raw_message.get("tool_calls")
                if isinstance(tool_calls, list):
                    for tool_call in tool_calls:
                        if not isinstance(tool_call, dict):
                            continue
                        function = tool_call.get("function")
                        if not isinstance(function, dict):
                            continue
                        arguments = normalize_function_arguments(function.get("arguments", "{}"))
                        parts.append(
                            {
                                "functionCall": {
                                    "id": str(tool_call.get("id", "")) or None,
                                    "name": str(function.get("name", "")),
                                    "args": arguments,
                                }
                            }
                        )
        contents.append(
            {
                "role": "model" if role == "assistant" else "user",
                "parts": parts,
            }
        )

    payload: dict[str, Any] = {"contents": contents}
    if system_parts:
        payload["systemInstruction"] = {"parts": system_parts}
    if tools:
        payload["tools"] = [{"functionDeclarations": [_gemini_tool(tool) for tool in tools]}]
    if tool_choice is not None:
        payload["toolConfig"] = _gemini_tool_config(tool_choice)
    if temperature is not None:
        payload["generationConfig"] = {"temperature": temperature}
    return payload


def _parts_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content")
    parts = [{"text": part["text"]} for part in content_as_text_blocks(content) if isinstance(part.get("text"), str) and part["text"]]
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type", "text"))
            if item_type in {"image", "input_audio"}:
                media = item.get("media")
                if not hasattr(media, "file_path"):
                    continue
                parts.append(
                    {
                        "inline_data": {
                            "mime_type": guess_mime_type(media),
                            "data": media_to_base64(media),
                        }
                    }
                )
            elif item_type == "tool_result":
                parts.append(
                    {
                        "functionResponse": {
                            "id": str(item.get("tool_call_id", "") or item.get("id", "")) or None,
                            "name": str(item.get("name", "")),
                            "response": _gemini_function_response(item.get("response", {})),
                        }
                    }
                )
            elif item_type == "tool_call":
                parts.append(
                    {
                        "functionCall": {
                            "id": str(item.get("id", "")) or None,
                            "name": str(item.get("name", "")),
                            "args": normalize_function_arguments(item.get("arguments", {})),
                        }
                    }
                )
    return parts


def _gemini_tool(tool: dict[str, Any]) -> dict[str, Any]:
    function = tool.get("function")
    if not isinstance(function, dict):
        raise ValueError("Gemini tools must use function specs.")
    payload = {
        "name": function.get("name"),
        "description": function.get("description"),
        "parameters": _gemini_schema(function.get("parameters", {"type": "object"})),
    }
    return payload


def _gemini_schema(schema: object) -> dict[str, Any]:
    if not isinstance(schema, dict):
        return {"type": "object"}
    allowed_keys = {
        "type",
        "format",
        "description",
        "nullable",
        "enum",
        "items",
        "properties",
        "required",
    }
    normalized: dict[str, Any] = {}
    for key, value in schema.items():
        if key not in allowed_keys:
            continue
        if key == "properties" and isinstance(value, dict):
            normalized[key] = {
                str(prop_name): _gemini_schema(prop_schema)
                for prop_name, prop_schema in value.items()
            }
            continue
        if key == "items":
            normalized[key] = _gemini_schema(value)
            continue
        normalized[key] = value
    return normalized or {"type": "object"}


def _gemini_tool_config(tool_choice: str | dict[str, Any]) -> dict[str, Any]:
    mode = "AUTO"
    allowed_function_names: list[str] | None = None
    if isinstance(tool_choice, str):
        lowered = tool_choice.lower()
        if lowered == "none":
            mode = "NONE"
        elif lowered == "required":
            mode = "ANY"
    elif isinstance(tool_choice, dict):
        function = tool_choice.get("function")
        if isinstance(function, dict):
            name = str(function.get("name", "")).strip()
            if name:
                mode = "ANY"
                allowed_function_names = [name]
    config: dict[str, Any] = {"functionCallingConfig": {"mode": mode}}
    if allowed_function_names:
        config["functionCallingConfig"]["allowedFunctionNames"] = allowed_function_names
    return config


def _gemini_function_response(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {"content": value}
        return parsed if isinstance(parsed, dict) else {"content": value}
    return {"content": str(value)}


def _message_from_response(payload: dict[str, Any]) -> tuple[dict[str, Any], tuple[ToolCall, ...]]:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Gemini response must include candidates.")
    first = candidates[0]
    if not isinstance(first, dict):
        raise ValueError("Gemini candidate must be an object.")
    content = first.get("content")
    if not isinstance(content, dict):
        raise ValueError("Gemini candidate must include content.")
    parts = content.get("parts")
    if not isinstance(parts, list):
        parts = []
    message_content: list[dict[str, Any]] = []
    tool_calls: list[ToolCall] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        text = part.get("text")
        if isinstance(text, str) and text:
            message_content.append({"type": "text", "text": text})
        function_call = part.get("functionCall")
        if isinstance(function_call, dict):
            arguments = function_call.get("args", {})
            if isinstance(arguments, str):
                arguments = json.loads(arguments or "{}")
            if not isinstance(arguments, dict):
                arguments = {}
            tool_calls.append(
                ToolCall(
                    id=str(function_call.get("id")) if function_call.get("id") is not None else None,
                    name=str(function_call.get("name", "")),
                    arguments=arguments,
                )
            )
    message = {
        "role": "assistant",
        "content": message_content if message_content else "",
        "_gemini_parts": parts,
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


def _candidate_text(payload: dict[str, Any]) -> str:
    message, _ = _message_from_response(payload)
    return text_from_content(message.get("content"))
