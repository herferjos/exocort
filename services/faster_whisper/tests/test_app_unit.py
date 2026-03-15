from __future__ import annotations

import asyncio
import io

import pytest
from starlette.datastructures import UploadFile

from services.faster_whisper.app import transcribe_audio


pytestmark = [pytest.mark.service, pytest.mark.unit]


class FakeSegment:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeModel:
    def transcribe(self, path, beam_size, language, vad_filter, initial_prompt):
        return [FakeSegment("hello"), FakeSegment("world")], None


def test_transcribe_audio_returns_joined_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("services.faster_whisper.app.get_model", lambda: FakeModel())
    upload = UploadFile(filename="voice.wav", file=io.BytesIO(b"fake-audio"))

    payload = asyncio.run(transcribe_audio(file=upload, language="en", prompt="test"))

    assert payload == {"text": "hello world"}
