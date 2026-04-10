from __future__ import annotations

import asyncio
import io
import types

import pytest
from fastapi import HTTPException
from starlette.responses import Response
from starlette.datastructures import UploadFile

from common.models.asr import TranscriptionRequest, TranscriptionResponse
from services.mac_asr.app.api.v1.endpoints.transcriptions import transcribe_audio


pytestmark = [pytest.mark.service, pytest.mark.unit, pytest.mark.stt]


def test_transcribe_audio_returns_transcription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "services.mac_asr.app.api.v1.endpoints.transcriptions.ensure_speech_permission",
        lambda prompt=False: True,
    )
    monkeypatch.setattr(
        "services.mac_asr.app.api.v1.endpoints.transcriptions.resolve_request_locale",
        lambda path, language: language or "es-ES",
    )

    monkeypatch.setattr(
        "services.mac_asr.app.api.v1.endpoints.transcriptions.transcribe_audio_file",
        lambda path, locale, timeout_s: TranscriptionResponse(
            text="hello world",
            language=locale,
            duration=None,
        ),
    )

    upload = UploadFile(filename="voice.wav", file=io.BytesIO(b"fake-audio"))
    payload = asyncio.run(
        transcribe_audio(
            file=upload,
            payload=TranscriptionRequest(
                model="whisper-1",
                language="en",
                prompt="ignore this",
                response_format="json",
                temperature=0.0,
            ),
        )
    )
    assert isinstance(payload, TranscriptionResponse)
    assert payload.model_dump() == {
        "text": "hello world",
        "task": "transcribe",
        "language": "en",
        "duration": None,
    }


def test_transcribe_audio_requires_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.mac_asr.app.api.v1.endpoints.transcriptions.ensure_speech_permission",
        lambda prompt=False: False,
    )
    upload = UploadFile(filename="voice.wav", file=io.BytesIO(b"fake-audio"))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(transcribe_audio(file=upload, payload=TranscriptionRequest(language="en")))

    assert exc.value.status_code == 409


def test_transcribe_audio_no_speech_returns_204(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "services.mac_asr.app.api.v1.endpoints.transcriptions.ensure_speech_permission",
        lambda prompt=False: True,
    )
    monkeypatch.setattr(
        "services.mac_asr.app.api.v1.endpoints.transcriptions.resolve_request_locale",
        lambda path, language: language or "es-ES",
    )
    monkeypatch.setattr(
        "services.mac_asr.app.api.v1.endpoints.transcriptions.transcribe_audio_file",
        lambda path, locale, timeout_s: (_ for _ in ()).throw(
            RuntimeError(
                'Error Domain=kAFAssistantErrorDomain Code=1110 "No speech detected"'
            )
        ),
    )

    upload = UploadFile(filename="voice.wav", file=io.BytesIO(b"fake-audio"))
    resp = asyncio.run(transcribe_audio(file=upload, payload=TranscriptionRequest(language="es-ES")))
    assert isinstance(resp, Response)
    assert resp.status_code == 204


def test_transcribe_audio_retry_error_returns_204(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "services.mac_asr.app.api.v1.endpoints.transcriptions.ensure_speech_permission",
        lambda prompt=False: True,
    )
    monkeypatch.setattr(
        "services.mac_asr.app.api.v1.endpoints.transcriptions.resolve_request_locale",
        lambda path, language: language or "es-ES",
    )
    monkeypatch.setattr(
        "services.mac_asr.app.api.v1.endpoints.transcriptions.transcribe_audio_file",
        lambda path, locale, timeout_s: (_ for _ in ()).throw(
            RuntimeError(
                'Error Domain=kAFAssistantErrorDomain Code=203 "Retry" '
                "UserInfo={NSLocalizedDescription=Retry, "
                "NSUnderlyingError=0x0 {Error Domain=SiriSpeechErrorDomain Code=1 \"(null)\"}}"
            )
        ),
    )

    upload = UploadFile(filename="voice.wav", file=io.BytesIO(b"fake-audio"))
    resp = asyncio.run(transcribe_audio(file=upload, payload=TranscriptionRequest(language="es-ES")))
    assert isinstance(resp, Response)
    assert resp.status_code == 204


def test_transcribe_audio_empty_text_returns_204(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "services.mac_asr.app.api.v1.endpoints.transcriptions.ensure_speech_permission",
        lambda prompt=False: True,
    )
    monkeypatch.setattr(
        "services.mac_asr.app.api.v1.endpoints.transcriptions.resolve_request_locale",
        lambda path, language: language or "es-ES",
    )

    monkeypatch.setattr(
        "services.mac_asr.app.api.v1.endpoints.transcriptions.transcribe_audio_file",
        lambda path, locale, timeout_s: TranscriptionResponse(
            text="",
            language=locale,
            duration=None,
        ),
    )

    upload = UploadFile(filename="voice.wav", file=io.BytesIO(b"fake-audio"))
    resp = asyncio.run(transcribe_audio(file=upload, payload=TranscriptionRequest(language="es-ES")))
    assert isinstance(resp, Response)
    assert resp.status_code == 204


def test_transcribe_audio_auto_language_uses_default_detector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "services.mac_asr.app.api.v1.endpoints.transcriptions.ensure_speech_permission",
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
    captured: dict[str, object] = {}

    def fake_transcribe(path, locale, timeout_s):
        captured["locale"] = locale
        return TranscriptionResponse(
            text="hello",
            language=locale,
            duration=None,
        )

    monkeypatch.setattr(
        "services.mac_asr.app.api.v1.endpoints.transcriptions.transcribe_audio_file",
        fake_transcribe,
    )
    monkeypatch.setattr(
        "services.mac_asr.app.api.v1.endpoints.transcriptions.resolve_request_locale",
        lambda path, language: "en-US",
    )
    upload = UploadFile(filename="voice.wav", file=io.BytesIO(b"fake-audio"))
    payload = asyncio.run(
        transcribe_audio(
            file=upload,
            payload=TranscriptionRequest(model="whisper-1", language="auto"),
        )
    )
    assert payload.model_dump() == {
        "text": "hello",
        "task": "transcribe",
        "language": "en-US",
        "duration": None,
    }
    assert captured["locale"] == "en-US"
