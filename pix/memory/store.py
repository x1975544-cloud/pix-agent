"""Persistent memory store with SQLite plus optional semantic search."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from pix.embedding.base import EmbeddingProvider
from pix.persistence.models import MemoryRecord
from pix.persistence.repositories import MemoryStore


@dataclass(slots=True)
class MemoryStoreFacade:
    """Remember, recall, search and forget across sessions."""

    sqlite: MemoryStore
    embedding: EmbeddingProvider | None = None
    chroma: Any | None = None

    def remember(
        self,
        content: str,
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryRecord:
        record = MemoryRecord(
            session_id=session_id,
            content=content,
            metadata=metadata or {},
        )
        self.sqlite.add(record)
        if self.chroma is not None and self.embedding is not None:
            try:
                vector = self.embedding.embed([content])[0]
                self.chroma.add(ids=[record.id], embeddings=[vector], metadatas=[{"content": content}])
            except Exception:  # noqa: BLE001 - semantic indexing is best effort
                pass
        return record

    def recall(self, query: str, limit: int = 10) -> list[MemoryRecord]:
        return self.search(query, limit=limit)

    def search(self, query: str, limit: int = 10) -> list[MemoryRecord]:
        if self.chroma is not None and self.embedding is not None:
            try:
                vector = self.embedding.embed([query])[0]
                result = self.chroma.query(query_embeddings=[vector], n_results=min(limit, 20))
                ids = result.get("ids", [[]])[0]
                if ids:
                    return self.sqlite.list_by_ids([str(item) for item in ids])
            except Exception:  # noqa: BLE001 - fall back to SQLite keyword search
                pass
        return self.sqlite.search(query, limit=limit)

    def forget(self, memory_id: str) -> bool:
        removed = self.sqlite.delete(memory_id)
        if removed and self.chroma is not None:
            with suppress(Exception):
                self.chroma.delete(ids=[memory_id])
        return removed

    def list(self, session_id: str | None = None, limit: int = 50) -> list[MemoryRecord]:
        return self.sqlite.list(session_id=session_id, limit=limit)
