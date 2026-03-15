from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path
from typing import Any

import requests
from pydantic import BaseModel

from engine.config import build_http_headers, guess_mime_type


def _data_uri(path: Path, fallback_mime_type: str) -> str:
    mime_type = guess_mime_type(path, fallback_mime_type)
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{b64}"


def _audio_format(mime_type: str) -> str:
    value = (mime_type or "").strip().lower()
    if "/" in value:
        value = value.split("/", 1)[1]
    aliases = {
        "x-wav": "wav",
        "wave": "wav",
        "mpeg": "mp3",
        "x-m4a": "m4a",
    }
    return aliases.get(value, value or "wav")


def _strip_code_fences(text: str) -> str:
    raw = text.strip()
    if raw.startswith("```") and raw.endswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return raw


def _extract_openai_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = str(item.get("type") or "").strip().lower()
        if item_type in {"text", "output_text"}:
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return "\n".join(parts).strip()


def _extract_openai_chat_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0] if isinstance(choices[0], dict) else {}
    message = first.get("message") if isinstance(first.get("message"), dict) else {}
    return _extract_openai_content(message.get("content"))


def _extract_anthropic_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if str(item.get("type") or "").strip().lower() != "text":
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n".join(parts).strip()


def _schema_prompt(output_model: type[BaseModel]) -> str:
    schema = json.dumps(output_model.model_json_schema(), ensure_ascii=False, indent=2)
    return (
        "Return only valid JSON that matches this schema exactly.\n\n"
        f"{schema}"
    )


def _openai_response_schema(output_model: type[BaseModel]) -> dict[str, Any]:
    def normalize(node: Any) -> Any:
        if isinstance(node, list):
            return [normalize(item) for item in node]
        if not isinstance(node, dict):
            return node

        normalized = {key: normalize(value) for key, value in node.items()}
        if normalized.get("type") == "object":
            normalized["additionalProperties"] = False
            properties = normalized.get("properties")
            if isinstance(properties, dict):
                normalized["required"] = list(properties.keys())
        return normalized
    raw_schema = output_model.model_json_schema()
    return normalize(raw_schema)


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    response = requests.post(url, headers=headers, json=payload, timeout=timeout_s)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object response from {url}")
    return data


def chat_completion(
    *,
    endpoint_url: str,
    format_name: str,
    model: str | None,
    api_key: str,
    headers: dict[str, str] | None,
    api_key_header: str | None,
    auth_scheme: str | None,
    anthropic_version: str | None,
    system: str,
    user: str,
    timeout_s: float,
    temperature: float | None = None,
    max_tokens: int | None = None,
    image_path: Path | None = None,
    audio_path: Path | None = None,
    audio_mime_type: str | None = None,
    output_model: type[BaseModel] | None = None,
) -> str:
    normalized_format = format_name.strip().lower()
    request_headers = build_http_headers(
        format_name=normalized_format,
        api_key=api_key,
        headers=headers,
        api_key_header=api_key_header,
        auth_scheme=auth_scheme,
        anthropic_version=anthropic_version,
    )

    if normalized_format == "openai":
        payload: dict[str, Any] = {
            "model": model,
            "messages": [],
        }
        if system.strip():
            payload["messages"].append({"role": "system", "content": system})

        user_content: list[dict[str, Any]] = []
        if user.strip():
            user_content.append({"type": "text", "text": user})
        if image_path is not None:
            user_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": _data_uri(image_path, "image/png")},
                }
            )
        if audio_path is not None:
            mime_type = audio_mime_type or guess_mime_type(audio_path, "audio/wav")
            user_content.append(
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": base64.b64encode(audio_path.read_bytes()).decode("utf-8"),
                        "format": _audio_format(mime_type),
                    },
                }
            )
        payload["messages"].append(
            {
                "role": "user",
                "content": user_content if user_content else user,
            }
        )

        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if output_model is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": output_model.__name__,
                    "strict": True,
                    "schema": _openai_response_schema(output_model),
                },
            }

        data = _post_json(endpoint_url, request_headers, payload, timeout_s)
        return _extract_openai_chat_text(data)

    if normalized_format == "anthropic":
        user_content_blocks: list[dict[str, Any]] = []
        final_user = user.strip()
        if output_model is not None:
            final_user = f"{final_user}\n\n{_schema_prompt(output_model)}".strip()
        if final_user:
            user_content_blocks.append({"type": "text", "text": final_user})
        if image_path is not None:
            mime_type = guess_mime_type(image_path, "image/png")
            user_content_blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": base64.b64encode(image_path.read_bytes()).decode("utf-8"),
                    },
                }
            )
        if audio_path is not None:
            raise ValueError("Anthropic chat audio is not supported by this project")

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": user_content_blocks or final_user}],
            "max_tokens": max_tokens or 1024,
        }
        if system.strip():
            payload["system"] = system
        if temperature is not None:
            payload["temperature"] = temperature

        data = _post_json(endpoint_url, request_headers, payload, timeout_s)
        return _extract_anthropic_text(data)

    raise ValueError(f"Unsupported API format: {format_name}")


def openai_transcription(
    *,
    endpoint_url: str,
    model: str | None,
    api_key: str,
    headers: dict[str, str] | None,
    api_key_header: str | None,
    auth_scheme: str | None,
    file_path: Path,
    timeout_s: float,
    prompt: str | None = None,
    language: str | None = None,
) -> str:
    request_headers = build_http_headers(
        format_name="openai",
        api_key=api_key,
        headers=headers,
        api_key_header=api_key_header,
        auth_scheme=auth_scheme,
    )
    request_headers.pop("content-type", None)

    mime_type = guess_mime_type(file_path, "application/octet-stream")
    data = {"model": model or "transcription"}
    if prompt and prompt.strip():
        data["prompt"] = prompt.strip()
    if language and language.strip():
        data["language"] = language.strip()

    with file_path.open("rb") as fh:
        files = {
            "file": (file_path.name, fh, mime_type),
        }
        response = requests.post(
            endpoint_url,
            headers=request_headers,
            data=data,
            files=files,
            timeout=timeout_s,
        )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object response from {endpoint_url}")
    text = payload.get("text")
    if isinstance(text, str):
        return text.strip()
    return ""


def parse_structured_output(raw_text: str, output_model: type[BaseModel]) -> BaseModel:
    cleaned = _strip_code_fences(raw_text)
    try:
        return output_model.model_validate_json(cleaned)
    except Exception:
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise
        return output_model.model_validate_json(match.group(0))


def openai_chat_response(text: str, model: str) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-local-{int(time.time() * 1000)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": text,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }
