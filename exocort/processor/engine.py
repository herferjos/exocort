"""Vault processor: turn raw vault records into derived events and profile data."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


@dataclass
class ProcessorConfig:
    vault_dir: Path
    out_dir: Path
    state_path: Path
    batch_size: int
    poll_interval_s: float
    min_text_chars: int
    max_text_chars: int
    write_notes: bool
    dry_run: bool


@dataclass
class ProcessorState:
    last_path: str | None = None
    processed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_path": self.last_path,
            "processed": self.processed,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProcessorState":
        return cls(
            last_path=data.get("last_path") or None,
            processed=int(data.get("processed") or 0),
        )


_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "were",
    "have",
    "has",
    "you",
    "your",
    "about",
    "then",
    "they",
    "them",
    "their",
    "there",
    "what",
    "when",
    "where",
    "who",
    "why",
    "how",
    "que",
    "como",
    "para",
    "con",
    "por",
    "las",
    "los",
    "una",
    "uno",
    "unos",
    "unas",
    "del",
    "al",
    "en",
    "de",
    "la",
    "el",
    "y",
    "o",
    "es",
    "son",
    "ser",
    "esto",
    "esta",
    "este",
}


def run_watch(config: ProcessorConfig) -> None:
    while True:
        processed = run_once(config)
        if processed == 0:
            time.sleep(config.poll_interval_s)


def run_once(config: ProcessorConfig) -> int:
    config.out_dir.mkdir(parents=True, exist_ok=True)
    state = _load_state(config.state_path)
    profile = _load_profile(config.out_dir / "profile.json")

    new_files = list(_iter_new_vault_files(config.vault_dir, state.last_path))
    if config.batch_size > 0:
        new_files = new_files[: config.batch_size]

    processed = 0
    for path in new_files:
        record = _load_record(path)
        event = _build_event(record, path, config)
        if event is None:
            state.last_path = str(path)
            continue
        if not config.dry_run:
            _write_event(event, config)
        _update_profile(profile, event)
        state.last_path = str(path)
        state.processed += 1
        processed += 1

    if not config.dry_run:
        _save_profile(config.out_dir / "profile.json", profile)
        _save_state(config.state_path, state)
    return processed


_DATE_DIR_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _iter_new_vault_files(vault_dir: Path, last_path: str | None) -> Iterable[Path]:
    if not vault_dir.exists():
        return []
    date_dirs = [d for d in vault_dir.iterdir() if d.is_dir() and _DATE_DIR_RE.fullmatch(d.name)]
    for date_dir in sorted(date_dirs, key=lambda p: p.name):
        for path in sorted(date_dir.glob("*.json")):
            resolved = path.resolve()
            if last_path and str(resolved) <= last_path:
                continue
            yield resolved


def _load_record(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_event(record: dict[str, Any], path: Path, config: ProcessorConfig) -> dict[str, Any] | None:
    timestamp = str(record.get("timestamp") or "")
    type_ = str(record.get("type") or "unknown")
    record_id = str(record.get("id") or "")
    meta_raw = record.get("meta") or {}
    meta = _parse_meta(meta_raw)

    text = _extract_text(record.get("responses") or [])
    if config.max_text_chars > 0 and len(text) > config.max_text_chars:
        text = text[: config.max_text_chars]

    if len(text.strip()) < config.min_text_chars:
        return None

    summary = _summarize(text, meta, type_)
    signals = _extract_signals(text)
    topics = _extract_topics(text)

    safe_ts = timestamp.replace(":", "-")
    event_id = f"{safe_ts}_{type_}_{record_id}" if record_id else f"{safe_ts}_{type_}"
    date = timestamp[:10] if len(timestamp) >= 10 else datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return {
        "event_id": event_id,
        "timestamp": timestamp,
        "date": date,
        "type": type_,
        "record_id": record_id,
        "app": meta.get("app"),
        "window": meta.get("window"),
        "capture": meta.get("capture"),
        "permissions": meta.get("permissions"),
        "meta": _trim_meta(meta),
        "text": text,
        "summary": summary,
        "topics": topics,
        "signals": signals,
        "source": {
            "path": str(path),
            "responses": len(record.get("responses") or []),
        },
    }


def _parse_meta(meta: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = dict(meta)
    for key in ("app", "capture", "permissions", "window"):
        val = out.get(key)
        if isinstance(val, str) and val.strip().startswith("{"):
            try:
                out[key] = json.loads(val)
            except json.JSONDecodeError:
                out[key] = val
    return out


def _trim_meta(meta: dict[str, Any]) -> dict[str, Any]:
    trimmed: dict[str, Any] = {}
    for key in ("screen_id", "segment_id", "width", "height", "hash", "sample_rate", "duration_ms", "rms"):
        if key in meta:
            trimmed[key] = meta[key]
    return trimmed


def _extract_text(responses: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for resp in responses:
        raw = resp.get("text") or resp.get("raw") or ""
        if not isinstance(raw, str):
            continue
        part = _extract_text_fragment(raw)
        if part:
            parts.append(part)
    return "\n\n".join(parts).strip()


def _extract_text_fragment(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    if text.startswith("{") or text.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return text
        extracted = _extract_text_from_data(data)
        if extracted:
            return extracted.strip()
        return text
    return text


def _extract_text_from_data(data: Any) -> str | None:
    if isinstance(data, dict):
        if isinstance(data.get("text"), str):
            return data["text"]
        if isinstance(data.get("output_text"), str):
            return data["output_text"]
        if isinstance(data.get("content"), str):
            return data["content"]
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message")
                if isinstance(msg, dict):
                    content = msg.get("content")
                    if isinstance(content, str):
                        return content
                delta = first.get("delta")
                if isinstance(delta, dict) and isinstance(delta.get("content"), str):
                    return delta["content"]
        return None
    if isinstance(data, list):
        parts: list[str] = []
        for item in data:
            extracted = _extract_text_from_data(item)
            if extracted:
                parts.append(extracted)
        if parts:
            return " ".join(parts)
    return None


_URL_RE = re.compile(r"https?://[^\s)\]]+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PATH_RE = re.compile(r"(?:~?/)?[\w\-./]+\.(?:py|md|json|toml|yaml|yml|js|ts|tsx|go|rs|java|cpp|c|h|rb|php|sh)")


def _extract_signals(text: str) -> dict[str, list[str]]:
    urls = _uniq(_URL_RE.findall(text))
    emails = _uniq(_EMAIL_RE.findall(text))
    paths = _uniq(_PATH_RE.findall(text))
    return {
        "urls": urls,
        "emails": emails,
        "paths": paths,
    }


def _extract_topics(text: str, max_items: int = 12) -> list[str]:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9_\-]{2,}", text.lower())
    counts: dict[str, int] = {}
    for w in words:
        if w in _STOPWORDS or len(w) < 4:
            continue
        counts[w] = counts.get(w, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:max_items]]


def _summarize(text: str, meta: dict[str, Any], type_: str) -> str:
    app_name = None
    app = meta.get("app")
    if isinstance(app, dict):
        app_name = app.get("name")
    prefix = "audio" if type_ == "audio" else "screen"
    if app_name:
        prefix = f"{prefix} ({app_name})"
    snippet = text.strip().splitlines()[0] if text.strip() else ""
    if len(snippet) > 180:
        snippet = snippet[:180].rstrip() + "..."
    return f"{prefix}: {snippet}" if snippet else prefix


def _write_event(event: dict[str, Any], config: ProcessorConfig) -> None:
    date = event.get("date") or "unknown"
    event_id = event["event_id"]

    events_dir = config.out_dir / "events" / date
    events_dir.mkdir(parents=True, exist_ok=True)
    event_path = events_dir / f"{event_id}.json"
    event_path.write_text(json.dumps(event, ensure_ascii=False, indent=2), encoding="utf-8")

    if config.write_notes:
        notes_dir = config.out_dir / "notes" / date
        notes_dir.mkdir(parents=True, exist_ok=True)
        note_path = notes_dir / f"{event_id}.md"
        note_path.write_text(_render_note(event), encoding="utf-8")


def _render_note(event: dict[str, Any]) -> str:
    topics = event.get("topics") or []
    signals = event.get("signals") or {}
    app = event.get("app") or {}
    app_name = app.get("name") if isinstance(app, dict) else None
    links = []
    if app_name:
        links.append(f"[[app:{app_name}]]")
    for topic in topics:
        links.append(f"[[topic:{topic}]]")

    text = event.get("text") or ""
    if len(text) > 1200:
        text = text[:1200].rstrip() + "..."

    lines = [
        "---",
        f"id: {event.get('event_id')}",
        f"timestamp: {event.get('timestamp')}",
        f"type: {event.get('type')}",
        f"app: {app_name or ''}",
        f"source: {event.get('source', {}).get('path', '')}",
        "---",
        "",
        f"Summary: {event.get('summary')}",
        "",
        "Links:",
        " ".join(links) if links else "(none)",
        "",
        "Topics:",
        ", ".join(topics) if topics else "(none)",
        "",
        "Signals:",
        f"urls: {', '.join(signals.get('urls') or []) or '(none)'}",
        f"emails: {', '.join(signals.get('emails') or []) or '(none)'}",
        f"paths: {', '.join(signals.get('paths') or []) or '(none)'}",
        "",
        "Text:",
        text,
        "",
    ]
    return "\n".join(lines)


def _update_profile(profile: dict[str, Any], event: dict[str, Any]) -> None:
    _bump(profile.setdefault("types", {}), event.get("type"))
    app = event.get("app") or {}
    if isinstance(app, dict):
        _bump(profile.setdefault("apps", {}), app.get("name"))
    for topic in event.get("topics") or []:
        _bump(profile.setdefault("topics", {}), topic)
    for path in (event.get("signals") or {}).get("paths") or []:
        _bump(profile.setdefault("paths", {}), path)
    for url in (event.get("signals") or {}).get("urls") or []:
        _bump(profile.setdefault("urls", {}), url)


def _bump(counter: dict[str, int], key: str | None) -> None:
    if not key:
        return
    counter[key] = int(counter.get(key) or 0) + 1


def _load_profile(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "types": {},
            "apps": {},
            "topics": {},
            "paths": {},
            "urls": {},
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {
            "types": {},
            "apps": {},
            "topics": {},
            "paths": {},
            "urls": {},
        }


def _save_profile(path: Path, profile: dict[str, Any]) -> None:
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_state(path: Path) -> ProcessorState:
    if not path.exists():
        return ProcessorState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ProcessorState()
    return ProcessorState.from_dict(data)


def _save_state(path: Path, state: ProcessorState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _uniq(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out

