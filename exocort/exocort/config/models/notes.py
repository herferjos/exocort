from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

@dataclass(slots=True, frozen=True)
class NotesSettings:
    enabled: bool = False
    interval_seconds: int = 60
    max_input_tokens: int = 10_000
    max_concurrent_batch: int = 4
    vault_dir: Path = field(default_factory=lambda: Path("captures") / "vault")
    state_dir: Path = field(default_factory=lambda: Path("captures") / "processed" / "notes")
    provider: str = ""
    model: str = ""
    api_base: str = ""
    api_key_env: str = "test_key"
    timeout_s: float = 30.0
    retries: int = 2
    temperature: float = 0.0
    max_tool_iterations: int = 8
    language: str = "English"
    prompt: str = ""
