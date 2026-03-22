from __future__ import annotations

import logging
import time
from dataclasses import replace
from threading import Event, Thread

import sounddevice as sd

from .device import ResolvedDevice, resolve_input_device
from .models import AudioConfig, AudioSegment, Settings
from .processing import PcmProcessor, pcm_rms
from .uploader import SpoolUploader
from .vad import VadSegmenter

log = logging.getLogger("audio_capturer")


class AudiocapturerAgent:
    def __init__(self, settings_obj: Settings):
        self.settings = settings_obj
        self.uploader = SpoolUploader(settings_obj)
        self.stop_event = Event()

    def run(self) -> None:
        if not self.settings.enabled:
            log.info(
                "Audio capturer disabled (set [runtime].enable_audio_capturer = true to enable)."
            )
            return

        sources = [self.settings.audio]

        self.uploader.flush_pending(max_files=10_000)
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
            "Starting audio capturer | collector_audio_url=%s | sources=%s",
            self.settings.api_audio_url,
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
            self.uploader.flush_pending(max_files=10_000)
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
            except Exception as e:
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


def _iter_sounddevice_frames(
    config: AudioConfig,
    *,
    stop_event: Event | None,
    idle_timeout_s: float | None,
):
    frame_samples = int(config.capturer_sample_rate * config.frame_ms / 1000)
    resolved = resolve_input_device(
        requested_device=config.input_device,
        source=config.source,
    )
    stream_kwargs: dict[str, object] = {
        "samplerate": config.capturer_sample_rate,
        "channels": max(1, config.channels),
        "dtype": "int16",
        "blocksize": frame_samples,
    }
    if config.latency is not None:
        stream_kwargs["latency"] = config.latency
    if resolved.index is not None:
        stream_kwargs["device"] = resolved.index
    if resolved.overrides:
        stream_kwargs.update(resolved.overrides)

    _log_stream_open(
        config=config,
        resolved=resolved,
        source_sample_rate=config.capturer_sample_rate,
        source_channels=max(1, config.channels),
    )

    started_at = time.monotonic()
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
            yield (
                config.capturer_sample_rate,
                max(1, config.channels),
                resolved,
                bytes(data),
            )


def _stream_frames(
    config: AudioConfig,
    *,
    stop_event: Event | None,
    idle_timeout_s: float | None,
):
    yield from _iter_sounddevice_frames(
        config, stop_event=stop_event, idle_timeout_s=idle_timeout_s
    )


def listen_microphone(
    config: AudioConfig,
    on_segment,
    *,
    stop_event: Event | None = None,
    idle_timeout_s: float | None = None,
) -> None:
    segmenter: VadSegmenter | None = None
    processor: PcmProcessor | None = None
    effective_config = config

    for source_rate, source_channels, _, chunk in _stream_frames(
        config,
        stop_event=stop_event,
        idle_timeout_s=idle_timeout_s,
    ):
        if segmenter is None:
            effective_config = replace(
                config,
                capturer_sample_rate=source_rate,
                channels=source_channels,
            )
            segmenter = VadSegmenter(effective_config)
            processor = PcmProcessor(
                target_sample_rate=effective_config.target_sample_rate,
                frame_ms=effective_config.frame_ms,
                gain_db=effective_config.gain_db,
                source_channels=source_channels,
                source_sample_rate=source_rate,
            )

        assert processor is not None
        assert segmenter is not None
        for frame in processor.feed(chunk):
            for segment in segmenter.feed(frame):
                if on_segment(segment) is False:
                    return

    if segmenter is not None and processor is not None:
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
    processor: PcmProcessor | None = None
    samples = b""
    source_rate = config.capturer_sample_rate
    source_channels = config.channels

    for source_rate, source_channels, _, chunk in _stream_frames(
        config,
        stop_event=stop_event,
        idle_timeout_s=diagnostic_s,
    ):
        if processor is None:
            processor = PcmProcessor(
                target_sample_rate=config.target_sample_rate,
                frame_ms=config.frame_ms,
                gain_db=config.gain_db,
                source_channels=source_channels,
                source_sample_rate=source_rate,
            )
        frames = processor.feed(chunk)
        if frames:
            samples += b"".join(frames)

    rms = pcm_rms(samples)
    clipped = samples.count(b"\xff\x7f") + samples.count(b"\x00\x80")
    log.info(
        "Audio diagnostics | source=%s | capturer_rate=%d | target_rate=%d | channels=%d | rms=%d | clipped=%d",
        config.source,
        source_rate,
        config.target_sample_rate,
        source_channels,
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
