"""Combine short-term and long-term memory into context-ready facts."""

from __future__ import annotations

from typing import Any

from pix.memory.long_term import LongTermMemory
from pix.memory.short_term import ShortTermMemory


class RetrievalEngine:
    def __init__(self, short_term: ShortTermMemory, long_term: LongTermMemory) -> None:
        self.short_term = short_term
        self.long_term = long_term

    def retrieve(self, query: str, *, limit: int = 8) -> dict[str, Any]:
        recent = self.short_term.recall(limit=max(3, limit // 2))
        semantic = self.long_term.recall(query, limit=max(1, limit // 2))
        return {
            "query": query,
            "recent": recent,
            "long_term": [record.content for record in semantic],
            "count": len(recent) + len(semantic),
        }

    def remember(self, content: str, session_id: str | None = None) -> None:
        self.short_term.remember(content)
        self.long_term.remember(content, session_id=session_id)
