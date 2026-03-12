"""Google Gemini API client via google-genai."""
import logging
from typing import Type

from google import genai

from ai.config import resolve_api_key
from . import base

log = logging.getLogger("processor.llm.gemini")


class GeminiClient(base.LLMClient):
    """Client for Google Gemini using the official google-genai package."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        api_key_env: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ):
        self.model = model
        api_key = resolve_api_key(api_key, api_key_env, "GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required")
        self._client = genai.Client(api_key=api_key)
        self.max_tokens = max_tokens
        self.temperature = temperature

    def generate(self, system: str, user: str, output_model: Type[base.T]) -> base.T:
        log.info("Using Gemini for structured output | model=%s", self.model)

        config = {
            "system_instruction": system,
            "response_mime_type": "application/json",
            "response_json_schema": output_model.model_json_schema(),
            "max_output_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        response = self._client.models.generate_content(
            model=self.model,
            contents=user,
            config=config,
        )
        raw_response = (response.text or "").strip()
        return output_model.model_validate_json(raw_response)
