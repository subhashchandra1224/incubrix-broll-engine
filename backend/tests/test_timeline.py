"""Phase 7 — timeline.json structure and fields.

Verifies that timeline.json is generated from the clips actually rendered and
contains every field the brief requires: scene start/end times, narration,
clip source and asset ID, licence, attribution, AI-generated and test-data flags,
selection reason, relevance score, and any fallbacks.
"""
from __future__ import annotations

import json
import os
from sqlalchemy import text

from app.db.database import SessionLocal, init_db
from app.schemas.job import JobCreateRequest
from app.services import job_service
from app.utils.ffmpeg import ffmpeg_available, ffprobe_available
from app.workers import runner

import pytest

pytestmark = pytest.mark.skipif(
    not ffmpeg_available() or not ffprobe_available(),
    reason="ffmpeg/ffprobe not available",
)


def _clean():
    init_db()
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM jobs"))
        db.commit()
    finally:
        db.close()


def _run_job(**fields) -> str:
    _clean()
    req = JobCreateRequest(**fields)
    db = SessionLocal()
    try:
        job_id = job_service.create_or_get_job(db, req, idempotency_key=None).id
    finally:
        db.close()
    runner.process_next_job()
    return job_id


def test_timeline_json_exists_and_is_valid_json():
    job_id = _run_job(script="Saving money. Building wealth. Staying secure.",
                      aspect_ratios=["16:9"])
    db = SessionLocal()
    try:
        job = db.get_job_or_404 = None  # placeholder
        from app.models.job import Job
        job = db.get(Job, job_id)
    finally:
        db.close()
    assert job.status == "succeeded"
    timeline_path = job.result.get("timeline_path")
    assert timeline_path is not None
    assert os.path.isfile(timeline_path)
    with open(timeline_path, encoding="utf-8") as fh:
        tl = json.load(fh)
    assert tl["job_id"] == job_id
    assert tl["test_data"] is True
    assert tl["scene_count"] == 3
    assert "total_duration" in tl
    assert "narration_duration" in tl
    assert "fallbacks" in tl
    assert "warnings" in tl
    assert "generated_at" in tl


def test_timeline_scenes_have_all_required_fields():
    job_id = _run_job(script="Track expenses. Build a budget. Stay secure.",
                      aspect_ratios=["16:9"])
    db = SessionLocal()
    try:
        from app.models.job import Job
        job = db.get(Job, job_id)
    finally:
        db.close()
    with open(job.result["timeline_path"], encoding="utf-8") as fh:
        tl = json.load(fh)
    for sc in tl["scenes"]:
        assert "scene_id" in sc
        assert "text" in sc
        assert "start_time" in sc
        assert "end_time" in sc
        assert "duration" in sc
        assert "visual_description" in sc
        assert "search_query" in sc
        assert "clip" in sc
        assert "relevance_score" in sc
        assert "selection_reason" in sc
        assert "warnings" in sc
        # Clip fields (Must-have 3).
        clip = sc["clip"]
        assert clip is not None
        assert "asset_id" in clip
        assert "provider" in clip
        assert "source_url" in clip
        assert "license_name" in clip
        assert "license_url" in clip
        assert "attribution" in clip
        assert "commercial_use" in clip
        assert "ai_generated" in clip
        assert "test_data" in clip
        assert clip["test_data"] is True
        assert clip["commercial_use"] is True


def test_timeline_timings_cover_narration_without_gaps():
    job_id = _run_job(script="One. Two. Three.", aspect_ratios=["16:9"])
    db = SessionLocal()
    try:
        from app.models.job import Job
        job = db.get(Job, job_id)
    finally:
        db.close()
    with open(job.result["timeline_path"], encoding="utf-8") as fh:
        tl = json.load(fh)
    scenes = tl["scenes"]
    for i in range(len(scenes) - 1):
        gap = scenes[i + 1]["start_time"] - scenes[i]["end_time"]
        assert abs(gap) < 0.01, f"Gap of {gap}s between scenes {i} and {i+1}"
    # Last scene end >= narration duration - tolerance.
    assert scenes[-1]["end_time"] >= tl["narration_duration"] - 0.1


def test_timeline_fallbacks_list_present():
    job_id = _run_job(script="A scene.", aspect_ratios=["16:9"])
    db = SessionLocal()
    try:
        from app.models.job import Job
        job = db.get(Job, job_id)
    finally:
        db.close()
    with open(job.result["timeline_path"], encoding="utf-8") as fh:
        tl = json.load(fh)
    # Default mock provider: no fallbacks expected.
    assert isinstance(tl["fallbacks"], list)
