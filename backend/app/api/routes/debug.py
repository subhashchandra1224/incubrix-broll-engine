"""Test-only routes used to exercise the error envelope and request validation.

Registered only when ENVIRONMENT != prod (see app.main.create_app). These are
not part of the public API and are excluded from documentation reliance.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.errors import (
    ConflictError,
    InvalidInputError,
    NotFoundError,
    UpstreamProviderError,
)

router = APIRouter(prefix="/api/v1/_debug", tags=["debug"])


@router.get("/error/{code}")
def raise_error(code: str) -> None:
    """Raise a specific error so tests can check the response envelope."""
    if code == "invalid_input":
        raise InvalidInputError("test invalid input", {"field": "x"})
    if code == "not_found":
        raise NotFoundError("test not found")
    if code == "conflict":
        raise ConflictError("test conflict")
    if code == "upstream":
        raise UpstreamProviderError("test upstream provider error")
    if code == "boom":
        raise RuntimeError("unexpected boom")
    raise NotFoundError(f"unknown debug code: {code}")


class EchoIn(BaseModel):
    name: str
    count: int


@router.post("/echo")
def echo(payload: EchoIn) -> EchoIn:
    """Echo back the body; used to trigger RequestValidationError on bad input."""
    return payload
