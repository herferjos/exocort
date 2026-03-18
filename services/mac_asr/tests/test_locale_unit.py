from __future__ import annotations

import pytest

from src import asr


pytestmark = [pytest.mark.service, pytest.mark.unit, pytest.mark.stt]


def test_resolve_locale_picks_matching_supported_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(asr, "_supported_locale_ids", lambda: ["es-ES", "en-US"])
    monkeypatch.setattr(asr, "_language_code_for_locale", lambda loc: loc.split("-")[0].lower())
    monkeypatch.setattr(asr, "LOCALE", "")

    assert asr.resolve_locale("es", None) == "es-ES"


def test_resolve_locale_prefers_configured_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(asr, "_supported_locale_ids", lambda: ["en-US", "en-GB"])
    monkeypatch.setattr(asr, "_language_code_for_locale", lambda loc: loc.split("-")[0].lower())
    monkeypatch.setattr(asr, "LOCALE", "en-GB")

    assert asr.resolve_locale("en", None) == "en-GB"


def test_resolve_locale_fallbacks_to_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(asr, "_supported_locale_ids", lambda: ["fr-FR"])
    monkeypatch.setattr(asr, "_language_code_for_locale", lambda loc: loc.split("-")[0].lower())
    monkeypatch.setattr(asr, "LOCALE", "es-ES")

    assert asr.resolve_locale(None, None) == "es-ES"
