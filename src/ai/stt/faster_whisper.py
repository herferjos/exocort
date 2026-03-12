import logging
from pathlib import Path

from .base import SpeechTranscriber

log = logging.getLogger("ai.stt.faster_whisper")


class FasterWhisperTranscriber(SpeechTranscriber):
    _model = None
    _model_key = None

    def __init__(self, model: str, device: str, compute_type: str, language: str | None, vad_filter: bool):
        self.model_name = model
        self.device = device
        self.compute_type = compute_type
        self.language = language or None
        self.vad_filter = vad_filter

    def _get_model(self):
        if self.__class__._model is not None and self.__class__._model_key == self._key():
            return self.__class__._model
        from faster_whisper import WhisperModel

        self.__class__._model = WhisperModel(self.model_name, device=self.device, compute_type=self.compute_type)
        self.__class__._model_key = self._key()
        return self.__class__._model

    def _key(self) -> str:
        return f"{self.model_name}|{self.device}|{self.compute_type}"

    def transcribe(self, path: Path, mime_type: str | None = None) -> str:
        try:
            model = self._get_model()
            segments, info = model.transcribe(
                str(path),
                language=self.language,
                task="transcribe",
                vad_filter=self.vad_filter,
            )
            text = "".join((seg.text or "") for seg in segments).strip()
            return text
        except Exception as exc:
            log.warning("Local transcription failed | path=%s | error=%s", path, exc)
            return ""
