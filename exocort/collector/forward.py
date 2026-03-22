"""Forward received uploads to configured processing APIs."""

from __future__ import annotations

import logging

import requests

from .config import EndpointConfig
from .formats import get_adapter

log = logging.getLogger("collector.forward")


def forward_upload(
    endpoint: EndpointConfig,
    file_content: bytes,
    filename: str,
    content_type: str,
    stream_type: str = "audio",
) -> tuple[bool, int, str]:
    """Send file to one endpoint via format adapter.
    Returns (ok, status_code, text).
    """
    adapter = get_adapter(endpoint.format)
    req = adapter.build_request(
        endpoint, file_content, filename, content_type, stream_type
    )
    try:
        r = requests.request(
            req.method,
            req.url,
            headers=req.headers,
            files=req.files,
            data=req.data,
            json=req.json,
            timeout=endpoint.timeout,
        )
        body = r.text or ""
        parsed = adapter.parse_response(r.status_code, body)
        if not parsed.ok:
            log.warning(
                "Forward rejected | url=%s | status=%d | body=%s",
                endpoint.url,
                r.status_code,
                body[:500],
            )
        else:
            log.info("Forwarded | url=%s | status=%d", endpoint.url, r.status_code)
        return parsed.ok, parsed.status, (parsed.parsed_text or "").strip()
    except Exception as e:
        log.exception("Forward failed | url=%s", endpoint.url)
        return False, 0, ""
