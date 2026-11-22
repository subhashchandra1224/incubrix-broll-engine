"""Phase 4 pipeline through the worker: mock providers produce a draft scene plan;
footage fallback / all-fail behave correctly; the job API contract is preserved.
"""
from __future__ import annotations

from sqlalchemy import text

from app.config import get_settings
from app.db.database import SessionLocal, init_db
from app.models.job import Job
from app.schemas.job import JobCreateRequest
from app.services import job_service
from app.workers import runner


def _clean() -> None:
    init_db()
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM jobs"))
        db.commit()
    finally:
        db.close()


def _create(**fields) -> str:
    req = JobCreateRequest(**fields)
    db = SessionLocal()
    try:
        return job_service.create_or_get_job(db, req, idempotency_key=None).id
    finally:
        db.close()


def _get(job_id: str) -> Job:
    db = SessionLocal()
    try:
        return db.get(Job, job_id)
    finally:
        db.close()


def _footage(monkeypatch, primary, fallback=""):
    s = get_settings()
    monkeypatch.setattr(s, "footage_provider", primary)
    monkeypatch.setattr(s, "footage_fallback_providers", fallback)


def test_script_job_succeeds_with_draft_scene_plan():
    _clean()
    job_id = _create(script="Saving money. Building wealth. Staying secure.", aspect_ratios=["16:9"])
    assert runner.process_next_job() is True
    job = _get(job_id)
    assert job.status == "succeeded"
    assert job.progress == 100
    r = job.result
    assert r["pipeline"] == "phase4-mock-providers"
    assert r["test_data"] is True
    assert r["scene_count"] == 3
    sc = r["scenes"][0]
    assert sc["clip"] is not None
    assert sc["clip"]["test_data"] is True
    assert sc["clip"]["commercial_use"] is True
    assert "not a real licence" in sc["clip"]["license_name"]
    assert 0.0 <= sc["relevance_score"] <= 1.0
    assert sc["selection_reason"]
    # timings are monotonic with no overlap
    assert sc["start_time"] == 0.0
    assert r["scenes"][0]["end_time"] <= r["scenes"][1]["start_time"] + 1e-6
    # providers recorded for the manifest
    assert r["providers"]["footage"] == ["mock"]


def test_audio_job_succeeds():
    _clean()
    job_id = _create(audio_url="https://e/voiceover.mp3", aspect_ratios=["9:16"])
    assert runner.process_next_job() is True
    job = _get(job_id)
    assert job.status == "succeeded"
    assert job.result["input_type"] == "audio"
    assert len(job.result["scenes"]) >= 1


def test_scenes_input_uses_visual_hints():
    _clean()
    job_id = _create(scenes=[{"text": "Intro line.", "visual_hint": "calm sunrise"},
                             {"text": "Second line."}], aspect_ratios=["1:1"])
    assert runner.process_next_job() is True
    job = _get(job_id)
    assert job.status == "succeeded"
    assert job.result["input_type"] == "scenes"
    assert len(job.result["scenes"]) == 2
    assert job.result["scenes"][0]["visual_description"] == "calm sunrise"


def test_all_footage_providers_fail_fails_job(monkeypatch):
    _clean()
    _footage(monkeypatch, "mock_fail", "")
    job_id = _create(script="A script.", aspect_ratios=["16:9"])
    assert runner.process_next_job() is True
    job = _get(job_id)
    assert job.status == "failed"
    assert job.error["code"] == "FOOTAGE_UNAVAILABLE"
    assert job.error["retryable"] is False


def test_primary_fail_fallback_succeeds(monkeypatch):
    _clean()
    _footage(monkeypatch, "mock_fail", "mock")
    job_id = _create(script="A script.", aspect_ratios=["16:9"])
    assert runner.process_next_job() is True
    job = _get(job_id)
    assert job.status == "succeeded"
    assert job.result["providers"]["footage"] == ["mock_fail", "mock"]


def test_primary_empty_fallback_succeeds(monkeypatch):
    _clean()
    _footage(monkeypatch, "mock_empty", "mock")
    job_id = _create(script="A script.", aspect_ratios=["16:9"])
    assert runner.process_next_job() is True
    job = _get(job_id)
    assert job.status == "succeeded"


def test_job_api_contract_preserved_via_http(client):
    _clean()
    r = client.post("/api/v1/broll/jobs",
                    json={"script": "One script sentence.", "aspect_ratios": ["16:9"]})
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    assert runner.process_next_job() is True
    g = client.get(f"/api/v1/jobs/{job_id}")
    assert g.status_code == 200
    body = g.json()
    assert set(body) == {"job_id", "status", "progress", "result", "error"}
    assert body["job_id"] == job_id
    assert body["status"] == "succeeded"
    assert body["progress"] == 100
    assert body["result"]["pipeline"] == "phase4-mock-providers"
    assert body["error"] is None
