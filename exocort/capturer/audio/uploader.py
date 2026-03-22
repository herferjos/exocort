from __future__ import annotations

import json
import logging
import time
import wave
from pathlib import Path
from threading import Lock
from uuid import uuid4

import requests

from .device import remove_wav_and_meta, wav_rms
from .models import AudioSegment, Settings


class SpoolUploader:
    def __init__(self, settings_obj: Settings):
        self.settings = settings_obj
        self.settings.spool_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("audio_capturer.uploader")
        self._lock = Lock()

    def save_segment(
        self,
        segment: AudioSegment,
    ) -> Path:
        seg_id = uuid4().hex
        filename = f"{int(time.time() * 1000)}_{seg_id}.wav"
        path = self.settings.spool_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(segment.sample_rate)
            wav_file.writeframes(segment.pcm_bytes)
        meta_path = path.with_suffix(".wav.meta.json")
        meta_path.write_text(
            json.dumps(
                {
                    "duration_ms": segment.duration_ms,
                    "vad_reason": segment.ended_by,
                    "source": segment.source,
                    "original_sample_rate": segment.original_sample_rate,
                    "original_channels": segment.original_channels,
                }
            ),
            encoding="utf-8",
        )
        return path

    def flush_pending(self, max_files: int) -> None:
        with self._lock:
            files = sorted(self.settings.spool_dir.glob("*.wav"))[: max(1, max_files)]
            for path in files:
                if not self._upload(path):
                    break

    def _upload(self, wav_path: Path) -> bool:
        rms = wav_rms(wav_path)
        if rms < self.settings.min_rms:
            self.logger.info(
                "Discarding silent segment before upload | file=%s | min_rms=%d",
                wav_path.name,
                self.settings.min_rms,
            )
            return remove_wav_and_meta(wav_path, self.logger)

        meta_path = wav_path.with_suffix(".wav.meta.json")
        meta_data = {}
        if meta_path.exists():
            try:
                meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta_data = {}

        segment_id = wav_path.stem
        try:
            with wav_path.open("rb") as f:
                files = {"file": (wav_path.name, f, "audio/wav")}
                data = {
                    "segment_id": segment_id,
                    "sample_rate": str(self.settings.audio.target_sample_rate),
                    "client_source": "audio_capturer",
                    "source": str(meta_data.get("source", "mic")),
                    "duration_ms": str(meta_data.get("duration_ms", "")),
                    "vad_reason": str(meta_data.get("vad_reason", "")),
                    "rms": str(rms),
                }
                response = requests.post(
                    self.settings.api_audio_url,
                    files=files,
                    data=data,
                    timeout=self.settings.request_timeout_s,
                )
        except Exception:
            self.logger.exception("Upload failed | file=%s", wav_path.name)
            return False

        if response.status_code >= 300:
            self.logger.error(
                "Upload rejected | file=%s | status=%d | body=%s",
                wav_path.name,
                response.status_code,
                response.text[:300],
            )
            return False

        if not remove_wav_and_meta(wav_path, self.logger):
            return False

        self.logger.info("Uploaded segment | file=%s", wav_path.name)
        return True
