"""Agent state, plan model and loop result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pix.providers.base import ChatMessage


class AgentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PlanStep(BaseModel):
    """One planned phase in a software engineering task."""

    title: str
    description: str = ""
    commands: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    """Structured plan produced by the planner and consumed by the executor."""

    title: str
    summary: str
    steps: list[PlanStep] = Field(default_factory=list)

    def render(self) -> str:
        lines = [self.title, self.summary]
        for index, step in enumerate(self.steps, start=1):
            lines.append(f"{index}. {step.title}")
            if step.description:
                lines.append(f"   {step.description}")
        return "\n".join(lines)


@dataclass(slots=True)
class ToolObservation:
    """A completed tool call plus its result inside one iteration."""

    call_id: str
    name: str
    arguments: dict[str, Any]
    success: bool
    output: Any
    error: str | None = None
    duration_seconds: float = 0.0


@dataclass(slots=True)
class AgentState:
    """Mutable state owned by one agent session."""

    session_id: str
    task: str
    workspace: Path
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: AgentStatus = AgentStatus.PENDING
    iteration: int = 0
    max_iterations: int = 30
    messages: list[ChatMessage] = field(default_factory=list)
    observations: list[ToolObservation] = field(default_factory=list)
    plan: Plan | None = None
    final_answer: str | None = None
    summary: str | None = None
    error: str | None = None
    auto_commit: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def current_iteration(self) -> int:
        return self.iteration

    def add_message(self, message: ChatMessage) -> None:
        self.messages.append(message)

    def add_tool_observation(self, observation: ToolObservation) -> None:
        self.observations.append(observation)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task": self.task,
            "workspace": str(self.workspace),
            "started_at": self.started_at.isoformat(),
            "status": self.status.value,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "plan": self.plan.model_dump() if self.plan else None,
            "final_answer": self.final_answer,
            "summary": self.summary,
            "error": self.error,
            "auto_commit": self.auto_commit,
        }


@dataclass(slots=True)
class AgentResult:
    """Result returned to callers after an agent session finishes."""

    state: AgentState
    status: AgentStatus
    message: str
    trace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status.value, "message": self.message, **self.state.to_dict()}
