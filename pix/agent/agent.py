"""Public facade used by the CLI, API and examples."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pix.agent.executor import AgentExecutor
from pix.agent.state import AgentResult
from pix.config.settings import Settings
from pix.indexing import RepositoryRetriever
from pix.persistence.models import SessionRecord
from pix.providers.base import LLMProvider
from pix.tracing.bus import EventBus


class Agent:
    """High-level agent entry point backed by :class:`AgentExecutor`."""

    def __init__(
        self,
        settings: Settings,
        *,
        provider: LLMProvider | None = None,
        repository_retriever: RepositoryRetriever | None = None,
    ) -> None:
        self.settings = settings
        self.executor = AgentExecutor(
            settings,
            provider=provider,
            repository_retriever=repository_retriever,
        )

    def run(
        self,
        task: str,
        *,
        workspace: str | Path | None = None,
        model: str | None = None,
        max_iterations: int | None = None,
        auto_verify: bool = True,
        auto_fix_attempts: int = 2,
        stream: bool = False,
        event_bus: EventBus | None = None,
    ) -> AgentResult:
        return self.executor.execute(
            task,
            workspace=workspace,
            model=model,
            max_iterations=max_iterations,
            auto_verify=auto_verify,
            auto_fix_attempts=auto_fix_attempts,
            stream=stream,
            event_bus=event_bus,
        )

    def sessions(self, limit: int = 50) -> list[SessionRecord]:
        return self.executor.list_sessions(limit)

    def session(self, session_id: str) -> SessionRecord:
        return self.executor.get_session(session_id)

    def trace(self, session_id: str) -> list[dict[str, Any]]:
        return self.executor.trace(session_id)

    def close(self) -> None:
        self.executor.close()
