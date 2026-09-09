"""Pydantic models persisted by SQLite repositories."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class SessionRecord(BaseModel):
    id: str
    task: str
    workspace: str
    status: str = "pending"
    model: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    plan: dict[str, Any] | None = None
    final_answer: str | None = None
    summary: str | None = None
    error: str | None = None


class TraceEventRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:16])
    session_id: str
    type: str
    timestamp: datetime = Field(default_factory=utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    session_id: str | None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
