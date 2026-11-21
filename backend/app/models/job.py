"""Job ORM model - the persistent SQLite job queue.

The api creates rows here; the separate worker process polls for ``queued``
jobs, claims one (status -> running), runs the pipeline, and updates
status/progress/result. Because state lives in the database, a crashed
worker's ``running`` jobs can be re-queued on the next startup (restart
recovery) instead of being lost.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    """One B-roll video generation job."""

    __tablename__ = "jobs"

    # "job_<uuid>"
    id: Mapped[str] = mapped_column(String, primary_key=True)

    # Idempotency: if set, unique. Same key + same request hash -> same job.
    idempotency_key: Mapped[str | None] = mapped_column(
        String, nullable=True, unique=True, index=True
    )
    # sha256 of the canonical request body, used to detect key reuse with a
    # different payload (-> 409 CONFLICT).
    request_hash: Mapped[str | None] = mapped_column(String, nullable=True)

    # queued | running | succeeded | failed
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # The original request and the produced results (JSON columns).
    request: Mapped[dict] = mapped_column(JSON, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    callback_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # Worker bookkeeping.
    claim_token: Mapped[str | None] = mapped_column(String, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_jobs_status_created", "status", "created_at"),)
