from __future__ import annotations

import asyncio
import io

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from services.mac_asr.src.app import transcribe_audio


pytestmark = [pytest.mark.service, pytest.mark.unit, pytest.mark.stt]


def test_transcribe_audio_returns_transcription(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.mac_asr.src.app.ensure_speech_permission",
        lambda prompt=False: True,
    )

    class FakeTranscription:
        def to_dict(self) -> dict[str, object]:
            return {"text": "hello world", "locale": "en", "is_final": True}

    monkeypatch.setattr(
        "services.mac_asr.src.app.transcribe_audio_file",
        lambda path, locale, timeout_s: FakeTranscription(),
    )

    upload = UploadFile(filename="voice.wav", file=io.BytesIO(b"fake-audio"))

    payload = asyncio.run(transcribe_audio(file=upload, language="en"))

    assert payload == {"text": "hello world", "locale": "en", "is_final": True}


def test_transcribe_audio_requires_permission(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.mac_asr.src.app.ensure_speech_permission",
        lambda prompt=False: False,
    )
    upload = UploadFile(filename="voice.wav", file=io.BytesIO(b"fake-audio"))

    with pytest.raises(HTTPException) as exc:
        asyncio.run(transcribe_audio(file=upload, language="en"))

    assert exc.value.status_code == 409
