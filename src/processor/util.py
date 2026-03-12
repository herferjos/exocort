import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def json_line(obj: dict) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def slugify(text: str, max_len: int = 64) -> str:
    """Produce a filesystem-safe slug from text."""
    s = text.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s)
    s = s.strip("-")[:max_len].strip("-")
    return s or "untitled"
