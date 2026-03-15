"""Unit tests for collector forward (forward_upload)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("requests")
from exocort.collector.config import EndpointConfig
from exocort.collector.forward import forward_upload


pytestmark = pytest.mark.unit


@patch("exocort.collector.forward.requests.request")
def test_forward_upload_success_default_format(mock_request: MagicMock) -> None:
    mock_request.return_value.status_code = 200
    mock_request.return_value.text = '{"text": "hello"}'

    ep = EndpointConfig(url="http://localhost:9092/transcribe", timeout=10.0)
    ok, status, body, extra = forward_upload(ep, b"wav-data", "x.wav", "audio/wav")
    assert ok is True
    assert status == 200
    assert "hello" in body
    assert extra.get("parsed_text") == '{"text": "hello"}'
    mock_request.assert_called_once()
    call_kw = mock_request.call_args[1]
    assert call_kw["timeout"] == 10.0
    assert call_kw["files"]["file"][0] == "x.wav"
    assert call_kw["data"] is None or call_kw["data"] == {}


@patch("exocort.collector.forward.requests.request")
def test_forward_upload_rejected(mock_request: MagicMock) -> None:
    mock_request.return_value.status_code = 400
    mock_request.return_value.text = "Bad request"

    ep = EndpointConfig(url="http://localhost:9092/transcribe")
    ok, status, body, extra = forward_upload(ep, b"", "x.wav", "audio/wav")
    assert ok is False
    assert status == 400
    assert body == "Bad request"
    assert extra == {}


@patch("exocort.collector.forward.requests.request")
def test_forward_upload_openai_format_parses_json(mock_request: MagicMock) -> None:
    mock_request.return_value.status_code = 200
    mock_request.return_value.text = '{"text": "transcribed words"}'

    ep = EndpointConfig(
        url="http://localhost:9092/v1/audio/transcriptions",
        format="openai",
        body={"model": "whisper-1"},
    )
    ok, status, body, extra = forward_upload(ep, b"wav", "a.wav", "audio/wav", stream_type="audio")
    assert ok is True
    assert status == 200
    assert extra.get("parsed_text") == "transcribed words"
    assert extra.get("parsed_json") == {"text": "transcribed words"}
    call_kw = mock_request.call_args[1]
    assert call_kw["data"] == {"model": "whisper-1"}


@patch("exocort.collector.forward.requests.request")
def test_forward_upload_openai_fallback_plain_text(mock_request: MagicMock) -> None:
    mock_request.return_value.status_code = 200
    mock_request.return_value.text = "plain text response"

    ep = EndpointConfig(url="http://localhost:9092/transcribe", format="openai")
    ok, status, body, extra = forward_upload(ep, b"wav", "a.wav", "audio/wav")
    assert ok is True
    assert extra.get("parsed_text") == "plain text response"
    assert "parsed_json" not in extra


