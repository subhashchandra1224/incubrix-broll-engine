"""Tests for the standard JSON error envelope."""
from __future__ import annotations

import re


def test_invalid_input_envelope(client):
    r = client.get("/api/v1/_debug/error/invalid_input")
    assert r.status_code == 400
    err = r.json()["error"]
    assert err["code"] == "INVALID_INPUT"
    assert err["retryable"] is False
    assert err["details"] == {"field": "x"}


def test_not_found_envelope(client):
    r = client.get("/api/v1/_debug/error/not_found")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_conflict_envelope(client):
    r = client.get("/api/v1/_debug/error/conflict")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "CONFLICT"


def test_upstream_retryable(client):
    r = client.get("/api/v1/_debug/error/upstream")
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "UPSTREAM_PROVIDER_ERROR"
    assert r.json()["error"]["retryable"] is True


def test_unhandled_returns_internal_error(client):
    r = client.get("/api/v1/_debug/error/boom")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "INTERNAL_ERROR"
    assert r.json()["error"]["retryable"] is False


def test_validation_error_envelope(client):
    r = client.post("/api/v1/_debug/echo", json={})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "INVALID_INPUT"
    assert "errors" in err["details"]


def test_echo_ok(client):
    r = client.post("/api/v1/_debug/echo", json={"name": "a", "count": 3})
    assert r.status_code == 200
    assert r.json() == {"name": "a", "count": 3}


def test_error_codes_are_upper_snake(client):
    codes = [
        client.get("/api/v1/_debug/error/invalid_input").json()["error"]["code"],
        client.get("/api/v1/_debug/error/not_found").json()["error"]["code"],
        client.get("/api/v1/_debug/error/conflict").json()["error"]["code"],
        client.get("/api/v1/_debug/error/upstream").json()["error"]["code"],
        client.get("/api/v1/_debug/error/boom").json()["error"]["code"],
    ]
    for code in codes:
        assert re.fullmatch(r"[A-Z][A-Z0-9_]*", code), f"{code!r} is not UPPER_SNAKE_CASE"
