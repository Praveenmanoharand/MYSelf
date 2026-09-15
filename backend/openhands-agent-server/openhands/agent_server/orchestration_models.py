from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class OrchestrationStatus(StrEnum):
    QUEUED = "queued"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_TOOL = "waiting_for_tool"
    RETRYING = "retrying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrchestrationEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    kind: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)


class OrchestrationTask(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    session_id: str
    request: str = Field(min_length=1, max_length=100_000)
    mode: str = Field(default="general", max_length=100)
    workspace: str
    repository: str | None = None
    classification: str = "general"
    selected_skills: list[str] = Field(default_factory=list)
    execution_plan: list[str] = Field(default_factory=list)
    current_step: int = 0
    completed_steps: list[int] = Field(default_factory=list)
    pending_steps: list[int] = Field(default_factory=list)
    status: OrchestrationStatus = OrchestrationStatus.QUEUED
    errors: list[str] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    conversation_id: UUID | None = None
    model: str | None = None
    provider: str | None = None
    fallback_model: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CreateTaskRequest(BaseModel):
    request: str = Field(min_length=1, max_length=100_000)
    mode: str = Field(default="general", max_length=100)
    workspace: str | None = None
    repository: str | None = None
    model: str | None = Field(default=None, max_length=500)
    fallback_model: str | None = Field(default=None, max_length=500)


class TaskResponse(BaseModel):
    task: OrchestrationTask


class ResumeTaskRequest(BaseModel):
    message: str | None = Field(default=None, max_length=100_000)


class ApprovalRequest(BaseModel):
    approved: bool
    reason: str = Field(default="", max_length=10_000)


class TaskEventsResponse(BaseModel):
    items: list[OrchestrationEvent]
    next_page_id: str | None = None


def classify_request(request: str, mode: str) -> str:
    if mode != "general":
        return mode
    lowered = request.lower()
    for category, terms in {
        "coding": ("build", "code", "debug", "api", "database", "project", "implement"),
        "research": ("research", "sources", "citations", "compare", "investigate"),
        "proposal": ("proposal", "client", "freelance", "quotation"),
        "document": ("document", "report", "resume", "cv", "meeting notes"),
        "workflow": ("workflow", "automate", "pipeline", "approval"),
        "data-analysis": ("csv", "spreadsheet", "metrics", "analyze", "analyse"),
    }.items():
        if any(term in lowered for term in terms):
            return category
    return "general"


def validate_workspace(candidate: str | None, allowed_root: Path) -> str:
    root = allowed_root.resolve()
    path = (Path(candidate).expanduser() if candidate else root).resolve()
    if path != root and root not in path.parents:
        raise ValueError("workspace must be inside the configured workspace root")
    path.mkdir(parents=True, exist_ok=True)
    return str(path)
