"""Structured logging.

Every log line is one JSON object: timestamp, level, logger, message, plus
correlation_id and job_id when they are in scope. Those two ids come from
context variables (set by the correlation-id middleware per request and by
the worker per job), so any code in the request/job flow can log them without
threading the ids through every function call.

Set LOG_JSON=false for human-readable output during local development.
"""
from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

# Per-request / per-job ids, available anywhere in the call stack.
correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)
job_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "job_id", default=None
)

# Attributes that always exist on a LogRecord and are NOT caller-supplied "extra".
_RESERVED_RECORD_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message", "getMessage",
}


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log record."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        cid = correlation_id_var.get()
        jid = job_id_var.get()
        if cid:
            payload["correlation_id"] = cid
        if jid:
            payload["job_id"] = jid
        # Attach anything the caller passed via logger.info("...", extra={...}).
        for key, value in vars(record).items():
            if key in _RESERVED_RECORD_ATTRS or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO", json_output: bool = True) -> None:
    """Configure the root logger. Safe to call more than once."""
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in list(root.handlers):
        root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s %(message)s")
        )
    root.addHandler(handler)
    # uvicorn's access log duplicates request info; keep it quiet.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
