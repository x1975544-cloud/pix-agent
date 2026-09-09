"""API authentication and workspace access helpers."""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pix.config.settings import Settings

_bearer = HTTPBearer(auto_error=False)


def require_api_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Require the configured PIX_API_TOKEN on protected API routes."""

    settings: Settings = request.app.state.settings
    expected = settings.api_token.get_secret_value() if settings.api_token else None
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="PIX_API_TOKEN is not configured",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not secrets.compare_digest(credentials.credentials, expected):
        raise HTTPException(
            status_code=401,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def resolve_api_workspace(settings: Settings, workspace: str | None) -> Path:
    """Resolve an API workspace and reject anything outside PIX_WORKSPACE."""

    root = Path(settings.workspace).expanduser().resolve()
    if not root.is_dir():
        raise HTTPException(
            status_code=503,
            detail=f"PIX_WORKSPACE is not a directory: {root}",
        )

    candidate = Path(workspace).expanduser() if workspace else root
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Workspace must be inside PIX_WORKSPACE root: {root}",
        ) from exc
    if not candidate.is_dir():
        raise HTTPException(status_code=400, detail=f"Workspace does not exist: {candidate}")
    return candidate
