"""Trace event model and canonical event types."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

SESSION_STARTED = "SESSION_STARTED"
LLM_REQUEST = "LLM_REQUEST"
LLM_RESPONSE = "LLM_RESPONSE"
TOOL_CALL = "TOOL_CALL"
TOOL_RESULT = "TOOL_RESULT"
CONTEXT_BUILD = "CONTEXT_BUILD"
MEMORY_READ = "MEMORY_READ"
MEMORY_WRITE = "MEMORY_WRITE"
PLAN_CREATED = "PLAN_CREATED"
REPOSITORY_ANALYZED = "REPOSITORY_ANALYZED"
VERIFICATION_STARTED = "VERIFICATION_STARTED"
VERIFICATION_FINISHED = "VERIFICATION_FINISHED"
GIT_OPERATION = "GIT_OPERATION"
AGENT_ERROR = "AGENT_ERROR"
AGENT_FINISHED = "AGENT_FINISHED"
ITERATION_STARTED = "ITERATION_STARTED"

EVENT_TYPES: set[str] = {
    SESSION_STARTED,
    LLM_REQUEST,
    LLM_RESPONSE,
    TOOL_CALL,
    TOOL_RESULT,
    CONTEXT_BUILD,
    MEMORY_READ,
    MEMORY_WRITE,
    PLAN_CREATED,
    REPOSITORY_ANALYZED,
    VERIFICATION_STARTED,
    VERIFICATION_FINISHED,
    GIT_OPERATION,
    AGENT_ERROR,
    AGENT_FINISHED,
    ITERATION_STARTED,
}


class TraceEvent(BaseModel):
    """Observability event emitted by the agent runtime."""

    id: str = Field(default_factory=lambda: uuid4().hex[:16])
    session_id: str
    type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


AgentTraceEvent = TraceEvent
