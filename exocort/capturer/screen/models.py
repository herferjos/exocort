from __future__ import annotations

from dataclasses import asdict, dataclass

from exocort import settings


@dataclass(frozen=True)
class ScreenSettings:
    enabled: bool
    fps: float
    request_timeout_s: float
    screen_url: str
    prompt_permission: bool
    dedup_window_s: float
    dedup_threshold: int

    @classmethod
    def from_env(cls) -> "ScreenSettings":
        return cls(
            enabled=settings.screen_capturer_enabled(),
            fps=settings.screen_capturer_fps(),
            request_timeout_s=settings.screen_capturer_request_timeout_s(),
            screen_url=settings.collector_screen_url(),
            prompt_permission=settings.screen_capturer_prompt_permission(),
            dedup_window_s=settings.screen_capturer_dedup_window_s(),
            dedup_threshold=settings.screen_capturer_dedup_threshold(),
        )


@dataclass(frozen=True)
class RunningWindow:
    window_id: int
    owner_name: str
    owner_pid: int
    title: str
    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict[str, str | int | float]:
        return asdict(self)


@dataclass(frozen=True)
class capturerRegion:
    mode: str
    source: str
    display_id: int | None
    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict[str, str | int | float | None]:
        return asdict(self)


@dataclass(frozen=True)
class DisplayBounds:
    display_id: int
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class capturerdScreen:
    screen_id: str
    image_bytes: bytes
    width: int
    height: int
    content_hash: str
    perceptual_hash: str
    app: dict[str, object]
    window: dict[str, object] | None
    capturer: dict[str, object]
    permissions: dict[str, object]
