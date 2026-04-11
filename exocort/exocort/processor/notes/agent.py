from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from litellm import completion

from exocort.config import NotesSettings

from .models import BatchCandidate, BatchRunResult, ToolCallResult
from .tools import build_tool_handlers, parse_tool_arguments, tool_specs


SYSTEM_PROMPT = """You are the Exocort notes agent.
Your job is to turn OCR and ASR captures into a durable personal wiki inside a markdown vault.
Work only inside the vault using the available tools.
Prefer updating existing notes over duplicating information.
Use wiki-style links [[...]] when appropriate.
Do not invent facts that do not appear in the captures.
Do not create or update timeline, diary, session-log, or dump-style notes unless the user explicitly asked for chronology.
Do not add disclaimers such as "I did not invent..." or "this is only a transcription".
Ignore UI chrome, repeated buttons, ads, navigation labels, timestamps, and OCR garbage unless they matter to the knowledge itself.
Prefer thematic notes that accumulate knowledge over time.
Group related information into stable subject notes instead of creating one note per capture.
Choose note paths from the subject itself, not from time, source app, or batch identity.
Each note should be concise, structured, and cumulative. Prefer sections like:
- # Title
- ## Summary
- ## Knowledge
- ## Sources
- ## Open Questions
- ## Recent Updates
When a note exists already, read it first and then replace_note with a merged version instead of blindly appending more raw text.
When a note needs to be created, use create_note. Use append_note only for a short incremental section such as Recent Updates when the rest of the note stays intact.
Choose stable, lowercase snake_case filenames that describe the subject.
Reply briefly when done, summarizing what you've updated."""


def run_notes_agent(notes: NotesSettings, batch: BatchCandidate) -> BatchRunResult:
    api_key = os.getenv(notes.api_key_env, "test_key") if notes.api_key_env else "test_key"
    handlers = build_tool_handlers(notes.vault_dir)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Process this capture batch and update the vault as a thematic wiki.\n\n"
                "Objectives:\n"
                "- Create or update notes by durable subject, not by time.\n"
                "- Merge new knowledge into existing notes when the subject already exists.\n"
                "- Preserve useful source links that appear in the captures.\n"
                "- Prefer one strong note per subject over many tiny notes.\n"
                "- Never write a timeline note for this task.\n\n"
                "The items are already ordered by proximity so nearby items may be related, but time itself is not important.\n"
                "Extract durable knowledge, organize it, and merge it into the right notes.\n\n"
                f"Capture batch:\n{batch.input_text}\n"
            ),
        },
    ]
    results: list[ToolCallResult] = []

    for _ in range(notes.max_tool_iterations):
        response = completion(
            model=notes.model,
            messages=messages,
            tools=tool_specs(),
            tool_choice="auto",
            api_base=notes.api_base,
            api_key=api_key,
        )
        message = response.choices[0].message
        assistant_message = _message_to_dict(message)
        messages.append(assistant_message)

        tool_calls = assistant_message.get("tool_calls") or []
        if not tool_calls:
            content = assistant_message.get("content")
            return BatchRunResult(
                assistant_message=str(content or "").strip(),
                tool_results=tuple(results),
            )

        for tool_call in tool_calls:
            function_call = tool_call.get("function") or {}
            tool_name = str(function_call.get("name", "")).strip()
            if tool_name not in handlers:
                raise ValueError(f"unsupported tool requested: {tool_name}")
            raw_arguments = function_call.get("arguments", "{}")
            parsed_arguments = parse_tool_arguments(raw_arguments)
            result = handlers[tool_name](parsed_arguments)
            results.append(result)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": str(tool_call.get("id") or uuid.uuid4().hex),
                    "name": tool_name,
                    "content": result.summary,
                }
            )

    raise RuntimeError("notes agent reached max_tool_iterations without finishing")


def touched_note_paths(result: BatchRunResult) -> list[str]:
    seen: list[str] = []
    for tool_result in result.tool_results:
        if tool_result.note_path is None or tool_result.note_path in seen:
            continue
        seen.append(tool_result.note_path)
    return seen


def _message_to_dict(message: Any) -> dict[str, Any]:
    role = getattr(message, "role", None) or "assistant"
    content = getattr(message, "content", None)
    tool_calls = getattr(message, "tool_calls", None)
    normalized_tool_calls: list[dict[str, Any]] = []
    if tool_calls:
        for tool_call in tool_calls:
            function = getattr(tool_call, "function", None)
            normalized_tool_calls.append(
                {
                    "id": getattr(tool_call, "id", None),
                    "type": getattr(tool_call, "type", "function"),
                    "function": {
                        "name": getattr(function, "name", None),
                        "arguments": getattr(function, "arguments", "{}"),
                    },
                }
            )
    return {
        "role": role,
        "content": content,
        "tool_calls": normalized_tool_calls or None,
    }
