from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pix.config.settings import Settings
from pix.vectorstore import ChromaVectorStore, MemoryVectorStore, create_vector_store

pytest.importorskip("chromadb")


def _upsert_sample(store: ChromaVectorStore) -> None:
    store.upsert(
        ["alpha", "beta", "gamma", "delta"],
        [[1.0, 0.0, 0.0], [0.9, 0.1, 0.0], [0.5, 0.5, 0.0], [-0.2, 0.8, 0.0]],
        [
            {"path": "src/alpha.py", "content": "alpha chunk"},
            {"path": "src/beta.py", "content": "beta chunk"},
            {"path": "src/gamma.py", "content": "gamma chunk"},
            {"path": "src/delta.py", "content": "delta chunk"},
        ],
    )


@pytest.fixture
def chroma_store(tmp_path: Path) -> Iterator[ChromaVectorStore]:
    store = ChromaVectorStore(tmp_path / "vectors", "pix_unit_test")
    yield store
    store.close()


def test_chroma_upsert_and_top_k_query_returns_vector_results(chroma_store: ChromaVectorStore) -> None:
    _upsert_sample(chroma_store)

    hits = chroma_store.query([1.0, 0.0, 0.0], top_k=2)

    assert [hit.id for hit in hits] == ["alpha", "beta"]
    assert hits[0].score > hits[1].score
    assert hits[0].path == "src/alpha.py"
    assert hits[0].content == "alpha chunk"


def test_chroma_upsert_replaces_and_delete_removes_entries(chroma_store: ChromaVectorStore) -> None:
    _upsert_sample(chroma_store)

    chroma_store.upsert(
        ["alpha"],
        [[0.0, 0.0, 1.0]],
        [{"path": "src/new.py", "content": "replacement chunk"}],
    )
    replaced = chroma_store.query([0.0, 0.0, 1.0], top_k=1)
    assert replaced[0].id == "alpha"
    assert replaced[0].path == "src/new.py"

    chroma_store.delete(["alpha", "missing"])

    assert len(chroma_store) == 3
    assert [hit.id for hit in chroma_store.query([1.0, 0.0, 0.0], top_k=10)] == ["beta", "gamma", "delta"]


def test_chroma_query_on_empty_store_returns_no_results(chroma_store: ChromaVectorStore) -> None:
    assert chroma_store.query([1.0, 0.0]) == []
    assert chroma_store.query([1.0, 0.0], top_k=0) == []
    assert chroma_store.query([], top_k=5) == []


def test_chroma_upsert_validates_input_counts(chroma_store: ChromaVectorStore) -> None:
    with pytest.raises(ValueError, match="same length"):
        chroma_store.upsert(["one"], [[1.0], [2.0]])
    with pytest.raises(ValueError, match="same length"):
        chroma_store.upsert(["one", "two"], [[1.0], [2.0]], [{}])


def test_chroma_persists_and_queries_after_client_restart(tmp_path: Path) -> None:
    path = tmp_path / "vectors"
    collection_name = "pix_restart_test"
    store = ChromaVectorStore(path, collection_name)
    _upsert_sample(store)
    store.close()

    reopened = ChromaVectorStore(path, collection_name)
    try:
        assert len(reopened) == 4
        hits = reopened.query([1.0, 0.0, 0.0], top_k=1)
        assert hits[0].id == "alpha"
        assert hits[0].path == "src/alpha.py"
        assert hits[0].content == "alpha chunk"
    finally:
        reopened.close()


def test_config_and_factory_select_memory_or_chroma(tmp_path: Path) -> None:
    memory_settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        vector_store="memory",
        vector_store_path=str(tmp_path / "vectors"),
    )
    memory_store = create_vector_store(
        memory_settings.vector_store,
        path=memory_settings.vector_store_path,
        collection_name=memory_settings.chroma_collection,
    )
    assert isinstance(memory_store, MemoryVectorStore)

    chroma_settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        vector_store_type="chroma",
        vector_store_path=str(tmp_path / "chroma"),
        chroma_collection="pix_factory_test",
    )
    chroma_store = create_vector_store(
        chroma_settings.vector_store,
        path=chroma_settings.vector_store_path,
        collection_name=chroma_settings.chroma_collection,
    )
    try:
        assert isinstance(chroma_store, ChromaVectorStore)
        assert chroma_store.collection_name == "pix_factory_test"
    finally:
        chroma_store.close()
