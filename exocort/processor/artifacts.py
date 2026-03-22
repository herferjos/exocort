"""Artifact rendering and path helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .models import ArtifactEnvelope
from .utils import normalize_list, safe_id, slugify, utc_date, utc_iso


def note_path(out_dir: Path, envelope: ArtifactEnvelope | dict[str, Any]) -> Path:
    payload = envelope.payload if isinstance(envelope, ArtifactEnvelope) else envelope
    date = str(payload.get("date") or utc_date())
    note_id = str(payload.get("note_id") or slugify(str(payload.get("title") or "note")))
    return out_dir / "notes" / "inbox" / date / f"{note_id}.md"


def render_note(envelope: ArtifactEnvelope | dict[str, Any]) -> str:
    payload = envelope.payload if isinstance(envelope, ArtifactEnvelope) else envelope
    source_event_ids = [str(item).strip() for item in normalize_list(payload.get("source_event_ids")) if str(item).strip()]
    lines = [
        "---",
        "kind: inbox_note",
        f"note_id: {safe_id(str(payload.get('note_id') or 'note'))}",
        f"timestamp: {payload.get('timestamp') or ''}",
        f"date: {payload.get('date') or ''}",
        f"title: {payload.get('title') or ''}",
        f"description: {payload.get('description') or ''}",
        f"category: {payload.get('category') or ''}",
        f"subject: {payload.get('subject') or ''}",
        f"super_event_id: {payload.get('super_event_id') or ''}",
        "source_event_ids:",
    ]
    if source_event_ids:
        lines.extend([f"  - {item}" for item in source_event_ids])
    else:
        lines.append("  -")
    lines.extend(
        [
            f"updated_at: {utc_iso()}",
            "---",
            "",
            f"# {payload.get('title') or 'Untitled note'}",
            "",
            payload.get("description") or "",
            "",
            "## Content",
            payload.get("content") or "",
            "",
            "## Traceability",
            f"- Super event: `{payload.get('super_event_id') or ''}`",
            *([f"- Source event: `{item}`" for item in source_event_ids] or ["- Source event: `(none)`"]),
            "",
        ]
    )
    return "\n".join(lines)
