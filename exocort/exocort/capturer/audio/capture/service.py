from __future__ import annotations

from datetime import datetime
import io
import time
import wave

import numpy as np
import sounddevice as sd

from exocort.config import AudioSettings
from exocort.logs import get_logger

from ..vad import WebRTCVAD
from .models import _SegmentCollector

log = get_logger("audio")


def capture_audio_chunk(config: AudioSettings) -> tuple[np.ndarray, bytes]:
    frames = int(config.chunk_seconds * config.sample_rate)
    recording = sd.rec(frames, samplerate=config.sample_rate, channels=config.channels, dtype="int16")
    sd.wait()
    return recording, _encode_wav(config, recording)


def _encode_wav(config: AudioSettings, recording: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(config.channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(config.sample_rate)
        wav_file.writeframes(recording.astype(np.int16, copy=False).tobytes())
    return buffer.getvalue()


def _capture_vad_segment(config: AudioSettings, vad: WebRTCVAD) -> tuple[np.ndarray, float]:
    window_frames = max(1, vad.frame_samples)
    max_segment_frames = max(window_frames, int(config.chunk_seconds * config.sample_rate))
    collector = _SegmentCollector(
        max_frames=max_segment_frames,
        pre_roll_chunks=max(0, int(round(config.vad.pre_roll_seconds * config.sample_rate / window_frames))),
        min_speech_chunks=max(1, int(round(config.vad.min_speech_seconds * config.sample_rate / window_frames))),
        min_silence_chunks=max(1, int(round(config.vad.min_silence_seconds * config.sample_rate / window_frames))),
    )
    started_at = time.monotonic()
    with sd.InputStream(samplerate=config.sample_rate, channels=config.channels, dtype="int16") as stream:
        while True:
            chunk, _ = stream.read(window_frames)
            segment = collector.push(chunk, vad.is_speech(chunk))
            if segment is None:
                continue
            return segment, time.monotonic() - started_at


def audio_loop(config: AudioSettings) -> None:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = config.output_dir
    vad = WebRTCVAD(config.vad, config.sample_rate) if config.vad.enabled else None
    while True:
        if vad is None:
            started_at = time.monotonic()
            recording, audio_bytes = capture_audio_chunk(config)
            elapsed = time.monotonic() - started_at
        else:
            recording, elapsed = _capture_vad_segment(config, vad)
            audio_bytes = _encode_wav(config, recording)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
        file_path = output_dir / f"{timestamp}.wav"
        file_path.write_bytes(audio_bytes)
        vad_suffix = f" (VAD ratio {vad.last_ratio:.2%})" if vad is not None else ""
        log.info(
            "captured %s bytes (%.1fs) -> %s%s",
            len(audio_bytes),
            elapsed,
            file_path,
            vad_suffix,
        )
