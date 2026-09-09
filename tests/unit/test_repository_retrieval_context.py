from __future__ import annotations

from pathlib import Path

from pix.agent.state import AgentState
from pix.context.manager import ContextManager
from pix.embedding.base import EmbeddingProvider
from pix.indexing import RepositoryIndexer, RepositoryRetriever, SearchResult
from pix.providers.base import ChatMessage
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
    (root / "payments.py").write_text(
        "def charge_card(amount):\n    return process_payment(amount)\n",
        encoding="utf-8",
    )
    return root


def _indexer(tmp_path: Path) -> RepositoryIndexer:
    return RepositoryIndexer(
        index_path=tmp_path / "repository-index.json",
        embedding=KeywordEmbeddingProvider(["authentication", "login", "payment"]),
        vector_store=MemoryVectorStore(),
    )


def test_repository_retriever_returns_relevant_chunks_for_task(tmp_path: Path) -> None:
    root = _create_workspace(tmp_path)
    retriever = RepositoryRetriever(_indexer(tmp_path), top_k=5)

    hits = retriever.retrieve("add authentication login", root, top_k=1)

    assert len(hits) == 1
    assert hits[0].path == "auth.py"
    assert "login_user" in hits[0].content


def test_context_manager_includes_retrieved_code_snippet(tmp_path: Path) -> None:
    state = AgentState(session_id="s1", task="Add authentication", workspace=tmp_path)
    state.add_message(ChatMessage.user("Add authentication"))
    hit = SearchResult(
        chunk_id="auth.py:1:2",
        path="auth.py",
        content="def login_user(credentials):\n    return authentication_login(credentials)\n",
        score=0.98,
        language="python",
        start_line=1,
        end_line=2,
    )

    built = ContextManager(budget_tokens=2_000).build(
        state,
        repository_hits=[hit],
    )

    assert built.sections[-1].key == "repository_retrieval"
    assert "def login_user" in built.system_prompt
    assert "auth.py:1-2" in built.system_prompt
