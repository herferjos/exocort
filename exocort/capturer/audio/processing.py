from __future__ import annotations

import audioop
from array import array


class PcmProcessor:
    def __init__(
        self,
        *,
        target_sample_rate: int,
        frame_ms: int,
        gain_db: float,
        source_channels: int,
        source_sample_rate: int,
    ) -> None:
        self.target_sample_rate = int(target_sample_rate)
        self.frame_ms = int(frame_ms)
        self.gain_db = float(gain_db)
        self.source_channels = int(source_channels)
        self.source_sample_rate = int(source_sample_rate)
        self.frame_bytes = int(self.target_sample_rate * self.frame_ms / 1000) * 2
        self._buffer = b""
        self._resample_state: object | None = None

    def feed(self, chunk: bytes) -> list[bytes]:
        if not chunk:
            return []
        pcm = _downmix_to_mono(chunk, self.source_channels)
        if self.source_sample_rate != self.target_sample_rate:
            pcm = _resample_pcm(
                pcm,
                src_rate=self.source_sample_rate,
                dst_rate=self.target_sample_rate,
                state=self,
            )
        if self.gain_db:
            pcm = _apply_gain_db(pcm, self.gain_db)
        self._buffer += pcm
        frames: list[bytes] = []
        while len(self._buffer) >= self.frame_bytes:
            frames.append(self._buffer[: self.frame_bytes])
            self._buffer = self._buffer[self.frame_bytes :]
        return frames

    def flush(self) -> list[bytes]:
        frames: list[bytes] = []
        if not self._buffer:
            return frames
        remainder = self._buffer
        self._buffer = b""
        while len(remainder) >= self.frame_bytes:
            frames.append(remainder[: self.frame_bytes])
            remainder = remainder[self.frame_bytes :]
        if remainder:
            frames.append(remainder.ljust(self.frame_bytes, b"\x00"))
        return frames


def pcm_rms(pcm_bytes: bytes) -> int:
    if not pcm_bytes:
        return 0
    return int(audioop.rms(pcm_bytes, 2))


def _downmix_to_mono(pcm_bytes: bytes, channels: int) -> bytes:
    if channels <= 1:
        return pcm_bytes
    if channels == 2:
        return audioop.tomono(pcm_bytes, 2, 0.5, 0.5)

    samples = array("h")
    samples.frombytes(pcm_bytes)
    if not samples:
        return b""
    out = array("h")
    step = channels
    for i in range(0, len(samples), step):
        frame = samples[i : i + step]
        if not frame:
            break
        out.append(int(sum(frame) / len(frame)))
    return out.tobytes()


def _apply_gain_db(pcm_bytes: bytes, gain_db: float) -> bytes:
    if not pcm_bytes or gain_db == 0.0:
        return pcm_bytes
    factor = 10 ** (gain_db / 20.0)
    return audioop.mul(pcm_bytes, 2, factor)


def _resample_pcm(
    pcm_bytes: bytes,
    *,
    src_rate: int,
    dst_rate: int,
    state: PcmProcessor | None,
) -> bytes:
    if src_rate == dst_rate:
        return pcm_bytes
    converted, new_state = audioop.ratecv(
        pcm_bytes,
        2,
        1,
        src_rate,
        dst_rate,
        state._resample_state if state else None,
    )
    if state is not None:
        state._resample_state = new_state
    return converted
