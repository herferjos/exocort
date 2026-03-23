from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from threading import Event, Thread

import sounddevice as sd

from .device import ResolvedDevice, resolve_input_device
from .models import AudioConfig, AudioSegment, Settings
from .processing import PcmProcessor, pcm_rms
from .uploader import SpoolProcessor
from .vad import VadSegmenter

log = logging.getLogger("audio_capturer")


class AudiocapturerAgent:
    def __init__(self, settings_obj: Settings):
        self.settings = settings_obj
        self.processor = SpoolProcessor(settings_obj)
        self.stop_event = Event()

    def run(self) -> None:
        if not self.settings.enabled:
            log.info(
                "Audio capturer disabled (set [runtime].enable_audio_capturer = true to enable)."
            )
            return

        sources = [self.settings.audio]

        self.processor.flush_pending(max_files=10_000)
        threads = [
            Thread(
                target=self._run_source,
                args=(source,),
                name=f"audio-capturer-{source.source}",
                daemon=True,
            )
            for source in sources
        ]

        log.info(
            "Starting audio capturer | model=%s | sources=%s",
            self.settings.service.model if self.settings.service else "disabled",
            [source.source for source in sources],
        )

        for thread in threads:
            thread.start()

        try:
            while any(thread.is_alive() for thread in threads):
                time.sleep(0.5)
        except KeyboardInterrupt:
            log.info("Stopping audio capturer by user request")
        finally:
            self.stop_event.set()
            for thread in threads:
                thread.join(timeout=5.0)
            self.processor.flush_pending(max_files=10_000)
            log.info("Audio capturer stopped")

    def _run_source(self, config: AudioConfig) -> None:
        if self.settings.diagnostic_s > 0:
            try:
                diagnose_source(
                    config,
                    diagnostic_s=self.settings.diagnostic_s,
                    stop_event=self.stop_event,
                )
            except Exception:
                log.exception("Audio diagnostics failed | source=%s", config.source)

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
        min_rms = max(self.settings.min_rms, self.settings.audio.start_rms)
        if segment.rms < min_rms:
            log.info(
                "Segment dropped (silent) | source=%s | duration_ms=%d | ended_by=%s | min_rms=%d",
                segment.source,
                segment.duration_ms,
                segment.ended_by,
                min_rms,
            )
            return not self.stop_event.is_set()

        saved = self.processor.save_segment(segment)
        log.info(
            "Segment queued | source=%s | file=%s | duration_ms=%d | ended_by=%s",
            segment.source,
            saved.name,
            segment.duration_ms,
            segment.ended_by,
        )
        self.processor.flush_pending(max_files=self.settings.max_upload_per_cycle)
        return not self.stop_event.is_set()


def _log_stream_open(
    *,
    config: AudioConfig,
    resolved: ResolvedDevice | None,
    source_sample_rate: int,
    source_channels: int,
) -> None:
    info = resolved.info if resolved else None
    log.info(
        "Opening %s audio | capturer_rate=%d | target_rate=%d | frame_ms=%d | channels=%d | latency=%s | device=%s | hostapi=%s | device_rate=%.0f",
        config.source,
        source_sample_rate,
        config.target_sample_rate,
        config.frame_ms,
        source_channels,
        config.latency,
        resolved.label if resolved else "default",
        info.hostapi_name if info else "",
        info.default_samplerate if info else 0.0,
    )


def _stream_kwargs(
    config: AudioConfig,
    resolved: ResolvedDevice,
) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "samplerate": config.capturer_sample_rate,
        "channels": max(1, config.channels),
        "dtype": "int16",
        "blocksize": int(config.capturer_sample_rate * config.frame_ms / 1000),
    }
    if config.latency is not None:
        kwargs["latency"] = config.latency
    if resolved.index is not None:
        kwargs["device"] = resolved.index
    return kwargs


def _iter_input_chunks(
    config: AudioConfig,
    *,
    stop_event: Event | None,
    idle_timeout_s: float | None,
) -> Iterator[bytes]:
    resolved = resolve_input_device(
        requested_device=config.input_device,
        source=config.source,
    )
    frame_samples = int(config.capturer_sample_rate * config.frame_ms / 1000)

    _log_stream_open(
        config=config,
        resolved=resolved,
        source_sample_rate=config.capturer_sample_rate,
        source_channels=max(1, config.channels),
    )

    started_at = time.monotonic()
    with sd.RawInputStream(**_stream_kwargs(config, resolved)) as stream:
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
            yield bytes(data)


def _build_processor(config: AudioConfig) -> PcmProcessor:
    return PcmProcessor(
        target_sample_rate=config.target_sample_rate,
        frame_ms=config.frame_ms,
        gain_db=config.gain_db,
        source_channels=max(1, config.channels),
        source_sample_rate=config.capturer_sample_rate,
    )


def _emit_segments(
    processor: PcmProcessor,
    segmenter: VadSegmenter,
    chunk: bytes,
    on_segment: Callable[[AudioSegment], bool | None],
) -> bool:
    for frame in processor.feed(chunk):
        for segment in segmenter.feed(frame):
            if on_segment(segment) is False:
                return False
    return True


def listen_microphone(
    config: AudioConfig,
    on_segment: Callable[[AudioSegment], bool | None],
    *,
    stop_event: Event | None = None,
    idle_timeout_s: float | None = None,
) -> None:
    processor = _build_processor(config)
    segmenter = VadSegmenter(config)

    for chunk in _iter_input_chunks(
        config,
        stop_event=stop_event,
        idle_timeout_s=idle_timeout_s,
    ):
        if not _emit_segments(processor, segmenter, chunk, on_segment):
            return

    for frame in processor.flush():
        for segment in segmenter.feed(frame):
            if on_segment(segment) is False:
                return
    tail = segmenter.flush()
    if tail is not None:
        on_segment(tail)


def diagnose_source(
    config: AudioConfig,
    *,
    diagnostic_s: float,
    stop_event: Event | None,
) -> None:
    processor = _build_processor(config)
    samples = b""

    for chunk in _iter_input_chunks(
        config,
        stop_event=stop_event,
        idle_timeout_s=diagnostic_s,
    ):
        frames = processor.feed(chunk)
        if frames:
            samples += b"".join(frames)

    rms = pcm_rms(samples)
    clipped = samples.count(b"\xff\x7f") + samples.count(b"\x00\x80")
    log.info(
        "Audio diagnostics | source=%s | capturer_rate=%d | target_rate=%d | channels=%d | rms=%d | clipped=%d",
        config.source,
        config.capturer_sample_rate,
        config.target_sample_rate,
        max(1, config.channels),
        rms,
        clipped,
    )


def capturer_once(config: AudioConfig, timeout_s: float) -> AudioSegment | None:
    capturerd: list[AudioSegment] = []

    def on_segment(segment: AudioSegment) -> bool:
        capturerd.append(segment)
        return False

    listen_microphone(config, on_segment, idle_timeout_s=timeout_s)
    return capturerd[0] if capturerd else None
