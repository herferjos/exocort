"""LLM client helpers for the processor."""

from __future__ import annotations

import copy
import json
import multiprocessing
import logging
import time
from typing import Any, Protocol

from .config import LLMConfig
from .utils import extract_text_from_data

logger = logging.getLogger(__name__)


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
    def complete_json(self, stage_name: str, prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...


class ProcessorLLMClient:
    def __init__(self, llm_config: LLMConfig, timeout_s: float = 60.0) -> None:
        self._config = llm_config
        self._timeout_s = timeout_s

    def complete_json(self, stage_name: str, prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
        logger.debug(
            "Completing LLM JSON request: stage=%s payload_keys=%s timeout_s=%s",
            stage_name,
            sorted(payload.keys()),
            self._timeout_s,
        )
        text = self._complete(stage_name, prompt, payload)
        parsed = parse_json_payload(text)
        if isinstance(parsed, dict):
            logger.debug("Parsed LLM response as object: stage=%s keys=%s", stage_name, sorted(parsed.keys()))
            return parsed
        logger.debug("Parsed LLM response as list: stage=%s items=%s", stage_name, len(parsed))
        return {"items": parsed}

    def _complete(self, stage_name: str, prompt: str, payload: dict[str, Any]) -> str:
        import requests

        url = self._config.url
        if not url:
            raise RuntimeError("Processor LLM URL is not configured")

        body = copy.deepcopy(self._config.body)
        body["messages"] = build_prompt_payload(stage_name, prompt, payload)
        logger.info(
            "Sending LLM request: stage=%s url=%s body_keys=%s messages=%s",
            stage_name,
            url,
            sorted(body.keys()),
            len(body["messages"]),
        )

        response = requests.post(
            url,
            json=body,
            headers=normalize_headers(self._config.headers),
            timeout=self._timeout_s,
        )
        if not response.ok:
            logger.error(
                "LLM request failed: stage=%s status=%s body=%s",
                stage_name,
                response.status_code,
                response.text.strip(),
            )
            raise RuntimeError(f"LLM request failed with status {response.status_code}: {response.text.strip()}")
        text = response_text(response)
        if not text:
            logger.error("LLM response was empty: stage=%s", stage_name)
            raise RuntimeError("LLM response was empty")
        logger.debug("Received LLM response text: stage=%s chars=%s", stage_name, len(text))
        return text


class SemaphoreLLMClient:
    def __init__(self, inner: SupportsLLMClient, semaphore: multiprocessing.Semaphore) -> None:
        self._inner = inner
        self._semaphore = semaphore

    def complete_json(self, stage_name: str, prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
        start = time.monotonic()
        logger.debug("Waiting for LLM semaphore: stage=%s", stage_name)
        self._semaphore.acquire()
        try:
            waited_s = time.monotonic() - start
            if waited_s > 0:
                logger.debug("Acquired LLM semaphore: stage=%s wait_s=%.3f", stage_name, waited_s)
            return self._inner.complete_json(stage_name, prompt, payload)
        finally:
            self._semaphore.release()
            logger.debug("Released LLM semaphore: stage=%s", stage_name)
