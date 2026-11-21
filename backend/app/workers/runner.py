"""Worker runner: claim a queued job, run the pipeline, update status.

Designed so the worker logic is testable without a real worker process: tests
call process_next_job() and recover_stale_jobs() directly. The worker.py loop
is a thin wrapper around these.

Retry policy: a retryable BrollError (e.g. UPSTREAM_PROVIDER_ERROR) re-queues
the job up to JOB_MAX_RETRIES times; a non-retryable error fails the job
immediately. The worker never silently substitutes unrelated footage just to
finish a job (that rule is enforced when real footage providers arrive in
Phase 4).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.errors import BrollError
from app.config import get_settings
from app.db.database import SessionLocal
from app.models.job import Job
from app.utils import callbacks
from app.workers import pipeline

log = logging.getLogger(__name__)
settings = get_settings()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _error_dict(exc: BrollError) -> dict:
    return {
        "code": exc.code,
        "message": exc.message,
        "retryable": exc.retryable,
        "details": exc.details,
    }


def claim_next_job(db: Session) -> Job | None:
    """Atomically claim the oldest 'queued' job (status -> running).

    The conditional UPDATE (WHERE status='queued') means two workers cannot
    claim the same job: only one UPDATE matches.
    """
    job_id = db.execute(
        select(Job.id).where(Job.status == "queued").order_by(Job.created_at).limit(1)
    ).scalar()
    if job_id is None:
        return None
    token = uuid.uuid4().hex
    result = db.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == "queued")
        .values(status="running", claim_token=token, started_at=_utcnow())
    )
    db.commit()
    if result.rowcount != 1:
        # Someone else claimed it between our SELECT and UPDATE.
        return None
    return db.get(Job, job_id)


def recover_stale_jobs(db: Session) -> int:
    """Re-queue jobs left 'running' from a crashed worker. Call on startup.

    On a fresh worker start, any 'running' job was orphaned by a previous worker
    that died before finishing it, so it is safe to re-queue.
    """
    running = db.execute(select(Job).where(Job.status == "running")).scalars().all()
    for job in running:
        job.status = "queued"
        job.claim_token = None
        job.started_at = None
        log.warning("Recovered stale running job %s -> queued", job.id)
    db.commit()
    return len(running)


def _maybe_callback(job: Job) -> None:
    """Send the signed callback if the job finished and a secret is configured."""
    if not job.callback_url:
        return
    if not settings.callback_hmac_secret:
        log.warning(
            "Job %s has callback_url=%s but CALLBACK_HMAC_SECRET is unset; skipping callback.",
            job.id, job.callback_url,
        )
        return
    payload = {"job_id": job.id, "status": job.status, "result": job.result}
    try:
        callbacks.send(job.callback_url, payload, settings.callback_hmac_secret)
    except Exception as exc:  # noqa: BLE001
        log.warning("Callback to %s failed: %s", job.callback_url, exc)


def process_next_job(session_factory: Callable[[], Session] = SessionLocal) -> bool:
    """Claim and process one queued job. Returns True if a job was processed."""
    db = session_factory()
    try:
        job = claim_next_job(db)
        if job is None:
            return False
        try:
            def progress(value: int) -> None:
                job.progress = max(0, min(100, int(value)))
                db.commit()

            result = pipeline.run_pipeline(job, progress)
            job.result = result
            job.status = "succeeded"
            job.progress = 100
            job.finished_at = _utcnow()
            db.commit()
        except BrollError as exc:
            log.warning(
                "Job %s failed with %s (retryable=%s, retry_count=%s/%s)",
                job.id, exc.code, exc.retryable, job.retry_count, settings.job_max_retries,
            )
            if exc.retryable and job.retry_count < settings.job_max_retries:
                job.status = "queued"
                job.retry_count += 1
                job.claim_token = None
                job.started_at = None
                job.error = _error_dict(exc)
                db.commit()
                log.info("Job %s re-queued for retry (attempt %s)", job.id, job.retry_count)
            else:
                job.status = "failed"
                job.error = _error_dict(exc)
                job.finished_at = _utcnow()
                db.commit()
        except Exception as exc:  # noqa: BLE001
            log.exception("Job %s failed unexpectedly", job.id)
            job.status = "failed"
            job.error = {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred during processing.",
                "retryable": False,
                "details": {},
            }
            job.finished_at = _utcnow()
            db.commit()

        if job.status in ("succeeded", "failed"):
            _maybe_callback(job)
        return True
    finally:
        db.close()
