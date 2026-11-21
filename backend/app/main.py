"""FastAPI application factory and entrypoint.

Run locally (from the backend/ folder) with:
    uvicorn app.main:app --reload
or:
    python -m uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.middleware import CorrelationIdMiddleware
from app.api.routes import debug, health, jobs
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: configure logging and ensure the DB + storage dir exist."""
    from app.logging_config import setup_logging

    setup_logging(level=settings.log_level, json_output=settings.log_json)

    from app.db.database import init_db

    init_db()
    yield
    # Shutdown: nothing to clean up yet (Phase 3 will stop the worker cleanly).


def create_app() -> FastAPI:
    """Build the FastAPI app. Called once at import time to create `app`."""
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Script and Voiceover to B-roll Video Engine. Accepts a script, an "
            "audio voiceover, or a scene list and returns a finished, "
            "licence-clean B-roll video with captions and a full record of where "
            "every clip came from."
        ),
        openapi_url="/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(health.router)  # /health, /ready at root
    app.include_router(jobs.router, prefix=settings.api_v1_prefix)  # /api/v1/broll/jobs, /api/v1/jobs/{id}
    if not settings.is_production:
        # Test-only routes to exercise the error envelope and logging.
        app.include_router(debug.router)
    register_exception_handlers(app)
    return app


app = create_app()
