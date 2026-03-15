"""Collector API: receives capture uploads and forwards to configured processing endpoints."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, File, Form, UploadFile

from .config import CollectorConfig
from .dedup import get_dedup
from .forward import forward_upload
from .vault import save_to_tmp, remove_tmp, write_vault_record, VaultIndex

log = logging.getLogger("collector")

_config: CollectorConfig | None = None
_vault_index: VaultIndex | None = None


def get_config() -> CollectorConfig:
    global _config
    if _config is None:
        _config = CollectorConfig.load()
    return _config


def get_vault_index() -> VaultIndex:
    global _vault_index
    if _vault_index is None:
        _vault_index = VaultIndex(days_back=2)
        log.info("Vault index loaded | keys=%d", len(_vault_index))
    return _vault_index


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_config()
    get_vault_index()
    yield
    pass


app = FastAPI(title="Exocort Collector", lifespan=lifespan)


def _now() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d"), now.isoformat()


@app.post("/api/audio")
async def api_audio(
    file: UploadFile = File(...),
    segment_id: str = Form(""),
    sample_rate: str = Form(""),
    client_source: str = Form(""),
    source: str = Form(""),
    duration_ms: str = Form(""),
    vad_reason: str = Form(""),
    rms: str = Form(""),
):
    """Receive audio from capture agent; save to tmp, forward, persist responses to vault, remove tmp."""
    config = get_config()
    body = await file.read()
    form_data = {
        "segment_id": segment_id,
        "sample_rate": sample_rate,
        "client_source": client_source,
        "source": source,
        "duration_ms": duration_ms,
        "vad_reason": vad_reason,
        "rms": rms,
    }
    segment_id = segment_id or _now()[1].replace(":", "-")
    filename = file.filename or "audio.wav"
    content_type = file.content_type or "audio/wav"

    dedup = get_dedup()
    vault_index = get_vault_index()
    audio_key = f"audio:{segment_id}"
    if dedup.is_duplicate(audio_key):
        log.debug("Audio duplicate skipped (recent) | segment_id=%s", segment_id)
        return {"ok": True, "forwarded": 0, "duplicate": True}
    if vault_index.contains(audio_key):
        log.debug("Audio duplicate skipped (vault) | segment_id=%s", segment_id)
        return {"ok": True, "forwarded": 0, "duplicate": True}
    dedup.mark_seen(audio_key)

    if config.audio is None:
        return {"ok": True, "forwarded": 0, "message": "No audio endpoint configured"}

    date, timestamp_iso = _now()
    safe_ts = timestamp_iso.replace(":", "-")
    tmp_path = save_to_tmp(body, "audio", date, f"{safe_ts}_{segment_id}", ".wav")
    try:
        ep = config.audio
        ok, status, resp_body, extra = forward_upload(
            ep, body, filename, content_type, stream_type="audio"
        )
        results = [{"url": ep.url, "format": ep.format, "ok": ok, "status": status, "body": resp_body, **extra}]
        vault_path = write_vault_record(
            date, timestamp_iso, "audio", segment_id, form_data, results
        )
        vault_index.add(audio_key)
        log.info("Vault wrote | path=%s", vault_path)
        return {"ok": True, "forwarded": 1, "results": [{"url": results[0]["url"], "ok": results[0]["ok"], "status": results[0]["status"]}]}
    finally:
        remove_tmp(tmp_path)


@app.post("/api/screen")
async def api_screen(
    file: UploadFile = File(...),
    screen_id: str = Form(""),
    width: str = Form(""),
    height: str = Form(""),
    hash: str = Form(""),  # noqa: A002
    app_json: str = Form("", alias="app"),
    capture: str = Form(""),
    permissions: str = Form(""),
    window: str = Form(""),
):
    """Receive screen capture; save to tmp, forward, persist responses to vault, remove tmp."""
    config = get_config()
    body = await file.read()
    form_data = {
        "screen_id": screen_id,
        "width": width,
        "height": height,
        "hash": hash,
        "app": app_json,
        "capture": capture,
        "permissions": permissions,
    }
    if window:
        form_data["window"] = window
    screen_id = screen_id or _now()[1].replace(":", "-")
    filename = file.filename or "screen.png"
    content_type = file.content_type or "image/png"

    dedup = get_dedup()
    vault_index = get_vault_index()
    screen_key = f"screen:{hash}" if hash else f"screen:id:{screen_id}"
    if dedup.is_duplicate(screen_key):
        log.debug("Screen duplicate skipped (recent) | hash=%s", hash or screen_id)
        return {"ok": True, "forwarded": 0, "duplicate": True}
    if vault_index.contains(screen_key):
        log.debug("Screen duplicate skipped (vault) | hash=%s", hash or screen_id)
        return {"ok": True, "forwarded": 0, "duplicate": True}
    dedup.mark_seen(screen_key)

    if config.screen is None:
        return {"ok": True, "forwarded": 0, "message": "No screen endpoint configured"}

    date, timestamp_iso = _now()
    safe_ts = timestamp_iso.replace(":", "-")
    tmp_path = save_to_tmp(body, "screen", date, f"{safe_ts}_{screen_id}", ".png")
    try:
        ep = config.screen
        ok, status, resp_body, extra = forward_upload(
            ep, body, filename, content_type, stream_type="screen"
        )
        results = [{"url": ep.url, "format": ep.format, "ok": ok, "status": status, "body": resp_body, **extra}]
        vault_path = write_vault_record(
            date, timestamp_iso, "screen", screen_id, form_data, results
        )
        vault_index.add(screen_key)
        log.info("Vault wrote | path=%s", vault_path)
        return {"ok": True, "forwarded": 1, "results": [{"url": results[0]["url"], "ok": results[0]["ok"], "status": results[0]["status"]}]}
    finally:
        remove_tmp(tmp_path)


def main() -> None:
    import uvicorn

    from exocort import settings

    logging.basicConfig(
        level=settings.log_level(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    host = os.environ.get("COLLECTOR_HOST", "127.0.0.1")
    port = int(os.environ.get("COLLECTOR_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
