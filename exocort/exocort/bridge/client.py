from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

import requests


@dataclass(slots=True, frozen=True)
class HttpResponse:
    status_code: int
    headers: dict[str, str]
    json: dict[str, Any] | None
    text: str


class HttpClient:
    def __init__(self, timeout_s: float, retries: int) -> None:
        self._timeout_s = timeout_s
        self._retries = max(0, retries)

    def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        *,
        params: dict[str, str] | None = None,
    ) -> HttpResponse:
        return self._request(
            "POST",
            url,
            headers=headers,
            json=payload,
            params=params,
        )

    def post_multipart(
        self,
        url: str,
        headers: dict[str, str],
        files: dict[str, tuple[str, bytes, str]],
        data: dict[str, str],
        *,
        params: dict[str, str] | None = None,
    ) -> HttpResponse:
        prepared_files = {
            name: (filename, content, mime_type)
            for name, (filename, content, mime_type) in files.items()
        }
        return self._request(
            "POST",
            url,
            headers=headers,
            files=prepared_files,
            data=data,
            params=params,
        )

    def put_bytes(
        self,
        url: str,
        headers: dict[str, str],
        content: bytes,
    ) -> HttpResponse:
        return self._request(
            "PUT",
            url,
            headers=headers,
            data=content,
        )

    def _request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        last_error: Exception | None = None
        for attempt in range(self._retries + 1):
            try:
                response = requests.request(
                    method,
                    url,
                    timeout=self._timeout_s,
                    **kwargs,
                )
                response.raise_for_status()
                payload: dict[str, Any] | None = None
                content_type = response.headers.get("content-type", "")
                if "json" in content_type:
                    loaded = response.json()
                    if isinstance(loaded, dict):
                        payload = loaded
                return HttpResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    json=payload,
                    text=response.text,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt >= self._retries:
                    break
                time.sleep(min(1.0, 0.2 * (attempt + 1)))
        if last_error is None:
            raise RuntimeError(f"request failed without an error: {method} {url}")
        raise RuntimeError(f"request failed: {method} {url}: {last_error}") from last_error

