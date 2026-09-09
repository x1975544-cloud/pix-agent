from __future__ import annotations

from pix.persistence.database import Database
from pix.persistence.models import SessionRecord
from pix.persistence.repositories import MemoryStore, SessionStore, TraceStore
from pix.security import redact_payload
from pix.tracing.tracer import Tracer


def test_session_and_trace_storage(tmp_path):
    database = Database(tmp_path / "pix.db")
    session_store = SessionStore(database)
    session = SessionRecord(id="s1", task="Task", workspace=str(tmp_path))
    session_store.create(session)
    assert session_store.get("s1").id == "s1"
    assert session_store.list()[0].task == "Task"

    tracer = Tracer(TraceStore(database), "s1", secret_values=["super-secret-token"])
    tracer.emit("TOOL_CALL", {"args": {"token": "super-secret-token", "name": "write_file"}})
    events = TraceStore(database).events_for_session("s1")
    assert events[0].payload["args"]["token"] == "[REDACTED]"
    assert len(events) == 1


def test_memory_store_roundtrip(tmp_path):
    database = Database(tmp_path / "pix.db")
    store = MemoryStore(database)
    from pix.persistence.models import MemoryRecord

    store.add(MemoryRecord(session_id="s1", content="FastAPI project uses pytest"))
    hits = store.search("pytest")
    assert len(hits) == 1
    assert store.list(session_id="s1")[0].content == "FastAPI project uses pytest"
    assert store.delete(hits[0].id)
    assert not store.list()


def test_redact_payload_deep():
    assert redact_payload({"nested": [{"password": "123456789"}]}) == {"nested": [{"password": "[REDACTED]"}]}
