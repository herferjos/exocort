from __future__ import annotations

import asyncio
import io
import types

import pytest
from fastapi import HTTPException
from starlette.responses import Response
from starlette.datastructures import UploadFile

from app.api.v1.endpoints.transcriptions import transcribe_audio


pytestmark = [pytest.mark.service, pytest.mark.unit, pytest.mark.stt]


def test_transcribe_audio_returns_transcription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.v1.endpoints.transcriptions.ensure_speech_permission",
        lambda prompt=False: True,
    )
    monkeypatch.setattr(
        "src.transcription.resolve_locale",
        lambda code, explicit: explicit or "es-ES",
    )

    class FakeTranscription:
        def to_dict(self) -> dict[str, object]:
            return {"text": "hello world", "locale": "en"}

    monkeypatch.setattr(
        "app.api.v1.endpoints.transcriptions.transcribe_audio_file",
        lambda path, locale, timeout_s: FakeTranscription(),
    )

    upload = UploadFile(filename="voice.wav", file=io.BytesIO(b"fake-audio"))
    payload = asyncio.run(
        transcribe_audio(
            file=upload,
            model="whisper-1",
            language="en",
            prompt="ignore this",
            response_format="json",
            temperature=0.0,
        )
    )
    assert payload == {
        "text": "hello world",
        "task": "transcribe",
        "language": "en",
        "duration": None,
    }


def test_transcribe_audio_requires_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.v1.endpoints.transcriptions.ensure_speech_permission",
        lambda prompt=False: False,
    )
    upload = UploadFile(filename="voice.wav", file=io.BytesIO(b"fake-audio"))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(transcribe_audio(file=upload, language="en"))

    assert exc.value.status_code == 409


def test_transcribe_audio_no_speech_returns_204(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.v1.endpoints.transcriptions.ensure_speech_permission",
        lambda prompt=False: True,
    )
    monkeypatch.setattr(
        "src.transcription.resolve_locale",
        lambda code, explicit: explicit or "es-ES",
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.transcriptions.transcribe_audio_file",
        lambda path, locale, timeout_s: (_ for _ in ()).throw(
            RuntimeError(
                'Error Domain=kAFAssistantErrorDomain Code=1110 "No speech detected"'
            )
        ),
    )

    upload = UploadFile(filename="voice.wav", file=io.BytesIO(b"fake-audio"))
    resp = asyncio.run(transcribe_audio(file=upload, language="es-ES"))
    assert isinstance(resp, Response)
    assert resp.status_code == 204


def test_transcribe_audio_empty_text_returns_204(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.v1.endpoints.transcriptions.ensure_speech_permission",
        lambda prompt=False: True,
    )
    monkeypatch.setattr(
        "src.transcription.resolve_locale",
        lambda code, explicit: explicit or "es-ES",
    )

    class FakeEmptyTranscription:
        text = ""

        def to_dict(self) -> dict[str, object]:
            return {"text": "", "locale": "es-ES"}

    monkeypatch.setattr(
        "app.api.v1.endpoints.transcriptions.transcribe_audio_file",
        lambda path, locale, timeout_s: FakeEmptyTranscription(),
    )

    upload = UploadFile(filename="voice.wav", file=io.BytesIO(b"fake-audio"))
    resp = asyncio.run(transcribe_audio(file=upload, language="es-ES"))
    assert isinstance(resp, Response)
    assert resp.status_code == 204


def test_transcribe_audio_auto_language_uses_default_detector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.api.v1.endpoints.transcriptions.ensure_speech_permission",
        lambda prompt=False: True,
    )
    monkeypatch.setattr(
        "src.transcription.load_settings",
        lambda: types.SimpleNamespace(
            locale="auto",
            default_locale="es",
            detect_discard_min_prob=0.5,
            detect_default_min_prob=0.7,
        ),
    )
    capturerd: dict[str, object] = {}

    class FakeTranscription:
        def to_dict(self) -> dict[str, object]:
            return {"text": "hello", "locale": "en-US"}

    def fake_transcribe(path, locale, timeout_s):
        capturerd["locale"] = locale
        return FakeTranscription()

    monkeypatch.setattr(
        "app.api.v1.endpoints.transcriptions.transcribe_audio_file",
        fake_transcribe,
    )
    monkeypatch.setattr("src.transcription.detect_language", lambda path: ("en", 0.9))
    monkeypatch.setattr(
        "src.transcription.resolve_locale", lambda code, explicit: "en-US"
    )
    upload = UploadFile(filename="voice.wav", file=io.BytesIO(b"fake-audio"))
    payload = asyncio.run(
        transcribe_audio(file=upload, model="whisper-1", language="auto")
    )
    assert payload == {
        "text": "hello",
        "task": "transcribe",
        "language": "en-US",
        "duration": None,
    }
    assert capturerd["locale"] == "en-US"
