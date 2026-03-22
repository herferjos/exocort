"""Pure utility helpers for the processor."""

from __future__ import annotations

import copy
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_iso() -> str:
    return utc_now().isoformat()


def utc_date() -> str:
    return utc_now().strftime("%Y-%m-%d")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.debug("Ensured parent directory: path=%s parent=%s", path, path.parent)


def safe_id(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", value.strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._-")
    return cleaned or "item"


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "item"


def date_from_timestamp(timestamp: str | None) -> str:
    if timestamp and len(timestamp) >= 10:
        return timestamp[:10]
    return utc_date()


def normalize_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def iter_json_files_recursive(root: Path) -> list[Path]:
    if not root.exists():
        logger.debug("Collection root missing: root=%s", root)
        return []
    paths = [path for path in root.rglob("*.json") if path.name != "state.json"]
    paths.sort(key=lambda path: str(path))
    logger.debug("Enumerated json files recursively: root=%s count=%s", root, len(paths))
    return paths


def iter_json_files_flat(root: Path) -> list[Path]:
    if not root.exists():
        logger.debug("Collection root missing: root=%s", root)
        return []
    paths = [path for path in root.glob("*.json") if path.name != "state.json"]
    paths.sort(key=lambda path: str(path))
    logger.debug("Enumerated json files flat: root=%s count=%s", root, len(paths))
    return paths


def load_json(path: Path) -> dict[str, Any]:
    logger.debug("Loading json file: path=%s", path)
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_text(path: Path, text: str) -> None:
    ensure_parent(path)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    logger.debug("Wrote text atomically: path=%s bytes=%s", path, len(text.encode("utf-8")))


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))
    logger.debug("Wrote json atomically: path=%s keys=%s", path, sorted(payload.keys()))


def parse_meta(meta: Any) -> dict[str, Any]:
    if not isinstance(meta, dict):
        return {}
    out = copy.deepcopy(meta)
    for key in ("app", "capturer", "permissions", "window"):
        value = out.get(key)
        if isinstance(value, str) and value.strip().startswith("{"):
            try:
                out[key] = json.loads(value)
            except json.JSONDecodeError:
                pass
    logger.debug("Parsed meta payload: keys=%s", sorted(out.keys()))
    return out


def extract_text_from_data(data: Any) -> str | None:
    if isinstance(data, dict):
        for key in (
            "markdown",
            "text",
            "output_text",
            "content",
            "parsed_text",
            "body",
        ):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                message = first.get("message")
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str) and content.strip():
                        return content
        return None
    if isinstance(data, list):
        parts = [
            piece for piece in (extract_text_from_data(item) for item in data) if piece
        ]
        if parts:
            return "\n".join(parts)
    return None


def extract_text_fragment(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    if text.startswith("{") or text.startswith("["):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return text
        extracted = extract_text_from_data(data)
        if extracted:
            return extracted.strip()
    return text


def extract_record_text(record: dict[str, Any]) -> str:
    parts: list[str] = []
    for response in record.get("responses") or []:
        if not isinstance(response, dict):
            continue
        for candidate in (
            response.get("parsed_text"),
            response.get("text"),
            response.get("raw"),
            response.get("body"),
        ):
            if not isinstance(candidate, str):
                continue
            piece = extract_text_fragment(candidate)
            if piece:
                parts.append(piece)
                break
    text = "\n\n".join(parts).strip()
    logger.debug(
        "Extracted record text: responses=%s chars=%s",
        len(record.get("responses") or []),
        len(text),
    )
    return text


def canonical_path(path: Path | str) -> str:
    return str(Path(path).resolve())


def pending_paths(paths: list[Path], last_path: str | None) -> list[Path]:
    if not last_path:
        logger.debug("No cursor path set; all paths pending: count=%s", len(paths))
        return paths
    canonical = [canonical_path(path) for path in paths]
    try:
        index = canonical.index(canonical_path(last_path))
    except ValueError:
        logger.debug("Cursor path not found; returning all paths pending: cursor=%s count=%s", last_path, len(paths))
        return paths
    pending = paths[index + 1 :]
    logger.debug(
        "Resolved pending paths: cursor=%s total=%s pending=%s",
        last_path,
        len(paths),
        len(pending),
    )
    return pending
