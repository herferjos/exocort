from __future__ import annotations

import json
from typing import Any

from ..client import HttpClient
from ..models.asr import AsrRequest, AsrResult
from ..models.ocr import OcrPage, OcrRequest, OcrResult
from ..models.response import ResponseRequest, ResponseResult, ToolCall
from ..utils.media import guess_mime_type, media_to_data_uri, read_media_bytes
from ..utils.messages import collect_tool_calls, text_from_content
from ..utils.provider import split_model_provider
from ..utils.urls import maybe_join_openai_path

DEFAULT_OCR_PROMPT = "Extract the readable text from this image. Return only the extracted text."


def asr(
    client: HttpClient,
    api_base: str,
    api_key: str,
    req: AsrRequest,
    extra_headers: dict[str, str],
) -> AsrResult:
    _, model = split_model_provider(req.model)
    url = maybe_join_openai_path(api_base, "/audio/transcriptions")
    headers = {"Authorization": f"Bearer {api_key}", **extra_headers}
    file_name = req.media.file_path.name if req.media.file_path is not None else "audio"
    response = client.post_multipart(
        url,
        headers=headers,
        files={
            "file": (
                file_name,
                read_media_bytes(req.media),
                guess_mime_type(req.media),
            )
        },
        data=_compact_strings(
            {
                "model": model,
                "language": req.language or "",
                "prompt": req.prompt or "",
                "temperature": _float_to_str(req.temperature),
            }
        ),
    )
    payload = _require_payload(response.json, "ASR")
    text = str(payload.get("text", "")).strip()
    if not text:
        raise ValueError("ASR response text is empty.")
    segments = tuple(item for item in payload.get("segments", []) if isinstance(item, dict))
    language = payload.get("language")
    return AsrResult(
        text=text,
        segments=segments,
        language=str(language) if isinstance(language, str) else None,
        raw=payload,
    )


def ocr(
    client: HttpClient,
    api_base: str,
    api_key: str,
    req: OcrRequest,
    extra_headers: dict[str, str],
) -> OcrResult:
    _, model = split_model_provider(req.model)
    prompt = req.prompt or DEFAULT_OCR_PROMPT
    messages = (
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": media_to_data_uri(req.media)}},
            ],
        },
    )
    result = response(
        client,
        api_base,
        api_key,
        ResponseRequest(model=model, messages=messages),
        extra_headers,
    )
    text = result.text.strip()
    if not text:
        raise ValueError("OCR page markdown is empty.")
    return OcrResult(
        text=text,
        pages=(OcrPage(index=0, text=text),),
        raw=result.raw,
    )


def response(
    client: HttpClient,
    api_base: str,
    api_key: str,
    req: ResponseRequest,
    extra_headers: dict[str, str],
) -> ResponseResult:
    _, model = split_model_provider(req.model)
    url = maybe_join_openai_path(api_base, "/chat/completions")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        **extra_headers,
    }
    payload = {
        "model": model,
        "messages": list(req.messages),
    }
    if req.tools:
        payload["tools"] = list(req.tools)
    if req.tool_choice is not None:
        payload["tool_choice"] = req.tool_choice
    if req.temperature is not None:
        payload["temperature"] = req.temperature
    response_data = client.post_json(url, headers=headers, payload=payload)
    payload_json = _require_payload(response_data.json, "response")
    choices = payload_json.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("response payload must include choices.")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise ValueError("response choice must be an object.")
    message = choice.get("message")
    if not isinstance(message, dict):
        raise ValueError("response choice must include a message object.")
    tool_calls = tuple(_parse_tool_call(item) for item in collect_tool_calls(message))
    return ResponseResult(
        message=message,
        text=text_from_content(message.get("content")),
        tool_calls=tool_calls,
        raw=payload_json,
    )


def _compact_strings(values: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in values.items() if value != ""}


def _float_to_str(value: float | None) -> str:
    if value is None:
        return ""
    return json.dumps(value)


def _require_payload(payload: dict[str, Any] | None, label: str) -> dict[str, Any]:
    if payload is None:
        raise ValueError(f"{label} endpoint did not return JSON.")
    return payload


def _parse_tool_call(tool_call: dict[str, Any]) -> ToolCall:
    function = tool_call.get("function")
    if not isinstance(function, dict):
        raise ValueError("tool call must include function details.")
    raw_arguments = function.get("arguments", "{}")
    if isinstance(raw_arguments, str):
        arguments = json.loads(raw_arguments or "{}")
    elif isinstance(raw_arguments, dict):
        arguments = raw_arguments
    else:
        raise ValueError("tool arguments must be a JSON object.")
    if not isinstance(arguments, dict):
        raise ValueError("tool arguments must decode to an object.")
    return ToolCall(
        id=str(tool_call.get("id")) if tool_call.get("id") is not None else None,
        name=str(function.get("name", "")).strip(),
        arguments=arguments,
    )
