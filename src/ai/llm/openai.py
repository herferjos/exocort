"""OpenAI API client using the official openai library."""
import logging
from typing import Type

from openai import OpenAI

from ai.config import resolve_api_key
from . import base

log = logging.getLogger("processor.llm.openai")


class OpenAIClient(base.LLMClient):
    """Client for OpenAI chat completions with structured output via Pydantic."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        api_key_env: str | None = None,
        base_url: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ):
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.model = model
        self.api_key = resolve_api_key(api_key, api_key_env, "OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required")
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self.max_tokens = max_tokens
        self.temperature = temperature

    def generate(self, system: str, user: str, output_model: Type[base.T]) -> base.T:
        log.info("Using OpenAI for structured output | model=%s", self.model)

        response = self.client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            text_format=output_model,
            max_output_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        return response.output_parsed
