from __future__ import annotations

import pytest
from pix.vectorstore import MemoryVectorStore


def _upsert_sample(store: MemoryVectorStore) -> None:
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


def test_upsert_and_top_k_query_ranks_by_cosine_similarity() -> None:
    store = MemoryVectorStore()
    _upsert_sample(store)

    hits = store.query([1.0, 0.0, 0.0], top_k=2)

    assert [hit.id for hit in hits] == ["alpha", "beta"]
    assert hits[0].score > hits[1].score
    assert hits[0].path == "src/alpha.py"
    assert hits[0].content == "alpha chunk"


def test_upsert_replaces_same_id_and_delete_removes_entries() -> None:
    store = MemoryVectorStore()
    _upsert_sample(store)

    store.upsert(
        ["alpha"],
        [[0.0, 0.0, 1.0]],
        [{"path": "src/new.py", "content": "replacement chunk"}],
    )
    replaced = store.query([0.0, 0.0, 1.0], top_k=1)
    assert replaced[0].id == "alpha"
    assert replaced[0].path == "src/new.py"

    store.delete(["alpha", "missing"])

    assert len(store) == 3
    assert [hit.id for hit in store.query([1.0, 0.0, 0.0], top_k=10)] == ["beta", "gamma", "delta"]


def test_query_on_empty_store_returns_no_results() -> None:
    store = MemoryVectorStore()

    assert store.query([1.0, 0.0]) == []
    assert store.query([1.0, 0.0], top_k=0) == []
    assert store.query([], top_k=5) == []


def test_upsert_validates_input_counts() -> None:
    store = MemoryVectorStore()

    with pytest.raises(ValueError, match="same length"):
        store.upsert(["one"], [[1.0], [2.0]])
    with pytest.raises(ValueError, match="same length"):
        store.upsert(["one", "two"], [[1.0], [2.0]], [{}])


def test_query_rejects_mismatched_dimensions() -> None:
    store = MemoryVectorStore()
    store.upsert(["one"], [[1.0, 0.0]])

    with pytest.raises(ValueError, match="dimensions"):
        store.query([1.0])
