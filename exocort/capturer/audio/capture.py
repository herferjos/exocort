from __future__ import annotations

import io
import time
import wave
from collections.abc import Callable

import sounddevice as sd

from .config import AudioCaptureConfig


def capture_audio_chunk(config: AudioCaptureConfig) -> bytes:
    frames = int(config.chunk_seconds * config.sample_rate)
    recording = sd.rec(
        frames,
        samplerate=config.sample_rate,
        channels=config.channels,
        dtype="int16",
    )
    sd.wait()

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(config.channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(config.sample_rate)
        wav_file.writeframes(recording.tobytes())

    return buffer.getvalue()


def audio_loop(
    config: AudioCaptureConfig,
    handler: Callable[[bytes], None] | None = None,
) -> None:
    while True:
        started_at = time.monotonic()
        audio_bytes = capture_audio_chunk(config)
        elapsed = time.monotonic() - started_at
        print(f"[audio] captured {len(audio_bytes)} bytes ({elapsed:.1f}s)")
        if handler is not None:
            handler(audio_bytes)
