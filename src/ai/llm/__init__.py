"""Pluggable LLM clients: local GGUF (llama-cpp-python), OpenAI, Gemini."""
import logging
from . import base, gemini, llama_cpp, openai, retry
from .config import get_llm_config

log = logging.getLogger("processor.llm")


def get_client(provider: str | None = None) -> base.LLMClient:
    """Return LLM client for the given provider (from config if None), wrapped with retry."""
    cfg = get_llm_config()
    p = (provider or cfg.provider).lower()

    if p == "llama_cpp":
        client = llama_cpp.LocalLlamaClient(cfg)
    elif p == "openai":
        model = cfg.model or "gpt-4o-mini"
        client = openai.OpenAIClient(
            model=model,
            api_key=cfg.api_key,
            api_key_env=cfg.api_key_env,
            base_url=cfg.base_url,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
        )
    elif p == "gemini":
        model = cfg.model or "gemini-2.0-flash"
        client = gemini.GeminiClient(
            model=model,
            api_key=cfg.api_key_env,
            api_key_env=cfg.api_key_env,
            max_tokens=cfg.max_tokens,
            temperature=cfg.temperature,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {p}")
    return retry.RetryingLLMClient(client, max_retries=cfg.max_retries)


__all__ = [
    "get_client",
    "get_llm_config",
    "base",
]
