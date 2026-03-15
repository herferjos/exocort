from __future__ import annotations

import audioop
import logging
import time
from collections import deque
from dataclasses import dataclass
from threading import Event

import sounddevice as sd
import webrtcvad

log = logging.getLogger("mac_asr.audio")
LOOPBACK_KEYWORDS = ("blackhole", "loopback", "soundflower", "vb-cable", "background music")


@dataclass(frozen=True)
class AudioConfig:
    source: str
    sample_rate: int
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


@dataclass(frozen=True)
class AudioSegment:
    source: str
    pcm_bytes: bytes
    sample_rate: int
    duration_ms: int
    rms: int
    ended_by: str


class VadSegmenter:
    def __init__(self, config: AudioConfig) -> None:
        if config.sample_rate not in {8000, 16000, 32000, 48000}:
            raise ValueError("sample_rate must be 8000, 16000, 32000 or 48000")
        if config.frame_ms not in {10, 20, 30}:
            raise ValueError("frame_ms must be 10, 20 or 30")

        self.config = config
        self.frame_bytes = int(config.sample_rate * config.frame_ms / 1000) * 2
        self.start_trigger_frames = max(1, int(config.start_trigger_ms / config.frame_ms))
        self.start_window_frames = max(1, int(config.start_window_ms / config.frame_ms))
        self.end_silence_frames = max(1, int(config.end_silence_ms / config.frame_ms))
        self.pre_roll_frames = max(1, int(config.pre_roll_ms / config.frame_ms))
        self.min_segment_frames = max(1, int(config.min_segment_ms / config.frame_ms))
        self.max_segment_frames = max(1, int(config.max_segment_ms / config.frame_ms))

        self._vad = webrtcvad.Vad(max(0, min(3, config.vad_mode)))
        self._buffer = b""
        self._pre_roll: deque[bytes] = deque(maxlen=self.pre_roll_frames)
        self._recent_flags: deque[bool] = deque(maxlen=self.start_window_frames)
        self._frames: list[bytes] = []
        self._silence_frames = 0
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
        is_speech = self._vad.is_speech(frame, self.config.sample_rate)
        start_active = is_speech and rms >= self.config.start_rms
        continue_active = is_speech and rms >= self.config.continue_rms
        self._pre_roll.append(frame)

        if not self._recording:
            self._recent_flags.append(start_active)
            if sum(1 for flag in self._recent_flags if flag) >= self.start_trigger_frames:
                self._recording = True
                self._silence_frames = 0
                self._frames = list(self._pre_roll)
                self._recent_flags.clear()
            return None

        self._frames.append(frame)
        if continue_active:
            self._silence_frames = 0
        else:
            self._silence_frames += 1

        if len(self._frames) >= self.max_segment_frames:
            return self._finalize(self._frames, "max_segment")

        if self._silence_frames >= self.end_silence_frames:
            frames = self._frames[:-self._silence_frames] or self._frames
            return self._finalize(frames, "silence")
        return None

    def _finalize(self, frames: list[bytes], ended_by: str) -> AudioSegment | None:
        frame_count = len(frames)
        segment = None
        if frame_count >= self.min_segment_frames:
            pcm_bytes = b"".join(frames)
            rms = int(audioop.rms(pcm_bytes, 2)) if pcm_bytes else 0
            if rms > 0:
                segment = AudioSegment(
                    source=self.config.source,
                    pcm_bytes=pcm_bytes,
                    sample_rate=self.config.sample_rate,
                    duration_ms=frame_count * self.config.frame_ms,
                    rms=rms,
                    ended_by=ended_by,
                )

        self._frames = []
        self._silence_frames = 0
        self._recording = False
        self._recent_flags.clear()
        return segment


def listen_microphone(
    config: AudioConfig,
    on_segment,
    *,
    stop_event: Event | None = None,
    idle_timeout_s: float | None = None,
) -> None:
    frame_samples = int(config.sample_rate * config.frame_ms / 1000)
    resolved_device, resolved_label = _resolve_input_device(
        requested_device=config.input_device,
        source=config.source,
    )
    stream_kwargs: dict[str, object] = {
        "samplerate": config.sample_rate,
        "channels": 1,
        "dtype": "int16",
        "blocksize": frame_samples,
    }
    if resolved_device is not None:
        stream_kwargs["device"] = resolved_device

    segmenter = VadSegmenter(config)
    started_at = time.monotonic()

    log.info(
        "Opening %s audio | sample_rate=%d | frame_ms=%d | vad_mode=%d | device=%s",
        config.source,
        config.sample_rate,
        config.frame_ms,
        config.vad_mode,
        resolved_label,
    )

    with sd.RawInputStream(**stream_kwargs) as stream:
        while True:
            if stop_event is not None and stop_event.is_set():
                break
            if idle_timeout_s is not None and (time.monotonic() - started_at) >= idle_timeout_s:
                break

            data, overflowed = stream.read(frame_samples)
            if overflowed:
                log.warning("Microphone input overflow detected")

            for segment in segmenter.feed(bytes(data)):
                if on_segment(segment) is False:
                    return

        tail = segmenter.flush()
        if tail is not None:
            on_segment(tail)


def capture_once(config: AudioConfig, timeout_s: float) -> AudioSegment | None:
    captured: list[AudioSegment] = []

    def on_segment(segment: AudioSegment) -> bool:
        captured.append(segment)
        return False

    listen_microphone(config, on_segment, idle_timeout_s=timeout_s)
    return captured[0] if captured else None


def detect_loopback_input_device_name() -> str | None:
    detected = _detect_loopback_input_device(_list_input_devices())
    if detected is None:
        return None
    return detected[1]


def _resolve_input_device(
    *,
    requested_device: str | None,
    source: str,
) -> tuple[int | None, str]:
    devices = _list_input_devices()

    if requested_device:
        exact = _match_input_device(devices, requested_device, exact=True)
        if exact is not None:
            return exact

        partial = _match_input_device(devices, requested_device, exact=False)
        if partial is not None:
            log.warning(
                "Input device %r was not an exact match; using %s",
                requested_device,
                partial[1],
            )
            return partial

        log.warning(
            "Input device %r was not found for %s source; falling back to auto/default input",
            requested_device,
            source,
        )

    if source == "system":
        detected = _detect_loopback_input_device(devices)
        if detected is not None:
            return detected

    return None, "default"


def _list_input_devices() -> list[tuple[int, str]]:
    devices: list[tuple[int, str]] = []
    for index, device in enumerate(sd.query_devices()):
        if int(device.get("max_input_channels", 0) or 0) <= 0:
            continue
        devices.append((index, str(device.get("name", f"device-{index}"))))
    return devices


def _match_input_device(
    devices: list[tuple[int, str]],
    requested_device: str,
    *,
    exact: bool,
) -> tuple[int, str] | None:
    requested = requested_device.strip().lower()
    if not requested:
        return None

    if requested.isdigit():
        requested_index = int(requested)
        for index, name in devices:
            if index == requested_index:
                return index, name
        return None

    for index, name in devices:
        candidate = name.lower()
        if exact and candidate == requested:
            return index, name
        if not exact and requested in candidate:
            return index, name
    return None


def _detect_loopback_input_device(
    devices: list[tuple[int, str]],
) -> tuple[int, str] | None:
    for index, name in devices:
        candidate = name.lower()
        if any(keyword in candidate for keyword in LOOPBACK_KEYWORDS):
            log.info("Detected loopback input device automatically: %s", name)
            return index, name
    return None
