"""Tests for the job API: POST /api/v1/broll/jobs and GET /api/v1/jobs/{id}."""
from __future__ import annotations


def _script_payload(**overrides) -> dict:
    payload = {"script": "A short script about saving money.", "aspect_ratios": ["16:9"]}
    payload.update(overrides)
    return payload


def test_create_job_returns_202_with_links(client):
    r = client.post("/api/v1/broll/jobs", json=_script_payload())
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "queued"
    assert body["job_id"].startswith("job_")
    assert body["status_url"] == f"/api/v1/jobs/{body['job_id']}"


def test_get_job_status(client):
    r = client.post("/api/v1/broll/jobs", json=_script_payload())
    job_id = r.json()["job_id"]
    g = client.get(f"/api/v1/jobs/{job_id}")
    assert g.status_code == 200
    body = g.json()
    assert body["job_id"] == job_id
    assert body["status"] == "queued"
    assert body["progress"] == 0
    assert body["result"] is None
    assert body["error"] is None


def test_get_unknown_job_returns_not_found_envelope(client):
    r = client.get("/api/v1/jobs/job_does_not_exist")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_idempotency_same_key_same_body_returns_same_job(client):
    headers = {"Idempotency-Key": "key-1"}
    r1 = client.post("/api/v1/broll/jobs", json=_script_payload(), headers=headers)
    r2 = client.post("/api/v1/broll/jobs", json=_script_payload(), headers=headers)
    assert r1.status_code == 202 and r2.status_code == 202
    assert r1.json()["job_id"] == r2.json()["job_id"]


def test_idempotency_different_keys_create_different_jobs(client):
    r1 = client.post("/api/v1/broll/jobs", json=_script_payload(), headers={"Idempotency-Key": "k-a"})
    r2 = client.post("/api/v1/broll/jobs", json=_script_payload(), headers={"Idempotency-Key": "k-b"})
    assert r1.json()["job_id"] != r2.json()["job_id"]


def test_idempotency_same_key_different_body_conflicts(client):
    headers = {"Idempotency-Key": "key-conflict"}
    r1 = client.post("/api/v1/broll/jobs", json=_script_payload(script="one"), headers=headers)
    r2 = client.post("/api/v1/broll/jobs", json=_script_payload(script="two"), headers=headers)
    assert r1.status_code == 202
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "CONFLICT"


def test_no_key_allows_multiple_jobs(client):
    r1 = client.post("/api/v1/broll/jobs", json=_script_payload())
    r2 = client.post("/api/v1/broll/jobs", json=_script_payload())
    assert r1.json()["job_id"] != r2.json()["job_id"]


def test_missing_input_rejected(client):
    r = client.post("/api/v1/broll/jobs", json={"aspect_ratios": ["16:9"]})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_INPUT"


def test_empty_script_rejected(client):
    r = client.post("/api/v1/broll/jobs", json={"script": "   ", "aspect_ratios": ["16:9"]})
    assert r.status_code in (400, 422)
    assert r.json()["error"]["code"] == "INVALID_INPUT"


def test_multiple_inputs_rejected(client):
    r = client.post(
        "/api/v1/broll/jobs",
        json={"script": "x", "audio_url": "http://e/a.mp3", "aspect_ratios": ["16:9"]},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_INPUT"


def test_bad_aspect_ratio_rejected(client):
    r = client.post("/api/v1/broll/jobs", json={"script": "x", "aspect_ratios": ["4:3"]})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_INPUT"


def test_audio_url_input_accepted(client):
    r = client.post("/api/v1/broll/jobs", json={"audio_url": "https://e/v.mp3", "aspect_ratios": ["16:9"]})
    assert r.status_code == 202


def test_scenes_input_accepted(client):
    r = client.post("/api/v1/broll/jobs", json={"scenes": [{"text": "scene one"}], "aspect_ratios": ["9:16"]})
    assert r.status_code == 202


def test_correlation_id_propagated_on_jobs(client):
    r = client.post("/api/v1/broll/jobs", json=_script_payload(), headers={"X-Correlation-Id": "cid-99"})
    assert r.headers["X-Correlation-Id"] == "cid-99"
