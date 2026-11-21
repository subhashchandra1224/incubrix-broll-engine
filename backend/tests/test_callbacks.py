"""Tests for HMAC-SHA256 callback signing and delivery (Integration Standard #3)."""
from __future__ import annotations

import hashlib
import hmac
import json

import httpx
from sqlalchemy import text

from app.db.database import SessionLocal, init_db
from app.models.job import Job
from app.schemas.job import JobCreateRequest
from app.services import job_service
from app.utils import callbacks


def test_sign_matches_hmac_sha256():
    payload = {"job_id": "job_1", "status": "succeeded"}
    secret = "topsecret"
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert callbacks.sign(payload, secret) == expected


def test_sign_is_deterministic_and_secret_dependent():
    payload = {"a": 1, "b": 2}
    assert callbacks.sign(payload, "k1") == callbacks.sign(payload, "k1")
    assert callbacks.sign(payload, "k1") != callbacks.sign(payload, "k2")


def test_send_includes_correct_signature_header():
    received: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        received["body"] = request.content
        received["headers"] = dict(request.headers)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    try:
        payload = {"job_id": "job_x", "status": "succeeded"}
        secret = "abc123"
        callbacks.send("http://callback.example/cb", payload, secret, client=client)
    finally:
        client.close()

    body = received["body"]
    # The header equals HMAC over the exact bytes that were sent.
    assert callbacks.sign_bytes(body, secret) == received["headers"]["x-incubrix-signature"]
    # And those bytes are the canonical JSON of the payload.
    assert json.loads(body) == payload


def test_worker_sends_signed_callback_on_success(monkeypatch):
    """A finished job with a callback_url + configured secret triggers a signed callback."""
    sent: list = []

    def fake_send(url, payload, secret, **kwargs):
        sent.append((url, payload, secret))

    monkeypatch.setattr(callbacks, "send", fake_send)

    import app.workers.runner as runner_mod

    monkeypatch.setattr(runner_mod.settings, "callback_hmac_secret", "sekret")

    init_db()
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM jobs"))
        db.commit()
    finally:
        db.close()

    db = SessionLocal()
    try:
        req = JobCreateRequest(
            script="cb script", aspect_ratios=["16:9"], callback_url="http://cb.example/x"
        )
        job_id = job_service.create_or_get_job(db, req, idempotency_key=None).id
    finally:
        db.close()

    runner_mod.process_next_job()

    assert len(sent) == 1
    url, payload, secret = sent[0]
    assert url == "http://cb.example/x"
    assert payload["job_id"] == job_id
    assert payload["status"] == "succeeded"
    assert secret == "sekret"

    db = SessionLocal()
    try:
        assert db.get(Job, job_id).status == "succeeded"
    finally:
        db.close()
