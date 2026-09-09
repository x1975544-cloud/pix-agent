"""Small typed repository classes over SQLite."""

from __future__ import annotations

import json
import sqlite3

from pix.persistence.database import Database
from pix.persistence.models import MemoryRecord, SessionRecord, TraceEventRecord


def _row_to_session(row: sqlite3.Row) -> SessionRecord:
    return SessionRecord(
        id=row["id"],
        task=row["task"],
        workspace=row["workspace"],
        status=row["status"],
        model=row["model"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        plan=json.loads(row["plan"]) if row["plan"] else None,
        final_answer=row["final_answer"],
        summary=row["summary"],
        error=row["error"],
    )


class SessionStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create(self, record: SessionRecord) -> SessionRecord:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO sessions "
                "(id, task, workspace, status, model, started_at, plan, final_answer, summary, error) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.id,
                    record.task,
                    record.workspace,
                    record.status,
                    record.model,
                    record.started_at.isoformat(),
                    json.dumps(record.plan) if record.plan else None,
                    record.final_answer,
                    record.summary,
                    record.error,
                ),
            )
        return record

    def update(self, record: SessionRecord) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE sessions SET status=?, finished_at=?, plan=?, final_answer=?, summary=?, error=? WHERE id=?",
                (
                    record.status,
                    record.finished_at.isoformat() if record.finished_at else None,
                    json.dumps(record.plan) if record.plan else None,
                    record.final_answer,
                    record.summary,
                    record.error,
                    record.id,
                ),
            )

    def get(self, session_id: str) -> SessionRecord | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        return _row_to_session(row) if row else None

    def list(self, limit: int = 100) -> list[SessionRecord]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
        return [_row_to_session(row) for row in rows]


class TraceStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def insert(self, record: TraceEventRecord) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO trace_events "
                "(id, session_id, type, timestamp, payload, duration_ms, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    record.id,
                    record.session_id,
                    record.type,
                    record.timestamp.isoformat(),
                    json.dumps(record.payload, ensure_ascii=False, default=str),
                    record.duration_ms,
                    json.dumps(record.metadata, ensure_ascii=False, default=str),
                ),
            )

    def events_for_session(self, session_id: str) -> list[TraceEventRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM trace_events WHERE session_id=? ORDER BY timestamp ASC",
                (session_id,),
            ).fetchall()
        return [
            TraceEventRecord(
                id=row["id"],
                session_id=row["session_id"],
                type=row["type"],
                timestamp=row["timestamp"],
                payload=json.loads(row["payload"]),
                duration_ms=row["duration_ms"],
                metadata=json.loads(row["metadata"]),
            )
            for row in rows
        ]


class MemoryStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def add(self, record: MemoryRecord) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO memories (id, session_id, content, metadata, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    record.id,
                    record.session_id,
                    record.content,
                    json.dumps(record.metadata, ensure_ascii=False, default=str),
                    record.created_at.isoformat(),
                ),
            )

    def search(self, query: str, limit: int = 20) -> list[MemoryRecord]:
        """SQL keyword fallback used when no semantic index is available."""

        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM memories WHERE content LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def list_by_ids(self, ids: list[str]) -> list[MemoryRecord]:
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        with self.database.connect() as connection:
            rows = connection.execute(f"SELECT * FROM memories WHERE id IN ({placeholders})", list(ids)).fetchall()
        records = {row["id"]: self._from_row(row) for row in rows}
        return [records[item] for item in ids if item in records]

    def list(self, session_id: str | None = None, limit: int = 50) -> list[MemoryRecord]:
        with self.database.connect() as connection:
            if session_id:
                rows = connection.execute(
                    "SELECT * FROM memories WHERE session_id=? ORDER BY created_at DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [self._from_row(row) for row in rows]

    def delete(self, memory_id: str) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _from_row(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=row["id"],
            session_id=row["session_id"],
            content=row["content"],
            metadata=json.loads(row["metadata"]),
            created_at=row["created_at"],
        )
