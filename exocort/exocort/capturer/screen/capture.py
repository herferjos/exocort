from __future__ import annotations

from datetime import datetime
import time

from mss import mss
from mss.tools import to_png

from exocort.config import ScreenSettings
from exocort.logs import get_logger

log = get_logger("screen")


def capture_screenshot(_: ScreenSettings) -> tuple[bytes, tuple[int, int]]:
    with mss() as sct:
        shot = sct.grab(sct.monitors[0])
        return shot.rgb, shot.size


def screenshot_loop(config: ScreenSettings) -> None:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    output_dir = config.output_dir

    while True:
        image_bytes, size = capture_screenshot(config)
        png_bytes = to_png(image_bytes, size)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
        file_path = output_dir / f"{timestamp}.png"
        file_path.write_bytes(png_bytes)
        log.info("captured %s bytes -> %s", len(png_bytes), file_path)
        time.sleep(config.interval_seconds)
