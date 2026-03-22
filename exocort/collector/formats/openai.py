"""OpenAI-compatible format: STT (audio) and vision/OCR (image) endpoints."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .base import BuiltRequest, FormatAdapter, ParsedResponse
from .utils import file_replacements, render_placeholders

if TYPE_CHECKING:
    from exocort.collector.config import EndpointConfig


def _extract_text_from_openai_body(data: dict[str, Any]) -> str | None:
    """Extract text from common OpenAI-style response shapes."""
    if isinstance(data.get("text"), str):
        return data["text"]
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            msg = first.get("message")
            if isinstance(msg, dict):
                content = msg.get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts = [c.get("text", c) for c in content if isinstance(c, dict)]
                    if parts:
                        return " ".join(str(p) for p in parts)
            delta = first.get("delta")
            if isinstance(delta, dict) and isinstance(delta.get("content"), str):
                return delta["content"]
    return None


class OpenAIAdapter(FormatAdapter):
    """Adapter for OpenAI-style transcription (STT) and chat/vision (OCR) APIs."""

    def build_request(
        self,
        endpoint: "EndpointConfig",
        file_content: bytes,
        filename: str,
        content_type: str,
        stream_type: str,
    ) -> BuiltRequest:
        if stream_type == "screen":
            return self._build_json_request(endpoint, file_content, filename, content_type)
        files = {"file": (filename, file_content, content_type)}
        data = render_placeholders(
            dict(endpoint.body) if endpoint.body else {},
            file_replacements(file_content, filename, content_type, stream_type),
        )
        return BuiltRequest(
            method=endpoint.method,
            url=endpoint.url,
            headers=dict(endpoint.headers),
            files=files,
            data=data if data else None,
            json=None,
        )

    def _build_json_request(
        self,
        endpoint: "EndpointConfig",
        file_content: bytes,
        filename: str,
        content_type: str,
    ) -> BuiltRequest:
        payload = render_placeholders(
            dict(endpoint.body) if endpoint.body else {},
            file_replacements(file_content, filename, content_type, "screen"),
        )
        return BuiltRequest(
            method=endpoint.method,
            url=endpoint.url,
            headers=dict(endpoint.headers),
            files=None,
            data=None,
            json=payload,
        )

    def parse_response(self, status_code: int, raw_body: str) -> ParsedResponse:
        ok = 200 <= status_code < 300
        parsed_text = None
        if raw_body:
            try:
                parsed_text = _extract_text_from_openai_body(json.loads(raw_body))
            except (json.JSONDecodeError, TypeError):
                if ok:
                    parsed_text = raw_body
        return ParsedResponse(
            ok=ok,
            status=status_code,
            raw_body=raw_body,
            parsed_text=parsed_text,
        )
