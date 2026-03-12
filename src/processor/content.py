import logging
from pathlib import Path

import settings
from ai.ocr import get_ocr_engine
from ai.stt import get_transcriber
from ai.util import sha256_file
from .storage import state_db

log = logging.getLogger("processor.content")


def resolve_events_text(events: list[dict], data_dir: Path) -> str:
    parts: list[str] = []
    for ev in events:
        text = resolve_event_text(ev, data_dir)
        if not text:
            continue
        meta = ev.get("meta", {}) if isinstance(ev.get("meta"), dict) else {}
        url = meta.get("url") or meta.get("page_url")
        title = meta.get("title") or meta.get("page_title")
        header = ""
        if url or title:
            header = f"\n\n---\n\nURL: {url or ''}\nTitle: {title or ''}\n\n"
        parts.append(header + text)
    return "".join(parts).strip()


def resolve_event_text(event: dict, data_dir: Path) -> str:
    ev_type = event.get("type")
    meta = event.get("meta") if isinstance(event.get("meta"), dict) else {}

    if ev_type == "browser.page_text":
        if isinstance(meta.get("text"), str) and meta["text"].strip():
            return meta["text"].strip()
        text_path = meta.get("text_path")
        if isinstance(text_path, str):
            path = data_dir / text_path
            if path.exists():
                return path.read_text(encoding="utf-8").strip()
        return ""

    if ev_type == "audio.segment":
        audio_path = meta.get("audio_path")
        if not isinstance(audio_path, str):
            return ""
        return _resolve_audio_text(event, data_dir / audio_path)

    if ev_type == "screen.frame":
        frame_path = meta.get("frame_path")
        if not isinstance(frame_path, str):
            return ""
        return _resolve_frame_text(event, data_dir / frame_path)

    return ""


def _resolve_audio_text(event: dict, audio_path: Path) -> str:
    if not audio_path.exists():
        log.warning("Audio file missing: %s", audio_path)
        return ""

    db_path = _state_db_path()
    if db_path is None:
        return ""

    content_hash = sha256_file(audio_path)
    artifact_key = f"derived:audio:{event.get('id')}"
    cached = _read_cached_derived(db_path, artifact_key, content_hash)
    if cached is not None:
        return cached

    transcriber = get_transcriber()
    text = transcriber.transcribe(audio_path, mime_type=event.get("meta", {}).get("content_type"))
    if not text.strip():
        return ""

    derived_path = _write_derived(event, text)
    state_db.set_artifact(db_path, artifact_key, "derived_audio", str(derived_path), content_hash)
    return text.strip()


def _resolve_frame_text(event: dict, frame_path: Path) -> str:
    if not frame_path.exists():
        log.warning("Frame file missing: %s", frame_path)
        return ""

    db_path = _state_db_path()
    if db_path is None:
        return ""

    content_hash = sha256_file(frame_path)
    artifact_key = f"derived:frame:{event.get('id')}"
    cached = _read_cached_derived(db_path, artifact_key, content_hash)
    if cached is not None:
        return cached

    ocr_engine = get_ocr_engine()
    text = ocr_engine.extract_text(frame_path)
    if not text.strip():
        return ""

    derived_path = _write_derived(event, text)
    state_db.set_artifact(db_path, artifact_key, "derived_frame", str(derived_path), content_hash)
    return text.strip()


def _write_derived(event: dict, text: str) -> Path:
    data_dir = settings.data_dir()
    day = (event.get("ts") or "")[:10] or "unknown"
    out_dir = data_dir / "derived" / day
    out_dir.mkdir(parents=True, exist_ok=True)
    event_id = event.get("id") or "unknown"
    path = out_dir / f"{event_id}.md"
    path.write_text(text.strip(), encoding="utf-8")
    return path


def _read_cached_derived(db_path: Path, artifact_key: str, content_hash: str) -> str | None:
    rec = state_db.get_artifact(db_path, artifact_key)
    if not rec or rec.get("content_sha") != content_hash:
        return None
    target = rec.get("target_path")
    if not target:
        return None
    path = Path(target)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def _state_db_path() -> Path | None:
    vault_dir = settings.vault_dir()
    try:
        return state_db.init_db(vault_dir)
    except Exception as exc:
        log.warning("Failed to init state DB: %s", exc)
        return None
