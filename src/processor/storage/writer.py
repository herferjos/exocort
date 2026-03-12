"""Idempotent file writer for vault notes."""
import logging
from pathlib import Path

from ..util import sha256_text

log = logging.getLogger("processor.writer")


def content_sha(content: str) -> str:
    return sha256_text(content)


def write_idempotent(
    path: Path,
    content: str,
    existing_sha: str | None = None,
    overwrite: bool = False,
) -> str:
    """Write content atomically. Skip if content hash unchanged. Returns content_sha."""
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    sha = content_sha(content)

    if not overwrite and path.exists():
        if existing_sha and existing_sha == sha:
            return sha
        if content_sha(path.read_text(encoding="utf-8")) == sha:
            return sha

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.rename(path)
    return sha
