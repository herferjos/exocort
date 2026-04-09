from __future__ import annotations

import types

import pytest

from src import lang_detect


pytestmark = [pytest.mark.service, pytest.mark.unit, pytest.mark.stt]


def test_detect_language_accepts_confident_result(monkeypatch: pytest.MonkeyPatch) -> None:
    info = types.SimpleNamespace(language="es", language_probability=0.9)

    class FakeModel:
        def transcribe(self, path, beam_size, language):
            return [], info

    monkeypatch.setattr(lang_detect, "get_detector_model", lambda: FakeModel())
    monkeypatch.setattr(
        lang_detect,
        "load_settings",
        lambda: type("Settings", (), {"detect_discard_min_prob": 0.5})(),
    )

    detected, prob = lang_detect.detect_language(path=types.SimpleNamespace())
    assert detected == "es"
    assert prob == 0.9


def test_detect_language_rejects_low_probability(monkeypatch: pytest.MonkeyPatch) -> None:
    info = types.SimpleNamespace(language="en", language_probability=0.2)

    class FakeModel:
        def transcribe(self, path, beam_size, language):
            return [], info

    monkeypatch.setattr(lang_detect, "get_detector_model", lambda: FakeModel())
    monkeypatch.setattr(
        lang_detect,
        "load_settings",
        lambda: type("Settings", (), {"detect_discard_min_prob": 0.5})(),
    )

    detected, prob = lang_detect.detect_language(path=types.SimpleNamespace())
    assert detected is None
    assert prob == 0.2
