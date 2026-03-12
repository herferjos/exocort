"""Pydantic models for vault planning and LLM outputs."""
from typing import List, Literal

from pydantic import BaseModel, Field

TaskType = Literal["CREATE_OR_UPDATE_NOTE", "GENERATE_QUESTIONS"]
TaskStatus = Literal["pending", "running", "completed", "failed"]


class Concept(BaseModel):
    """Single concept name extracted from text (2–5 words)."""
    concept: str = Field(..., description="The extracted concept.")


class GeneratedQuestions(BaseModel):
    """Markdown list of reflection questions."""
    questions_markdown: str = Field(
        ...,
        description="Markdown list of 3–5 open-ended questions.",
    )


class MarkdownContent(BaseModel):
    """Raw markdown text (daily summary, concept note, etc.)."""
    content: str = Field(..., description="Markdown text only.")


class Task(BaseModel):
    """One task for a worker agent."""
    task_id: str = Field(..., description="Unique ID, e.g. 'concept_1'.")
    task_type: TaskType = Field(..., description="CREATE_OR_UPDATE_NOTE or GENERATE_QUESTIONS.")
    description: str = Field(..., description="What the worker should do.")
    related_event_ids: List[str] = Field(default_factory=list, description="Event IDs for this task.")
    dependencies: List[str] = Field(default_factory=list, description="Task IDs that must run first.")
    status: TaskStatus = "pending"
    result: str | None = None


class Plan(BaseModel):
    """Full plan of tasks for a run."""
    tasks: List[Task]
