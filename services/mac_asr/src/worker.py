from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .asr import ensure_permissions, transcribe_pcm_bytes
from .audio import AudioConfig, AudioSegment, listen_microphone
from .storage import TranscriptStore

log = logging.getLogger("mac_asr")


@dataclass(frozen=True)
class WorkerConfig:
    reconnect_delay_s: float
    capture_once_timeout_s: float
    transcription_timeout_s: float
    output_dir: Path
    prompt_permission: bool
    locale: str
    audio: AudioConfig
    system_audio: AudioConfig | None


class MacAsrWorker:
    def __init__(self, config: WorkerConfig) -> None:
        self.config = config
        self.store = TranscriptStore(config.output_dir)
        self._stop_event = threading.Event()
        self._segment_queue: queue.Queue[AudioSegment] = queue.Queue(maxsize=32)
        self._audio_threads: list[threading.Thread] = []
        self._transcribe_thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._captures = 0
        self._errors = 0
        self._last_error = ""
        self._last_capture_at = ""
        self._latest: dict[str, object] | None = None

    def start(self) -> None:
        if any(thread.is_alive() for thread in self._audio_threads):
            return
        self._stop_event.clear()
        self._audio_threads = [
            threading.Thread(
                target=self._audio_loop,
                args=(self.config.audio,),
                name=f"mac-asr-{self.config.audio.source}",
                daemon=True,
            )
        ]
        if self.config.system_audio is not None:
            self._audio_threads.append(
                threading.Thread(
                    target=self._audio_loop,
                    args=(self.config.system_audio,),
                    name=f"mac-asr-{self.config.system_audio.source}",
                    daemon=True,
                )
            )
        self._transcribe_thread = threading.Thread(
            target=self._transcription_loop, name="mac-asr-transcribe", daemon=True
        )
        for thread in self._audio_threads:
            thread.start()
        self._transcribe_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        for t in [*self._audio_threads, self._transcribe_thread]:
            if t:
                t.join(timeout=5.0)

    def capture_once(self) -> dict[str, object]:
        self._require_permissions()
        from .audio import capture_once as _capture_once
        segment = _capture_once(self.config.audio, timeout_s=self.config.capture_once_timeout_s)
        if segment is None:
            return {"skipped": True, "reason": "timeout_waiting_for_speech"}
        return self._transcribe_and_store(segment)

    def status(self) -> dict[str, object]:
        with self._lock:
            return {
                "running": any(thread.is_alive() for thread in self._audio_threads),
                "output_dir": str(self.config.output_dir),
                "locale": self.config.locale,
                "sources": [
                    self.config.audio.source,
                    *(
                        [self.config.system_audio.source]
                        if self.config.system_audio is not None
                        else []
                    ),
                ],
                "captures": self._captures,
                "errors": self._errors,
                "last_error": self._last_error,
                "last_capture_at": self._last_capture_at,
                "latest": self._latest,
            }

    # --- audio thread: mic → VAD → queue (never blocks on transcription) ---

    def _audio_loop(self, audio_config: AudioConfig) -> None:
        while not self._stop_event.is_set():
            try:
                self._require_permissions()
                listen_microphone(
                    audio_config,
                    self._enqueue_segment,
                    stop_event=self._stop_event,
                )
            except Exception as exc:
                with self._lock:
                    self._errors += 1
                    self._last_error = str(exc)
                log.exception("Audio loop failed: %s", exc)
                self._stop_event.wait(self.config.reconnect_delay_s)

    def _enqueue_segment(self, segment: AudioSegment) -> bool:
        try:
            self._segment_queue.put_nowait(segment)
            log.debug(
                    "Queued segment | source=%s | duration_ms=%d | rms=%d | ended_by=%s",
                    segment.source,
                segment.duration_ms,
                segment.rms,
                segment.ended_by,
            )
        except queue.Full:
            log.warning("Segment queue full, dropping segment (transcription is too slow)")
        return not self._stop_event.is_set()

    # --- transcription thread: dequeue → transcribe → store ---

    def _transcription_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                segment = self._segment_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                result = self._transcribe_and_store(segment)
                if result.get("skipped"):
                    log.info(
                        "Skipped segment | source=%s | reason=%s | duration_ms=%d",
                        result.get("source", ""),
                        result.get("reason", ""),
                        result.get("duration_ms", 0),
                    )
                else:
                    log.info(
                        "Transcription stored | source=%s | text=%r | duration_ms=%d | path=%s",
                        result.get("source", ""),
                        str(result.get("text", ""))[:80],
                        result.get("duration_ms", 0),
                        result.get("path", ""),
                    )
            except Exception as exc:
                with self._lock:
                    self._errors += 1
                    self._last_error = str(exc)
                log.exception("Transcription failed: %s", exc)

    def _transcribe_and_store(self, segment: AudioSegment) -> dict[str, object]:
        if segment.rms < 300:
            return {
                "skipped": True,
                "reason": "low_rms",
                "captured_at": datetime.now().astimezone().isoformat(),
                "source": segment.source,
                "duration_ms": segment.duration_ms,
                "rms": segment.rms,
                "ended_by": segment.ended_by,
            }

        transcription = transcribe_pcm_bytes(
            segment.pcm_bytes,
            sample_rate=segment.sample_rate,
            locale=self.config.locale,
            timeout_s=self.config.transcription_timeout_s,
        )
        captured_at = datetime.now().astimezone()

        if not transcription.text:
            return {
                "skipped": True,
                "reason": "empty_transcription",
                "captured_at": captured_at.isoformat(),
                "source": segment.source,
                "duration_ms": segment.duration_ms,
                "rms": segment.rms,
                "ended_by": segment.ended_by,
            }

        stored = self.store.write(segment, transcription, captured_at)
        result = {
            "captured_at": stored.captured_at,
            "source": segment.source,
            "text": transcription.text,
            "locale": transcription.locale,
            "is_final": transcription.is_final,
            "duration_ms": segment.duration_ms,
            "rms": segment.rms,
            "ended_by": segment.ended_by,
            "path": str(stored.json_path),
            "audio_path": str(stored.wav_path),
        }
        with self._lock:
            self._captures += 1
            self._last_capture_at = result["captured_at"]
            self._last_error = ""
            self._latest = result
        return result

    def _require_permissions(self) -> None:
        permissions = ensure_permissions(prompt=self.config.prompt_permission)
        if not permissions["microphone"]:
            raise PermissionError("Microphone permission is required for mac_asr.")
        if not permissions["speech"]:
            raise PermissionError("Speech recognition permission is required for mac_asr.")
