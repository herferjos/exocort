from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    pass


def load_json_config(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"{label} config not found: {path}")
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} config is invalid JSON: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"{label} config must be a JSON object at the top level")
    return data


def read_str(data: dict[str, Any], key: str, default: str | None = None) -> str | None:
    value = data.get(key)
    if value is None:
        return default
    if isinstance(value, str):
        value = value.strip()
        return value if value else default
    return str(value)


def read_int(data: dict[str, Any], key: str, default: int) -> int:
    value = data.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def read_float(data: dict[str, Any], key: str, default: float) -> float:
    value = data.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def read_bool(data: dict[str, Any], key: str, default: bool) -> bool:
    value = data.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def read_list_str(data: dict[str, Any], key: str, default: list[str]) -> list[str]:
    value = data.get(key)
    if value is None:
        return default
    if isinstance(value, list):
        out = [str(item).strip() for item in value if str(item).strip()]
        return out or default
    if isinstance(value, str):
        out = [part.strip() for part in value.split(",") if part.strip()]
        return out or default
    return default


def resolve_api_key(
    api_key: str | None,
    api_key_env: str | None,
    fallback_env: str | None = None,
) -> str:
    if isinstance(api_key, str) and api_key.strip():
        return api_key.strip()
    if isinstance(api_key_env, str) and api_key_env.strip():
        value = os.getenv(api_key_env.strip(), "").strip()
        if value:
            return value
    if isinstance(fallback_env, str) and fallback_env.strip():
        value = os.getenv(fallback_env.strip(), "").strip()
        if value:
            return value
    return ""
