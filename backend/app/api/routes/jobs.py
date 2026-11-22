"""Job API routes: create a job (POST), query status/progress (GET), and
download outputs (timeline, manifest, MP4s, SRT).

Routes are mounted under the /api/v1 prefix in app.main, giving:
    POST /api/v1/broll/jobs                    -> 202 {job_id, status, status_url}
    GET  /api/v1/jobs/{job_id}                 -> 200 {job_id, status, progress, result, error, links}
    GET  /api/v1/broll/jobs/{job_id}/timeline  -> 200 timeline.json
    GET  /api/v1/broll/jobs/{job_id}/manifest  -> 200 manifest.json
    GET  /api/v1/broll/jobs/{job_id}/outputs   -> 200 {job_id, status, outputs: [...]}
    GET  /api/v1/broll/jobs/{job_id}/outputs/{filename} -> file stream

Downloads are scoped to the job's own output directory; path traversal is
blocked by validating the filename (no /, \\, or ..).
"""
from __future__ import annotations

import json
import os

from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.api.errors import NotFoundError
from app.config import get_settings
from app.db.database import get_db
from app.schemas.job import JobAcceptedResponse, JobCreateRequest, JobStatusResponse
from app.services import job_service

router = APIRouter(tags=["jobs"])
settings = get_settings()


# --------------------------------------------------------------------------- create

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


# --------------------------------------------------------------------------- status

@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status and progress",
)
def get_job_status(job_id: str, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = job_service.get_job(db, job_id)
    return JobStatusResponse(**job_service.to_status_dict(job))


# --------------------------------------------------------------------------- timeline

@router.get(
    "/broll/jobs/{job_id}/timeline",
    summary="Download timeline.json",
)
def get_timeline(job_id: str, db: Session = Depends(get_db)) -> JSONResponse:
    job_service.get_job(db, job_id)  # raises 404 if not found
    path = _job_output_path(job_id, "timeline.json")
    if not os.path.isfile(path):
        raise NotFoundError(
            "timeline.json not available (job may not have completed).",
            {"job_id": job_id, "status": "check job status first"},
        )
    with open(path, encoding="utf-8") as fh:
        return JSONResponse(content=json.load(fh))


# --------------------------------------------------------------------------- manifest

@router.get(
    "/broll/jobs/{job_id}/manifest",
    summary="Download manifest.json",
)
def get_manifest(job_id: str, db: Session = Depends(get_db)) -> JSONResponse:
    job_service.get_job(db, job_id)  # raises 404 if not found
    path = _job_output_path(job_id, "manifest.json")
    if not os.path.isfile(path):
        raise NotFoundError(
            "manifest.json not available (job may not have completed).",
            {"job_id": job_id, "status": "check job status first"},
        )
    with open(path, encoding="utf-8") as fh:
        return JSONResponse(content=json.load(fh))


# --------------------------------------------------------------------------- outputs list

@router.get(
    "/broll/jobs/{job_id}/outputs",
    summary="List output files for a job",
)
def list_outputs(job_id: str, db: Session = Depends(get_db)) -> dict:
    job = job_service.get_job(db, job_id)  # raises 404 if not found
    out_dir = _job_output_dir(job_id)
    if not os.path.isdir(out_dir):
        return {"job_id": job_id, "status": job.status, "outputs": [],
                "message": "No outputs available yet."}
    files = []
    for f in sorted(os.listdir(out_dir)):
        fpath = os.path.join(out_dir, f)
        if os.path.isfile(fpath):
            files.append({
                "filename": f,
                "size_bytes": os.path.getsize(fpath),
                "download_url": f"{settings.api_v1_prefix}/broll/jobs/{job_id}/outputs/{f}",
            })
    return {"job_id": job_id, "status": job.status, "outputs": files}


# --------------------------------------------------------------------------- output download

@router.get(
    "/broll/jobs/{job_id}/outputs/{filename}",
    summary="Download a single output file",
)
def download_output(job_id: str, filename: str, db: Session = Depends(get_db)) -> FileResponse:
    job_service.get_job(db, job_id)  # raises 404 if not found
    # Path traversal protection: filename must be a simple basename.
    if "/" in filename or "\\" in filename or ".." in filename:
        raise NotFoundError("Invalid filename.", {"filename": filename})
    path = _job_output_path(job_id, filename)
    if not os.path.isfile(path):
        raise NotFoundError(
            "File not found in job outputs.",
            {"job_id": job_id, "filename": filename},
        )
    return FileResponse(path, filename=filename)


# --------------------------------------------------------------------------- helpers

def _job_output_dir(job_id: str) -> str:
    return os.path.join(settings.storage_local_root, "jobs", job_id)


def _job_output_path(job_id: str, filename: str) -> str:
    return os.path.join(_job_output_dir(job_id), filename)
