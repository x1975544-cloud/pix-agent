"""Agent run routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from pix.agent.agent import Agent
from pix.api.schemas import AgentRunRequest, AgentRunResponse
from pix.errors import PiXError, SecurityError

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _agent(request: Request) -> Agent:
    return request.app.state.agent


@router.post("/run", response_model=AgentRunResponse)
def run_agent(request: Request, body: AgentRunRequest) -> AgentRunResponse:
    try:
        result = _agent(request).run(
            body.task,
            workspace=body.workspace,
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
