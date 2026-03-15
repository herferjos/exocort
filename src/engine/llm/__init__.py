"""HTTP-only LLM client using a single endpoint and wire format."""

import logging
from typing import Type

from pydantic import BaseModel

from engine import http
from .config import get_llm_config
from .retry import RetryingLLMClient

log = logging.getLogger("processor.llm")


class _HttpLLMClient:
    def generate(self, system: str, user: str, output_model: Type[BaseModel]) -> BaseModel:
        cfg = get_llm_config()
        from engine.config import resolve_api_key  # local import to avoid cycles

        api_key = resolve_api_key(cfg.api_key, cfg.api_key_env, None)
        if not api_key and cfg.format in {"openai", "anthropic"}:
            raise ValueError("LLM config requires an API key via 'api_key' or 'api_key_env'")

        text = http.chat_completion(
            endpoint_url=cfg.endpoint_url,
            format_name=cfg.format,
            model=cfg.model,
            api_key=api_key,
            headers=cfg.headers,
            api_key_header=cfg.api_key_header,
            auth_scheme=cfg.auth_scheme,
            anthropic_version=cfg.anthropic_version,
            system=system,
            user=user,
            timeout_s=cfg.timeout_s,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            image_path=None,
            audio_path=None,
            audio_mime_type=None,
            output_model=output_model,
        )
        return http.parse_structured_output(text, output_model)


def get_client(provider: str | None = None) -> _HttpLLMClient:
    """Return a generic HTTP LLM client wrapped with retry (provider arg ignored)."""
    cfg = get_llm_config()
    client = _HttpLLMClient()
    return RetryingLLMClient(client, max_retries=cfg.max_retries)


__all__ = [
    "get_client",
    "get_llm_config",
]
