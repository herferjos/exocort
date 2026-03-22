"""Collector API: receives uploads, forwards them to processing endpoints, and stores the returned text."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, File, UploadFile

from .config import CollectorConfig
from .forward import forward_upload
from .vault import new_record_id, write_vault_record

log = logging.getLogger("collector")

_config: CollectorConfig | None = None


def get_config() -> CollectorConfig:
    global _config
    if _config is None:
        _config = CollectorConfig.load()
    return _config


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_config()
    yield


app = FastAPI(title="Exocort Collector", lifespan=lifespan)


def _now() -> str:
    now = datetime.now(timezone.utc)
    return now.isoformat()


@app.post("/api/audio")
async def api_audio(
    file: UploadFile = File(...),
):
    """Receive audio from the capturer, forward it, and store the transcription."""
    config = get_config()
    body = await file.read()
    record_id = new_record_id()
    filename = file.filename or "audio.wav"
    content_type = file.content_type or "audio/wav"

    if config.audio is None:
        return {"ok": True, "forwarded": 0, "message": "No audio endpoint configured"}

    timestamp_iso = _now()
    ep = config.audio
    ok, status, text = forward_upload(ep, body, filename, content_type, stream_type="audio")

    if not ok:
        log.warning(
            "Audio forward failed; skipping vault write | id=%s | status=%d",
            record_id,
            status,
        )
        return {
            "ok": False,
            "forwarded": 0,
            "status": status,
            "error": "audio_forward_failed",
        }

    if not text:
        log.info(
            "Audio response empty; skipping vault write | id=%s | url=%s",
            record_id,
            ep.url,
        )
        return {
            "ok": True,
            "forwarded": 1,
            "empty": True,
            "status": status,
        }

    vault_path = write_vault_record(record_id, timestamp_iso, text)
    log.info("Vault wrote | path=%s", vault_path)
    return {
        "ok": True,
        "forwarded": 1,
        "id": record_id,
    }


@app.post("/api/screen")
async def api_screen(
    file: UploadFile = File(...),
):
    """Receive screen captures, forward them, and store the extracted text."""
    config = get_config()
    body = await file.read()
    record_id = new_record_id()
    filename = file.filename or "screen.jpg"
    content_type = file.content_type or "image/jpeg"

    if config.screen is None:
        return {"ok": True, "forwarded": 0, "message": "No screen endpoint configured"}

    timestamp_iso = _now()
    ep = config.screen
    ok, status, text = forward_upload(ep, body, filename, content_type, stream_type="screen")
    if not ok:
        log.warning(
            "Screen forward failed; skipping vault write | id=%s | status=%d",
            record_id,
            status,
        )
        return {
            "ok": False,
            "forwarded": 0,
            "status": status,
            "error": "screen_forward_failed",
        }
    if not text:
        log.info(
            "Screen response empty; skipping vault write | id=%s | url=%s",
            record_id,
            ep.url,
        )
        return {
            "ok": True,
            "forwarded": 1,
            "empty": True,
            "status": status,
        }
    vault_path = write_vault_record(record_id, timestamp_iso, text)
    log.info("Vault wrote | path=%s", vault_path)
    return {
        "ok": True,
        "forwarded": 1,
        "id": record_id,
    }


def main() -> None:
    import uvicorn

    from exocort import settings

    logging.basicConfig(
        level=settings.log_level(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    host = settings.collector_host()
    port = settings.collector_port()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
