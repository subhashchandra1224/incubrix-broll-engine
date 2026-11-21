"""Job API routes: create a job (POST) and query status/progress (GET).

Routes are mounted under the /api/v1 prefix in app.main, giving:
    POST /api/v1/broll/jobs        -> 202 {job_id, status, status_url}
    GET  /api/v1/jobs/{job_id}      -> 200 {job_id, status, progress, result, error}
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db
from app.schemas.job import JobAcceptedResponse, JobCreateRequest, JobStatusResponse
from app.services import job_service

router = APIRouter(tags=["jobs"])
settings = get_settings()


@router.post(
    "/broll/jobs",
    response_model=JobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a B-roll video generation job",
)
def create_job(
    payload: JobCreateRequest,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> JobAcceptedResponse:
    """Accept a script, audio URL, or scene list and queue a background job.

    Idempotency: send the same request twice with the same Idempotency-Key and
    you get the same job back; the work is never done twice.
    """
    job = job_service.create_or_get_job(db, payload, idempotency_key)
    return JobAcceptedResponse(
        job_id=job.id,
        status=job.status,
        status_url=f"{settings.api_v1_prefix}/jobs/{job.id}",
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status and progress",
)
def get_job_status(job_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = job_service.get_job(db, job_id)
    return JobStatusResponse(**job_service.to_status_dict(job))
