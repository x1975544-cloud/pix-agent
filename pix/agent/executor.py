"""Orchestrator that drives one end-to-end coding agent session."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pix.agent.loop import AgentLoop, LoopOptions
from pix.agent.planner import Planner
from pix.agent.state import AgentResult, AgentState, AgentStatus, Plan
from pix.analysis.repository import RepositoryAnalyzer, RepositoryContext
from pix.config.settings import Settings
from pix.context.manager import ContextManager
from pix.embedding import create_embedding_provider
from pix.errors import SecurityError, SessionNotFoundError
from pix.indexing.indexer import RepositoryIndexer
from pix.mcp.client import StdioMCPClient
from pix.mcp.registry import MCPRegistry
from pix.memory.long_term import LongTermMemory
from pix.memory.short_term import ShortTermMemory
from pix.memory.store import MemoryStoreFacade
from pix.persistence.database import Database, connect_database
from pix.persistence.models import SessionRecord
from pix.persistence.repositories import MemoryStore, SessionStore, TraceStore
from pix.providers.base import ChatMessage, LLMProvider
from pix.providers.factory import create_provider
from pix.security import Workspace
from pix.skills.loader import load_skills
from pix.skills.registry import SkillRegistry
from pix.tools.base import Tool
from pix.tools.filesystem import default_filesystem_tools
from pix.tools.git import default_git_tools
from pix.tools.registry import ToolRegistry
from pix.tools.search import default_search_tool
from pix.tools.semantic import SemanticSearchTool
from pix.tools.shell import default_shell_tool
from pix.tracing.bus import EventBus
from pix.tracing.events import (
    AGENT_ERROR,
    AGENT_FINISHED,
    MEMORY_WRITE,
    PLAN_CREATED,
    REPOSITORY_ANALYZED,
    SESSION_STARTED,
    VERIFICATION_FINISHED,
    VERIFICATION_STARTED,
)
from pix.tracing.tracer import Tracer
from pix.verification.engine import VerificationEngine, VerificationResult

logger = logging.getLogger(__name__)


class AgentExecutor:
    """Own one agent session end to end: plan, loop, verify and persist."""

    def __init__(
        self,
        settings: Settings,
        *,
        provider: LLMProvider | None = None,
        database: Database | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.settings = settings
        self._database = database or connect_database(settings.database_url)
        self._session_store = SessionStore(self._database)
        self._trace_store = TraceStore(self._database)
        self._memory_store = MemoryStoreFacade(MemoryStore(self._database))
        self._provider = provider
        self._owns_provider = provider is None
        self._event_bus = event_bus or EventBus()

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    def close(self) -> None:
        if self._provider and self._owns_provider:
            self._provider.close()

    def list_sessions(self, limit: int = 50) -> list[SessionRecord]:
        return self._session_store.list(limit=limit)

    def get_session(self, session_id: str) -> SessionRecord:
        record = self._session_store.get(session_id)
        if record is None:
            raise SessionNotFoundError(session_id)
        return record

    def trace(self, session_id: str) -> list[dict[str, Any]]:
        if self._session_store.get(session_id) is None:
            raise SessionNotFoundError(session_id)
        return [event.model_dump(mode="json") for event in self._trace_store.events_for_session(session_id)]

    def execute(
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
        workspace_path = Path(workspace or self.settings.workspace).expanduser().resolve()
        if not workspace_path.is_dir():
            raise SecurityError(f"Workspace does not exist: {workspace_path}")
        sandbox = Workspace(workspace_path)

        session_id = f"sess_{uuid4().hex[:12]}"
        tracer = Tracer(
            self._trace_store,
            session_id,
            secret_values=self.settings.secret_values,
            event_bus=event_bus or self._event_bus,
        )
        record = SessionRecord(
            id=session_id,
            task=task,
            workspace=str(workspace_path),
            status=AgentStatus.PENDING.value,
            model=model or self.settings.model,
        )
        self._session_store.create(record)
        tracer.emit(SESSION_STARTED, {"task": task, "workspace": str(workspace_path)})

        provider = self._provider or create_provider(
            self.settings,
            model=model,
        )
        try:
            analyzer = RepositoryAnalyzer()
            repository = analyzer.analyze(workspace_path)
            tracer.emit(
                REPOSITORY_ANALYZED,
                {
                    "language": repository.language,
                    "framework": repository.framework,
                    "entrypoint": repository.entrypoint,
                    "test_command": repository.test_command,
                    "summary": repository.summary,
                },
            )

            repository_indexer: RepositoryIndexer | None = None
            if self.settings.enable_repository_index:
                embedding = create_embedding_provider(
                    self.settings.embedding_provider,
                    api_key=self.settings.api_key.get_secret_value() if self.settings.api_key else None,
                    api_base=self.settings.api_base,
                    model=self.settings.embedding_model,
                )
                repository_indexer = RepositoryIndexer(
                    embedding,
                    vector_store_path=self.settings.vector_store_path,
                    collection_name=self.settings.chroma_collection,
                )
                indexed_chunks = repository_indexer.index_repository(workspace_path)
                tracer.emit(
                    "REPOSITORY_INDEXED",
                    {
                        "provider": embedding.name,
                        "chunks": len(indexed_chunks),
                        "collection": self.settings.chroma_collection,
                    },
                )

            planner = Planner(provider, model=model or self.settings.model)
            plan = planner.plan(task, repository)
            tracer.emit(PLAN_CREATED, plan.model_dump(mode="json"))

            state = AgentState(
                session_id=session_id,
                task=task,
                workspace=workspace_path,
                max_iterations=max_iterations or self.settings.max_iterations,
                plan=plan,
                auto_commit=self.settings.auto_commit,
                metadata={"model": model or self.settings.model},
            )
            state.add_message(ChatMessage.user(task))

            registry = self._build_tool_registry(sandbox, workspace_path, repository_indexer)
            memory = self._build_memory()
            short_term = ShortTermMemory(session_id=session_id)
            memory_hits = memory.recall(task, limit=5)
            if memory_hits:
                tracer.emit("MEMORY_READ", {"query": task, "hits": [hit.id for hit in memory_hits]})

            skills = SkillRegistry(load_skills(self.settings.skills_dir))
            system_prompt = self._system_prompt(repository, plan, skills.instruction_texts())
            context_manager = ContextManager(self.settings.context_limit_tokens)
            loop_options = LoopOptions(
                max_iterations=state.max_iterations,
                tool_timeout=self.settings.tool_timeout,
                model=model or self.settings.model,
                stream=stream,
            )

            verification = VerificationEngine()
            result_state, verification_result = self._run_with_verification(
                state=state,
                provider=provider,
                registry=registry,
                context_manager=context_manager,
                system_prompt=system_prompt,
                tracer=tracer,
                loop_options=loop_options,
                memory_hits=[item.model_dump(mode="json") for item in memory_hits],
                verification=verification,
                repository=repository,
                auto_verify=auto_verify,
                auto_fix_attempts=auto_fix_attempts,
            )

            self._persist_completion(record, result_state, verification_result)
            tracer.emit(
                AGENT_FINISHED,
                {
                    "status": result_state.status.value,
                    "final_answer": (result_state.final_answer or "")[:2000],
                    "iterations": result_state.iteration,
                    "observations": len(result_state.observations),
                },
            )
            if result_state.status == AgentStatus.SUCCESS:
                short_term.remember(task)
                memory.remember(
                    f"Completed task: {task}",
                    session_id=session_id,
                    metadata={"status": "success", "summary": result_state.summary or ""},
                )
                tracer.emit(MEMORY_WRITE, {"kind": "task_summary", "task": task})
            message = result_state.final_answer or result_state.error or "Agent finished with an unknown status."
            return AgentResult(
                state=result_state,
                status=result_state.status,
                message=message,
                trace_id=session_id,
            )
        except Exception as exc:
            tracer.emit(
                AGENT_ERROR,
                {
                    "error": str(exc)[:2000],
                    "type": exc.__class__.__name__,
                },
            )
            record.status = AgentStatus.FAILED.value
            record.finished_at = datetime.now(UTC)
            record.error = str(exc)
            self._session_store.update(record)
            raise

    def _run_with_verification(
        self,
        *,
        state: AgentState,
        provider: LLMProvider,
        registry: ToolRegistry,
        context_manager: ContextManager,
        system_prompt: str,
        tracer: Tracer,
        loop_options: LoopOptions,
        memory_hits: list[dict[str, Any]],
        verification: VerificationEngine,
        repository: RepositoryContext,
        auto_verify: bool,
        auto_fix_attempts: int,
    ) -> tuple[AgentState, VerificationResult]:
        verification_result = VerificationResult(command=None, success=True, skipped=True)
        state = self._run_loop(
            state=state,
            provider=provider,
            registry=registry,
            context_manager=context_manager,
            system_prompt=system_prompt,
            tracer=tracer,
            loop_options=loop_options,
            memory_hits=memory_hits,
        )
        attempts = 0
        while (
            auto_verify
            and state.status == AgentStatus.SUCCESS
            and repository.test_command is not None
            and attempts <= auto_fix_attempts
        ):
            tracer.emit(VERIFICATION_STARTED, {"command": repository.test_command, "attempt": attempts + 1})
            verification_result = verification.verify(workspace=state.workspace)
            tracer.emit(
                VERIFICATION_FINISHED,
                {
                    "success": verification_result.success,
                    "skipped": verification_result.skipped,
                    "exit_code": verification_result.exit_code,
                    "duration_seconds": verification_result.duration_seconds,
                },
            )
            if verification_result.success or verification_result.skipped:
                state.summary = (
                    f"Verification {'skipped' if verification_result.skipped else 'passed'} "
                    f"({repository.test_command or 'no command'})."
                )
                break
            attempts += 1
            if attempts > auto_fix_attempts:
                state.status = AgentStatus.FAILED
                state.error = "Verification still failing after automated fix attempts."
                state.summary = verification_result.summary()
                break
            state.messages.append(
                ChatMessage.user(
                    "Automated verification reported these failures. Fix the root cause, rerun the command, "
                    "and continue only after it passes.\n\n" + verification_result.summary()
                )
            )
            state = AgentState(
                session_id=state.session_id,
                task=state.task,
                workspace=state.workspace,
                max_iterations=state.max_iterations,
                messages=state.messages,
                observations=state.observations,
                plan=state.plan,
                auto_commit=state.auto_commit,
                metadata=state.metadata,
            )
            state = self._run_loop(
                state=state,
                provider=provider,
                registry=registry,
                context_manager=context_manager,
                system_prompt=system_prompt,
                tracer=tracer,
                loop_options=loop_options,
                memory_hits=memory_hits,
            )
        return state, verification_result

    def _run_loop(
        self,
        *,
        state: AgentState,
        provider: LLMProvider,
        registry: ToolRegistry,
        context_manager: ContextManager,
        system_prompt: str,
        tracer: Tracer,
        loop_options: LoopOptions,
        memory_hits: list[dict[str, Any]],
    ) -> AgentState:
        state.status = AgentStatus.PENDING
        loop = AgentLoop(
            provider,
            registry,
            context_manager,
            options=loop_options,
            event_sink=tracer.sink,
            system_prompt=system_prompt,
            memory_hits=memory_hits,
        )
        return loop.run(state)

    def _build_tool_registry(
        self,
        sandbox: Workspace,
        workspace_path: Path,
        repository_indexer: RepositoryIndexer | None = None,
    ) -> ToolRegistry:
        tools: list[Tool] = [
            *default_filesystem_tools(sandbox, self.settings.max_file_bytes),
            default_shell_tool(sandbox, self.settings.shell_timeout),
            default_search_tool(sandbox, self.settings.max_search_results, self.settings.max_file_bytes),
            *default_git_tools(str(workspace_path)),
        ]
        if repository_indexer is not None:
            tools.append(SemanticSearchTool(repository_indexer))
        registry = ToolRegistry(tools)
        if self.settings.enable_mcp:
            mcp_registry = MCPRegistry()
            for entry in self.settings.mcp_servers:
                name, separator, command = entry.partition("|")
                if separator:
                    mcp_registry.register_server(
                        name.strip(), StdioMCPClient.from_command_string(name.strip(), command)
                    )
            mcp_registry.add_to_registry(registry)
        return registry

    def _build_memory(self) -> LongTermMemory:
        # Chroma is optional; SQLite keyword search remains the always-on store.
        try:
            import chromadb  # type: ignore[import-not-found]

            collection_name = "pix_memories"
            chroma_client = chromadb.Client()
            collection = chroma_client.get_or_create_collection(collection_name)
            self._memory_store.chroma = collection
            if self.settings.api_key:
                from pix.embedding.openai import OpenAIEmbeddingProvider

                self._memory_store.embedding = OpenAIEmbeddingProvider(
                    self.settings.api_key.get_secret_value(),
                    api_base=self.settings.api_base,
                    model=self.settings.embedding_model,
                )
        except (ImportError, Exception):  # noqa: BLE001
            self._memory_store.chroma = None
        return LongTermMemory(self._memory_store)

    def _system_prompt(self, repository: RepositoryContext, plan: Plan, skill_texts: list[str]) -> str:
        sections = [
            "You are PiX, an autonomous software engineering agent.",
            "Your job is to complete the user's task with real repository work.",
            "Repository facts:",
            repository.summary,
            "Plan:",
            plan.render(),
            "Workflow:",
            "1. Inspect manifests, entrypoints and relevant code before editing.",
            "2. Make minimal, consistent changes and add or update tests.",
            "3. Run the detected verification command when it exists"
            + f" ({repository.test_command or 'no command detected'}).",
            "4. If verification fails, read the errors, fix the cause and rerun.",
            "5. Review the git diff before finishing.",
            "6. Commit only when all checks pass, using a concise conventional message.",
            "Security:",
            "- You operate inside the workspace sandbox only.",
            "- Never read or write files outside the workspace.",
            "- Never echo credentials, API keys, tokens or passwords.",
            "- Do not run destructive shell commands or git history rewrites.",
        ]
        if skill_texts:
            sections.append("Active skills:")
            sections.extend(skill_texts)
        return "\n\n".join(sections)

    def _persist_completion(
        self,
        record: SessionRecord,
        state: AgentState,
        verification_result: VerificationResult,
    ) -> None:
        record.status = state.status.value
        record.finished_at = datetime.now(UTC)
        record.plan = state.plan.model_dump(mode="json") if state.plan else None
        record.final_answer = state.final_answer
        record.summary = state.summary or verification_result.summary()
        record.error = state.error
        self._session_store.update(record)
