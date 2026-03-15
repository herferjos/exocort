from __future__ import annotations

import audioop
import json
import logging
import time
import wave
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Lock, Thread
from uuid import uuid4

import requests
import sounddevice as sd
import webrtcvad

import settings

log = logging.getLogger("audio_capture")
LOOPBACK_KEYWORDS = (
    "loopback",
    "vb-cable",
    "stereo mix",
    "what u hear",
)


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


@dataclass(frozen=True)
class Settings:
    enabled: bool
    api_audio_url: str
    spool_dir: Path
    request_timeout_s: float
    max_upload_per_cycle: int
    min_rms: int
    reconnect_delay_s: float
    audio: AudioConfig
    system_audio: AudioConfig | None

    @classmethod
    def from_env(cls) -> "Settings":
        system_device = settings.audio_capture_system_input_device()
        if system_device is None and settings.audio_capture_system_enabled():
            system_device = detect_loopback_input_device_name()

        sample_rate = settings.audio_capture_sample_rate()
        frame_ms = settings.audio_capture_frame_ms()
        return cls(
            enabled=settings.audio_capture_enabled(),
            api_audio_url=settings.audio_capture_api_audio_url(),
            spool_dir=settings.audio_capture_spool_dir(),
            request_timeout_s=settings.audio_capture_request_timeout_s(),
            max_upload_per_cycle=settings.audio_capture_max_upload_per_cycle(),
            min_rms=settings.audio_capture_min_rms(),
            reconnect_delay_s=settings.audio_capture_reconnect_delay_s(),
            audio=AudioConfig(
                source="mic",
                sample_rate=sample_rate,
                frame_ms=frame_ms,
                vad_mode=settings.audio_capture_vad_mode(),
                start_rms=settings.audio_capture_start_rms(),
                continue_rms=settings.audio_capture_continue_rms(),
                start_trigger_ms=settings.audio_capture_start_trigger_ms(),
                start_window_ms=settings.audio_capture_start_window_ms(),
                end_silence_ms=settings.audio_capture_end_silence_ms(),
                pre_roll_ms=settings.audio_capture_pre_roll_ms(),
                min_segment_ms=settings.audio_capture_min_segment_ms(),
                max_segment_ms=settings.audio_capture_max_segment_ms(),
                input_device=settings.audio_capture_input_device(),
            ),
            system_audio=(
                AudioConfig(
                    source="system",
                    sample_rate=sample_rate,
                    frame_ms=frame_ms,
                    vad_mode=settings.audio_capture_system_vad_mode(),
                    start_rms=settings.audio_capture_system_start_rms(),
                    continue_rms=settings.audio_capture_system_continue_rms(),
                    start_trigger_ms=settings.audio_capture_system_start_trigger_ms(),
                    start_window_ms=settings.audio_capture_system_start_window_ms(),
                    end_silence_ms=settings.audio_capture_system_end_silence_ms(),
                    pre_roll_ms=settings.audio_capture_system_pre_roll_ms(),
                    min_segment_ms=settings.audio_capture_system_min_segment_ms(),
                    max_segment_ms=settings.audio_capture_system_max_segment_ms(),
                    input_device=system_device,
                )
                if system_device is not None
                else None
            ),
        )


class VadSegmenter:
    def __init__(self, config: AudioConfig) -> None:
        if config.sample_rate not in {8000, 16000, 32000, 48000}:
            raise ValueError("sample_rate must be 8000, 16000, 32000 or 48000")
        if config.frame_ms not in {10, 20, 30}:
            raise ValueError("frame_ms must be 10, 20 or 30")

        self.config = config
        self.frame_bytes = int(config.sample_rate * config.frame_ms / 1000) * 2
        self.start_trigger_frames = max(
            1, int(config.start_trigger_ms / config.frame_ms)
        )
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
            if (
                sum(1 for flag in self._recent_flags if flag)
                >= self.start_trigger_frames
            ):
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
            frames = self._frames[: -self._silence_frames] or self._frames
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


