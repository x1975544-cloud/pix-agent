"""Trace timeline routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from pix.api.schemas import TraceEvent, TraceResponse
from pix.errors import SessionNotFoundError

router = APIRouter(prefix="/api/traces", tags=["traces"])


@router.get("/{session_id}", response_model=TraceResponse)
def get_trace(request: Request, session_id: str) -> TraceResponse:
    try:
        events = request.app.state.agent.trace(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TraceResponse(session_id=session_id, events=[TraceEvent(**event) for event in events])
