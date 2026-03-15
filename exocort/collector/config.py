"""Load collector routing from config.json."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EndpointConfig:
    url: str
    method: str = "POST"
    timeout: float = 30.0
    headers: dict[str, str] = field(default_factory=dict)
    format: str = "default"
    body: dict[str, str] = field(default_factory=dict)
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

        def parse_one(key: str) -> EndpointConfig | None:
            block = data.get(key) or {}
            if not isinstance(block, dict) or not block.get("url"):
                return None
            body_raw = block.get("body") or {}
            if isinstance(body_raw, dict):
                body_dict = {str(k): str(v) for k, v in body_raw.items()}
            else:
                body_dict = {}
            return EndpointConfig(
                url=str(block["url"]),
                method=str(block.get("method", "POST")).upper(),
                timeout=float(block.get("timeout", 30)),
                headers=dict(block.get("headers") or {}),
                format=str(block.get("format", "default")).strip() or "default",
                body=body_dict,
                response_path=(str(block["response_path"]).strip() or None) if block.get("response_path") else None,
            )

        return cls(
            audio=parse_one("audio"),
            screen=parse_one("screen"),
        )
