"""Phase 7 — manifest.json structure and fields.

Verifies that manifest.json contains: provider and model versions, settings,
seed, measured timings, cost estimates, warnings, and rights information.
All fixture records are clearly labelled test_data=True.
"""
from __future__ import annotations

import json
import os
from sqlalchemy import text

from app.db.database import SessionLocal, init_db
from app.models.job import Job
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


def _get_manifest(job_id) -> dict:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
    finally:
        db.close()
    assert job.status == "succeeded"
    path = job.result["manifest_path"]
    assert os.path.isfile(path)
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def test_manifest_has_all_top_level_fields():
    job_id = _run_job(script="Saving money. Building wealth. Staying secure.",
                      aspect_ratios=["16:9"])
    m = _get_manifest(job_id)
    for key in [
        "job_id", "application_version", "creation_time", "test_data",
        "input", "outputs", "providers", "models", "settings", "rendering",
        "seed", "timings", "cost", "rights", "warnings", "errors", "validation",
    ]:
        assert key in m, f"Missing manifest field: {key}"


def test_manifest_test_data_labelled():
    job_id = _run_job(script="A test scene.", aspect_ratios=["16:9"])
    m = _get_manifest(job_id)
    assert m["test_data"] is True
    assert m["rights"]["all_clips_test_data"] is True
    assert "test data" in m["rights"]["note"].lower()


def test_manifest_providers_and_models():
    job_id = _run_job(script="Another scene.", aspect_ratios=["16:9"])
    m = _get_manifest(job_id)
    provs = m["providers"]
    assert "stt" in provs and "tts" in provs and "scene" in provs
    assert "embeddings" in provs and "footage" in provs and "safety" in provs
    models = m["models"]
    for cap in ["stt", "tts", "scene", "embeddings", "footage", "safety"]:
        assert cap in models
        assert "name" in models[cap]
        assert "version" in models[cap]


def test_manifest_cost_all_zero_for_mocks():
    job_id = _run_job(script="Cost test scene.", aspect_ratios=["16:9"])
    m = _get_manifest(job_id)
    cost = m["cost"]
    for cat in ["footage", "tts", "transcription", "embeddings", "compute", "total"]:
        assert cat in cost
        assert cost[cat]["amount"] == 0.0
        assert cost[cat]["measured"] is False
    assert "per_minute" in cost
    assert cost["per_minute"]["amount"] == 0.0


def test_manifest_timings_recorded():
    job_id = _run_job(script="Timing test scene.", aspect_ratios=["16:9"])
    m = _get_manifest(job_id)
    timings = m["timings"]
    assert "pipeline_total_seconds" in timings
    assert timings["pipeline_total_seconds"] > 0
    assert "narration_duration_seconds" in timings


def test_manifest_seed_present():
    job_id = _run_job(script="Seed test scene.", aspect_ratios=["16:9"])
    m = _get_manifest(job_id)
    assert m["seed"] is not None
    assert len(m["seed"]) == 16  # first 16 hex chars of sha256


def test_manifest_rendering_settings():
    job_id = _run_job(script="Render settings scene.", aspect_ratios=["16:9", "9:16"])
    m = _get_manifest(job_id)
    r = m["rendering"]
    assert r["fps"] == 30
    assert r["video_codec"] == "libx264"
    assert r["audio_codec"] == "aac"
    assert "16:9" in r["resolutions"]
    assert "9:16" in r["resolutions"]


def test_manifest_outputs_listed():
    job_id = _run_job(script="Outputs test.", aspect_ratios=["16:9", "9:16", "1:1"])
    m = _get_manifest(job_id)
    outs = m["outputs"]
    assert "videos" in outs
    assert len(outs["videos"]) >= 2  # at least 16:9 and 9:16
    assert outs["srt"] is not None
    assert outs["timeline"] == "timeline.json"
    assert outs["manifest"] == "manifest.json"
