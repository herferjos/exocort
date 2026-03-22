"""LLM client helpers for the processor."""

from __future__ import annotations

import copy
import json
import multiprocessing
from typing import Any, Protocol

from .config import LLMConfig
from .utils import extract_text_from_data


def strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return stripped.strip()


def parse_json_payload(text: str | dict[str, Any] | list[Any]) -> Any:
    if isinstance(text, (dict, list)):
        return text
    candidate = strip_code_fences(text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        for anchor in ("{", "["):
            idx = candidate.find(anchor)
            if idx < 0:
                continue
            try:
                value, _ = json.JSONDecoder().raw_decode(candidate[idx:])
                return value
            except json.JSONDecodeError:
                continue
    raise ValueError("LLM response did not contain valid JSON")


def response_text(response: Any) -> str:
    try:
        parsed = response.json()
    except ValueError:
        return response.text.strip()
    extracted = extract_text_from_data(parsed)
    if extracted:
        return extracted.strip()
    if isinstance(parsed, (dict, list)):
        return json.dumps(parsed, ensure_ascii=False)
    return response.text.strip()


def build_prompt_payload(level: str, prompt: str, payload: dict[str, Any]) -> list[dict[str, str]]:
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return [
        {"role": "system", "content": prompt.strip()},
        {"role": "user", "content": f"Level: {level}\n\nInput:\n{body}"},
    ]


def normalize_headers(headers: dict[str, str]) -> dict[str, str]:
    out = {str(k): str(v) for k, v in headers.items()}
    if "content-type" not in {key.lower() for key in out}:
        out["Content-Type"] = "application/json"
    return out


class SupportsLLMClient(Protocol):
    def complete_json(self, prompt_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...


class ProcessorLLMClient:
    def __init__(self, llm_config: LLMConfig, prompts: dict[str, str], timeout_s: float = 60.0) -> None:
        self._config = llm_config
        self._prompts = prompts
        self._timeout_s = timeout_s

    def complete_json(self, prompt_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        text = self._complete(prompt_key, payload)
        parsed = parse_json_payload(text)
        if isinstance(parsed, dict):
            return parsed
        return {"items": parsed}

    def _complete(self, prompt_key: str, payload: dict[str, Any]) -> str:
        import requests

        url = self._config.url
        if not url:
            raise RuntimeError("Processor LLM URL is not configured")

        prompt = self._prompts.get(prompt_key) or prompt_key
        body = copy.deepcopy(self._config.body)
        body["messages"] = build_prompt_payload(prompt_key, prompt, payload)

        response = requests.post(
            url,
            json=body,
            headers=normalize_headers(self._config.headers),
            timeout=self._timeout_s,
        )
        if not response.ok:
            raise RuntimeError(f"LLM request failed with status {response.status_code}: {response.text.strip()}")
        text = response_text(response)
        if not text:
            raise RuntimeError("LLM response was empty")
        return text


class SemaphoreLLMClient:
    def __init__(self, inner: SupportsLLMClient, semaphore: multiprocessing.Semaphore) -> None:
        self._inner = inner
        self._semaphore = semaphore

    def complete_json(self, prompt_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._semaphore.acquire()
        try:
            return self._inner.complete_json(prompt_key, payload)
        finally:
            self._semaphore.release()