class SpoolUploader:
    def __init__(self, settings_obj: Settings):
        self.settings = settings_obj
        self.settings.spool_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("audio_capture.uploader")
        self._lock = Lock()

    def save_segment(
        self,
        segment: AudioSegment,
    ) -> Path:
        seg_id = uuid4().hex
        filename = f"{int(time.time() * 1000)}_{seg_id}.wav"
        path = self.settings.spool_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(segment.sample_rate)
            wav_file.writeframes(segment.pcm_bytes)
        meta_path = path.with_suffix(".wav.meta.json")
        meta_path.write_text(
            json.dumps(
                {
                    "duration_ms": segment.duration_ms,
                    "vad_reason": segment.ended_by,
                    "source": segment.source,
                }
            ),
            encoding="utf-8",
        )
        return path

    def flush_pending(self, max_files: int) -> None:
        with self._lock:
            files = sorted(self.settings.spool_dir.glob("*.wav"))[: max(1, max_files)]
            for path in files:
                if not self._upload(path):
                    break

    def _upload(self, wav_path: Path) -> bool:
        rms = _wav_rms(wav_path)
        if rms < self.settings.min_rms:
            self.logger.info(
                "Discarding silent segment before upload | file=%s | min_rms=%d",
                wav_path.name,
                self.settings.min_rms,
            )
            return _remove_wav_and_meta(wav_path, self.logger)

        meta_path = wav_path.with_suffix(".wav.meta.json")
        meta_data = {}
        if meta_path.exists():
            try:
                meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta_data = {}

        segment_id = wav_path.stem
        try:
            with wav_path.open("rb") as f:
                files = {"file": (wav_path.name, f, "audio/wav")}
                data = {
                    "segment_id": segment_id,
                    "sample_rate": str(self.settings.audio.sample_rate),
                    "client_source": "audio_capture",
                    "source": str(meta_data.get("source", "mic")),
                    "duration_ms": str(meta_data.get("duration_ms", "")),
                    "vad_reason": str(meta_data.get("vad_reason", "")),
                    "rms": str(rms),
                }
                response = requests.post(
                    self.settings.api_audio_url,
                    files=files,
                    data=data,
                    timeout=self.settings.request_timeout_s,
                )
        except Exception:
            self.logger.exception("Upload failed | file=%s", wav_path.name)
            return False

        if response.status_code >= 300:
            self.logger.error(
                "Upload rejected | file=%s | status=%d | body=%s",
                wav_path.name,
                response.status_code,
                response.text[:300],
            )
            return False

        if not _remove_wav_and_meta(wav_path, self.logger):
            return False

        self.logger.info("Uploaded segment | file=%s", wav_path.name)
        return True


class AudioCaptureAgent:
    def __init__(self, settings_obj: Settings):
        self.settings = settings_obj
        self.uploader = SpoolUploader(settings_obj)
        self.stop_event = Event()

    def run(self) -> None:
        if not self.settings.enabled:
            log.info("Audio capture disabled (set AUDIO_CAPTURE_ENABLED=1 to enable).")
            return

        sources = [self.settings.audio]
        if self.settings.system_audio is not None:
            sources.append(self.settings.system_audio)

        self.uploader.flush_pending(max_files=10_000)
        threads = [
            Thread(
                target=self._run_source,
                args=(source,),
                name=f"audio-capture-{source.source}",
                daemon=True,
            )
            for source in sources
        ]

        log.info(
            "Starting audio capture | api_audio_url=%s | sources=%s",
            self.settings.api_audio_url,
            [source.source for source in sources],
        )

        for thread in threads:
            thread.start()

        try:
            while any(thread.is_alive() for thread in threads):
                time.sleep(0.5)
        except KeyboardInterrupt:
            log.info("Stopping audio capture by user request")
        finally:
            self.stop_event.set()
            for thread in threads:
                thread.join(timeout=5.0)
            self.uploader.flush_pending(max_files=10_000)
            log.info("Audio capture stopped")

    def _run_source(self, config: AudioConfig) -> None:
        while not self.stop_event.is_set():
            try:
                listen_microphone(
                    config,
                    self._handle_segment,
                    stop_event=self.stop_event,
                )
            except Exception:
                log.exception("Audio source failed | source=%s", config.source)
                self.stop_event.wait(self.settings.reconnect_delay_s)

    def _handle_segment(self, segment: AudioSegment) -> bool:
        if segment.rms < self.settings.min_rms:
            log.info(
                "Segment dropped (silent) | source=%s | duration_ms=%d | ended_by=%s | min_rms=%d",
                segment.source,
                segment.duration_ms,
                segment.ended_by,
                self.settings.min_rms,
            )
            return not self.stop_event.is_set()

        saved = self.uploader.save_segment(segment)
        log.info(
            "Segment queued | source=%s | file=%s | duration_ms=%d | ended_by=%s",
            segment.source,
            saved.name,
            segment.duration_ms,
            segment.ended_by,
        )
        self.uploader.flush_pending(max_files=self.settings.max_upload_per_cycle)
        return not self.stop_event.is_set()


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
            if (
                idle_timeout_s is not None
                and (time.monotonic() - started_at) >= idle_timeout_s
            ):
                break

            data, overflowed = stream.read(frame_samples)
            if overflowed:
                log.warning("Audio input overflow detected | source=%s", config.source)

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


def _pcm_rms(pcm_bytes: bytes) -> int:
    if not pcm_bytes:
        return 0
    return int(audioop.rms(pcm_bytes, 2))


def _wav_rms(path: Path) -> int:
    try:
        with wave.open(str(path), "rb") as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
        return _pcm_rms(frames)
    except Exception:
        return 0


def _remove_wav_and_meta(path: Path, logger: logging.Logger) -> bool:
    meta = path.with_suffix(".wav.meta.json")
    try:
        path.unlink(missing_ok=True)
        meta.unlink(missing_ok=True)
        return True
    except OSError:
        logger.exception("Failed to remove file | file=%s", path.name)
        return False


def main() -> None:
    logging.basicConfig(
        level=settings.audio_capture_log_level(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    AudioCaptureAgent(Settings.from_env()).run()


if __name__ == "__main__":
    main()
