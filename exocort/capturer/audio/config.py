from dataclasses import dataclass


@dataclass(slots=True)
class AudioCaptureConfig:
    chunk_seconds: int = 30
    sample_rate: int = 16_000
    channels: int = 1
