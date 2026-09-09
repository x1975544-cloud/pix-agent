"""Cross-session long-term memory facade."""

from __future__ import annotations

from typing import Any

from pix.memory.store import MemoryStoreFacade
from pix.persistence.models import MemoryRecord


class LongTermMemory:
    """Typed API over :class:`MemoryStoreFacade` used by agents."""

    def __init__(self, store: MemoryStoreFacade) -> None:
        self.store = store

    def remember(
        self,
        content: str,
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        return self.store.remember(content, session_id=session_id, metadata=metadata)

    def recall(self, query: str, limit: int = 10) -> list[MemoryRecord]:
        return self.store.recall(query, limit=limit)

    def search(self, query: str, limit: int = 10) -> list[MemoryRecord]:
        return self.store.search(query, limit=limit)

    def forget(self, memory_id: str) -> bool:
        return self.store.forget(memory_id)
