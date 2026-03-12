"""Event normalization and helpers."""
import hashlib
import json
from pathlib import Path


def event_id(ev: dict, line: str | None = None) -> str:
    """Unique ID for event: use id field or sha256 of line."""
    aid = ev.get("id")
    if aid and isinstance(aid, str) and aid.strip():
        return aid.strip()
    if line:
        return hashlib.sha256(line.encode("utf-8")).hexdigest()
    return hashlib.sha256(json.dumps(ev, sort_keys=True).encode("utf-8")).hexdigest()


def event_ts(ev: dict) -> str | None:
    """Extract ISO timestamp."""
    ts = ev.get("ts")
    if ts and isinstance(ts, str):
        return ts.strip()
    return None


def event_day(ts: str | None, filename: str | None = None) -> str | None:
    """Derive day (YYYY-MM-DD) from ts or filename."""
    if ts and len(ts) >= 10:
        return ts[:10]
    if filename:
        stem = Path(filename).stem
        if stem and len(stem) == 10 and stem[4] == "-" and stem[7] == "-":
            return stem
    return None


def event_type(ev: dict) -> str:
    """Event type string."""
    t = ev.get("type")
    return t if isinstance(t, str) and t.strip() else "unknown"


def event_source(ev: dict) -> str:
    """Event source string."""
    s = ev.get("source")
    return s if isinstance(s, str) and s.strip() else "unknown"


def event_url(ev: dict) -> str | None:
    """Extract URL from browser event meta."""
    meta = ev.get("meta")
    if not isinstance(meta, dict):
        return None
    url = meta.get("url")
    return url if isinstance(url, str) and url.strip() else None


def normalize_event(ev: dict, line: str | None, filepath: str) -> dict:
    """Produce normalized flat record for DB."""
    ts = event_ts(ev)
    day = event_day(ts, filepath)
    return {
        "event_id": event_id(ev, line),
        "ts": ts or "",
        "day": day or "",
        "type": event_type(ev),
        "source": event_source(ev),
        "url": event_url(ev) or "",
        "payload_json": json.dumps(ev, ensure_ascii=False),
    }


def get_events_by_id(all_events: list[dict], event_ids: list[str]) -> list[dict]:
    """Filter a list of events to find those matching the given IDs."""
    id_set = set(event_ids)
    return [ev for ev in all_events if ev.get("id") in id_set]
