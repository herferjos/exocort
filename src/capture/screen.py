import hashlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import cv2
import mss
import numpy as np
import requests

import settings


@dataclass
class ScreenSettings:
    enabled: bool
    fps: float
    monitor_index: int
    save_png: bool
    out_dir: Path
    request_timeout_s: float
    frame_url: str

    @classmethod
    def from_env(cls) -> "ScreenSettings":
        return cls(
            enabled=settings.screen_capture_enabled(),
            fps=settings.screen_capture_fps(),
            monitor_index=settings.screen_capture_monitor_index(),
            save_png=settings.screen_capture_save_png(),
            out_dir=settings.screen_capture_out_dir(),
            request_timeout_s=settings.screen_capture_request_timeout_s(),
            frame_url=settings.collector_frame_url(),
        )


class ScreenCapture:
    def __init__(self, cfg: ScreenSettings):
        self.cfg = cfg
        self.logger = logging.getLogger("screen_capture")
        self.last_frame_hash: str | None = None

    def run(self) -> None:
        if not self.cfg.enabled:
            self.logger.info("Screen capture disabled (set SCREEN_CAPTURE_ENABLED=1 to enable).")
            return

        interval = 1.0 / self.cfg.fps
        if self.cfg.save_png:
            self.cfg.out_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(
            "Starting screen capture | fps=%.2f | monitor_index=%d",
            self.cfg.fps,
            self.cfg.monitor_index,
        )

        with mss.mss() as sct:
            monitors = sct.monitors
            if self.cfg.monitor_index >= len(monitors):
                raise ValueError(
                    f"Monitor index {self.cfg.monitor_index} is invalid. Available: 1..{len(monitors)-1}"
                )
            monitor = monitors[self.cfg.monitor_index]

            while True:
                started = time.time()
                frame_bgr = self._capture_bgr(sct, monitor)
                frame_hash = self._hash_frame(frame_bgr)

                if frame_hash == self.last_frame_hash:
                    self._sleep_remaining(interval, started)
                    continue

                self.last_frame_hash = frame_hash
                frame_id = uuid4().hex

                ok, png_bytes = cv2.imencode(".png", frame_bgr)
                if not ok:
                    self.logger.warning("Failed to encode frame to PNG")
                    self._sleep_remaining(interval, started)
                    continue

                if self.cfg.save_png:
                    out_path = self.cfg.out_dir / f"{frame_id}.png"
                    out_path.write_bytes(png_bytes.tobytes())

                self._upload_frame(
                    frame_id=frame_id,
                    png_bytes=png_bytes.tobytes(),
                    width=frame_bgr.shape[1],
                    height=frame_bgr.shape[0],
                    content_hash=frame_hash,
                )

                self._sleep_remaining(interval, started)

    def _capture_bgr(self, sct: mss.mss, monitor: dict) -> np.ndarray:
        shot = sct.grab(monitor)
        frame = np.array(shot)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    def _hash_frame(self, frame_bgr: np.ndarray) -> str:
        small = cv2.resize(frame_bgr, (64, 36), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        return hashlib.sha1(gray.tobytes()).hexdigest()

    def _upload_frame(self, frame_id: str, png_bytes: bytes, width: int, height: int, content_hash: str) -> None:
        try:
            files = {"file": (f"{frame_id}.png", png_bytes, "image/png")}
            data = {
                "frame_id": frame_id,
                "monitor_index": str(self.cfg.monitor_index),
                "width": str(width),
                "height": str(height),
                "hash": content_hash,
            }
            resp = requests.post(
                self.cfg.frame_url,
                files=files,
                data=data,
                timeout=self.cfg.request_timeout_s,
            )
            if resp.status_code >= 300:
                self.logger.warning(
                    "Frame upload rejected | status=%d | body=%s",
                    resp.status_code,
                    resp.text[:200],
                )
        except Exception:
            self.logger.exception("Frame upload failed")

    @staticmethod
    def _sleep_remaining(interval: float, started: float) -> None:
        sleep_for = interval - (time.time() - started)
        if sleep_for > 0:
            time.sleep(sleep_for)


def main() -> None:
    logging.basicConfig(
        level="INFO",
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    cfg = ScreenSettings.from_env()
    ScreenCapture(cfg).run()


if __name__ == "__main__":
    main()
