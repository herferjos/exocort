from __future__ import annotations

import json
import uuid
from typing import Any

from exocort.config import NotesSettings
from exocort.bridge import ProviderBridge, ProviderConfig, ResponseRequest

from .models import BatchCandidate, BatchRunResult, ToolCallResult
from .tools import build_tool_handlers, parse_tool_arguments, tool_specs


DEFAULT_SYSTEM_PROMPT = """You are the Exocort notes agent.
Your job is to turn OCR and ASR captures into a durable personal wiki inside a markdown vault.
Always reply in {{language}}.
Work only inside the vault using the available tools.
Prefer updating existing notes over duplicating information.
Use wiki-style links [[...]] when appropriate.
Do not invent facts that do not appear in the captures.
Do not create or update timeline, diary, session-log, or dump-style notes unless the user explicitly asked for chronology.
Do not add disclaimers such as "I did not invent..." or "this is only a transcription".
Do not say "This was captured by OCR" or similar OCR-source disclaimers.
Ignore UI chrome, repeated buttons, ads, navigation labels, timestamps, and OCR garbage unless they matter to the knowledge itself.
Build a second-brain knowledge base, not a batch summary.
Write from the perspective of the topic itself, not from the ingestion process.
Do not say "this capture says", "the capture shows", "observed in the batch", "seen in the screenshot", or similar meta phrases unless provenance is itself the point.
Prefer thematic notes that accumulate knowledge over time.
Group related information into stable subject notes instead of creating one note per capture.
Choose note paths from the subject itself, not from time, source app, or batch identity.
Extract durable knowledge such as definitions, claims, comparisons, takeaways, workflows, and project conclusions.
Accumulate knowledge about recurring entities such as people, companies, teams, products, and projects when the captures support it.
It is useful to preserve working understanding about how a person thinks, what a company appears to prioritize, how a team operates, or how a project is evolving.
Prefer building coherent profiles and entity notes over passively accumulating disconnected facts.
When possible, create profiles for people, entities, or any recurring subject if the information allows it.
Only keep details that improve future understanding, decision-making, collaboration, or retrieval.
When you infer something, make it proportionate to the evidence and present it as an inference, pattern, or working conclusion rather than a certain fact.
Do not dump raw logs, copied feed text, or long capture-by-capture retellings when a distilled note would do.
If the batch contains several distinct concepts, split them into separate notes when that improves retrieval and reuse.
Create notes for the concept itself when possible, for example ocr.md, agent_skills.md, exocort_project.md.
Within a note, merge new information into the right section instead of appending a new batch-shaped block.
Do not create sections named Sources, References, or Recent Updates.
Interesting links may be included when they are genuinely useful for future retrieval, verification, or action.
Prefer embedding those links near the relevant point instead of dumping them in a generic link list.
If a statement is an opinion, interpretation, ranking, forecast, marketing claim, or otherwise attributable judgment rather than a clear fact, attribute it to the person, company, or source it belongs to.
Keep that attribution inside the note so future readers can tell whose view it is.
When the origin of information adds useful context, mention it inline near the relevant point, for example that it came from a profile, a conversation, a meeting, or another identifiable context.
Open Questions is useful only for concrete gaps in understanding that block a clean interpretation of the material.
Use it when the captures rely on unstated context, insider assumptions, references the user may understand but the agent does not, or ambiguous pronouns/entities/processes that remain unclear.
Do not use Open Questions as a generic backlog of things that might be nice to research, enrich, verify, or expand later.
If the note is already understandable without such gaps, omit the Open Questions section entirely.
Each note should be concise, structured, and cumulative. Prefer sections like:
- # Title
- ## Summary
- ## Key Points
- ## Details
- ## Open Questions
Notes should read like synthesized knowledge, not evidence logs.
Short quotes or concrete examples are allowed only when they preserve useful meaning.
When a note exists already, read it first and then replace_note with a merged version instead of blindly appending more raw text.
When a note needs to be created, use create_note. Avoid append_note unless a very small surgical addition is clearly better than rewriting the note.
Choose stable, lowercase snake_case filenames that describe the subject.
Reply briefly when done, summarizing what you've updated."""

WRITE_TOOL_NAMES = {"create_note", "replace_note", "append_note"}

def run_notes_agent(notes: NotesSettings, batch: BatchCandidate) -> BatchRunResult:
    handlers = build_tool_handlers(notes.vault_dir)
    initial_list_result = handlers["list_notes"]({})
    system_prompt = (notes.prompt.strip() or DEFAULT_SYSTEM_PROMPT).replace(
        "{{language}}",
        notes.language.strip() or "English",
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                "Process this capture batch. The items are ordered by proximity, not by time.\n\n"
                f"Capture batch:\n{batch.input_text}\n"
            ),
        },
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "list_notes",
                    "type": "function",
                    "function": {
                        "name": "list_notes",
                        "arguments": json.dumps({}),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "list_notes",
            "name": "list_notes",
            "content": initial_list_result.summary,
        },
    ]
    results: list[ToolCallResult] = []
    had_write_tool = False
    bridge = ProviderBridge(
        ProviderConfig(
            provider=notes.provider,
            api_base=notes.api_base,
            api_key_env=notes.api_key_env,
            timeout_s=notes.timeout_s,
            retries=notes.retries,
        )
    )

    for _ in range(notes.max_tool_iterations):
        response = bridge.response(
            ResponseRequest(
                model=notes.model,
                messages=tuple(messages),
                tools=tuple(tool_specs()),
                tool_choice="auto",
                temperature=notes.temperature,
            )
        )
        assistant_message = response.message
        messages.append(assistant_message)

        tool_calls = assistant_message.get("tool_calls") or []
        if not tool_calls:
            if not had_write_tool:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "You have not updated the vault yet. "
                            "Before finishing, you must call at least one write tool: "
                            "create_note, replace_note, or append_note."
                        ),
                    }
                )
                continue
            return BatchRunResult(
                assistant_message=_assistant_text(assistant_message),
                tool_results=tuple(results),
            )

        for tool_call in tool_calls:
            function_call = tool_call.get("function") or {}
            tool_name = str(function_call.get("name", "")).strip()
            tool_call_id = str(tool_call.get("id") or uuid.uuid4().hex)
            if tool_name not in handlers:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": f"error: unsupported tool requested: {tool_name}",
                    }
                )
                continue
            raw_arguments = function_call.get("arguments", "{}")
            try:
                parsed_arguments = parse_tool_arguments(raw_arguments)
                result = handlers[tool_name](parsed_arguments)
            except Exception as exc:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": f"error: {exc}",
                    }
                )
                continue
            results.append(result)
            if tool_name in WRITE_TOOL_NAMES:
                had_write_tool = True
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
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


def _assistant_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n".join(parts).strip()
