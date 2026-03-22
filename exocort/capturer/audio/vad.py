from __future__ import annotations

import audioop
from collections import deque
import logging

import webrtcvad

from .models import AudioConfig, AudioSegment

log = logging.getLogger("audio_capturer.vad")


class VadSegmenter:
    def __init__(self, config: AudioConfig) -> None:
        if config.target_sample_rate not in {8000, 16000, 32000, 48000}:
            raise ValueError("sample_rate must be 8000, 16000, 32000 or 48000")
        if config.frame_ms not in {10, 20, 30}:
            raise ValueError("frame_ms must be 10, 20 or 30")

        self.config = config
        self.frame_bytes = int(config.target_sample_rate * config.frame_ms / 1000) * 2
        self.start_trigger_frames = max(
            1, int(config.start_trigger_ms / config.frame_ms)
        )
        self.start_window_frames = max(1, int(config.start_window_ms / config.frame_ms))
        self.end_silence_frames = max(1, int(config.end_silence_ms / config.frame_ms))
        self.pre_roll_frames = max(1, int(config.pre_roll_ms / config.frame_ms))
        self.min_segment_frames = max(1, int(config.min_segment_ms / config.frame_ms))
        self.max_segment_frames = max(1, int(config.max_segment_ms / config.frame_ms))
        self.long_phrase_frames = max(1, int(1800 / config.frame_ms))
        self.very_long_phrase_frames = max(1, int(5000 / config.frame_ms))
        self.short_pause_extension_frames = max(1, int(400 / config.frame_ms))
        self.long_pause_extension_frames = max(1, int(800 / config.frame_ms))
        self.short_segment_frames = max(1, int(1600 / config.frame_ms))
        self.short_segment_extra_pause_frames = max(1, int(350 / config.frame_ms))
        self.max_end_silence_frames = max(
            self.end_silence_frames, int(2500 / config.frame_ms)
        )
        self.tail_keep_silence_frames = max(1, int(180 / config.frame_ms))

        self._vad = webrtcvad.Vad(max(0, min(3, config.vad_mode)))
        self._buffer = b""
        self._pre_roll: deque[bytes] = deque(maxlen=self.pre_roll_frames)
        self._recent_flags: deque[bool] = deque(maxlen=self.start_window_frames)
        self._frames: list[bytes] = []
        self._silence_frames = 0
        self._speech_frames = 0
        self._recording = False

    def feed(self, chunk: bytes) -> list[AudioSegment]:
        segments: list[AudioSegment] = []
        if not chunk:
            return segments

        self._buffer += chunk
        while len(self._buffer) >= self.frame_bytes:
            frame = self._buffer[: self.frame_bytes]
            self._buffer = self._buffer[self.frame_bytes :]
            segment = self._feed_frame(frame)
            if segment is not None:
                segments.append(segment)
        return segments

    def flush(self) -> AudioSegment | None:
        if not self._recording:
            return None
        return self._finalize(self._frames, "stop")

    def _feed_frame(self, frame: bytes) -> AudioSegment | None:
        rms = int(audioop.rms(frame, 2)) if frame else 0
        is_speech = self._vad.is_speech(frame, self.config.target_sample_rate)
        start_active = is_speech and rms >= self.config.start_rms
        continue_active = is_speech and rms >= self.config.continue_rms
        self._pre_roll.append(frame)

        if not self._recording:
            self._recent_flags.append(start_active)
            if (
                sum(1 for flag in self._recent_flags if flag)
                >= self.start_trigger_frames
            ):
                self._recording = True
                self._silence_frames = 0
                self._speech_frames = 0
                self._frames = list(self._pre_roll)
                self._recent_flags.clear()
            return None

        self._frames.append(frame)
        if continue_active:
            self._silence_frames = 0
            self._speech_frames += 1
        else:
            self._silence_frames += 1

        if len(self._frames) >= self.max_segment_frames:
            return self._finalize(self._frames, "max_segment")

        allowed_silence_frames = self._allowed_silence_frames(len(self._frames))
        if self._silence_frames >= allowed_silence_frames:
            if len(
                self._frames
            ) < self.short_segment_frames and self._silence_frames < (
                allowed_silence_frames + self.short_segment_extra_pause_frames
            ):
                return None
            trim_frames = max(0, self._silence_frames - self.tail_keep_silence_frames)
            frames = (
                self._frames[:-trim_frames] if trim_frames > 0 else list(self._frames)
            )
            return self._finalize(frames, "silence")
        return None

    def _allowed_silence_frames(self, frame_count: int) -> int:
        allowed = self.end_silence_frames
        if frame_count >= self.long_phrase_frames:
            allowed += self.short_pause_extension_frames
        if frame_count >= self.very_long_phrase_frames:
            allowed += self.long_pause_extension_frames
        return min(self.max_end_silence_frames, allowed)

    def _finalize(self, frames: list[bytes], ended_by: str) -> AudioSegment | None:
        frame_count = len(frames)
        segment = None
        if frame_count >= self.min_segment_frames:
            pcm_bytes = b"".join(frames)
            rms = int(audioop.rms(pcm_bytes, 2)) if pcm_bytes else 0
            if rms > 0:
                if (
                    self.config.low_speech_max_ms > 0
                    and self.config.low_speech_ratio > 0.0
                ):
                    max_frames = max(
                        1, int(self.config.low_speech_max_ms / self.config.frame_ms)
                    )
                else:
                    max_frames = 0
                if (
                    max_frames > 0
                    and frame_count <= max_frames
                    and (self._speech_frames / max(1, frame_count))
                    < self.config.low_speech_ratio
                ):
                    log.info(
                        "Dropping low-speech segment | source=%s | frames=%d | speech_frames=%d | rms=%d",
                        self.config.source,
                        frame_count,
                        self._speech_frames,
                        rms,
                    )
                    rms = 0
                if ended_by == "max_segment" and rms < self.config.start_rms:
                    log.info(
                        "Dropping low-RMS max segment | source=%s | rms=%d | start_rms=%d",
                        self.config.source,
                        rms,
                        self.config.start_rms,
                    )
                    rms = 0
                if rms > 0:
                    segment = AudioSegment(
                        source=self.config.source,
                        pcm_bytes=pcm_bytes,
                        sample_rate=self.config.target_sample_rate,
                        duration_ms=frame_count * self.config.frame_ms,
                        rms=rms,
                        ended_by=ended_by,
                        original_sample_rate=self.config.capturer_sample_rate,
                        original_channels=self.config.channels,
                    )

        self._frames = []
        self._silence_frames = 0
        self._speech_frames = 0
        self._recording = False
        self._recent_flags.clear()
        return segment
