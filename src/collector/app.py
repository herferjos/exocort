from datetime import datetime

import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import settings
from .event_store import EventStore
from .util import new_id, utc_now_iso

_data_dir = settings.collector_data_dir()
_store = EventStore(data_dir=_data_dir)

# Simple in-memory cache for deduplication: url -> {len, ts}
_last_saved_states: dict[str, dict] = {}

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {"ok": True}


def _save_page_content(event: dict) -> None:
    if event.get("type") != "browser.page_text":
        return
    meta = event.get("meta")
    if not isinstance(meta, dict):
        return
    text = meta.get("text")
    if not isinstance(text, str) or not text.strip():
        return

    ts = event.get("ts", utc_now_iso())
    day = ts[:10]
    content_dir = _data_dir / "content" / day
    content_dir.mkdir(parents=True, exist_ok=True)

    event_id = event.get("id", new_id())
    safe_ts = ts[:19].replace(":", "-")
    content_path = content_dir / f"{safe_ts}-{event_id}.md"
    content_path.write_text(text, encoding="utf-8")

    del meta["text"]
    meta["text_path"] = str(content_path.relative_to(_data_dir))
    meta["text_preview"] = text[:500]


def _should_process_event(event: dict) -> bool:
    if event.get("type") != "browser.page_text":
        return True

    meta = event.get("meta", {})
    url = meta.get("url")
    text = meta.get("text", "")
    reason = meta.get("reason", "")
    ts_str = event.get("ts") or utc_now_iso()

    if not url or not text:
        return True

    try:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        current_ts = datetime.fromisoformat(ts_str)
    except Exception:
        return True

    last_state = _last_saved_states.get(url)
    if not last_state:
        _last_saved_states[url] = {"len": len(text), "ts": current_ts}
        return True

    delta = (current_ts - last_state["ts"]).total_seconds()
    if delta > 120:
        _last_saved_states[url] = {"len": len(text), "ts": current_ts}
        return True

    if reason and str(reason).startswith("user_"):
        _last_saved_states[url] = {"len": len(text), "ts": current_ts}
        return True

    len_diff = abs(len(text) - last_state["len"])
    if len_diff < 50:
        return False

    _last_saved_states[url] = {"len": len(text), "ts": current_ts}
    return True


@app.post("/events")
async def events(payload: dict):
    events_list = payload.get("events") if isinstance(payload, dict) else None

    if isinstance(events_list, list):
        processed_count = 0
        for ev in events_list:
            if isinstance(ev, dict):
                if not _should_process_event(ev):
                    continue
                _save_page_content(ev)
                _store.append(ev)
                processed_count += 1
        return {"ok": True, "count": processed_count}

    if isinstance(payload, dict):
        if _should_process_event(payload):
            _save_page_content(payload)
            _store.append(payload)
            return {"ok": True, "count": 1}
        return {"ok": True, "count": 0, "status": "deduplicated"}

    return {"ok": False, "error": "invalid_payload"}


def _parse_optional_int(v: str | int | None) -> int | None:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = (v or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


@app.post("/audio")
async def audio(
    file: UploadFile = File(...),
    segment_id: str | None = Form(default=None),
    duration_ms: str | None = Form(default=None),
    vad_reason: str | None = Form(default=None),
    rms: str | None = Form(default=None),
    sample_rate: str | None = Form(default=None),
    client_source: str | None = Form(default=None),
    page_url: str | None = Form(default=None),
    page_title: str | None = Form(default=None),
):
    seg_id = (segment_id or "").strip() or new_id()
    duration_ms_val = _parse_optional_int(duration_ms)
    rms_val = _parse_optional_int(rms)
    sample_rate_val = _parse_optional_int(sample_rate)
    day = utc_now_iso()[:10]
    out_dir = _data_dir / "audio" / day
    out_dir.mkdir(parents=True, exist_ok=True)

    content_type = (file.content_type or "").strip().lower()
    filename = (file.filename or "").strip()
    if filename and "." in filename:
        suffix = "." + filename.rsplit(".", 1)[-1].lower()
    elif content_type == "audio/webm":
        suffix = ".webm"
    elif content_type in {"audio/ogg", "application/ogg"}:
        suffix = ".ogg"
    elif content_type in {"audio/wav", "audio/x-wav", "audio/wave"}:
        suffix = ".wav"
    elif content_type in {"audio/mpeg", "audio/mp3"}:
        suffix = ".mp3"
    elif content_type in {"audio/mp4", "audio/x-m4a", "audio/m4a"}:
        suffix = ".m4a"
    else:
        suffix = ".bin"

    audio_path = out_dir / f"{seg_id}{suffix}"
    audio_path.write_bytes(await file.read())

    event = {
        "id": new_id(),
        "ts": utc_now_iso(),
        "source": "audio",
        "type": "audio.segment",
        "meta": {
            "audio_path": str(audio_path.relative_to(_data_dir)),
            "duration_ms": duration_ms_val,
            "vad_reason": (vad_reason or "").strip() or None,
            "rms": rms_val,
            "sample_rate": sample_rate_val,
            "content_type": content_type or None,
            "client_source": (client_source or "").strip() or None,
            "page_url": (page_url or "").strip() or None,
            "page_title": (page_title or "").strip() or None,
        },
    }
    _store.append(event)
    return {"ok": True, "event_id": event["id"]}


@app.post("/frame")
async def frame(
    file: UploadFile = File(...),
    frame_id: str | None = Form(default=None),
    monitor_index: str | None = Form(default=None),
    width: str | None = Form(default=None),
    height: str | None = Form(default=None),
    hash: str | None = Form(default=None),
):
    frame_id_val = (frame_id or "").strip() or new_id()
    day = utc_now_iso()[:10]
    out_dir = _data_dir / "frame" / day
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = (file.filename or "").strip().lower()
    suffix = ".png" if filename.endswith(".png") else ".bin"
    frame_path = out_dir / f"{frame_id_val}{suffix}"
    frame_path.write_bytes(await file.read())

    event = {
        "id": new_id(),
        "ts": utc_now_iso(),
        "source": "screen",
        "type": "screen.frame",
        "meta": {
            "frame_path": str(frame_path.relative_to(_data_dir)),
            "monitor_index": _parse_optional_int(monitor_index),
            "width": _parse_optional_int(width),
            "height": _parse_optional_int(height),
            "hash": (hash or "").strip() or None,
        },
    }
    _store.append(event)
    return {"ok": True, "event_id": event["id"]}


def main() -> None:
    host = settings.collector_host()
    port = settings.collector_port()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
