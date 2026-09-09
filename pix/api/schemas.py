"""Pydantic request and response models for the HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    task: str = Field(min_length=1, max_length=10_000)
    workspace: str | None = None
    model: str | None = None
    max_iterations: int | None = Field(default=None, ge=1, le=200)
    auto_verify: bool = True
    auto_fix_attempts: int = Field(default=2, ge=0, le=5)


class AgentRunResponse(BaseModel):
    session_id: str
    task: str
    workspace: str
    status: str
    message: str
    plan: dict[str, Any] | None = None
    summary: str | None = None
    error: str | None = None
    created_at: datetime


class SessionSummary(BaseModel):
    id: str
    task: str
    workspace: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    model: str | None
    summary: str | None
    error: str | None


class SessionDetail(SessionSummary):
    plan: dict[str, Any] | None
    final_answer: str | None


class TraceEvent(BaseModel):
    id: str
    type: str
    timestamp: datetime
    payload: dict[str, Any]
    duration_ms: float | None
    metadata: dict[str, Any]


class TraceResponse(BaseModel):
    session_id: str
    events: list[TraceEvent]


class ToolInfo(BaseModel):
    name: str
    description: str


class SkillInfo(BaseModel):
    name: str
    path: str
