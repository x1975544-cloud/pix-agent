"""Public context manager facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pix.agent.state import AgentState
from pix.analysis.repository import RepositoryContext
from pix.context.builder import BuiltContext, ContextBuilder, ContextPriority, ContextSection
from pix.context.compression import ContextCompressor
from pix.context.window import estimate_tokens


@dataclass(slots=True)
class ContextManager:
    """Build and compress agent context using the configured token budget."""

    budget_tokens: int

    def build(
        self,
        state: AgentState,
        *,
        repository_context: RepositoryContext | None = None,
        memory_hits: list[dict[str, Any]] | None = None,
        skill_texts: list[str] | None = None,
        system_prompt: str | None = None,
        recent_max_messages: int = 40,
    ) -> BuiltContext:
        sections = self._build_sections(
            repository_context=repository_context,
            memory_hits=memory_hits or [],
            skill_texts=skill_texts or [],
        )
        base_system = system_prompt or self.default_system_prompt()
        builder = ContextBuilder(self.budget_tokens)
        built = builder.build(
            base_system=base_system,
            task=state.task,
            conversation=state.messages,
            extra_sections=sections,
            recent_max_messages=recent_max_messages,
        )
        if built.truncated and state.messages:
            compressor = ContextCompressor(keep_recent_messages=14)
            compressed_messages, summary = compressor.compress(state.messages)
            # Replace history with the summarized version only when a full
            # rebuild would exceed budget again.
            full_text = "\n".join(message.content for message in compressed_messages)
            if estimate_tokens(full_text) > self.budget_tokens // 2:
                rebuilt = builder.build(
                    base_system=base_system,
                    task=state.task,
                    conversation=compressed_messages,
                    extra_sections=sections,
                    recent_max_messages=recent_max_messages,
                )
                rebuilt.compression_summary = summary
                return rebuilt
        return built

    @staticmethod
    def default_system_prompt() -> str:
        return (
            "You are PiX, an autonomous software engineering agent. "
            "You plan, inspect, edit, verify and commit with tools. "
            "Use the smallest number of tool calls that makes progress. "
            "Never reveal credentials and never try to access paths outside the workspace."
        )

    def _build_sections(
        self,
        *,
        repository_context: RepositoryContext | None,
        memory_hits: list[dict[str, Any]],
        skill_texts: list[str],
    ) -> list[ContextSection]:
        sections: list[ContextSection] = []
        if repository_context:
            sections.append(
                ContextSection(
                    "repository",
                    f"Repository context:\n{repository_context.summary}\nProject root: {repository_context.root}",
                    ContextPriority.RELEVANT_CODE,
                )
            )
        if skill_texts:
            sections.append(
                ContextSection(
                    "skills",
                    "Active skill instructions:\n" + "\n\n".join(skill_texts),
                    ContextPriority.SYSTEM,
                )
            )
        if memory_hits:
            formatted = "\n".join(
                f"- {item.get('content', '')[:500]}" for item in memory_hits[:10] if item.get("content")
            )
            if formatted:
                sections.append(ContextSection("memory", f"Relevant memory:\n{formatted}", ContextPriority.MEMORY))
        return sections


__all__ = [
    "BuiltContext",
    "ContextBuilder",
    "ContextCompressor",
    "ContextManager",
    "ContextPriority",
    "ContextSection",
]
