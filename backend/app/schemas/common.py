"""Shared response schemas, including the standard error envelope."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(..., description="UPPER_SNAKE_CASE error code.")
    message: str = Field(..., description="Human-readable error message.")
    retryable: bool = Field(False, description="Whether retrying the request could succeed.")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Structured extra information about the error."
    )


class ErrorResponse(BaseModel):
    """Every error response is wrapped in {"error": {...}}."""
    error: ErrorDetail
