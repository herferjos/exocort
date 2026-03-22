"""Unit tests for audio device helpers (wav_rms, remove_wav_and_meta)."""

from __future__ import annotations

import logging
import wave
from pathlib import Path

import pytest

pytest.importorskip("sounddevice")
from exocort.capturer.audio.device import remove_wav_and_meta, wav_rms


pytestmark = [pytest.mark.unit, pytest.mark.stt]


def _make_wav(path: Path, pcm_bytes: bytes, sample_rate: int = 16000) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_bytes)


def test_wav_rms_empty_file(tmp_path: Path) -> None:
    wav_path = tmp_path / "empty.wav"
    _make_wav(wav_path, b"")
    assert wav_rms(wav_path) == 0


def test_wav_rms_missing_file_returns_zero(tmp_path: Path) -> None:
    assert wav_rms(tmp_path / "missing.wav") == 0


def test_wav_rms_silent_frames(tmp_path: Path) -> None:
    wav_path = tmp_path / "silent.wav"
    _make_wav(wav_path, b"\x00\x00\x00\x00\x00\x00\x00\x00")
    assert wav_rms(wav_path) == 0


def test_remove_wav_and_meta_removes_both(tmp_path: Path) -> None:
    wav_path = tmp_path / "x.wav"
    meta_path = tmp_path / "x.wav.meta.json"
    wav_path.write_bytes(b"wav")
    meta_path.write_text("{}")
    logger = logging.getLogger("test")
    assert remove_wav_and_meta(wav_path, logger) is True
    assert not wav_path.exists()
    assert not meta_path.exists()


def test_remove_wav_and_meta_missing_ok(tmp_path: Path) -> None:
    wav_path = tmp_path / "missing.wav"
    logger = logging.getLogger("test")
    assert remove_wav_and_meta(wav_path, logger) is True
