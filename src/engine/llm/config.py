from __future__ import annotations

from dataclasses import dataclass

import settings
from engine.config import (
    load_json_config,
    normalize_api_format,
    read_dict_str,
    read_float,
    read_int,
    read_str,
)


@dataclass(frozen=True)
class LLMConfig:
    format: str
    endpoint_url: str
    model: str | None
    api_key: str | None
    api_key_env: str | None
    api_key_header: str | None
    auth_scheme: str
    headers: dict[str, str]
    anthropic_version: str | None
    timeout_s: float
    max_tokens: int
    temperature: float
    max_retries: int
    concurrency: int
    processor_prompts: dict[str, dict[str, str]]


_llm_config: LLMConfig | None = None


def _load_config() -> LLMConfig:
    path = settings.llm_config_path()
    data = load_json_config(path, "LLM")

    format_name = normalize_api_format(read_str(data, "format", None) or "openai")
    model = read_str(data, "model", None)
    api_key = read_str(data, "api_key", None)
    api_key_env = read_str(data, "api_key_env", None)
    api_key_header = read_str(data, "api_key_header", None)
    auth_scheme = (read_str(data, "auth_scheme", "bearer") or "bearer").lower()
    headers = read_dict_str(data, "headers")
    anthropic_version = read_str(data, "anthropic_version", None)
    timeout_s = read_float(data, "timeout_s", 60.0)

    endpoint_url = read_str(data, "endpoint_url", None)
    if not endpoint_url:
        raise ValueError("LLM config requires 'endpoint_url'")

    max_tokens = read_int(data, "max_tokens", 4096)
    temperature = read_float(data, "temperature", 0.3)

    max_retries = read_int(data, "max_retries", 3)
    if max_retries < 1:
        max_retries = 1

    concurrency = read_int(data, "concurrency", 1)
    if concurrency < 1:
        concurrency = 1

    prompts_raw = (
        data.get("processor_prompts")
        if isinstance(data.get("processor_prompts"), dict)
        else None
    )
    if prompts_raw is None and isinstance(data.get("prompts"), dict):
        prompts_raw = data.get("prompts")
    processor_prompts: dict[str, dict[str, str]] = {}
    if isinstance(prompts_raw, dict):
        for key, value in prompts_raw.items():
            if not isinstance(value, dict):
                continue
            processor_prompts[key] = {
                str(field): str(text)
                for field, text in value.items()
                if isinstance(text, (str, int, float))
            }

    return LLMConfig(
        format=format_name,
        endpoint_url=endpoint_url,
        model=model,
        api_key=api_key,
        api_key_env=api_key_env,
        api_key_header=api_key_header,
        auth_scheme=auth_scheme,
        headers=headers,
        anthropic_version=anthropic_version,
        timeout_s=timeout_s,
        max_tokens=max_tokens,
        temperature=temperature,
        max_retries=max_retries,
        concurrency=concurrency,
        processor_prompts=processor_prompts,
    )


def get_llm_config() -> LLMConfig:
    global _llm_config
    if _llm_config is None:
        _llm_config = _load_config()
    return _llm_config


def get_processor_prompt(section: str, field: str) -> str:
    cfg = get_llm_config()
    raw = cfg.processor_prompts.get(section, {})
    value = raw.get(field) if isinstance(raw, dict) else None
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, (int, float)):
        return str(value)
    raise ValueError(
        f"Missing processor prompt '{section}.{field}' in LLM config. "
        "Define it under 'processor_prompts' in llm.json."
    )
