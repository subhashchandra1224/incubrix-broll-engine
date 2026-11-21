"""Tests for /health and /ready."""
from __future__ import annotations


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready_ok(client):
    r = client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"]["status"] == "ready"
    assert body["checks"]["storage"]["status"] == "ready"
    assert body["checks"]["storage"]["backend"] == "local"


def test_ready_echoes_correlation_id(client):
    r = client.get("/ready", headers={"X-Correlation-Id": "abc-123"})
    assert r.status_code == 200
    assert r.headers["X-Correlation-Id"] == "abc-123"
