"""Default format: multipart file + optional form data (backward compatible)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import BuiltRequest, FormatAdapter, ParsedResponse

if TYPE_CHECKING:
    from exocort.collector.config import EndpointConfig


class DefaultAdapter(FormatAdapter):
    """Backward-compatible adapter: single 'file' field plus endpoint.body as form data."""

    def build_request(
        self,
        endpoint: "EndpointConfig",
        file_content: bytes,
        filename: str,
        content_type: str,
        stream_type: str,
    ) -> BuiltRequest:
        files = {"file": (filename, file_content, content_type)}
        data = dict(endpoint.body) if endpoint.body else {}
        return BuiltRequest(
            method=endpoint.method,
            url=endpoint.url,
            headers=dict(endpoint.headers),
            files=files,
            data=data if data else None,
            json=None,
        )

    def parse_response(self, status_code: int, raw_body: str) -> ParsedResponse:
        ok = 200 <= status_code < 300
        return ParsedResponse(
            ok=ok,
            status=status_code,
            raw_body=raw_body,
            parsed_text=raw_body if raw_body and ok else None,
            parsed_json=None,
        )
