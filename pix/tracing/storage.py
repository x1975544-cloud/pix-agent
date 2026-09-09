"""Trace storage facade backed by the persistence layer."""

from __future__ import annotations

from pix.persistence.database import Database
from pix.persistence.models import SessionRecord, TraceEventRecord
from pix.persistence.repositories import SessionStore, TraceStore


class TraceStorage:
    """High-level read access to sessions and their traces."""

    def __init__(self, database: Database) -> None:
        self.database = database
        self.trace_store = TraceStore(database)
        self.session_store = SessionStore(database)

    def session(self, session_id: str) -> SessionRecord | None:
        return self.session_store.get(session_id)

    def events(self, session_id: str) -> list[TraceEventRecord]:
        return self.trace_store.events_for_session(session_id)

    def timeline(self, session_id: str) -> list[dict[str, object]]:
        return [
            {
                "id": event.id,
                "type": event.type,
                "timestamp": event.timestamp.isoformat(),
                "payload": event.payload,
                "duration_ms": event.duration_ms,
            }
            for event in self.trace_store.events_for_session(session_id)
        ]
