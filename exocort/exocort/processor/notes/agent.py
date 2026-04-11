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
Open Questions is useful and should capture missing understanding, contradictions, and gaps worth exploring.
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
                "- Prefer one strong note per subject over many tiny notes.\n"
                "- Never write a timeline note for this task.\n\n"
                "Important note-writing rules:\n"
                "- The output should feel like a personal wiki or second brain, not a summary of what was read in this batch.\n"
                "- Distill useful knowledge and conclusions. Do not just rewrite the captures in one big block.\n"
                "- Write about the subject directly, not about having seen or captured the subject.\n"
                "- Avoid phrases like 'the capture says', 'observed in the batch', 'seen in the screenshot', or 'this post mentions'.\n"
                "- If repeated evidence helps you understand a person, company, team, or project better, store that understanding in the relevant note.\n"
                "- Prefer building a useful profile of the entity or topic instead of accumulating isolated scraps.\n"
                "- Do not keep details just because they appeared; keep them when they help characterize the entity, topic, or working context.\n"
                "- Inferences are welcome when useful, but they must be framed as inferences or working conclusions, not as hard facts.\n"
                "- Split different topics into different notes when appropriate.\n"
                "- Avoid sections like Sources, References, and Recent Updates.\n"
                "- Include an interesting link when it is genuinely useful, but place it near the relevant idea instead of in a generic dump section.\n"
                "- Attribute opinions, rankings, forecasts, and non-settled claims to the person, company, or source that made them.\n"
                "- Open Questions is allowed when it captures real gaps or uncertainties.\n"
                "- For project notes such as exocort_project, write what the project appears to be, how it works, and what matters about it, not just a list of observed files or logs.\n\n"
                "The items are already ordered by proximity so nearby items may be related, but time itself is not important.\n"
                "First identify the durable topics/entities present in the batch, then update the right notes.\n"
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
