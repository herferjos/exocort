import abc
from pathlib import Path


class SpeechTranscriber(abc.ABC):
    @abc.abstractmethod
    def transcribe(self, path: Path, mime_type: str | None = None) -> str:
        ...
