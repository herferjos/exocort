from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import sounddevice as sd

log = logging.getLogger("audio_capturer")

PREFERRED_MIC_KEYWORDS = (
    "microphone",
    "mic",
    "built-in",
    "internal",
    "macbook",
)
AVOID_MIC_KEYWORDS = (
    "iphone",
    "continuity",
)


@dataclass(frozen=True)
class DeviceInfo:
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    hostapi_name: str


@dataclass(frozen=True)
class ResolvedDevice:
    index: int | None
    label: str
    info: DeviceInfo | None


def resolve_input_device(
    *,
    requested_device: str | None,
    source: str,
) -> ResolvedDevice:
    devices = _list_input_devices()
    if requested_device:
        exact = _match_input_device(devices, requested_device, exact=True)
        if exact is not None:
            return _resolved_device(exact)

        partial = _match_input_device(devices, requested_device, exact=False)
        if partial is not None:
            log.warning(
                "Input device %r was not an exact match; using %s",
                requested_device,
                partial.name,
            )
            return _resolved_device(partial)

        log.warning(
            "Input device %r was not found for %s source; falling back to auto/default input",
            requested_device,
            source,
        )

    default_device = _resolve_default_input(devices)
    if default_device is not None:
        return _resolved_device(default_device)

    preferred_mic = _detect_preferred_microphone(devices)
    if preferred_mic is not None:
        return _resolved_device(preferred_mic)

    return ResolvedDevice(None, "default", None)


def _list_input_devices() -> list[DeviceInfo]:
    devices: list[DeviceInfo] = []
    for index, device in enumerate(sd.query_devices()):
        max_in = int(device.get("max_input_channels", 0) or 0)
        if max_in <= 0:
            continue
        max_out = int(device.get("max_output_channels", 0) or 0)
        default_sr = float(device.get("default_samplerate", 0.0) or 0.0)
        hostapi_name = _device_hostapi_name(index)
        name = str(device.get("name", f"device-{index}"))
        devices.append(
            DeviceInfo(
                index=index,
                name=name,
                max_input_channels=max_in,
                max_output_channels=max_out,
                default_samplerate=default_sr,
                hostapi_name=hostapi_name,
            )
        )
    return devices


def _match_input_device(
    devices: list[DeviceInfo],
    requested_device: str,
    *,
    exact: bool,
) -> DeviceInfo | None:
    requested = requested_device.strip().lower()
    if not requested:
        return None

    if requested.isdigit():
        requested_index = int(requested)
        for device in devices:
            if device.index == requested_index:
                return device
        return None

    for device in devices:
        candidate = device.name.lower()
        if exact and candidate == requested:
            return device
        if not exact and requested in candidate:
            return device
    return None


def _detect_preferred_microphone(devices: list[DeviceInfo]) -> DeviceInfo | None:
    for device in devices:
        candidate = device.name.lower()
        if any(word in candidate for word in AVOID_MIC_KEYWORDS):
            continue
        if any(word in candidate for word in PREFERRED_MIC_KEYWORDS):
            return device
    return None


def _resolve_default_input(devices: list[DeviceInfo]) -> DeviceInfo | None:
    try:
        default_index = int(sd.default.device[0])  # type: ignore[index]
    except Exception:
        return None
    for device in devices:
        if device.index == default_index:
            return device
    return None


def _device_hostapi_name(index: int) -> str:
    try:
        device = sd.query_devices(index)
        hostapi_index = int(device.get("hostapi", -1) or -1)
        hostapis = sd.query_hostapis()
        if 0 <= hostapi_index < len(hostapis):
            return str(hostapis[hostapi_index].get("name", ""))
    except Exception:
        return ""
    return ""


def _resolved_device(device: DeviceInfo) -> ResolvedDevice:
    return ResolvedDevice(device.index, device.name, device)


def _pcm_rms(pcm_bytes: bytes) -> int:
    import audioop

    if not pcm_bytes:
        return 0
    return int(audioop.rms(pcm_bytes, 2))


def wav_rms(path: Path) -> int:
    import wave

    try:
        with wave.open(str(path), "rb") as wav_file:
            frames = wav_file.readframes(wav_file.getnframes())
        return _pcm_rms(frames)
    except Exception:
        return 0


def remove_wav_and_meta(path: Path, logger: logging.Logger) -> bool:
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError:
        logger.exception("Failed to remove file | file=%s", path.name)
        return False
