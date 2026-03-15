from __future__ import annotations

import json
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .audio import AudioSegment
from .asr import Transcription


@dataclass(frozen=True)
class StoredTranscription:
    json_path: Path
    wav_path: Path
    captured_at: str


class TranscriptStore:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir

    def write(
        self,
        segment: AudioSegment,
        transcription: Transcription,
        captured_at: datetime,
    ) -> StoredTranscription:
        day_dir = self.root_dir / captured_at.strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)

        stem = f"{segment.source}-{captured_at.strftime('%H-%M-%S-%f')}"
        wav_path = day_dir / f"{stem}.wav"
        json_path = day_dir / f"{stem}.json"
        captured_at_iso = captured_at.isoformat()

        self._write_wav(wav_path, segment.pcm_bytes, segment.sample_rate)
        payload = {
            "captured_at": captured_at_iso,
            "source": segment.source,
            "text": transcription.text,
            "locale": transcription.locale,
            "is_final": transcription.is_final,
            "duration_ms": segment.duration_ms,
            "rms": segment.rms,
            "ended_by": segment.ended_by,
            "audio_path": str(wav_path),
        }
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return StoredTranscription(
            json_path=json_path,
            wav_path=wav_path,
            captured_at=captured_at_iso,
        )

    def _write_wav(self, path: Path, pcm_bytes: bytes, sample_rate: int) -> None:
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)
