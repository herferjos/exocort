from __future__ import annotations

import logging
import wave
from pathlib import Path
from threading import Lock
from uuid import uuid4

from litellm import transcription

from .device import remove_wav_and_meta, wav_rms
from .models import AudioSegment, Settings
from ...vault import new_record_id, write_vault_record


def _transcription_text(response) -> str:
    text = getattr(response, "text", None)
    if text is None and isinstance(response, dict):
        text = response.get("text", "")
    return str(text or "").strip()


class SpoolProcessor:
    def __init__(self, settings_obj: Settings):
        self.settings = settings_obj
        self.settings.spool_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("audio_capturer.processor")
        self._lock = Lock()

    def save_segment(
        self,
        segment: AudioSegment,
    ) -> Path:
        filename = f"{uuid4().hex}.wav"
        path = self.settings.spool_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(segment.sample_rate)
            wav_file.writeframes(segment.pcm_bytes)
        return path

    def flush_pending(self, max_files: int) -> None:
        with self._lock:
            files = sorted(self.settings.spool_dir.glob("*.wav"))[: max(1, max_files)]
            for path in files:
                if not self._process(path):
                    break

    def _process(self, wav_path: Path) -> bool:
        rms = wav_rms(wav_path)
        if rms < self.settings.min_rms:
            self.logger.info(
                "Discarding silent segment before processing | file=%s | min_rms=%d",
                wav_path.name,
                self.settings.min_rms,
            )
            return remove_wav_and_meta(wav_path, self.logger)

        service = self.settings.service
        if service is None:
            self.logger.warning(
                "No [services.audio] configured; dropping segment | file=%s",
                wav_path.name,
            )
            return remove_wav_and_meta(wav_path, self.logger)

        try:
            with wav_path.open("rb") as file_obj:
                kwargs = dict(service.options)
                kwargs["model"] = service.model
                kwargs["file"] = file_obj
                kwargs["timeout"] = service.timeout
                if service.base_url:
                    kwargs["api_base"] = service.base_url
                if service.api_key:
                    kwargs["api_key"] = service.api_key
                if service.headers:
                    kwargs["extra_headers"] = dict(service.headers)
                if service.prompt:
                    kwargs["prompt"] = service.prompt
                text = _transcription_text(transcription(**kwargs))
        except Exception:
            self.logger.exception("Audio processing failed | file=%s", wav_path.name)
            return False

        if not text:
            self.logger.info("Audio produced empty text | file=%s", wav_path.name)
            return remove_wav_and_meta(wav_path, self.logger)

        record_id = new_record_id()
        vault_path = write_vault_record(
            record_id,
            text,
            stream="audio",
            model=service.model,
            metadata={"file": wav_path.name, "rms": rms},
        )

        if not remove_wav_and_meta(wav_path, self.logger):
            return False

        self.logger.info(
            "Audio segment processed | file=%s | id=%s | vault=%s",
            wav_path.name,
            record_id,
            vault_path,
        )
        return True
