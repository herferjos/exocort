"""Shared application config loading."""

from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config.toml"


def project_root() -> Path:
    return _PROJECT_ROOT


def config_path() -> Path:
    raw = os.environ.get("EXOCORT_CONFIG", "").strip()
    path = Path(raw).expanduser() if raw else _DEFAULT_CONFIG_PATH
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def load_root_config(path: Path | None = None) -> dict[str, Any]:
    resolved_path = path or config_path()
    if not resolved_path.exists():
        return {}
    suffix = resolved_path.suffix.lower()
    text = resolved_path.read_text(encoding="utf-8")
    if suffix == ".json":
        data = json.loads(text)
    else:
        data = tomllib.loads(text)
    return data if isinstance(data, dict) else {}


def get_value(data: dict[str, Any], *path: str, default: Any = None) -> Any:
    current: Any = data
    for part in path:
        if not isinstance(current, dict):
            return default
        current = current.get(part, default)
        if current is default:
            return default
    return current
