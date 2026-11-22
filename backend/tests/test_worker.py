"""Tests for the worker runner: processing, restart recovery, retry policy,
and the (explicitly labelled) placeholder pipeline.

We test the worker LOGIC via the runner functions directly; the real
worker loop (app.workers.worker.main) is exercised end-to-end in Phase 9.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from app.db.database import SessionLocal, init_db
from app.models.job import Job
from app.schemas.job import JobCreateRequest
from app.services import job_service
from app.workers import pipeline as pipeline_mod
from app.workers import runner


def _create_job(idempotency_key: str | None = None) -> str:
    db = SessionLocal()
    try:
        req = JobCreateRequest(script="a script", aspect_ratios=["16:9"])
        return job_service.create_or_get_job(db, req, idempotency_key=idempotency_key).id
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _clean_jobs():
    """Start each test with an empty jobs table (tests share one temp DB)."""
    init_db()
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM jobs"))
        db.commit()
    finally:
        db.close()
    yield


def test_process_next_job_succeeds():
    job_id = _create_job()
    assert runner.process_next_job() is True

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        assert job.status == "succeeded"
        assert job.progress == 100
        assert job.result is not None
        assert job.result["pipeline"] == "phase7-metadata"
        assert job.result["test_data"] is True
        assert job.error is None
        assert job.finished_at is not None
    finally:
        db.close()


def test_no_queued_job_returns_false():
    assert runner.process_next_job() is False


def test_recover_stale_jobs_requeues_running_then_process_succeeds():
    job_id = _create_job()
    # Simulate a worker that claimed the job and then crashed mid-run.
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        job.status = "running"
        job.claim_token = "dead-worker"
        db.commit()
    finally:
        db.close()

    # On (re)start the worker re-queues orphaned running jobs.
    db = SessionLocal()
    try:
        assert runner.recover_stale_jobs(db) == 1
        job = db.get(Job, job_id)
        assert job.status == "queued"
        assert job.claim_token is None
    finally:
        db.close()

    # The recovered job is now processable.
    assert runner.process_next_job() is True
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        assert job.status == "succeeded"
    finally:
        db.close()


def test_non_retryable_error_fails_job(monkeypatch):
    from app.api.errors import InvalidInputError

    def boom(job, progress):
        raise InvalidInputError("bad input mid-job", {"k": "v"})

    monkeypatch.setattr(pipeline_mod, "run_pipeline", boom)
    job_id = _create_job()
    assert runner.process_next_job() is True

    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        assert job.status == "failed"
        assert job.error["code"] == "INVALID_INPUT"
        assert job.error["retryable"] is False
        assert job.finished_at is not None
    finally:
        db.close()


def test_retryable_error_requeues_then_succeeds(monkeypatch):
    from app.api.errors import UpstreamProviderError

    calls = {"n": 0}

    def flaky(job, progress):
        calls["n"] += 1
        if calls["n"] == 1:
            raise UpstreamProviderError("provider down")
        return {"pipeline": "placeholder", "note": "ok on retry", "outputs": []}

    monkeypatch.setattr(pipeline_mod, "run_pipeline", flaky)
    job_id = _create_job()

    # First attempt: retryable -> re-queued (not failed).
    assert runner.process_next_job() is True
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        assert job.status == "queued"
        assert job.retry_count == 1
    finally:
        db.close()

    # Second attempt: succeeds.
    assert runner.process_next_job() is True
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        assert job.status == "succeeded"
        assert calls["n"] == 2
    finally:
        db.close()
