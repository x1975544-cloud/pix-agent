"""ChromaDB-backed persistent vector store."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pix.errors import ProviderError
from pix.vectorstore.base import VectorSearchResult, VectorStore


class ChromaVectorStore(VectorStore):
    """Persist vectors in ChromaDB and query them by cosine similarity."""

    def __init__(
        self,
        path: str | Path,
        collection_name: str = "pix_repository",
    ) -> None:
        try:
            import chromadb
        except ImportError as exc:
            raise ProviderError(
                "ChromaDB is not installed. Install it with `uv sync --extra memory` "
                "before using a persistent vector store."
            ) from exc
        self.path = Path(path).expanduser().resolve()
        self.collection_name = collection_name
        self._client = chromadb.PersistentClient(path=str(self.path))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._dimensions: int | None = None

    def __len__(self) -> int:
        return self._collection.count()

    def __enter__(self) -> ChromaVectorStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        """Release the persistent Chroma client so data can be reopened safely."""

        close = getattr(self._client, "close", None)
        if callable(close):
            close()

    def upsert(
        self,
        ids: Sequence[str],
        vectors: Sequence[Sequence[float]],
        metadatas: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        id_list = list(ids)
        vector_list = [[float(value) for value in vector] for vector in vectors]
        if len(id_list) != len(vector_list):
            raise ValueError("ids and vectors must have the same length")
        if metadatas is not None and len(metadatas) != len(id_list):
            raise ValueError("ids and metadatas must have the same length")
        if not id_list:
            return
        self._validate_vector_dimensions(vector_list)
        metadata_list = [dict(metadata) for metadata in metadatas] if metadatas is not None else None
        self._collection.upsert(
            ids=id_list,
            embeddings=vector_list,
            metadatas=metadata_list,
        )

    def delete(self, ids: Sequence[str]) -> None:
        id_list = list(ids)
        if id_list:
            self._collection.delete(ids=id_list)

    def query(
        self,
        vector: Sequence[float],
        *,
        top_k: int = 10,
        limit: int | None = None,
    ) -> list[VectorSearchResult]:
        count = limit if limit is not None else top_k
        query_vector = [float(value) for value in vector]
        if count <= 0 or not query_vector or len(self) == 0:
            return []
        self._load_dimensions_from_storage()
        if self._dimensions is not None and len(query_vector) != self._dimensions:
            raise ValueError(f"Query vector has {len(query_vector)} dimensions; store expects {self._dimensions}")
        response = self._collection.query(
            query_embeddings=[query_vector],
            n_results=min(count, len(self)),
            include=["metadatas", "distances"],
        )
        row_ids = list(response.get("ids") or [[]])[0]
        if not row_ids:
            return []
        metadata_rows = list(response.get("metadatas") or [[]])[0]
        distance_rows = list(response.get("distances") or [[]])[0]
        results: list[VectorSearchResult] = []
        for index, chunk_id in enumerate(row_ids):
            raw_metadata = metadata_rows[index] if index < len(metadata_rows) else {}
            distance = distance_rows[index] if index < len(distance_rows) else 1.0
            results.append(
                VectorSearchResult(
                    id=str(chunk_id),
                    score=1.0 - float(distance),
                    metadata=dict(raw_metadata or {}),
                )
            )
        return results

    def _validate_vector_dimensions(self, vectors: list[list[float]]) -> None:
        self._load_dimensions_from_storage()
        expected = self._dimensions if self._dimensions is not None else len(vectors[0])
        self._dimensions = expected
        for vector in vectors:
            if len(vector) != expected:
                raise ValueError(f"All vectors must have {expected} dimensions")

    def _load_dimensions_from_storage(self) -> None:
        if self._dimensions is not None or len(self) == 0:
            return
        response = self._collection.get(limit=1, include=["embeddings"])
        embeddings = response.get("embeddings")
        if embeddings is not None and len(embeddings) > 0:
            self._dimensions = len(embeddings[0])


__all__ = ["ChromaVectorStore"]
