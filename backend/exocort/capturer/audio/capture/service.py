from __future__ import annotations

from datetime import datetime
import io
import sys
import time
import wave

import numpy as np
import sounddevice as sd

from exocort.config import AudioSettings
from exocort.logs import get_logger

from ..vad import WebRTCVAD
from .models import _SegmentCollector

log = get_logger("audio")


def _audio_access_error(err: Exception) -> RuntimeError:
    detail = str(err).strip()
    if sys.platform == "darwin":
        hint = "Activa el micrófono en Ajustes del sistema > Privacidad y seguridad > Micrófono y vuelve a abrir la app."
    elif sys.platform.startswith("win"):
        hint = (
            "Activa el micrófono en Configuracion > Privacidad y seguridad > Microfono y "
            "habilita 'Permitir que las aplicaciones de escritorio accedan al micrófono'."
        )
    else:
        hint = "Revisa los permisos de entrada de audio del sistema."

    message = f"No se pudo acceder al micrófono. {hint}"
    if detail:
        message = f"{message} Detalle: {detail}"
    return RuntimeError(message)


def _probe_audio_input(config: AudioSettings) -> None:
    frames = max(1, int(config.sample_rate * min(config.chunk_seconds, 0.1)))
    try:
        with sd.InputStream(
            samplerate=config.sample_rate,
            channels=config.channels,
            dtype="int16",
            blocksize=frames,
        ):
            return
    except Exception as err:
        raise _audio_access_error(err) from err


def capture_audio_chunk(config: AudioSettings) -> tuple[np.ndarray, bytes]:
    frames = int(config.chunk_seconds * config.sample_rate)
    try:
        recording = sd.rec(frames, samplerate=config.sample_rate, channels=config.channels, dtype="int16")
        sd.wait()
    except Exception as err:
        raise _audio_access_error(err) from err
    return recording, _encode_wav(config, recording)


def _encode_wav(config: AudioSettings, recording: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(config.channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(config.sample_rate)
        wav_file.writeframes(recording.astype(np.int16, copy=False).tobytes())
    return buffer.getvalue()


def _capture_vad_segment(config: AudioSettings, vad: WebRTCVAD) -> tuple[np.ndarray, float, int]:
    window_frames = max(1, vad.frame_samples)
    max_segment_frames = max(window_frames, int(config.chunk_seconds * config.sample_rate))
    collector = _SegmentCollector(
        max_frames=max_segment_frames,
        pre_roll_chunks=max(0, int(round(config.vad.pre_roll_seconds * config.sample_rate / window_frames))),
        min_speech_chunks=max(1, int(round(config.vad.min_speech_seconds * config.sample_rate / window_frames))),
        min_silence_chunks=max(1, int(round(config.vad.min_silence_seconds * config.sample_rate / window_frames))),
    )
    started_at = time.monotonic()
    next_wait_log_at = started_at + 5.0
    overflows = 0
    log.debug(
        "starting VAD capture window_frames=%s max_segment_frames=%s pre_roll_chunks=%s min_speech_chunks=%s min_silence_chunks=%s",
        window_frames,
        max_segment_frames,
        collector.pre_roll_chunks,
        collector.min_speech_chunks,
        collector.min_silence_chunks,
    )
    try:
        with sd.InputStream(
            samplerate=config.sample_rate,
            channels=config.channels,
            dtype="int16",
            blocksize=window_frames,
        ) as stream:
            while True:
                chunk, overflowed = stream.read(window_frames)
                if overflowed:
                    overflows += 1
                segment = collector.push(chunk, vad.is_speech(chunk))
                if segment is None:
                    if time.monotonic() >= next_wait_log_at:
                        log.debug(
                            "VAD still waiting speech_chunks=%s recording=%s frames=%s",
                            collector.speech_chunks,
                            collector.recording,
                            collector.frames,
                        )
                        next_wait_log_at += 5.0
                    continue
                log.debug(
                    "VAD completed segment frames=%s duration=%.2fs overflows=%s",
                    int(segment.shape[0]),
                    time.monotonic() - started_at,
                    overflows,
                )
                return segment, time.monotonic() - started_at, overflows
    except Exception as err:
        raise _audio_access_error(err) from err


def audio_loop(config: AudioSettings) -> None:
    _probe_audio_input(config)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = config.output_dir
    vad = WebRTCVAD(config.vad, config.sample_rate) if config.vad.enabled else None
    log.info(
        "audio capture loop started chunk_seconds=%ss sample_rate=%s channels=%s output_dir=%s vad_enabled=%s",
        config.chunk_seconds,
        config.sample_rate,
        config.channels,
        output_dir,
        vad is not None,
    )
    while True:
        if vad is None:
            started_at = time.monotonic()
            log.debug("starting fixed-size audio capture for %ss", config.chunk_seconds)
            recording, audio_bytes = capture_audio_chunk(config)
            elapsed = time.monotonic() - started_at
            overflows = 0
        else:
            log.debug("waiting for VAD speech segment")
            recording, elapsed, overflows = _capture_vad_segment(config, vad)
            audio_bytes = _encode_wav(config, recording)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
        file_path = output_dir / f"{timestamp}.wav"
        file_path.write_bytes(audio_bytes)
        vad_suffix = f" (VAD ratio {vad.last_ratio:.2%})" if vad is not None else ""
        if overflows:
            log.warning("audio input overflowed %s time(s) while capturing %s", overflows, file_path)
        log.info(
            "captured %s bytes (%.1fs) -> %s%s",
            len(audio_bytes),
            elapsed,
            file_path,
            vad_suffix,
        )
