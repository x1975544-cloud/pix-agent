"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pix.agent.agent import Agent
from pix.api.routes import catalog, sessions, traces
from pix.api.routes.agent import router as agent_router
from pix.config.settings import Settings
from pix.errors import PiXError
from pix.logging import setup_logging


def create_app(
    settings: Settings | None = None,
    *,
    agent: Agent | None = None,
) -> FastAPI:
    """Build the API with an optional injected agent for tests."""

    runtime_settings = settings or Settings()
    setup_logging(runtime_settings.log_level, use_rich=False)
    runtime_agent = agent or Agent(runtime_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        runtime_agent.close()

    application = FastAPI(
        title="PiX Agent API",
        version="0.1.0",
        description="Run and inspect autonomous software engineering agents.",
        lifespan=lifespan,
    )
    application.state.settings = runtime_settings
    application.state.agent = runtime_agent
    application.include_router(agent_router)
    application.include_router(sessions.router)
    application.include_router(traces.router)
    application.include_router(catalog.router)

    @application.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "service": "pix-agent", "version": "0.1.0"}

    @application.exception_handler(PiXError)
    async def pix_error_handler(_: Request, exc: PiXError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    return application


app = create_app()
