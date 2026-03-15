"""Load collector routing from config.json."""

from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EndpointConfig:
    url: str
    method: str = "POST"
    timeout: float = 30.0
    headers: dict[str, str] = field(default_factory=dict)
    format: str = "default"
    body: dict[str, Any] = field(default_factory=dict)
    response_path: str | None = None


@dataclass
class CollectorConfig:
    audio: EndpointConfig | None = None
    screen: EndpointConfig | None = None

    @classmethod
    def load(cls, path: Path | None = None) -> "CollectorConfig":
        if path is None:
            raw = os.getenv("COLLECTOR_CONFIG", "").strip() or "config.json"
            path = Path(raw)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            return cls()

        data = json.loads(path.read_text(encoding="utf-8"))

        def expand_env(s: str) -> str:
            if "${" not in s:
                return s
            for k, v in os.environ.items():
                s = s.replace(f"${{{k}}}", v)
            return s

        def parse_one(key: str) -> EndpointConfig | None:
            block = data.get(key) or {}
            if not isinstance(block, dict) or not block.get("url"):
                return None
            body_raw = block.get("body") or {}
            body_dict = copy.deepcopy(body_raw) if isinstance(body_raw, dict) else {}
            raw_headers = block.get("headers") or {}
            headers = {str(k): expand_env(str(v)) for k, v in raw_headers.items()}
            return EndpointConfig(
                url=str(block["url"]),
                method=str(block.get("method", "POST")).upper(),
                timeout=float(block.get("timeout", 30)),
                headers=headers,
                format=str(block.get("format", "default")).strip() or "default",
                body=body_dict,
                response_path=(
                    (str(block["response_path"]).strip() or None)
                    if block.get("response_path")
                    else None
                ),
            )

        return cls(
            audio=parse_one("audio"),
            screen=parse_one("screen"),
        )
