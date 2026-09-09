"""Minimal SQLite database bootstrap."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from pix.errors import MemoryError

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    task TEXT NOT NULL,
    workspace TEXT NOT NULL,
    status TEXT NOT NULL,
    model TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    plan TEXT,
    final_answer TEXT,
    summary TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS trace_events (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    type TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    payload TEXT NOT NULL,
    duration_ms REAL,
    metadata TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_trace_events_session ON trace_events(session_id, timestamp);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    session_id TEXT,
    content TEXT NOT NULL,
    metadata TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
"""


class Database:
    """Owns the SQLite file and applies the schema once."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(self.path) as connection:
                connection.executescript(SCHEMA)
        except sqlite3.Error as exc:
            raise MemoryError(f"Cannot initialize SQLite database at {self.path}: {exc}") from exc

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection


def connect_database(database_url: str) -> Database:
    if not database_url.startswith("sqlite:"):
        raise MemoryError(f"Only sqlite:// database URLs are supported, got: {database_url}")
    raw = database_url.removeprefix("sqlite:///").removeprefix("sqlite://")
    path = Path(raw)
    if not path.is_absolute():
        path = Path.cwd() / path
    return Database(path)
