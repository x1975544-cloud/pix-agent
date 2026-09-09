"""Task-driven retrieval over an indexed repository."""

from __future__ import annotations

from pathlib import Path

from pix.indexing.documents import SearchResult
from pix.indexing.indexer import RepositoryIndexer


class RepositoryRetriever:
    """Keep a semantic repository indexer and return context-ready chunks."""

    def __init__(self, indexer: RepositoryIndexer, *, top_k: int = 5) -> None:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        self.indexer = indexer
        self.top_k = top_k

    def retrieve(
        self,
        query: str,
        root: str | Path | None = None,
        *,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """Index ``root`` when supplied, then run semantic top-K search."""

        resolved_top_k = self.top_k if top_k is None else top_k
        if resolved_top_k < 1:
            raise ValueError("top_k must be positive")
        if root is not None:
            self.indexer.index_repository(root)
        return self.indexer.search_repository(query, top_k=resolved_top_k)


__all__ = ["RepositoryRetriever"]
