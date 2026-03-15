from pathlib import Path

from .base import SpeechTranscriber


class NullTranscriber(SpeechTranscriber):
    def transcribe(self, path: Path, mime_type: str | None = None) -> str:
        return ""
