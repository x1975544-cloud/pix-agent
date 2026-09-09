"""In-memory cosine-similarity vector store."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pix.vectorstore.base import VectorSearchResult, VectorStore


@dataclass(slots=True)
class _VectorEntry:
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryVectorStore(VectorStore):
    """Store vectors in memory and rank query hits by cosine similarity."""

    def __init__(self) -> None:
        self._entries: dict[str, _VectorEntry] = {}

    def __len__(self) -> int:
        return len(self._entries)

    def upsert(
        self,
        ids: Sequence[str],
        vectors: Sequence[Sequence[float]],
        metadatas: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        id_list = list(ids)
        vector_list = [list(vector) for vector in vectors]
        if len(id_list) != len(vector_list):
            raise ValueError("ids and vectors must have the same length")
        if metadatas is not None and len(metadatas) != len(id_list):
            raise ValueError("ids and metadatas must have the same length")
        for index, chunk_id in enumerate(id_list):
            raw_metadata = metadatas[index] if metadatas is not None else {}
            self._entries[chunk_id] = _VectorEntry(
                vector=vector_list[index],
                metadata=dict(raw_metadata),
            )

    def delete(self, ids: Sequence[str]) -> None:
        for chunk_id in ids:
            self._entries.pop(chunk_id, None)

    def query(
        self,
        vector: Sequence[float],
        *,
        top_k: int = 10,
        limit: int | None = None,
    ) -> list[VectorSearchResult]:
        count = limit if limit is not None else top_k
        if count <= 0:
            return []
        query_vector = [float(value) for value in vector]
        if not query_vector or not self._entries:
            return []
        expected_dimensions = len(next(iter(self._entries.values())).vector)
        if len(query_vector) != expected_dimensions:
            raise ValueError(f"Query vector has {len(query_vector)} dimensions; store expects {expected_dimensions}")
        scored: list[tuple[float, str, _VectorEntry]] = []
        for chunk_id, entry in self._entries.items():
            score = _cosine_similarity(query_vector, entry.vector)
            scored.append((score, chunk_id, entry))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [
            VectorSearchResult(
                id=chunk_id,
                score=score,
                metadata=dict(entry.metadata),
            )
            for score, chunk_id, entry in scored[:count]
        ]


class InMemoryVectorStore(MemoryVectorStore):
    """Compatibility name for the in-memory cosine vector store."""


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Cannot compare vectors with different dimensions")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right, strict=True))
    return dot_product / (left_norm * right_norm)


__all__ = ["InMemoryVectorStore", "MemoryVectorStore"]
