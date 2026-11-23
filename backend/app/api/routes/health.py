"""/health (liveness) and /ready (readiness) endpoints.

/health: the app process is up. Does not check dependencies (so a flaky DB
does not kill liveness probes). Returns {"status": "ok"}.
/ready: dependencies are reachable - database and storage. Returns 200 if all
checks pass, 503 otherwise, with a per-check breakdown.
"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings

router = APIRouter(tags=["health"])
log = logging.getLogger(__name__)
settings = get_settings()


@router.get("/health", summary="Liveness probe")
def health() -> dict:
    """App process is up."""
    return {"status": "ok"}


@router.get("/ready", summary="Readiness probe")
def ready() -> JSONResponse:
    """All dependencies reachable."""
    checks: dict = {}
    overall = True

    # Database: open a connection and run SELECT 1.
    try:
        from app.db.database import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = {"status": "ready"}
    except Exception as exc:  # noqa: BLE001
        overall = False
        checks["database"] = {"status": "unhealthy", "error": str(exc)}

    # Storage: the local root must be creatable and writable.
    try:
        from app.utils.storage import get_storage
        store = get_storage()
        storage_ok = store.available()
        if storage_ok:
            checks["storage"] = {
                "status": "ready",
                "backend": settings.storage_backend,
                "root": settings.storage_local_root,
            }
        else:
            raise RuntimeError("Storage backend check returned False")
    except Exception as exc:  # noqa: BLE001
        overall = False
        checks["storage"] = {"status": "unhealthy", "error": str(exc)}

    body = {"status": "ready" if overall else "unhealthy", "checks": checks}
    return JSONResponse(
        status_code=status.HTTP_200_OK if overall else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=body,
    )
