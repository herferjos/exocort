from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .models import ToolCallResult
from . import vault


ToolHandler = Callable[[dict[str, Any]], ToolCallResult]


def tool_specs() -> list[dict[str, Any]]:
    return [
        _function_tool(
            "list_notes",
            "List markdown notes available inside the vault so you can reuse existing thematic notes.",
            {"type": "object", "properties": {}, "additionalProperties": False},
        ),
        _function_tool(
            "read_note",
            "Read one markdown note from the vault.",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        ),
        _function_tool(
            "create_note",
            "Create a new markdown note in the vault.",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        ),
        _function_tool(
            "replace_note",
            "Replace a markdown note in the vault.",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        ),
        _function_tool(
            "append_note",
            "Append content to a markdown note in the vault. Use sparingly, mainly for a short incremental update section.",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        ),
        _function_tool(
            "delete_note",
            "Delete a markdown note in the vault.",
            {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        ),
    ]


def build_tool_handlers(vault_dir: Path) -> dict[str, ToolHandler]:
    return {
        "list_notes": lambda _: ToolCallResult(
            tool_name="list_notes",
            summary=json.dumps({"paths": vault.list_notes(vault_dir)}, ensure_ascii=False),
        ),
        "read_note": lambda args: ToolCallResult(
            tool_name="read_note",
            summary=vault.read_note(vault_dir, str(args["path"])),
            note_path=str(args["path"]),
        ),
        "create_note": lambda args: _write_result(
            "create_note",
            vault.create_note(vault_dir, str(args["path"]), str(args["content"])),
            vault_dir,
        ),
        "replace_note": lambda args: _write_result(
            "replace_note",
            vault.replace_note(vault_dir, str(args["path"]), str(args["content"])),
            vault_dir,
        ),
        "append_note": lambda args: _write_result(
            "append_note",
            vault.append_note(vault_dir, str(args["path"]), str(args["content"])),
            vault_dir,
        ),
        "delete_note": lambda args: _write_result(
            "delete_note",
            vault.delete_note(vault_dir, str(args["path"])),
            vault_dir,
        ),
    }


def parse_tool_arguments(raw_arguments: object) -> dict[str, Any]:
    if isinstance(raw_arguments, str):
        payload = json.loads(raw_arguments or "{}")
    elif isinstance(raw_arguments, dict):
        payload = raw_arguments
    else:
        raise ValueError("tool arguments must be a JSON object")
    if not isinstance(payload, dict):
        raise ValueError("tool arguments must decode to an object")
    return payload


def _function_tool(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


def _write_result(tool_name: str, note_path: Path, vault_dir: Path) -> ToolCallResult:
    return ToolCallResult(
        tool_name=tool_name,
        summary=f"{tool_name} ok: {note_path.relative_to(vault_dir)}",
        note_path=str(note_path.relative_to(vault_dir)),
    )
