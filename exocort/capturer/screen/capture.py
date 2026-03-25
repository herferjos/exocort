from __future__ import annotations

import time
from collections.abc import Callable

from mss import mss

from .config import ScreenCaptureConfig


def capture_screenshot(_: ScreenCaptureConfig) -> bytes:
    with mss() as sct:
        shot = sct.grab(sct.monitors[0])
        return shot.rgb


def screenshot_loop(
    config: ScreenCaptureConfig,
    handler: Callable[[bytes], None] | None = None,
) -> None:
    while True:
        image_bytes = capture_screenshot(config)
        print(f"[screen] captured {len(image_bytes)} bytes")
        if handler is not None:
            handler(image_bytes)
        time.sleep(config.interval_seconds)
