"""Trace timeline routes."""

from __future__ import annotations

import asyncio
import json
import queue

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

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


@router.get("/{session_id}/stream")
async def stream_trace(request: Request, session_id: str) -> StreamingResponse:
    """Stream stored and live trace events for one session."""

    agent = request.app.state.agent
    terminal_statuses = {"success", "failed", "cancelled"}

    async def events():
        try:
            agent.session(session_id)
        except SessionNotFoundError:
            yield f"event: error\ndata: {json.dumps({'message': 'Session not found'})}\n\n"
            return

        bus = agent.executor.event_bus
        subscriber = bus.subscribe()
        try:
            seen_event_ids: set[str] = set()
            for event in agent.trace(session_id):
                seen_event_ids.add(event["id"])
                yield f"event: {event['type'].lower()}\ndata: {json.dumps(event, default=str)}\n\n"
            while True:
                if await request.is_disconnected():
                    return
                try:
                    live = subscriber.get_nowait()
                except queue.Empty:
                    current = agent.session(session_id)
                    if current.status in terminal_statuses:
                        completed = {"session_id": session_id, "status": current.status}
                        yield f"event: completed\ndata: {json.dumps(completed)}\n\n"
                        return
                    try:
                        live = await asyncio.to_thread(subscriber.get, timeout=0.25)
                    except queue.Empty:
                        continue
                if live.session_id != session_id or live.id in seen_event_ids:
                    continue
                seen_event_ids.add(live.id)
                yield f"event: {live.type.lower()}\ndata: {json.dumps(live.to_dict(), default=str)}\n\n"
                if live.type in {"AGENT_FINISHED", "AGENT_ERROR"}:
                    return
        finally:
            bus.unsubscribe(subscriber)

    return StreamingResponse(events(), media_type="text/event-stream")
