"""Unit tests for collector format adapters."""

from __future__ import annotations

import pytest

from exocort.collector.config import EndpointConfig
from exocort.collector.formats import get_adapter
from exocort.collector.formats.openai import _extract_text_from_openai_body


pytestmark = pytest.mark.unit


def test_get_adapter_default() -> None:
    a = get_adapter("default")
    assert a is not None
    assert a.__class__.__name__ == "DefaultAdapter"


def test_get_adapter_openai() -> None:
    a = get_adapter("openai")
    assert a is not None
    assert a.__class__.__name__ == "OpenAIAdapter"


def test_get_adapter_unknown_falls_back_to_default() -> None:
    a = get_adapter("unknown_format")
    assert a.__class__.__name__ == "DefaultAdapter"


def test_default_adapter_build_request() -> None:
    ep = EndpointConfig(url="http://x/y", body={"model": "whisper-1"})
    adapter = get_adapter("default")
    req = adapter.build_request(ep, b"data", "f.wav", "audio/wav", "audio")
    assert req.method == "POST"
    assert req.url == "http://x/y"
    assert req.files is not None
    assert req.files["file"][0] == "f.wav"
    assert req.data == {"model": "whisper-1"}


def test_openai_adapter_parse_response_text_key() -> None:
    adapter = get_adapter("openai")
    p = adapter.parse_response(200, '{"text": "hello world"}')
    assert p.ok is True
    assert p.parsed_text == "hello world"
    assert p.parsed_json == {"text": "hello world"}


def test_openai_adapter_parse_response_choices_content() -> None:
    adapter = get_adapter("openai")
    p = adapter.parse_response(200, '{"choices": [{"message": {"content": "OCR result"}}]}')
    assert p.ok is True
    assert p.parsed_text == "OCR result"


def test_extract_text_from_openai_body_plain_text_key() -> None:
    assert _extract_text_from_openai_body({"text": "hi"}) == "hi"


def test_extract_text_from_openai_body_choices() -> None:
    assert _extract_text_from_openai_body({
        "choices": [{"message": {"content": "out"}}]
    }) == "out"


def test_extract_text_from_openai_body_missing_returns_none() -> None:
    assert _extract_text_from_openai_body({}) is None
