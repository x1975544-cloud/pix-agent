"""Factories for provider-neutral vector stores."""

from __future__ import annotations

from pathlib import Path

from pix.vectorstore.base import VectorStore
from pix.vectorstore.chroma import ChromaVectorStore
from pix.vectorstore.memory import MemoryVectorStore


def create_vector_store(
    name: str = "memory",
    *,
    path: str | Path = ".pix/vectors",
    collection_name: str = "pix_repository",
) -> VectorStore:
    """Create a vector store by name.

    ``memory`` keeps vectors in process memory. ``chroma`` persists them under
    ``path`` using ChromaDB.
    """

    provider = name.strip().lower().replace("-", "_")
    if provider in {"memory", "in_memory"}:
        return MemoryVectorStore()
    if provider == "chroma":
        return ChromaVectorStore(path=path, collection_name=collection_name)
    raise ValueError(f"Unknown vector store provider: {name}")


__all__ = ["create_vector_store"]
