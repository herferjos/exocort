from __future__ import annotations

import base64
import hashlib
from io import BytesIO
import logging
import time
from uuid import uuid4

import imagehash
import mss
from PIL import Image
from litellm import completion

from ...vault import new_record_id, write_vault_record
from .app import frontmost_app
from .models import ScreenCapture, ScreenRegion, ScreenSettings


def _completion_text(response) -> str:
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, dict):
        choices = response.get("choices", [])
    if not choices:
        return ""
    first = choices[0]
    message = getattr(first, "message", None)
    if message is None and isinstance(first, dict):
        message = first.get("message", {})
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return " ".join(parts).strip()
    return str(content or "").strip()


def _capture_primary_monitor() -> tuple[dict[str, int], mss.base.ScreenShot]:
    with mss.mss() as sct:
        monitors = sct.monitors
        monitor = monitors[1] if len(monitors) > 1 else monitors[0]
        return monitor, sct.grab(monitor)


def _jpeg_bytes_and_hashes(screenshot: mss.base.ScreenShot) -> tuple[bytes, str, str]:
    image = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=70, optimize=False)
    jpeg_bytes = buffer.getvalue()
    return (
        jpeg_bytes,
        hashlib.sha1(jpeg_bytes).hexdigest(),
        str(imagehash.dhash(image)),
    )


def _screen_region(monitor: dict[str, int]) -> dict[str, str | int | float | None]:
    return ScreenRegion(
        mode="display",
        source="primary",
        display_id=0,
        x=float(monitor["left"]),
        y=float(monitor["top"]),
        width=float(monitor["width"]),
        height=float(monitor["height"]),
    ).to_dict()


def capturer_screen(prompt_permission: bool = False) -> ScreenCapture:
    """Capture one frame. content_hash is SHA-1 of JPEG bytes."""
    del prompt_permission
    monitor, screenshot = _capture_primary_monitor()
    jpeg_bytes, content_hash, perceptual_hash = _jpeg_bytes_and_hashes(screenshot)
    app_name, bundle_id, pid = frontmost_app()
    return ScreenCapture(
        screen_id=uuid4().hex,
        image_bytes=jpeg_bytes,
        width=screenshot.width,
        height=screenshot.height,
        content_hash=content_hash,
        perceptual_hash=perceptual_hash,
        app={"name": app_name, "bundle_id": bundle_id, "pid": pid},
        window=None,
        capturer=_screen_region(monitor),
        permissions={"screen_recording": True, "accessibility": False},
    )


class Screencapturer:
    """Dedup repeated frames and process only useful screenshots."""

    def __init__(self, cfg: ScreenSettings):
        self.cfg = cfg
        self.logger = logging.getLogger("screen_capturer")
        self.last_perceptual_hash: imagehash.ImageHash | None = None
        self._recent_sent: dict[str, float] = {}

    def _prune_recent(self) -> None:
        now = time.monotonic()
        window = self.cfg.dedup_window_s
        expired = [h for h, t in self._recent_sent.items() if (now - t) > window]
        for h in expired:
            del self._recent_sent[h]

    def _already_sent_recently(self, content_hash: str) -> bool:
        self._prune_recent()
        return content_hash in self._recent_sent

    def _should_skip(self, screen: ScreenCapture) -> bool:
        current_phash = imagehash.hex_to_hash(screen.perceptual_hash)
        if self.last_perceptual_hash is not None:
            distance = self.last_perceptual_hash - current_phash
            if distance <= self.cfg.dedup_threshold:
                return True
        if self._already_sent_recently(screen.content_hash):
            return True
        self.last_perceptual_hash = current_phash
        return False

    @staticmethod
    def _sleep_remaining(interval: float, started_at: float) -> None:
        sleep_for = interval - (time.monotonic() - started_at)
        if sleep_for > 0:
            time.sleep(sleep_for)

    def run(self) -> None:
        if not self.cfg.enabled:
            self.logger.info(
                "Screen capturer disabled (set [runtime].enable_screen_capturer = true to enable)."
            )
            return

        interval = 1.0 / self.cfg.fps

        self.logger.info(
            "Starting screen capturer | fps=%.2f | dedup_window_s=%.0f",
            self.cfg.fps,
            self.cfg.dedup_window_s,
        )

        while True:
            started_at = time.monotonic()
            try:
                screen = capturer_screen(prompt_permission=self.cfg.prompt_permission)
            except Exception:
                self.logger.exception("Screen capturer failed")
                self._sleep_remaining(interval, started_at)
                continue

            if self._should_skip(screen):
                self._sleep_remaining(interval, started_at)
                continue

            if self._process_screen(screen):
                self._recent_sent[screen.content_hash] = time.monotonic()
            self._sleep_remaining(interval, started_at)

    @staticmethod
    def _screen_prompt(service) -> str:
        return service.prompt or "Extract all visible text from this screenshot."

    @staticmethod
    def _screen_messages(service, data_url: str) -> list[dict[str, object]]:
        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": Screencapturer._screen_prompt(service)},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ]

    @staticmethod
    def _service_kwargs(service, data_url: str) -> dict[str, object]:
        kwargs = dict(service.options)
        kwargs["model"] = service.model
        kwargs["messages"] = Screencapturer._screen_messages(service, data_url)
        kwargs["timeout"] = service.timeout
        if service.base_url:
            kwargs["base_url"] = service.base_url
        if service.api_key:
            kwargs["api_key"] = service.api_key
        if service.headers:
            kwargs["extra_headers"] = dict(service.headers)
        return kwargs

    def _process_screen(self, screen: ScreenCapture) -> bool:
        service = self.cfg.service
        if service is None:
            self.logger.warning("No [services.screen] configured; skipping screenshot")
            return False

        try:
            encoded = base64.b64encode(screen.image_bytes).decode("ascii")
            data_url = f"data:image/jpeg;base64,{encoded}"
            text = _completion_text(
                completion(**self._service_kwargs(service, data_url))
            )
        except Exception:
            self.logger.exception("Screen processing failed")
            return False

        if not text:
            self.logger.info(
                "Screen produced empty text | screen_id=%s", screen.screen_id
            )
            return True

        record_id = new_record_id()
        vault_path = write_vault_record(
            record_id,
            text,
            stream="screen",
            model=service.model,
            metadata={
                "screen_id": screen.screen_id,
                "width": screen.width,
                "height": screen.height,
                "hash": screen.content_hash,
                "app": screen.app,
                "window": screen.window,
                "capturer": screen.capturer,
                "permissions": screen.permissions,
            },
        )
        self.logger.info(
            "Screen processed | screen_id=%s | id=%s | vault=%s",
            screen.screen_id,
            record_id,
            vault_path,
        )
        return True
