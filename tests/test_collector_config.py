"""Unit tests for collector config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from exocort.collector.config import CollectorConfig, EndpointConfig


pytestmark = pytest.mark.unit


def test_load_missing_file_returns_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXOCORT_CONFIG", str(tmp_path / "nonexistent.toml"))
    monkeypatch.chdir(tmp_path)
    cfg = CollectorConfig.load()
    assert cfg.audio is None
    assert cfg.screen is None


def test_load_from_path(tmp_path: Path) -> None:
    path = tmp_path / "exocort.toml"
    path.write_text(
        """
[services.audio]
url = "http://localhost:9092/transcribe"
method = "POST"
timeout = 15
headers = { X-Custom = "yes" }
body = {}

[services.screen]
url = "http://localhost:9091/ocr"
timeout = 10
headers = {}
body = {}
""",
        encoding="utf-8",
    )
    cfg = CollectorConfig.load(path=path)
    assert cfg.audio is not None
    assert cfg.audio.url == "http://localhost:9092/transcribe"
    assert cfg.audio.method == "POST"
    assert cfg.audio.timeout == 15.0
    assert cfg.audio.headers == {"X-Custom": "yes"}
    assert cfg.audio.format == "default"
    assert cfg.audio.body == {}
    assert cfg.audio.response_path is None

    assert cfg.screen is not None
    assert cfg.screen.url == "http://localhost:9091/ocr"
    assert cfg.screen.method == "POST"
    assert cfg.screen.timeout == 10.0


def test_load_format_and_body(tmp_path: Path) -> None:
    path = tmp_path / "exocort.toml"
    path.write_text(
        """
[services.audio]
url = "https://api.example.com/transcribe"
format = "openai"
response_path = "text"
body = { model = "whisper-1", language = "en" }
""",
        encoding="utf-8",
    )
    cfg = CollectorConfig.load(path=path)
    assert cfg.audio is not None
    assert cfg.audio.format == "openai"
    assert cfg.audio.body == {"model": "whisper-1", "language": "en"}
    assert cfg.audio.response_path == "text"
    assert cfg.screen is None


def test_endpoint_config_defaults() -> None:
    ep = EndpointConfig(url="http://x/y")
    assert ep.method == "POST"
    assert ep.timeout == 30.0
    assert ep.headers == {}
    assert ep.format == "default"
    assert ep.body == {}
    assert ep.response_path is None
