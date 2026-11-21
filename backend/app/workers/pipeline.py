"""PLACEHOLDER pipeline.

IMPORTANT: this is NOT the real video-generation pipeline. It only simulates
work (a few progress updates with short waits) and records an explicit
placeholder result. The real pipeline (audio prep -> transcription/segmentation
-> footage -> safety -> rendering -> outputs -> manifest) is implemented in
Phases 4-7.

We deliberately do NOT fabricate videos, timelines, licences, relevance
scores or any other outputs here. The result dict says so explicitly so
nothing downstream can mistake it for real content.
"""
from __future__ import annotations

import logging
import time
from typing import Callable

from app.models.job import Job

log = logging.getLogger(__name__)

ProgressFn = Callable[[int], None]


def run_pipeline(job: Job, progress: ProgressFn) -> dict:
    """Run the placeholder pipeline; return a clearly-labelled placeholder result."""
    log.warning("PLACEHOLDER pipeline running for job %s (real pipeline = Phases 4-7)", job.id)

    progress(10)
    time.sleep(0.03)
    progress(40)
    time.sleep(0.03)
    progress(80)
    time.sleep(0.03)
    progress(100)

    return {
        "pipeline": "placeholder",
        "note": (
            "Placeholder pipeline. No video, timeline, manifest, licences or "
            "scores were produced. The real pipeline is implemented in Phases 4-7."
        ),
        "outputs": [],
    }
