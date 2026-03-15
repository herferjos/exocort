"""Orchestrator: builds a task plan from events."""
import logging

from ..domain.models import Plan
from engine.llm.base import LLMClient
from engine.llm.config import get_processor_prompt

log = logging.getLogger("processor.orchestrator")


def _build_timeline(events: list[dict]) -> str:
    """Compact string of events for the orchestrator."""
    lines = []
    for ev in events:
        ts = ev.get("ts", "")[:19]
        typ = ev.get("type", "")
        eid = ev.get("id", "N/A")
        line = f"- {ts} [id:{eid}] [{typ}]"
        if typ == "browser.page_text":
            meta = ev.get("meta") or {}
            preview = (meta.get("text_preview") or "")[:100]
            line += f" {meta.get('title', '?')} -- {preview}..."
        lines.append(line)
    return "\n".join(lines)


class OrchestratorAgent:
    """Analyzes events and returns a list of tasks (plan)."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def create_plan(self, events: list[dict]) -> list:
        """From events, generate a plan (list of Task)."""
        if not events:
            return []
        timeline = _build_timeline(events)
        log.info("Generating task plan from timeline...")
        try:
            system = get_processor_prompt("task_plan", "system")
            user_template = get_processor_prompt("task_plan", "user_template")
            user = user_template.format(timeline=timeline)
            plan = self.llm.generate(system, user, Plan)
            log.info("Generated plan with %d tasks.", len(plan.tasks))
            return plan.tasks
        except Exception as e:
            log.error("Failed to generate task plan: %s", e)
            return []
