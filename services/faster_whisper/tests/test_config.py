from __future__ import annotations

import pytest

from src.config import load_settings


pytestmark = [pytest.mark.service, pytest.mark.unit]


def test_load_settings_reads_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    load_settings.cache_clear()
    monkeypatch.setenv("FASTER_WHISPER_MODEL_PATH", "small")
    monkeypatch.setenv("FASTER_WHISPER_DEVICE", "cpu")
    monkeypatch.setenv("FASTER_WHISPER_COMPUTE_TYPE", "int8")
    monkeypatch.setenv("FASTER_WHISPER_BEAM_SIZE", "7")
    monkeypatch.setenv("FASTER_WHISPER_LANGUAGE", "en")

    settings = load_settings()
    assert settings.model_path == "small"
    assert settings.beam_size == 7
    assert settings.language == "en"


def test_load_settings_maps_auto_language_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    load_settings.cache_clear()
    monkeypatch.setenv("FASTER_WHISPER_LANGUAGE", "auto")

    settings = load_settings()

    assert settings.language is None
