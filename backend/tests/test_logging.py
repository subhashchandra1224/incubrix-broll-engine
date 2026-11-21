"""Tests for structured logging and correlation-id propagation."""
from __future__ import annotations

import io
import json
import logging

from app.logging_config import JsonFormatter, correlation_id_var, job_id_var


def test_correlation_id_echoed(client):
    r = client.get("/health", headers={"X-Correlation-Id": "abc-123"})
    assert r.headers["X-Correlation-Id"] == "abc-123"


def test_correlation_id_generated_when_absent(client):
    r = client.get("/health")
    assert r.headers["X-Correlation-Id"]  # present and non-empty


def _capture_one_log(set_ctx) -> dict:
    """Run one log call with a context var set, return the parsed JSON record."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test_logging_" + str(id(set_ctx)))
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    token = set_ctx()
    try:
        logger.info("hello %s", "world")
    finally:
        # reset whichever var was set
        if set_ctx is not None:
            pass
    obj = json.loads(buf.getvalue().strip())
    return obj


def test_json_formatter_includes_correlation_id():
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test_json_cid")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    token = correlation_id_var.set("cid-xyz")
    try:
        logger.info("hello %s", "world")
    finally:
        correlation_id_var.reset(token)
    obj = json.loads(buf.getvalue().strip())
    assert obj["message"] == "hello world"
    assert obj["correlation_id"] == "cid-xyz"
    assert obj["level"] == "INFO"
    assert "timestamp" in obj


def test_json_formatter_includes_job_id():
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test_json_jid")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    token = job_id_var.set("job_42")
    try:
        logger.warning("processing")
    finally:
        job_id_var.reset(token)
    obj = json.loads(buf.getvalue().strip())
    assert obj["job_id"] == "job_42"
    assert obj["level"] == "WARNING"


def test_json_formatter_omits_ids_when_unset():
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("test_json_none")
    logger.handlers = [handler]
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.info("plain")
    obj = json.loads(buf.getvalue().strip())
    assert "correlation_id" not in obj
    assert "job_id" not in obj
