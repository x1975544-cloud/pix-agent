"""Session listing and detail routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from pix.api.schemas import SessionDetail, SessionSummary
from pix.errors import SessionNotFoundError

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSummary])
def list_sessions(request: Request, limit: int = 50) -> list[SessionSummary]:
    sessions = request.app.state.agent.sessions(limit=max(1, min(limit, 500)))
    return [SessionSummary(**session.model_dump(mode="json")) for session in sessions]


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(request: Request, session_id: str) -> SessionDetail:
    try:
        session = request.app.state.agent.session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionDetail(**session.model_dump(mode="json"))
