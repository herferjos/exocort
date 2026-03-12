"""Path helpers for vault notes (Daily, Concepts, Questions)."""
from pathlib import Path

from ..util import slugify


def daily_note_path(vault_dir: Path, day: str) -> Path:
    """vault/Daily/YYYY-MM-DD.md"""
    return vault_dir / "Daily" / f"{day}.md"


def concept_note_path(vault_dir: Path, concept_name: str) -> Path:
    """vault/Concepts/<slug>.md"""
    return vault_dir / "Concepts" / f"{slugify(concept_name)}.md"


def question_note_path(vault_dir: Path, concept_name: str) -> Path:
    """vault/Questions/<slug>.md"""
    return vault_dir / "Questions" / f"{slugify(concept_name)}.md"
