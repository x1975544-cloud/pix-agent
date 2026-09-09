from __future__ import annotations

from pathlib import Path

import pytest
from pix.embedding import HashingEmbeddingProvider, create_embedding_provider
from pix.embedding.base import EmbeddingProvider
from pix.indexing import RepositoryIndexer, SearchResult
from pix.vectorstore import MemoryVectorStore


class KeywordEmbeddingProvider(EmbeddingProvider):
    name = "keyword"

    def __init__(self, terms: list[str]) -> None:
        self._terms = terms

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * len(self._terms)
            lowered = text.lower()
            for index, term in enumerate(self._terms):
                if term in lowered:
                    vector[index] = 1.0
            norm = sum(value * value for value in vector) ** 0.5
            vectors.append([value / norm for value in vector] if norm else vector)
        return vectors


def _create_workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "auth.py").write_text(
        "def login_user(credentials):\n    return authentication_login(credentials)\n",
        encoding="utf-8",
    )
    (root / "database.py").write_text(
        "def apply_migration():\n    migrate_database_schema()\n",
        encoding="utf-8",
    )
    return root


def test_repository_chunks_are_indexed_and_searchable(tmp_path) -> None:
    root = _create_workspace(tmp_path)
    provider = KeywordEmbeddingProvider(["authentication", "login", "database", "migration"])
    store = MemoryVectorStore()
    indexer = RepositoryIndexer(
        index_path=tmp_path / "repository-index.json",
        embedding=provider,
        vector_store=store,
    )

    chunks = indexer.index_repository(root)

    assert len(chunks) == 2
    assert len(store) == 2
    hits = indexer.search_repository("authentication login", limit=10)
    assert hits
    assert all(isinstance(hit, SearchResult) for hit in hits)
    assert hits[0].path == "auth.py"
    assert hits[0].chunk_id.startswith("auth.py:")
    assert "login" in hits[0].content
    assert hits[0].score >= 0.0
    assert hits[0].to_dict()["path"] == "auth.py"


def test_repository_search_respects_top_k_and_empty_repository(tmp_path) -> None:
    root = _create_workspace(tmp_path)
    provider = KeywordEmbeddingProvider(["authentication", "login", "database", "migration"])
    store = MemoryVectorStore()
    indexer = RepositoryIndexer(
        index_path=tmp_path / "repository-index.json",
        embedding=provider,
        vector_store=store,
    )
    indexer.index_repository(root)

    auth_hits = indexer.search_repository("authentication login", top_k=1)
    migration_hits = indexer.search_repository("database migration", limit=1)
    assert len(auth_hits) == 1
    assert auth_hits[0].path == "auth.py"
    assert len(migration_hits) == 1
    assert migration_hits[0].path == "database.py"

    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    (empty_root / "notes.txt").write_text("not indexed", encoding="utf-8")
    assert indexer.index_repository(empty_root) == []
    assert indexer.search_repository("anything") == []


def test_repository_reindex_removes_stale_vector_entries(tmp_path) -> None:
    root = _create_workspace(tmp_path)
    provider = KeywordEmbeddingProvider(["authentication", "login", "database", "migration"])
    store = MemoryVectorStore()
    indexer = RepositoryIndexer(
        index_path=tmp_path / "repository-index.json",
        embedding=provider,
        vector_store=store,
    )
    indexer.index_repository(root)
    (root / "database.py").unlink()

    indexer.index_repository(root)

    assert len(store) == 1
    assert all(hit.path != "database.py" for hit in indexer.search_repository("database migration"))
    assert indexer.search_repository("authentication login")[0].path == "auth.py"


def test_default_embedding_provider_is_local_without_network() -> None:
    provider = create_embedding_provider()

    assert isinstance(provider, HashingEmbeddingProvider)
    vectors = provider.embed(["hello world", "hello repository"])
    assert len(vectors) == 2
    assert all(len(vector) == len(vectors[0]) for vector in vectors)


def test_semantic_search_requires_semantic_index_configuration(tmp_path) -> None:
    indexer = RepositoryIndexer(index_path=tmp_path / "repository-index.json")

    with pytest.raises(ValueError, match="embedding and vector_store"):
        indexer.search_repository("anything")
