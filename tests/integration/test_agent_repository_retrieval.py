from __future__ import annotations

import json
from pathlib import Path

import pytest
from pix.agent.agent import Agent
from pix.config.settings import Settings
from pix.embedding.base import EmbeddingProvider
from pix.indexing import RepositoryIndexer, RepositoryRetriever
from pix.providers.base import ChatMessage
from pix.vectorstore import MemoryVectorStore
from tests.conftest import ScriptedProvider


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


@pytest.mark.integration
def test_agent_run_includes_semantically_retrieved_repository_code(tmp_path: Path) -> None:
    (tmp_path / "auth.py").write_text(
        "def login_user(credentials):\n    return authentication_login(credentials)\n",
        encoding="utf-8",
    )
    (tmp_path / "payments.py").write_text(
        "def charge_card(amount):\n    return process_payment(amount)\n",
        encoding="utf-8",
    )
    plan = {
        "title": "Add authentication",
        "summary": "Extend login handling.",
        "steps": [
            {"title": "Inspect auth", "description": "Read auth.py."},
            {"title": "Implement", "description": "Update authentication flow."},
        ],
    }
    provider = ScriptedProvider(
        [
            ChatMessage.assistant(json.dumps(plan)),
            ChatMessage.assistant("Authentication task complete."),
        ]
    )
    indexer = RepositoryIndexer(
        index_path=tmp_path / "repository-index.json",
        embedding=KeywordEmbeddingProvider(["authentication", "login", "payment"]),
        vector_store=MemoryVectorStore(),
    )
    retriever = RepositoryRetriever(indexer, top_k=1)
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=f"sqlite:///{tmp_path}/agent.db",
        workspace=str(tmp_path),
        skills_dir=str(tmp_path / "skills"),
        max_iterations=3,
        log_level="ERROR",
        enable_repository_index=True,
        repository_top_k=1,
    )

    agent = Agent(settings, provider=provider, repository_retriever=retriever)
    try:
        result = agent.run("Add authentication login", workspace=tmp_path, auto_verify=False)
    finally:
        agent.close()

    assert result.status.value == "success"
    loop_call = provider.calls[1]
    system_message = loop_call["messages"][0]
    system_content = system_message["content"] if isinstance(system_message, dict) else str(system_message)
    assert "auth.py" in system_content
    assert "def login_user" in system_content
    assert "payments.py" not in system_content
