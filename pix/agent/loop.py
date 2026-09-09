"""The core reason-act-observe loop shared by every PiX agent."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pix.agent.state import AgentState, AgentStatus, ToolObservation
from pix.context.manager import ContextManager
from pix.errors import AgentLoopError, ProviderError, ToolTimeoutError
from pix.providers.base import ChatMessage, LLMProvider
from pix.tools.base import ToolResult
from pix.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

EventSink = Callable[[str, dict[str, Any]], None]


@dataclass(slots=True)
class LoopOptions:
    """Knobs that can be changed per run without touching settings globally."""

    max_iterations: int = 30
    tool_timeout: float = 60.0
    provider_retries: int = 2
    model: str | None = None


class AgentLoop:
    """Execute the agent loop until a final answer or a stop condition."""

    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        context_manager: ContextManager,
        *,
        options: LoopOptions | None = None,
        event_sink: EventSink | None = None,
        system_prompt: str | None = None,
        memory_hits: list[dict[str, Any]] | None = None,
    ) -> None:
        self.provider = provider
        self.registry = registry
        self.context_manager = context_manager
        self.options = options or LoopOptions()
        self.event_sink = event_sink or (lambda _kind, _payload: None)
        self.system_prompt = system_prompt
        self.memory_hits = memory_hits or []
        self.cancelled = threading.Event()

    def cancel(self) -> None:
        self.cancelled.set()

    def run(self, state: AgentState) -> AgentState:
        if state.status in {AgentStatus.SUCCESS, AgentStatus.CANCELLED}:
            return state
        state.status = AgentStatus.RUNNING
        try:
            while state.iteration < self.options.max_iterations:
                if self.cancelled.is_set():
                    state.status = AgentStatus.CANCELLED
                    state.final_answer = "Run cancelled by user."
                    return state
                state.iteration += 1
                self.event_sink("iteration_started", {"iteration": state.iteration})
                built = self.context_manager.build(
                    state,
                    memory_hits=self.memory_hits,
                    system_prompt=self.system_prompt,
                )
                self.event_sink(
                    "context_build",
                    {
                        "iteration": state.iteration,
                        "token_estimate": built.token_estimate,
                        "messages": len(built.messages),
                        "truncated": built.truncated,
                    },
                )
                result = self._generate(built.system_prompt, built.messages, state.iteration)
                assistant_message = result.message
                state.add_message(assistant_message)
                self.event_sink(
                    "llm_response",
                    {
                        "iteration": state.iteration,
                        "content": assistant_message.content[:2000],
                        "tool_calls": [call.to_dict() for call in assistant_message.tool_calls],
                        "latency_seconds": result.latency_seconds,
                        "usage": result.usage.to_dict(),
                    },
                )
                if not assistant_message.tool_calls:
                    content = assistant_message.content.strip()
                    if not content:
                        raise AgentLoopError("Model returned an empty final message")
                    state.final_answer = content
                    state.status = AgentStatus.SUCCESS
                    self.event_sink("agent_finished", {"final_answer": content[:2000]})
                    return state

                for call in assistant_message.tool_calls:
                    if self.cancelled.is_set():
                        break
                    observation = self._execute_tool(state, call)
                    if observation.success:
                        state.add_message(
                            ChatMessage.tool(
                                tool_call_id=call.id,
                                content=ToolResult(
                                    success=True,
                                    output=observation.output,
                                    duration_seconds=observation.duration_seconds,
                                ).text,
                                name=call.name,
                            )
                        )
                    else:
                        state.add_message(
                            ChatMessage.tool(
                                tool_call_id=call.id,
                                content=ToolResult(
                                    success=False,
                                    error=observation.error or "Unknown tool error",
                                    duration_seconds=observation.duration_seconds,
                                ).text,
                                name=call.name,
                            )
                        )
                    state.add_tool_observation(observation)
                    self.event_sink(
                        "tool_result",
                        {
                            "call_id": call.id,
                            "name": call.name,
                            "success": observation.success,
                            "duration_seconds": observation.duration_seconds,
                        },
                    )
                if self.cancelled.is_set():
                    state.status = AgentStatus.CANCELLED
                    state.final_answer = "Run cancelled by user."
                    return state
            raise AgentLoopError(f"Agent reached max iterations ({self.options.max_iterations}) without a final answer")
        except Exception as exc:
            state.status = AgentStatus.FAILED
            state.error = str(exc)
            self.event_sink("agent_error", {"error": state.error, "type": exc.__class__.__name__})
            raise

    def _generate(self, system_prompt: str, messages: list[ChatMessage], iteration: int) -> Any:
        attempts = self.options.provider_retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            if self.cancelled.is_set():
                raise AgentLoopError("Cancelled")
            try:
                self.event_sink(
                    "llm_request",
                    {
                        "iteration": iteration,
                        "attempt": attempt + 1,
                        "system_tokens": len(system_prompt) // 4,
                        "messages": len(messages),
                    },
                )
                result = self.provider.generate(
                    [ChatMessage.system(system_prompt), *messages],
                    self.registry.schemas(),
                    model=self.options.model,
                )
                return result
            except ProviderError as exc:
                last_error = exc
                delay = 0.5 * (2**attempt)
                logger.warning("Provider error on attempt %s, retrying in %ss: %s", attempt + 1, delay, exc)
                time.sleep(delay)
        assert last_error is not None
        raise AgentLoopError(f"Provider request failed after {attempts} attempts: {last_error}")

    def _execute_tool(self, state: AgentState, call: Any) -> ToolObservation:
        name = call.name
        arguments = call.arguments or {}
        started = time.perf_counter()
        if not self.registry.has(name):
            duration = time.perf_counter() - started
            return ToolObservation(
                call_id=call.id,
                name=name,
                arguments=arguments,
                success=False,
                output=None,
                error=f"Unknown tool: {name}",
                duration_seconds=duration,
            )
        tool = self.registry.get(name)
        self.event_sink("tool_call", {"name": name, "arguments": arguments})
        try:
            result = tool.execute(arguments)
        except ToolTimeoutError as exc:
            duration = time.perf_counter() - started
            return ToolObservation(
                call_id=call.id,
                name=name,
                arguments=arguments,
                success=False,
                output=None,
                error=str(exc),
                duration_seconds=duration,
            )
        duration = time.perf_counter() - started
        return ToolObservation(
            call_id=call.id,
            name=name,
            arguments=arguments,
            success=result.success,
            output=result.output,
            error=result.error,
            duration_seconds=duration,
        )


__all__ = ["AgentLoop", "LoopOptions"]
