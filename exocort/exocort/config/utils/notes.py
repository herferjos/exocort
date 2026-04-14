from __future__ import annotations

from pathlib import Path

from ..models.notes import NotesSettings
from .common import as_mapping, resolve_path


def parse_notes_settings(data: object, config_dir: Path) -> NotesSettings:
    mapping = as_mapping(data, "processor.notes")
    max_concurrent_batch = mapping.get("max_concurrent_batch", mapping.get("max_cocurrent_batch", 4))
    return NotesSettings(
        enabled=bool(mapping.get("enabled", False)),
        interval_seconds=int(mapping.get("interval_seconds", 60)),
        max_input_tokens=int(mapping.get("max_input_tokens", 10_000)),
        max_concurrent_batch=int(max_concurrent_batch),
        vault_dir=resolve_path(mapping.get("vault_dir", "captures/vault"), config_dir),
        state_dir=resolve_path(mapping.get("state_dir", "captures/processed/notes"), config_dir),
        provider=str(mapping.get("provider", "")),
        model=str(mapping.get("model", "")),
        api_base=str(mapping.get("api_base", "")),
        api_key_env=str(mapping.get("api_key_env", "test_key")),
        timeout_s=float(mapping.get("timeout_s", 30.0)),
        retries=int(mapping.get("retries", 2)),
        temperature=float(mapping.get("temperature", 0.0)),
        max_tool_iterations=int(mapping.get("max_tool_iterations", 8)),
        language=str(mapping.get("language", "English")),
        prompt=str(mapping.get("prompt", mapping.get("system_prompt", "")) or ""),
    )
