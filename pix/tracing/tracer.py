"""Tracer that writes redacted events and exposes a callable event sink."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from pix.persistence.models import TraceEventRecord
from pix.persistence.repositories import TraceStore
from pix.security import redact_payload

logger = logging.getLogger(__name__)


class Tracer:
    """Record agent events and guarantee secrets never reach storage."""

    def __init__(
        self,
        store: TraceStore,
        session_id: str,
        *,
        secret_values: Iterable[str] = (),
        events: list[TraceEventRecord] | None = None,
    ) -> None:
        self.store = store
        self.session_id = session_id
        self.secret_values = list(secret_values)
        self.events = events or []

    def emit(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceEventRecord:
        safe_payload = redact_payload(payload or {}, self.secret_values)
        safe_metadata = redact_payload(metadata or {}, self.secret_values)
        record = TraceEventRecord(
            session_id=self.session_id,
            type=event_type,
            payload=safe_payload,
            duration_ms=duration_ms,
            metadata=safe_metadata,
        )
        self.store.insert(record)
        self.events.append(record)
        return record

    def sink(self, event_type: str, payload: dict[str, Any]) -> None:
        """Callable signature compatible with :class:`AgentLoop`."""

        mapped = {
            "context_build": "CONTEXT_BUILD",
            "llm_request": "LLM_REQUEST",
            "llm_response": "LLM_RESPONSE",
            "tool_call": "TOOL_CALL",
            "tool_result": "TOOL_RESULT",
            "agent_error": "AGENT_ERROR",
            "agent_finished": "AGENT_FINISHED",
            "iteration_started": "ITERATION_STARTED",
        }.get(event_type, event_type.upper())
        try:
            self.emit(mapped, payload)
        except Exception:  # noqa: BLE001 - tracing must not kill an agent run
            logger.exception("Trace event could not be stored: %s", event_type)
