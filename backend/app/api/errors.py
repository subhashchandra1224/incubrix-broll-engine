"""Standard error envelope and FastAPI exception handlers.

Every error response is JSON and shaped like:
    {"error": {"code": "...", "message": "...", "retryable": false, "details": {}}}
Codes are UPPER_SNAKE_CASE and listed in the README (Integration Standard #5).

Why a custom exception hierarchy: the worker uses `retryable` to decide
whether a failed job should be retried or fail fast, and uses the code to
decide provider fallback (e.g. UPSTREAM_PROVIDER_ERROR).
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = logging.getLogger(__name__)


class BrollError(Exception):
    """Base class for all expected application errors."""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    retryable: bool = False

    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
        *,
        status_code: int | None = None,
    ) -> None:
        self.message = message
        self.details = details or {}
        if status_code is not None:
            self.status_code = status_code
        super().__init__(message)


class InvalidInputError(BrollError):
    """400 - malformed or semantically invalid request (incl. schema validation)."""

    code = "INVALID_INPUT"
    status_code = 400


class NotFoundError(BrollError):
    """404 - requested resource does not exist."""

    code = "NOT_FOUND"
    status_code = 404


class ConflictError(BrollError):
    """409 - idempotency / identity conflict."""

    code = "CONFLICT"
    status_code = 409


class RateLimitError(BrollError):
    """429 - too many requests; retryable after a delay."""

    code = "RATE_LIMITED"
    status_code = 429
    retryable = True


class UpstreamProviderError(BrollError):
    """502 - a configured AI/footage provider failed; try another provider or retry."""

    code = "UPSTREAM_PROVIDER_ERROR"
    status_code = 502
    retryable = True


class FootageUnavailableError(BrollError):
    """502 - all configured footage providers failed or returned no usable clips."""

    code = "FOOTAGE_UNAVAILABLE"
    status_code = 502
    retryable = False


class ProviderNotConfiguredError(BrollError):
    """500 - a selected provider adapter is not available (e.g. real provider without API keys)."""

    code = "PROVIDER_NOT_CONFIGURED"
    status_code = 500
    retryable = False


# Map plain FastAPI HTTPExceptions to our UPPER_SNAKE codes.
_STATUS_TO_CODE = {
    400: "INVALID_INPUT",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "INVALID_INPUT",
    429: "RATE_LIMITED",
}


def _envelope(code: str, message: str, retryable: bool, details: Any = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "retryable": retryable, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all error handlers to the app."""

    @app.exception_handler(BrollError)
    async def _handle_broll(_request: Request, exc: BrollError) -> JSONResponse:
        log.warning(
            "BrollError raised: code=%s status=%s message=%s details=%s",
            exc.code, exc.status_code, exc.message, exc.details,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.retryable, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # Body/schema validation failures are reported with the same envelope.
        return JSONResponse(
            status_code=422,
            content=_envelope(
                "INVALID_INPUT",
                "Request validation failed.",
                False,
                {"errors": jsonable_encoder(exc.errors())},
            ),
        )

    @app.exception_handler(HTTPException)
    async def _handle_http(_request: Request, exc: HTTPException) -> JSONResponse:
        code = _STATUS_TO_CODE.get(exc.status_code, "INTERNAL_ERROR")
        retryable = exc.status_code >= 500
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, str(exc.detail), retryable),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
        # Log the full traceback server-side; never leak internals to the client.
        log.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content=_envelope("INTERNAL_ERROR", "An internal error occurred.", False),
        )
