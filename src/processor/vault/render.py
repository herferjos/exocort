"""Render daily notes and concept (page) notes with LLM."""
import logging

from ..domain.models import MarkdownContent
from ai.llm import get_client
from ai.llm.config import get_processor_prompt

log = logging.getLogger("processor.render")


def build_compact_timeline(events: list[dict]) -> str:
    """Compact timeline string from events."""
    lines = []
    for ev in events:
        ts = ev.get("ts", "")[:19]
        typ = ev.get("type", "")
        src = ev.get("source", "")
        if typ == "browser.page_view":
            meta = ev.get("meta") or {}
            lines.append(f"- {ts} [page_view] {meta.get('title', '?')} | {meta.get('url', '')}")
        elif typ == "browser.page_text":
            meta = ev.get("meta") or {}
            lines.append(f"- {ts} [page_text] {meta.get('title', '?')} ({meta.get('text_len', 0)} chars)")
        elif typ == "audio.segment":
            meta = ev.get("meta") or {}
            txt = (meta.get("transcript_text") or "")[:200]
            lines.append(f"- {ts} [audio] {txt}..." if txt else f"- {ts} [audio]")
        else:
            lines.append(f"- {ts} [{typ}] {src}")
    return "\n".join(lines) if lines else "(no events)"


def extract_page_refs(events: list[dict]) -> list[tuple[str, str]]:
    """(url, title) from page_text events for daily note links."""
    seen = set()
    out = []
    for ev in events:
        if ev.get("type") != "browser.page_text":
            continue
        meta = ev.get("meta") or {}
        url = meta.get("url") or ""
        title = meta.get("title") or url or "?"
        if url and url not in seen:
            seen.add(url)
            out.append((url, title))
    return out


def extract_audio_snippets(events: list[dict]) -> list[dict]:
    """Audio segment info for daily note."""
    return [
        {"ts": ev.get("ts"), "text": (ev.get("meta") or {}).get("transcript_text") or "", "event_id": ev.get("id")}
        for ev in events
        if ev.get("type") == "audio.segment"
    ]


def render_daily_note(day: str, events: list[dict], llm_client) -> str:
    """Generate daily note markdown."""
    timeline = build_compact_timeline(events)
    page_refs = extract_page_refs(events)
    audio_snippets = extract_audio_snippets(events)

    user = f"""DAY: {day}
EVENTS:
{timeline}

Write: 5–10 bullet summary, 3 priorities/follow-ups, notable links as [[Page notes]]."""

    try:
        system = get_processor_prompt("daily_render", "system")
        out = llm_client.generate(system, user, MarkdownContent)
        summary_md = out.content
    except Exception as e:
        log.warning("LLM summary failed for %s: %s", day, e)
        summary_md = "*(Summary generation failed)*"

    parts = [
        "---", f"date: {day}", f"events: {len(events)}", "---", "",
        "## Summary", "", summary_md, "",
        "## Timeline", "", timeline, "",
        "## Pages", "",
    ]
    for url, title in page_refs:
        parts.append(f"- [[{title}]]")
    parts.extend(["", "## Captured audio", ""])
    for snip in audio_snippets:
        if (snip.get("text") or "").strip():
            parts.append(f"- {snip['text'].strip()}")
    parts.append("")
    return "\n".join(parts)


def render_page_note(
    text: str,
    llm_client,
    existing_concept_titles: list[str],
    existing_note_content: str | None,
) -> str:
    """Generate or merge concept note markdown."""
    concept_list = "\n- ".join(existing_concept_titles)

    if existing_note_content:
        user_prompt = f"""
Merge the new information into the existing note.

EXISTING NOTE:
---
{existing_note_content}
---

NEW CONTENT:
---
{text}
---

EXISTING CONCEPT NOTES:
- {concept_list}

1. Integrate new info into the note (rewrite sections, add bullets). Keep one coherent document. Preserve H1 if present.
2. Update "Related" with [[links]] ONLY from EXISTING CONCEPT NOTES above.
3. Update "Tags".
4. Output the full Markdown note.
"""
    else:
        user_prompt = f"""
Create a well-structured note from this content.

CONTENT:
---
{text}
---

EXISTING CONCEPT NOTES:
- {concept_list}

1. H1 title.
2. Short summary (2–4 bullets).
3. Key points as bullets.
4. "Related" section: 3–7 [[WikiLinks]] ONLY from EXISTING CONCEPT NOTES above.
5. "Tags" section: 5–12 tags (#example).
"""

    try:
        system = get_processor_prompt("page_render", "system")
        out = llm_client.generate(system, user_prompt, MarkdownContent)
        return out.content
    except Exception as e:
        log.warning("LLM concept note failed: %s", e)
        return "# Concept Note\n\n*(Generation failed)*"
