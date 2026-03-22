"""Base contract for provider format adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exocort.collector.config import EndpointConfig


@dataclass
class BuiltRequest:
    """Result of build_request: enough to call requests.request."""

    method: str
    url: str
    headers: dict[str, str]
    files: dict[str, tuple[str, bytes, str]] | None = None
    data: dict[str, str] | None = None
    json: dict[str, Any] | None = None


@dataclass
class ParsedResponse:
    """Normalized response from parse_response."""

    ok: bool
    status: int
    raw_body: str
    parsed_text: str | None = None


class FormatAdapter:
    """Adapter that builds outgoing requests and parses responses for a provider format."""

    def build_request(
        self,
        endpoint: "EndpointConfig",
        file_content: bytes,
        filename: str,
        content_type: str,
        stream_type: str,
    ) -> BuiltRequest:
        """Build HTTP request for the given file and endpoint. stream_type is 'audio' or 'screen'."""
        raise NotImplementedError

    def parse_response(self, status_code: int, raw_body: str) -> ParsedResponse:
        """Parse the HTTP response into a normalized structure."""
        raise NotImplementedError
