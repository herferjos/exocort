"""Sqlite-backed state for incremental ingestion and artifact tracking."""

import datetime
import json
import logging
import sqlite3
from pathlib import Path

from ..domain.events import normalize_event

log = logging.getLogger("processor.state_db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ingested_files (
    path TEXT PRIMARY KEY,
    mtime REAL,
    size INTEGER,
    last_line INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    ts TEXT,
    day TEXT,
    type TEXT,
    source TEXT,
    url TEXT,
    payload_json TEXT
);

CREATE TABLE IF NOT EXISTS pages (
    url TEXT PRIMARY KEY,
    canonical_url TEXT,
    title TEXT,
    last_seen_ts TEXT,
    content_sha TEXT
);

CREATE TABLE IF NOT EXISTS concepts (
    concept_name TEXT PRIMARY KEY,
    title TEXT,
    last_seen_ts TEXT,
    content_sha TEXT
);

CREATE TABLE IF NOT EXISTS artifacts (
    key TEXT PRIMARY KEY,
    kind TEXT,
    target_path TEXT,
    content_sha TEXT,
    updated_ts TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_day ON events(day);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_url ON events(url);
"""


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def init_db(vault_dir: Path) -> Path:
    """Ensure state DB exists; return its path."""
    state_dir = vault_dir / ".src"
    state_dir.mkdir(parents=True, exist_ok=True)
    db_path = state_dir / "state.sqlite"
    conn = _connect(db_path)
    conn.close()
    return db_path


def ingest_jsonl(
    db_path: Path,
    events_dir: Path,
    days: list[str],
    max_events: int | None = None,
) -> int:
    """
    Ingest new lines from JSONL files for given days.
    Returns number of events ingested.
    """
    conn = _connect(db_path)
    ingested = 0
    try:
        for day in days:
            path = events_dir / f"{day}.jsonl"
            if not path.exists():
                continue
            stat = path.stat()
            mtime = stat.st_mtime
            size = stat.st_size
            row = conn.execute(
                "SELECT last_line FROM ingested_files WHERE path = ?",
                (str(path.resolve()),),
            ).fetchone()
            start_line = row["last_line"] if row else 0

            with path.open("r", encoding="utf-8") as f:
                line_no = 0
                for line in f:
                    line_no += 1
                    if line_no <= start_line:
                        continue
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    rec = normalize_event(ev, line, path.name)
                    try:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO events
                            (event_id, ts, day, type, source, url, payload_json)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                rec["event_id"],
                                rec["ts"],
                                rec["day"],
                                rec["type"],
                                rec["source"],
                                rec["url"],
                                rec["payload_json"],
                            ),
                        )
                        ingested += 1
                        if max_events and ingested >= max_events:
                            conn.execute(
                                """
                                INSERT OR REPLACE INTO ingested_files
                                (path, mtime, size, last_line)
                                VALUES (?, ?, ?, ?)
                                """,
                                (str(path.resolve()), mtime, size, line_no),
                            )
                            conn.commit()
                            return ingested
                    except sqlite3.IntegrityError:
                        pass
                final_line = line_no
            conn.execute(
                """
                INSERT OR REPLACE INTO ingested_files
                (path, mtime, size, last_line)
                VALUES (?, ?, ?, ?)
                """,
                (str(path.resolve()), mtime, size, final_line),
            )
        conn.commit()
    finally:
        conn.close()
    return ingested


def get_events_by_day(db_path: Path, day: str) -> list[dict]:
    """Fetch all events for a day, ordered by ts."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT payload_json FROM events WHERE day = ? ORDER BY ts",
            (day,),
        ).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]
    finally:
        conn.close()


def get_page_text_events(db_path: Path, day: str | None = None) -> list[dict]:
    """Fetch browser.page_text events, optionally for a day."""
    conn = _connect(db_path)
    try:
        if day:
            rows = conn.execute(
                """
                SELECT payload_json FROM events
                WHERE type = 'browser.page_text' AND day = ?
                ORDER BY ts
                """,
                (day,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT payload_json FROM events
                WHERE type = 'browser.page_text'
                ORDER BY ts
                """,
            ).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]
    finally:
        conn.close()


def get_events_for_url(db_path: Path, url: str) -> list[dict]:
    """Fetch all events (any type) for a given URL."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT payload_json FROM events WHERE url = ? ORDER BY ts",
            (url,),
        ).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]
    finally:
        conn.close()


def get_audio_events(db_path: Path, day: str | None = None) -> list[dict]:
    """Fetch audio.segment events."""
    conn = _connect(db_path)
    try:
        if day:
            rows = conn.execute(
                """
                SELECT payload_json FROM events
                WHERE type = 'audio.segment' AND day = ?
                ORDER BY ts
                """,
                (day,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT payload_json FROM events
                WHERE type = 'audio.segment'
                ORDER BY ts
                """,
            ).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]
    finally:
        conn.close()


def upsert_page(
    db_path: Path, url: str, title: str | None, content_sha: str, ts: str
) -> None:
    """Update page metadata."""
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO pages (url, canonical_url, title, last_seen_ts, content_sha)
            VALUES (?, ?, ?, ?, ?)
            """,
            (url, url, title or "", ts, content_sha),
        )
        conn.commit()
    finally:
        conn.close()


def upsert_concept(
    db_path: Path, concept_name: str, title: str, content_sha: str, ts: str
) -> None:
    """Update concept metadata."""
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO concepts (concept_name, title, last_seen_ts, content_sha)
            VALUES (?, ?, ?, ?)
            """,
            (concept_name, title, ts, content_sha),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_concept_titles(db_path: Path) -> list[str]:
    """Fetch all concept titles."""
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT title FROM concepts ORDER BY title",
        ).fetchall()
        return [r["title"] for r in rows]
    finally:
        conn.close()


def get_artifact_sha(db_path: Path, key: str) -> str | None:
    """Get content_sha for artifact key."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT content_sha FROM artifacts WHERE key = ?",
            (key,),
        ).fetchone()
        return row["content_sha"] if row else None
    finally:
        conn.close()


def get_artifact(db_path: Path, key: str) -> dict | None:
    """Fetch artifact record by key."""
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT key, kind, target_path, content_sha FROM artifacts WHERE key = ?",
            (key,),
        ).fetchone()
        if not row:
            return None
        return {
            "key": row["key"],
            "kind": row["kind"],
            "target_path": row["target_path"],
            "content_sha": row["content_sha"],
        }
    finally:
        conn.close()


def set_artifact(
    db_path: Path, key: str, kind: str, target_path: str, content_sha: str
) -> None:
    """Record artifact with sha for idempotency."""
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO artifacts
            (key, kind, target_path, content_sha, updated_ts)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                key,
                kind,
                target_path,
                content_sha,
                datetime.datetime.utcnow().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
