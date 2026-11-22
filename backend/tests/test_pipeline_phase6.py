"""Phase 6 — end-to-end pipeline through the worker, producing real MP4 files.

Runs a full job via the normal POST → worker → GET path.
Uses deterministic test fixtures (sine-tone + colour-bar). All outputs are
labelled test_data=True. Verified with FFprobe.
"""
from __future__ import annotations

import os
import pytest
from sqlalchemy import text

from app.db.database import SessionLocal, init_db
from app.models.job import Job
from app.schemas.job import JobCreateRequest
from app.services import job_service
from app.utils.ffmpeg import ffmpeg_available, ffprobe_available, video_info, validate_output
from app.workers import runner


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


def _get(job_id: str) -> Job:
    db = SessionLocal()
    try:
        return db.get(Job, job_id)
    finally:
        db.close()


def _create(**fields) -> str:
    req = JobCreateRequest(**fields)
    db = SessionLocal()
    try:
        return job_service.create_or_get_job(db, req, idempotency_key=None).id
    finally:
        db.close()


# ---- Full E2E: script input, all three ratios ----

def test_script_job_renders_all_three_ratios():
    _clean()
    job_id = _create(
        script="Saving money. Building wealth. Staying secure.",
        aspect_ratios=["16:9", "9:16", "1:1"],
        captions={"srt": True, "burn_in": False},
    )
    assert runner.process_next_job() is True
    job = _get(job_id)
    assert job.status == "succeeded", f"status={job.status} error={job.error}"
    r = job.result
    assert r["pipeline"] == "phase7-metadata"
    assert r["test_data"] is True
    # Three output files produced.
    outputs = r.get("outputs", [])
    ratios = {o["ratio"] for o in outputs}
    assert "16:9" in ratios
    assert "9:16" in ratios
    assert "1:1" in ratios
    # All files exist on disk.
    for o in outputs:
        assert os.path.isfile(o["path"]), f"Output file missing: {o['path']}"
        assert o.get("validation_errors", []) == [], (
            f"Validation errors for {o['ratio']}: {o['validation_errors']}"
        )
    # SRT file created.
    assert r.get("srt_path") and os.path.isfile(r["srt_path"])


def test_all_outputs_pass_ffprobe_checks():
    _clean()
    job_id = _create(
        script="Track expenses carefully. Build a budget.",
        aspect_ratios=["16:9", "9:16"],
    )
    runner.process_next_job()
    job = _get(job_id)
    assert job.status == "succeeded"
    for out in job.result.get("outputs", []):
        info = video_info(out["path"])
        v = info["video"]
        a = info["audio"]
        assert v is not None, f"No video stream in {out['path']}"
        assert a is not None, f"No audio stream in {out['path']}"
        assert v["codec"] == "h264"
        assert a["codec"] == "aac"
        assert abs(v["fps"] - 30) < 1.0
        assert v["pix_fmt"] == "yuv420p"


def test_16x9_resolution():
    _clean()
    job_id = _create(script="A short scene.", aspect_ratios=["16:9"])
    runner.process_next_job()
    job = _get(job_id)
    assert job.status == "succeeded"
    out_16x9 = next(o for o in job.result["outputs"] if o["ratio"] == "16:9")
    info = video_info(out_16x9["path"])
    assert info["video"]["width"] == 1920
    assert info["video"]["height"] == 1080


def test_9x16_resolution_uses_padding():
    _clean()
    job_id = _create(script="Another scene.", aspect_ratios=["9:16"])
    runner.process_next_job()
    job = _get(job_id)
    assert job.status == "succeeded"
    out = next(o for o in job.result["outputs"] if o["ratio"] == "9:16")
    info = video_info(out["path"])
    assert info["video"]["width"] == 1080
    assert info["video"]["height"] == 1920


def test_scene_list_input_renders():
    _clean()
    job_id = _create(
        scenes=[{"text": "Opening line.", "visual_hint": "sunrise"},
                {"text": "Second line."}],
        aspect_ratios=["16:9"],
    )
    runner.process_next_job()
    job = _get(job_id)
    assert job.status == "succeeded"
    assert job.result["input_type"] == "scenes"
    assert len(job.result["outputs"]) >= 1


def test_coverage_warnings_propagated():
    _clean()
    job_id = _create(script="One sentence only.", aspect_ratios=["16:9"])
    runner.process_next_job()
    job = _get(job_id)
    assert job.status == "succeeded"
    # coverage_warnings key must be present (may be empty)
    assert "coverage_warnings" in job.result


def test_job_api_contract_preserved_e2e(client):
    _clean()
    r = client.post("/api/v1/broll/jobs", json={
        "script": "One final test scene.",
        "aspect_ratios": ["16:9"],
    })
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    runner.process_next_job()
    g = client.get(f"/api/v1/jobs/{job_id}")
    assert g.status_code == 200
    body = g.json()
    assert body["status"] == "succeeded"
    assert body["result"]["pipeline"] == "phase7-metadata"
    assert body["result"]["test_data"] is True
    # Verify outputs are in the result.
    assert len(body["result"]["outputs"]) >= 1
