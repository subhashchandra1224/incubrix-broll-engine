"""Middleware: per-request correlation id.

Reads X-Correlation-Id from the request (or generates a new UUID), stores it in
a context variable so every log line in the request carries it, and echoes it
back on the response. This satisfies Integration Standard point 8.
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import correlation_id_var


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Assign/propagate X-Correlation-Id for every request."""

    HEADER = "X-Correlation-Id"

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        # Starlette headers are case-insensitive, so the lower-case lookup works.
        cid = request.headers.get(self.HEADER.lower()) or str(uuid.uuid4())
        token = correlation_id_var.set(cid)
        try:
            response: Response = await call_next(request)
        finally:
            correlation_id_var.reset(token)
        response.headers[self.HEADER] = cid
        return response
