"""Test that simultaneous requests with the same Idempotency-Key create ONE job.

This is the race-condition part of Integration Standard point 4. The unique
constraint on jobs.idempotency_key plus the IntegrityError fallback in
job_service.make it correct under concurrency. We hit the app concurrently
from several threads, each with its own Starlette TestClient (one shared
TestClient is not safe for parallel use; httpx.ASGITransport is async-only).
"""
from __future__ import annotations

import threading
from sqlalchemy import func, select
from starlette.testclient import TestClient

from app.db.database import SessionLocal, init_db
from app.main import app
from app.models.job import Job


def test_simultaneous_same_key_creates_single_job():
    init_db()  # ensure the jobs table exists before any request runs.
    key = "concurrent-key-1"
    payload = {"script": "concurrent script", "aspect_ratios": ["16:9"]}
    results: dict[int, tuple[int, str | None]] = {}
    lock = threading.Lock()

    def post(i: int) -> None:
        # One TestClient per thread; each runs its own event loop via a portal.
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.post("/api/v1/broll/jobs", json=payload, headers={"Idempotency-Key": key})
            with lock:
                results[i] = (r.status_code, r.json().get("job_id"))

    threads = [threading.Thread(target=post, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All 6 responses are 202 and point at the same single job id.
    assert len(results) == 6, results
    assert all(status == 202 for status, _ in results.values()), results
    job_ids = {jid for _, jid in results.values()}
    assert len(job_ids) == 1, f"expected one job id, got {job_ids}"

    # And the database holds exactly one row for this key.
    db = SessionLocal()
    try:
        count = db.execute(
            select(func.count()).select_from(Job).where(Job.idempotency_key == key)
        ).scalar()
        assert count == 1
    finally:
        db.close()
