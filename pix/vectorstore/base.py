"""Provider-neutral vector store interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class VectorRecord:
    """A vector plus metadata intended for one upsert."""

    id: str
    vector: Sequence[float]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VectorSearchResult:
    """One vector query hit with its stored metadata."""

    id: str
    score: float
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @property
    def chunk_id(self) -> str:
        return self.id

    @property
    def path(self) -> str:
        value = self.metadata.get("path", "")
        return value if isinstance(value, str) else str(value)

    @property
    def content(self) -> str:
        value = self.metadata.get("content", "")
        return value if isinstance(value, str) else str(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "score": self.score,
            "metadata": dict(self.metadata),
        }


class VectorStore(ABC):
    """Store vectors under stable ids and query them by cosine similarity."""

    @abstractmethod
    def upsert(
        self,
        ids: Sequence[str],
        vectors: Sequence[Sequence[float]],
        metadatas: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        """Insert or replace vectors by id."""

    @abstractmethod
    def delete(self, ids: Sequence[str]) -> None:
        """Delete vectors by id; missing ids are ignored."""

    @abstractmethod
    def query(
        self,
        vector: Sequence[float],
        *,
        top_k: int = 10,
        limit: int | None = None,
    ) -> list[VectorSearchResult]:
        """Return the closest top-K vectors, ordered from best to worst."""
