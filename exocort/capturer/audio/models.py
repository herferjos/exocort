from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from exocort import settings


@dataclass(frozen=True)
class AudioConfig:
    source: str
    capturer_sample_rate: int
    target_sample_rate: int
    channels: int
    frame_ms: int
    vad_mode: int
    start_rms: int
    continue_rms: int
    start_trigger_ms: int
    start_window_ms: int
    end_silence_ms: int
    pre_roll_ms: int
    min_segment_ms: int
    max_segment_ms: int
    input_device: str | None
    latency: str | float | None
    gain_db: float
    low_speech_ratio: float
    low_speech_max_ms: int


@dataclass(frozen=True)
class AudioSegment:
    source: str
    pcm_bytes: bytes
    sample_rate: int
    duration_ms: int
    rms: int
    ended_by: str
    original_sample_rate: int
    original_channels: int


@dataclass(frozen=True)
class Settings:
    enabled: bool
    api_audio_url: str
    spool_dir: Path
    request_timeout_s: float
    max_upload_per_cycle: int
    min_rms: int
    reconnect_delay_s: float
    diagnostic_s: float
    audio: AudioConfig

    @classmethod
    def from_env(cls) -> "Settings":
        capturer_sample_rate = settings.audio_capturer_sample_rate()
        target_sample_rate = settings.audio_capturer_target_sample_rate()
        gain_db = settings.audio_capturer_gain_db()
        frame_ms = settings.audio_capturer_frame_ms()
        return cls(
            enabled=settings.audio_capturer_enabled(),
            api_audio_url=settings.collector_audio_url(),
            spool_dir=settings.audio_capturer_spool_dir(),
            request_timeout_s=settings.audio_capturer_request_timeout_s(),
            max_upload_per_cycle=settings.audio_capturer_max_upload_per_cycle(),
            min_rms=settings.audio_capturer_min_rms(),
            reconnect_delay_s=settings.audio_capturer_reconnect_delay_s(),
            diagnostic_s=settings.audio_capturer_diagnostic_s(),
            audio=AudioConfig(
                source="mic",
                capturer_sample_rate=capturer_sample_rate,
                target_sample_rate=target_sample_rate,
                channels=1,
                frame_ms=frame_ms,
                vad_mode=settings.audio_capturer_vad_mode(),
                start_rms=settings.audio_capturer_start_rms(),
                continue_rms=settings.audio_capturer_continue_rms(),
                start_trigger_ms=settings.audio_capturer_start_trigger_ms(),
                start_window_ms=settings.audio_capturer_start_window_ms(),
                end_silence_ms=settings.audio_capturer_end_silence_ms(),
                pre_roll_ms=settings.audio_capturer_pre_roll_ms(),
                min_segment_ms=settings.audio_capturer_min_segment_ms(),
                max_segment_ms=settings.audio_capturer_max_segment_ms(),
                input_device=settings.audio_capturer_input_device(),
                latency=settings.audio_capturer_latency(),
                gain_db=gain_db,
                low_speech_ratio=settings.audio_capturer_low_speech_ratio(),
                low_speech_max_ms=settings.audio_capturer_low_speech_max_ms(),
            ),
        )
