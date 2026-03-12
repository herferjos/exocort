from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StepConfig:
    step_id: str
    system_prompt: str | None
    user_prompt: str | None
    response_type: str
    response_path: str | None
    temperature: float | None
    max_tokens: int | None


@dataclass(frozen=True)
class StepOutputConfig:
    mode: str
    steps: list[str] | None
    separator: str
    label_format: str


def render_prompt(template: str | None, context: dict[str, str]) -> str:
    if not template:
        return ""
    rendered = template
    for key, value in context.items():
        rendered = rendered.replace(f"{{{key}}}", value)
    return rendered


def extract_json_path(payload: Any, path: str | None) -> Any:
    if not path:
        return payload
    current = payload
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def format_step_outputs(
    results: list[tuple[str, str]],
    config: StepOutputConfig | None,
) -> str:
    if not results:
        return ""

    if config is None or config.mode == "first":
        return results[0][1]

    include_steps = config.steps or [step_id for step_id, _ in results]
    lookup = {step_id: value for step_id, value in results}
    parts: list[str] = []
    for step_id in include_steps:
        if step_id not in lookup:
            continue
        value = lookup[step_id]
        parts.append(config.label_format.format(id=step_id, value=value))
    return config.separator.join(parts).strip()
