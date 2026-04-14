from __future__ import annotations

import json
from typing import Any

from ..client import HttpClient
from ..models.asr import AsrRequest, AsrResult
from ..models.ocr import OcrPage, OcrRequest, OcrResult
from ..models.response import ResponseRequest, ResponseResult, ToolCall
from ..utils.media import guess_mime_type, media_to_base64
from ..utils.messages import text_from_content
from ..utils.provider import split_model_provider
from ..utils.urls import join_url

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
    payload_json = _require_payload(response.json, "ASR")
    text = _candidate_text(payload_json).strip()
    if not text:
        raise ValueError("ASR response text is empty.")
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
    payload_json = _require_payload(response.json, "OCR")
    text = _candidate_text(payload_json).strip()
    if not text:
        raise ValueError("OCR page markdown is empty.")
    return OcrResult(
        text=text,
        pages=(OcrPage(index=0, text=text),),
        raw=payload_json,
    )


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
        temperature=req.temperature,
    )
    response = client.post_json(
        _generate_content_url(api_base, req.model),
        headers=_headers(api_key, extra_headers),
        payload=payload,
    )
    payload_json = _require_payload(response.json, "response")
    message, tool_calls = _message_from_response(payload_json)
    return ResponseResult(
        message=message,
        text=text_from_content(message.get("content")),
        tool_calls=tool_calls,
        raw=payload_json,
    )


def _headers(api_key: str, extra_headers: dict[str, str]) -> dict[str, str]:
    return {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
        **extra_headers,
    }


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
                                "name": str(raw_message.get("name", "")),
                                "response": {"content": str(raw_message.get("content", ""))},
                            }
                        }
                    ],
                }
            )
            continue
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
                    arguments = function.get("arguments", "{}")
                    if isinstance(arguments, str):
                        arguments = json.loads(arguments or "{}")
                    if not isinstance(arguments, dict):
                        arguments = {}
                    parts.append(
                        {
                            "functionCall": {
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
    if temperature is not None:
        payload["generationConfig"] = {"temperature": temperature}
    return payload


def _parts_from_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content")
    parts: list[dict[str, Any]] = []
    if isinstance(content, str):
        parts.append({"text": content})
    elif isinstance(content, list):
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type", "text"))
            if item_type == "text":
                text = item.get("text")
                if isinstance(text, str):
                    parts.append({"text": text})
            elif item_type in {"image", "input_audio"}:
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
                response_value = item.get("response", {})
                if not isinstance(response_value, dict):
                    response_value = {"content": str(response_value)}
                parts.append(
                    {
                        "functionResponse": {
                            "name": str(item.get("name", "")),
                            "response": response_value,
                        }
                    }
                )
            elif item_type == "tool_call":
                parts.append(
                    {
                        "functionCall": {
                            "name": str(item.get("name", "")),
                            "args": item.get("arguments", {}),
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
        "parameters": function.get("parameters", {"type": "object"}),
    }
    return payload


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
                    id=None,
                    name=str(function_call.get("name", "")),
                    arguments=arguments,
                )
            )
    message = {
        "role": "assistant",
        "content": message_content if message_content else "",
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


def _require_payload(payload: dict[str, Any] | None, label: str) -> dict[str, Any]:
    if payload is None:
        raise ValueError(f"{label} endpoint did not return JSON.")
    return payload
