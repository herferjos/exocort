"""Gemini format adapter: render JSON request body and parse JSON response."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .base import BuiltRequest, FormatAdapter, ParsedResponse
from .openai import _extract_text_from_openai_body
from .utils import file_replacements, render_placeholders

if TYPE_CHECKING:
    from exocort.collector.config import EndpointConfig


class GeminiAdapter(FormatAdapter):
    """Adapter for Gemini JSON endpoints (OpenAI-compatible chat/completions)."""

    def build_request(
        self,
        endpoint: "EndpointConfig",
        file_content: bytes,
        filename: str,
        content_type: str,
        stream_type: str,
    ) -> BuiltRequest:
        payload = render_placeholders(
            dict(endpoint.body) if endpoint.body else {},
            file_replacements(file_content, filename, content_type, stream_type),
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
