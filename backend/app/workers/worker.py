"""Worker process entrypoint.

Run as a separate service (from the backend/ folder):
    python -m app.workers.worker

Polls the jobs table for queued work and processes it. On startup it re-queues
any jobs left 'running' from a previous crash (restart recovery).
"""
from __future__ import annotations

import logging
import time

from app.config import get_settings
from app.db.database import SessionLocal, init_db
from app.logging_config import setup_logging
from app.workers.runner import process_next_job, recover_stale_jobs

log = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()
    setup_logging(level=settings.log_level, json_output=settings.log_json)
    init_db()

    # Restart recovery: re-queue jobs orphaned by a previous worker crash.
    db = SessionLocal()
    try:
        recovered = recover_stale_jobs(db)
    finally:
        db.close()
    if recovered:
        log.info("Recovered %s stale job(s) on startup", recovered)

    log.info(
        "Worker started (max_concurrency=%s, poll=%ss)",
        settings.job_max_concurrency, settings.job_poll_interval_seconds,
    )
    try:
        while True:
            processed = process_next_job()
            if not processed:
                time.sleep(settings.job_poll_interval_seconds)
    except KeyboardInterrupt:
        log.info("Worker stopping (received interrupt)")


if __name__ == "__main__":
    main()
