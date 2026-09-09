from __future__ import annotations

from pix.memory.long_term import LongTermMemory
from pix.memory.retrieval import RetrievalEngine
from pix.memory.short_term import ShortTermMemory
from pix.memory.store import MemoryStoreFacade
from pix.persistence.database import Database
from pix.persistence.repositories import MemoryStore


def test_memory_facade_and_retrieval(tmp_path):
    sqlite = MemoryStore(Database(tmp_path / "pix.db"))
    facade = MemoryStoreFacade(sqlite)
    long_term = LongTermMemory(facade)
    record = long_term.remember("The repository uses FastAPI and pytest", session_id="s1")
    assert record.id
    assert long_term.recall("pytest")[0].content == "The repository uses FastAPI and pytest"

    short_term = ShortTermMemory(session_id="s1")
    short_term.remember("current entrypoint is app.py")
    engine = RetrievalEngine(short_term, long_term)
    result = engine.retrieve("pytest")
    assert result["recent"]
    assert result["long_term"]
    assert long_term.forget(record.id)
