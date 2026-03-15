from __future__ import annotations

import json
import mimetypes
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


def read_dict_str(data: dict[str, Any], key: str) -> dict[str, str]:
    value = data.get(key)
    if not isinstance(value, dict):
        return {}
    out: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key_str = str(raw_key).strip()
        value_str = str(raw_value).strip()
        if key_str and value_str:
            out[key_str] = value_str
    return out


def normalize_api_format(value: str | None, default: str = "openai") -> str:
    raw = (value or default).strip().lower()
    if raw in {"openai", "anthropic"}:
        return raw
    raise ValueError(
        f"Unsupported API format: {raw!r}. "
        "Expected one of: 'openai', 'anthropic'."
    )


def guess_mime_type(path: Path, fallback: str) -> str:
    mime_type, _ = mimetypes.guess_type(str(path))
    return mime_type or fallback


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


def build_http_headers(
    *,
    format_name: str,
    api_key: str,
    headers: dict[str, str] | None = None,
    api_key_header: str | None = None,
    auth_scheme: str | None = None,
    anthropic_version: str | None = None,
) -> dict[str, str]:
    out = {"content-type": "application/json"}
    if headers:
        out.update(headers)

    scheme = (auth_scheme or "").strip().lower()
    header_name = (api_key_header or "").strip()

    if api_key:
        if header_name:
            if scheme == "bearer":
                out[header_name] = f"Bearer {api_key}"
            elif scheme in {"raw", "plain"}:
                out[header_name] = api_key
            else:
                out[header_name] = api_key
        elif format_name == "anthropic":
            out["x-api-key"] = api_key
        else:
            out["Authorization"] = f"Bearer {api_key}"

    if format_name == "anthropic":
        out["anthropic-version"] = anthropic_version or "2023-06-01"

    return out
