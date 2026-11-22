"""Job lifecycle: creation, idempotency, and status.

The api uses create_or_get_job (idempotent) and get_job. The worker uses the
transition helpers in app.workers.runner.

Idempotency rules (Integration Standard #4):
- No Idempotency-Key: always create a new job.
- Same key + same request body: return the existing job (no duplicate work).
- Same key + different request body: 409 CONFLICT.

The unique constraint on jobs.idempotency_key plus the IntegrityError fallback
below make this correct even when two requests with the same key race.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import ConflictError, InvalidInputError, NotFoundError
from app.models.job import Job
from app.schemas.job import JobCreateRequest

log = logging.getLogger(__name__)


def _new_job_id() -> str:
    return "job_" + uuid.uuid4().hex


def _request_hash(req: JobCreateRequest) -> str:
    """sha256 of the canonical (order-stable) request JSON."""
    payload = req.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_request(req: JobCreateRequest) -> None:
    """Semantic validation: exactly one input source must be provided."""
    inputs = []
    if req.audio_url:
        inputs.append("audio_url")
    if req.script and req.script.strip():
        inputs.append("script")
    if req.scenes:
        inputs.append("scenes")
    if len(inputs) != 1:
        raise InvalidInputError(
            "Exactly one of audio_url, script, or scenes must be provided.",
            {"provided": inputs},
        )


def create_or_get_job(
    db: Session, req: JobCreateRequest, idempotency_key: Optional[str]
) -> Job:
    """Create a new queued job, or return the existing job for an idempotency key."""
    validate_request(req)
    rhash = _request_hash(req)

    if idempotency_key:
        existing = db.execute(
            select(Job).where(Job.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing is not None:
            if existing.request_hash != rhash:
                raise ConflictError(
                    "Idempotency-Key was already used with a different request body.",
                    {"idempotency_key": idempotency_key},
                )
            log.info("Idempotent reuse: returning existing job %s for key %s",
                      existing.id, idempotency_key)
            return existing

    job = Job(
        id=_new_job_id(),
        idempotency_key=idempotency_key,
        request_hash=rhash,
        status="queued",
        progress=0,
        request=req.model_dump(mode="json"),
        callback_url=req.callback_url,
    )
    db.add(job)
    try:
        db.commit()
    except IntegrityError:
        # Race: another request inserted the same idempotency_key first.
        db.rollback()
        if not idempotency_key:
            raise
        existing = db.execute(
            select(Job).where(Job.idempotency_key == idempotency_key)
        ).scalar_one_or_none()
        if existing is None:
            raise
        if existing.request_hash != rhash:
            raise ConflictError(
                "Idempotency-Key was already used with a different request body.",
                {"idempotency_key": idempotency_key},
            )
        log.info("Idempotent reuse after race: returning existing job %s", existing.id)
        return existing
    db.refresh(job)
    log.info("Created job %s (status=queued, key=%s)", job.id, idempotency_key)
    return job


def get_job(db: Session, job_id: str) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found.", {"job_id": job_id})
    return job


def to_status_dict(job: Job) -> dict:
    import os
    from app.config import get_settings
    settings = get_settings()
    base = {
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "result": job.result,
        "error": job.error,
    }
    # Add download links when the job has succeeded and outputs exist on disk.
    if job.status == "succeeded" and job.result:
        out_dir = os.path.join(settings.storage_local_root, "jobs", job.id)
        if os.path.isdir(out_dir):
            prefix = settings.api_v1_prefix
            links = {
                "self": f"{prefix}/jobs/{job.id}",
                "timeline": f"{prefix}/broll/jobs/{job.id}/timeline",
                "manifest": f"{prefix}/broll/jobs/{job.id}/manifest",
                "outputs": f"{prefix}/broll/jobs/{job.id}/outputs",
            }
            for f in sorted(os.listdir(out_dir)):
                if os.path.isfile(os.path.join(out_dir, f)):
                    links[f] = f"{prefix}/broll/jobs/{job.id}/outputs/{f}"
            base["links"] = links
    return base
