"""Agent run routes."""

from __future__ import annotations

import asyncio
import json
import queue
import threading

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from pix.agent.agent import Agent
from pix.api.access import resolve_api_workspace
from pix.api.schemas import AgentRunRequest, AgentRunResponse
from pix.errors import PiXError, SecurityError

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _agent(request: Request) -> Agent:
    return request.app.state.agent


def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


def _stream_event_name(event_type: str) -> str:
    return {
        "LLM_REQUEST": "thinking",
        "CONTEXT_BUILD": "thinking",
        "REPOSITORY_ANALYZED": "thinking",
        "PLAN_CREATED": "thinking",
        "TOOL_CALL": "tool_call",
        "TOOL_RESULT": "tool_result",
        "TOKEN": "token",
        "AGENT_FINISHED": "completed",
        "AGENT_ERROR": "error",
    }.get(event_type, event_type.lower())


@router.post("/run", response_model=AgentRunResponse)
def run_agent(request: Request, body: AgentRunRequest) -> AgentRunResponse:
    workspace = resolve_api_workspace(request.app.state.settings, body.workspace)
    try:
        result = _agent(request).run(
            body.task,
            workspace=workspace,
            model=body.model,
            max_iterations=body.max_iterations,
            auto_verify=body.auto_verify,
            auto_fix_attempts=body.auto_fix_attempts,
        )
    except SecurityError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PiXError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    state = result.state
    return AgentRunResponse(
        session_id=state.session_id,
        task=state.task,
        workspace=str(state.workspace),
        status=state.status.value,
        message=result.message,
        plan=state.plan.model_dump(mode="json") if state.plan else None,
        summary=state.summary,
        error=state.error,
        created_at=state.started_at,
    )


@router.post("/run/stream")
async def run_agent_stream(request: Request, body: AgentRunRequest) -> StreamingResponse:
    """Run an agent and stream planning, tool, token and completion events."""

    executor = _agent(request).executor
    workspace = resolve_api_workspace(request.app.state.settings, body.workspace)
    outcome: dict[str, object] = {}

    def target() -> None:
        try:
            result = executor.execute(
                body.task,
                workspace=workspace,
                model=body.model,
                max_iterations=body.max_iterations,
                auto_verify=body.auto_verify,
                auto_fix_attempts=body.auto_fix_attempts,
                stream=True,
            )
            outcome["result"] = result
        except Exception as exc:  # noqa: BLE001 - stream boundary
            outcome["error"] = exc

    thread = threading.Thread(target=target, name="pix-agent-stream", daemon=True)

    async def events():
        bus = executor.event_bus
        subscriber = bus.subscribe()
        thread.start()
        try:
            yield _sse("thinking", {"message": "Agent run started", "task": body.task})
            own_session_id: str | None = None
            while thread.is_alive() or not subscriber.empty():
                if await request.is_disconnected():
                    return
                try:
                    live = await asyncio.to_thread(subscriber.get, timeout=0.1)
                except queue.Empty:
                    continue
                if await request.is_disconnected():
                    return
                if own_session_id is None:
                    if live.type != "SESSION_STARTED":
                        continue
                    own_session_id = live.session_id
                elif live.session_id != own_session_id:
                    continue
                event_name = _stream_event_name(live.type)
                if event_name == "completed":
                    # The final completed event is emitted below after the result is
                    # available, so keep intermediate finish events from the tracer
                    # from duplicating it.
                    continue
                yield _sse(event_name, {"session_id": live.session_id, **live.payload})
            thread.join()
            if "error" in outcome:
                error = outcome["error"]
                yield _sse("error", {"message": str(error), "type": error.__class__.__name__})
                return
            result = outcome.get("result")
            if result is None:
                yield _sse("error", {"message": "Agent run finished without a result"})
                return
            state = result.state
            yield _sse(
                "completed",
                {
                    "session_id": state.session_id,
                    "status": state.status.value,
                    "message": result.message,
                    "summary": state.summary,
                    "iterations": state.iteration,
                    "tool_calls": len(state.observations),
                },
            )
        finally:
            bus.unsubscribe(subscriber)

    return StreamingResponse(events(), media_type="text/event-stream")
