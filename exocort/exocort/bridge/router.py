from __future__ import annotations

import os

from .client import HttpClient
from .models.asr import AsrRequest, AsrResult
from .models.common import ProviderConfig
from .models.ocr import OcrRequest, OcrResult
from .models.response import ResponseRequest, ResponseResult
from .providers import anthropic, gemini, mistral, openai
from .utils.provider import infer_provider


class ProviderBridge:
    def __init__(self, config: ProviderConfig) -> None:
        self._config = config
        self._client = HttpClient(timeout_s=config.timeout_s, retries=config.retries)

    def asr(self, req: AsrRequest) -> AsrResult:
        provider = self._provider_for(req.model)
        api_key = self._api_key()
        if req.format == "llm":
            if provider == "gemini":
                return gemini.asr(self._client, self._config.api_base, api_key, req, self._config.extra_headers)
            if provider == "mistral":
                return self._asr_via_response(req)
            raise ValueError(f"ASR llm format is not supported for provider={provider}.")
        if provider == "mistral":
            return mistral.asr(self._client, self._config.api_base, api_key, req, self._config.extra_headers)
        if provider == "openai":
            return openai.asr(self._client, self._config.api_base, api_key, req, self._config.extra_headers)
        if provider == "gemini":
            return gemini.asr(self._client, self._config.api_base, api_key, req, self._config.extra_headers)
        raise ValueError(f"ASR dedicated format is not supported for provider={provider}.")

    def ocr(self, req: OcrRequest) -> OcrResult:
        provider = self._provider_for(req.model)
        api_key = self._api_key()
        if req.format == "ocr":
            if provider == "mistral":
                return mistral.ocr(self._client, self._config.api_base, api_key, req, self._config.extra_headers)
            raise ValueError(f"OCR format=ocr is only supported for provider=mistral.")
        if provider == "mistral":
            return mistral.ocr_llm(self._client, self._config.api_base, api_key, req, self._config.extra_headers)
        if provider == "openai":
            return openai.ocr(self._client, self._config.api_base, api_key, req, self._config.extra_headers)
        if provider == "gemini":
            return gemini.ocr(self._client, self._config.api_base, api_key, req, self._config.extra_headers)
        if provider == "anthropic":
            return anthropic.ocr(self._client, self._config.api_base, api_key, req, self._config.extra_headers)
        raise ValueError(f"OCR is not supported for provider={provider}.")

    def response(self, req: ResponseRequest) -> ResponseResult:
        provider = self._provider_for(req.model)
        api_key = self._api_key()
        if provider == "openai":
            return openai.response(self._client, self._config.api_base, api_key, req, self._config.extra_headers)
        if provider == "mistral":
            return mistral.response(self._client, self._config.api_base, api_key, req, self._config.extra_headers)
        if provider == "gemini":
            return gemini.response(self._client, self._config.api_base, api_key, req, self._config.extra_headers)
        if provider == "anthropic":
            return anthropic.response(self._client, self._config.api_base, api_key, req, self._config.extra_headers)
        raise ValueError(f"response mode is not supported for provider={provider}.")

    def _api_key(self) -> str:
        return os.getenv(self._config.api_key_env, "test_key") if self._config.api_key_env else "test_key"

    def _provider_for(self, model: str) -> str:
        return infer_provider(model, self._config.api_base, self._config.provider)

    def _asr_via_response(self, req: AsrRequest) -> AsrResult:
        result = self.response(
            ResponseRequest(
                model=req.model,
                messages=(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": req.prompt or "Transcribe the audio and return only the transcript.",
                            },
                            {
                                "type": "input_audio",
                                "media": req.media,
                            },
                        ],
                    },
                ),
                temperature=req.temperature,
            )
        )
        text = result.text.strip()
        if not text:
            raise ValueError("ASR response text is empty.")
        return AsrResult(text=text, raw=result.raw)
