from dataclasses import dataclass


@dataclass(slots=True)
class ScreenCaptureConfig:
    interval_seconds: int = 5
