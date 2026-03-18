"""Unit tests for audio VAD segmenter."""

from __future__ import annotations

import pytest

pytest.importorskip("sounddevice")
from exocort.capture.audio.models import AudioConfig
from exocort.capture.audio.vad import VadSegmenter


pytestmark = [pytest.mark.unit, pytest.mark.stt]


def test_vad_segmenter_rejects_invalid_sample_rate() -> None:
    config = AudioConfig(
        source="mic",
        capture_sample_rate=44100,
        target_sample_rate=44100,
        channels=1,
        frame_ms=20,
        vad_mode=2,
        start_rms=150,
        continue_rms=100,
        start_trigger_ms=120,
        start_window_ms=400,
        end_silence_ms=700,
        pre_roll_ms=300,
        min_segment_ms=500,
        max_segment_ms=30_000,
        input_device=None,
        latency=None,
        gain_db=0.0,
        helper_path=None,
    )
    with pytest.raises(ValueError, match="sample_rate"):
        VadSegmenter(config)


def test_vad_segmenter_rejects_invalid_frame_ms() -> None:
    config = AudioConfig(
        source="mic",
        capture_sample_rate=16000,
        target_sample_rate=16000,
        channels=1,
        frame_ms=15,
        vad_mode=2,
        start_rms=150,
        continue_rms=100,
        start_trigger_ms=120,
        start_window_ms=400,
        end_silence_ms=700,
        pre_roll_ms=300,
        min_segment_ms=500,
        max_segment_ms=30_000,
        input_device=None,
        latency=None,
        gain_db=0.0,
        helper_path=None,
    )
    with pytest.raises(ValueError, match="frame_ms"):
        VadSegmenter(config)


def test_vad_segmenter_feed_empty_returns_empty() -> None:
    config = AudioConfig(
        source="mic",
        capture_sample_rate=16000,
        target_sample_rate=16000,
        channels=1,
        frame_ms=20,
        vad_mode=2,
        start_rms=150,
        continue_rms=100,
        start_trigger_ms=120,
        start_window_ms=400,
        end_silence_ms=700,
        pre_roll_ms=300,
        min_segment_ms=500,
        max_segment_ms=30_000,
        input_device=None,
        latency=None,
        gain_db=0.0,
        helper_path=None,
    )
    seg = VadSegmenter(config)
    out = seg.feed(b"")
    assert out == []


def test_vad_segmenter_flush_when_not_recording_returns_none() -> None:
    config = AudioConfig(
        source="mic",
        capture_sample_rate=16000,
        target_sample_rate=16000,
        channels=1,
        frame_ms=20,
        vad_mode=2,
        start_rms=150,
        continue_rms=100,
        start_trigger_ms=120,
        start_window_ms=400,
        end_silence_ms=700,
        pre_roll_ms=300,
        min_segment_ms=500,
        max_segment_ms=30_000,
        input_device=None,
        latency=None,
        gain_db=0.0,
        helper_path=None,
    )
    seg = VadSegmenter(config)
    assert seg.flush() is None


def test_vad_segmenter_extends_pause_for_short_segments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeVad:
        def __init__(self, mode: int):
            self._frames = [True] * 8 + [False] * 30
            self._idx = 0

        def is_speech(self, frame: bytes, sample_rate: int) -> bool:
            value = self._frames[self._idx] if self._idx < len(self._frames) else False
            self._idx += 1
            return value

    monkeypatch.setattr("exocort.capture.audio.vad.webrtcvad.Vad", FakeVad)

    config = AudioConfig(
        source="mic",
        capture_sample_rate=16000,
        target_sample_rate=16000,
        channels=1,
        frame_ms=20,
        vad_mode=2,
        start_rms=150,
        continue_rms=100,
        start_trigger_ms=40,
        start_window_ms=80,
        end_silence_ms=200,
        pre_roll_ms=20,
        min_segment_ms=100,
        max_segment_ms=30_000,
        input_device=None,
        latency=None,
        gain_db=0.0,
        helper_path=None,
    )
    seg = VadSegmenter(config)
    frame = b"\x00\x20" * int(config.target_sample_rate * config.frame_ms / 1000)

    # Speech frames should not produce a segment yet.
    for _ in range(8):
        assert seg.feed(frame) == []

    # Due to short-segment pause extension, early silence should still keep recording.
    for _ in range(10):
        assert seg.feed(frame) == []
    assert seg.flush() is not None


def test_vad_segmenter_keeps_small_tail_before_finalize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeVad:
        def __init__(self, mode: int):
            self._frames = [True] * 120 + [False] * 100
            self._idx = 0

        def is_speech(self, frame: bytes, sample_rate: int) -> bool:
            value = self._frames[self._idx] if self._idx < len(self._frames) else False
            self._idx += 1
            return value

    monkeypatch.setattr("exocort.capture.audio.vad.webrtcvad.Vad", FakeVad)

    config = AudioConfig(
        source="mic",
        capture_sample_rate=16000,
        target_sample_rate=16000,
        channels=1,
        frame_ms=20,
        vad_mode=2,
        start_rms=150,
        continue_rms=100,
        start_trigger_ms=40,
        start_window_ms=80,
        end_silence_ms=300,
        pre_roll_ms=20,
        min_segment_ms=100,
        max_segment_ms=30_000,
        input_device=None,
        latency=None,
        gain_db=0.0,
        helper_path=None,
    )
    seg = VadSegmenter(config)
    frame = b"\x00\x20" * int(config.target_sample_rate * config.frame_ms / 1000)

    segments = []
    for _ in range(220):
        segments.extend(seg.feed(frame))

    assert len(segments) == 1
    # Segment should be longer than raw speech frames because we keep a small silence tail.
    assert segments[0].duration_ms > (120 * config.frame_ms)
