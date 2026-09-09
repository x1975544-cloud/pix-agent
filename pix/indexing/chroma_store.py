"""Chroma-backed vector store for repository chunks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pix.errors import ProviderError
from pix.indexing.documents import IndexedChunk, SearchResult


class ChromaVectorStore:
    """Persist and query repository chunks with ChromaDB."""

    def __init__(self, path: str | Path, collection_name: str = "pix_repository") -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise ProviderError(
                "ChromaDB is not installed. Install it with `uv sync --extra memory` "
                "before using repository indexing."
            ) from exc
        self._client = chromadb.PersistentClient(path=str(path))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, chunks: list[IndexedChunk], vectors: list[list[float]]) -> None:
        if len(chunks) != len(vectors):
            raise ProviderError("Chunk and vector counts do not match")
        if not chunks:
            return
        self._collection.upsert(
            ids=[chunk.id for chunk in chunks],
            embeddings=vectors,
            documents=[chunk.content for chunk in chunks],
            metadatas=[
                {
                    "document_path": chunk.document_path,
                    "language": chunk.language,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    **chunk.metadata,
                }
                for chunk in chunks
            ],
        )

    def search(self, vector: list[float], limit: int = 10) -> list[SearchResult]:
        if not vector:
            return []
        response = self._collection.query(
            query_embeddings=[vector],
            n_results=min(limit, 100),
            include=["documents", "metadatas", "distances"],
        )
        ids = response.get("ids", [[]])[0]
        documents = response.get("documents", [[]])[0]
        metadatas = response.get("metadatas", [[]])[0]
        distances = response.get("distances", [[]])[0]
        results: list[SearchResult] = []
        for index, chunk_id in enumerate(ids):
            metadata: dict[str, Any] = metadatas[index] or {}
            distance = float(distances[index]) if index < len(distances) else 1.0
            results.append(
                SearchResult(
                    chunk_id=str(chunk_id),
                    document_path=str(metadata.get("document_path") or ""),
                    language=str(metadata.get("language") or "unknown"),
                    content=str(documents[index] or ""),
                    start_line=int(metadata.get("start_line") or 1),
                    end_line=int(metadata.get("end_line") or 1),
                    score=max(0.0, 1.0 - distance),
                    metadata=metadata,
                )
            )
        return results


__all__ = ["ChromaVectorStore"]
