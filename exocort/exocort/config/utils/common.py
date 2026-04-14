from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from exocort.provider import infer_provider

from ..models.common import ContentFilterRule, ContentFilterSettings


def parse_expired_in(value: object, label: str) -> int | bool:
    if value is False:
        return False
    if value is True:
        raise ValueError(f"{label} must be a non-negative integer or False.")

    seconds = int(value)
    if seconds < 0:
        raise ValueError(f"{label} must be greater than or equal to 0, or False to keep files.")
    return seconds


def as_mapping(data: object, label: str) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    raise ValueError(f"{label} section must be a mapping.")


def resolve_path(value: object, config_dir: Path) -> Path:
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path
    return (config_dir / path).resolve()


def parse_string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list.")

    items: list[str] = []
    for item in value:
        text = str(item).strip()
        if not text:
            raise ValueError(f"{label} must not contain empty values.")
        items.append(text)
    return items


def parse_log_level(value: object) -> str:
    level = str(value).strip().upper()
    allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    if level not in allowed:
        raise ValueError(f"log_level must be one of: {', '.join(sorted(allowed))}.")
    return level


def parse_format_value(
    value: object,
    label: str,
    *,
    allowed: tuple[str, ...],
    default: str,
) -> str:
    if value is None or str(value).strip() == "":
        return default

    format_value = str(value).strip().lower()
    if format_value not in allowed:
        allowed_text = ", ".join(allowed)
        raise ValueError(f"{label} must be one of: {allowed_text}.")
    return format_value


def parse_endpoint_common(mapping: dict[str, Any], label: str) -> dict[str, Any]:
    enabled = mapping.get("enabled")
    if enabled is None:
        enabled = bool(mapping.get("model") and mapping.get("api_base"))

    provider = infer_provider(
        str(mapping.get("model", "")),
        str(mapping.get("api_base", "")),
        str(mapping.get("provider", "")),
    )
    return {
        "enabled": bool(enabled),
        "provider": provider,
        "model": str(mapping.get("model", "")),
        "api_base": str(mapping.get("api_base", "")),
        "api_key_env": str(mapping.get("api_key_env", "test_key")),
        "timeout_s": float(mapping.get("timeout_s", 30.0)),
        "retries": int(mapping.get("retries", 2)),
        "expired_in": parse_expired_in(mapping.get("expired_in", 0), f"{label}.expired_in"),
    }


def parse_content_filter_settings(data: object) -> ContentFilterSettings:
    mapping = as_mapping(data, "processor.content_filter")
    rules_value = mapping.get("rules", [])
    if not isinstance(rules_value, list):
        raise ValueError("processor.content_filter.rules must be a list.")

    rules: list[ContentFilterRule] = []
    for index, item in enumerate(rules_value, start=1):
        rule_label = f"processor.content_filter.rules[{index}]"
        rule = as_mapping(item, rule_label)
        keywords = parse_string_list(rule.get("keywords", []), f"{rule_label}.keywords")
        regexes = parse_string_list(rule.get("regexes", []), f"{rule_label}.regexes")
        if not keywords and not regexes:
            raise ValueError(f"{rule_label} must define keywords or regexes.")
        for regex in regexes:
            try:
                re.compile(regex)
            except re.error as exc:
                raise ValueError(f"{rule_label}.regexes contains an invalid regex: {exc}") from exc

        name = str(rule.get("name", f"rule_{index}")).strip() or f"rule_{index}"
        rules.append(ContentFilterRule(name=name, keywords=tuple(keywords), regexes=tuple(regexes)))

    return ContentFilterSettings(enabled=bool(mapping.get("enabled", False)), rules=tuple(rules))
