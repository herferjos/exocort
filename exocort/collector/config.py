"""Load collector routing from the shared app config."""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from exocort.config import (
    config_path as default_config_path,
    get_value,
    load_root_config,
)


@dataclass
class EndpointConfig:
    url: str
    method: str = "POST"
    timeout: float = 30.0
    headers: dict[str, str] = field(default_factory=dict)
    format: str = "default"
    body: dict[str, Any] = field(default_factory=dict)


@dataclass
class CollectorConfig:
    audio: EndpointConfig | None = None
    screen: EndpointConfig | None = None

    @classmethod
    def load(cls, path: Path | None = None) -> "CollectorConfig":
        if path is None:
            path = default_config_path()
        if not path.exists():
            return cls()
        data = load_root_config(path)

        def expand_env(s: str) -> str:
            if "${" not in s:
                return s
            for k, v in os.environ.items():
                s = s.replace(f"${{{k}}}", v)
            return s

        def parse_one(*paths: tuple[str, ...]) -> EndpointConfig | None:
            block: Any = {}
            for path_parts in paths:
                candidate = get_value(data, *path_parts, default={})
                if isinstance(candidate, dict) and candidate.get("url"):
                    block = candidate
                    break
            if not isinstance(block, dict) or not block.get("url"):
                return None
            body_raw = block.get("body") or {}
            body_dict = copy.deepcopy(body_raw) if isinstance(body_raw, dict) else {}
            raw_headers = block.get("headers") or {}
            headers = {str(k): expand_env(str(v)) for k, v in raw_headers.items()}
            return EndpointConfig(
                url=expand_env(str(block["url"])),
                method=str(block.get("method", "POST")).upper(),
                timeout=float(block.get("timeout", 30)),
                headers=headers,
                format=str(block.get("format", "default")).strip() or "default",
                body=body_dict,
            )

        return cls(
            audio=parse_one(("services", "audio"), ("audio",)),
            screen=parse_one(("services", "screen"), ("screen",)),
        )
