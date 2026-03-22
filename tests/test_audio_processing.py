from __future__ import annotations

from array import array

from exocort.capturer.audio.processing import (
    _downmix_to_mono,
    pcm_rms,
    _resample_pcm,
    ResampleState,
)


def _make_interleaved_stereo(samples: list[int]) -> bytes:
    data = array("h")
    for value in samples:
        data.append(value)
        data.append(value)
    return data.tobytes()


def test_downmix_stereo_to_mono_preserves_rms() -> None:
    stereo = _make_interleaved_stereo([1000] * 100)
    mono = _downmix_to_mono(stereo, 2)
    assert pcm_rms(mono) == 1000


def test_resample_length_scales() -> None:
    samples = array("h", [1000] * 1600).tobytes()
    state = ResampleState(16000, 8000)
    out = _resample_pcm(samples, src_rate=16000, dst_rate=8000, state=state)
    assert len(out) in (1600, 1598, 1602)
