from __future__ import annotations

from pathlib import Path

import pytest
from pix.embedding.local import HashingEmbeddingProvider
from pix.indexing import RepositoryIndexer
from pix.vectorstore import ChromaVectorStore, create_vector_store

pytest.importorskip("chromadb")


def _create_workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "auth.py").write_text(
        "def login_user(credentials):\n    return authentication_login(credentials)\n",
        encoding="utf-8",
    )
    return root


def test_repository_indexer_uses_chroma_through_vector_store_abstraction(tmp_path: Path) -> None:
    root = _create_workspace(tmp_path)
    vector_path = tmp_path / "vectors"
    embedding = HashingEmbeddingProvider()
    store = create_vector_store("chroma", path=vector_path, collection_name="pix_indexer_test")
    indexer = RepositoryIndexer(
        index_path=tmp_path / "repository-index.json",
        embedding=embedding,
        vector_store=store,
    )

    chunks = indexer.index_repository(root)

    assert len(chunks) == 1
    assert len(store) == 1
    assert indexer.search_repository("authentication login")[0].path == "auth.py"
    store.close()

    reopened = ChromaVectorStore(vector_path, "pix_indexer_test")
    try:
        assert len(reopened) == 1
        query_vector = embedding.embed(["authentication login"])[0]
        assert reopened.query(query_vector, top_k=1)[0].path == "auth.py"
    finally:
        reopened.close()
