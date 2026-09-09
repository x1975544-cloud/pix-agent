"""Public endpoints for the deterministic autonomous coding dashboard."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from pix.coding_demo import load_coding_dashboard_snapshot, run_coding_dashboard
from pix.errors import PiXError

router = APIRouter(prefix="/api/coding-demo", tags=["coding-demo"])


@router.get("", response_model=dict[str, Any])
def get_coding_demo_snapshot() -> dict[str, Any]:
    """Return the persisted deterministic snapshot without rerunning the demo."""

    snapshot = load_coding_dashboard_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No coding dashboard snapshot has been generated yet")
    return snapshot


@router.post("/run", response_model=dict[str, Any])
def run_coding_demo_snapshot() -> dict[str, Any]:
    """Run and persist one GIF-friendly deterministic coding demo."""

    try:
        return run_coding_dashboard()
    except PiXError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
