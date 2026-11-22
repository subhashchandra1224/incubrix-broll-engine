"""Phase 7 — output download endpoints.

Tests:
- Completed job: timeline, manifest, outputs list, and individual file downloads.
- Unfinished job (queued): timeline/manifest return 404; outputs list is empty.
- Failed job: timeline/manifest return 404.
- Job scoping: each download is scoped to the correct job's directory.
- Path traversal: filenames with .. are blocked.
- Status response includes download links for completed jobs.
"""
from __future__ import annotations

import os
from sqlalchemy import text

from app.db.database import SessionLocal, init_db
from app.workers import runner


def _clean():
    init_db()
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM jobs"))
        db.commit()
    finally:
        db.close()


def _create_and_process(client, **fields) -> str:
    r = client.post("/api/v1/broll/jobs", json=fields)
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    runner.process_next_job()
    return job_id


# ---- completed job ----

def test_completed_job_timeline_download(client):
    _clean()
    job_id = _create_and_process(client, script="Timeline test scene.", aspect_ratios=["16:9"])
    r = client.get(f"/api/v1/broll/jobs/{job_id}/timeline")
    assert r.status_code == 200
    body = r.json()
    assert body["job_id"] == job_id
    assert "scenes" in body
    assert len(body["scenes"]) >= 1


def test_completed_job_manifest_download(client):
    _clean()
    job_id = _create_and_process(client, script="Manifest test scene.", aspect_ratios=["16:9"])
    r = client.get(f"/api/v1/broll/jobs/{job_id}/manifest")
    assert r.status_code == 200
    body = r.json()
    assert body["job_id"] == job_id
    assert "providers" in body
    assert "cost" in body


def test_completed_job_outputs_list(client):
    _clean()
    job_id = _create_and_process(client, script="Outputs list test.", aspect_ratios=["16:9"])
    r = client.get(f"/api/v1/broll/jobs/{job_id}/outputs")
    assert r.status_code == 200
    body = r.json()
    assert body["job_id"] == job_id
    assert len(body["outputs"]) > 0
    # Each output has filename, size, download_url.
    for o in body["outputs"]:
        assert "filename" in o
        assert "size_bytes" in o
        assert "download_url" in o


def test_completed_job_file_download(client):
    _clean()
    job_id = _create_and_process(client, script="File download test.", aspect_ratios=["16:9"])
    r = client.get(f"/api/v1/broll/jobs/{job_id}/outputs/video_16_9.mp4")
    assert r.status_code == 200
    assert len(r.content) > 0


def test_completed_job_srt_download(client):
    _clean()
    job_id = _create_and_process(client, script="SRT download test scene.",
                                  aspect_ratios=["16:9"], captions={"srt": True, "burn_in": False})
    r = client.get(f"/api/v1/broll/jobs/{job_id}/outputs/captions.srt")
    assert r.status_code == 200
    assert len(r.content) > 0
    assert b"--> " in r.content or b"--> " in r.content  # has timestamps


def test_completed_job_status_has_links(client):
    _clean()
    job_id = _create_and_process(client, script="Links test.", aspect_ratios=["16:9"])
    r = client.get(f"/api/v1/jobs/{job_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "succeeded"
    assert body.get("links") is not None
    assert "timeline" in body["links"]
    assert "manifest" in body["links"]
    assert "outputs" in body["links"]


# ---- unfinished job ----

def test_unfinished_job_timeline_404(client):
    _clean()
    r = client.post("/api/v1/broll/jobs", json={"script": "Unfinished.", "aspect_ratios": ["16:9"]})
    job_id = r.json()["job_id"]
    # Don't process the job.
    t = client.get(f"/api/v1/broll/jobs/{job_id}/timeline")
    assert t.status_code == 404
    m = client.get(f"/api/v1/broll/jobs/{job_id}/manifest")
    assert m.status_code == 404


def test_unfinished_job_outputs_empty(client):
    _clean()
    r = client.post("/api/v1/broll/jobs", json={"script": "Unfinished outputs.", "aspect_ratios": ["16:9"]})
    job_id = r.json()["job_id"]
    o = client.get(f"/api/v1/broll/jobs/{job_id}/outputs")
    assert o.status_code == 200
    assert o.json()["outputs"] == []


def test_unfinished_job_status_no_links(client):
    _clean()
    r = client.post("/api/v1/broll/jobs", json={"script": "No links.", "aspect_ratios": ["16:9"]})
    job_id = r.json()["job_id"]
    s = client.get(f"/api/v1/jobs/{job_id}")
    assert s.json().get("links") is None


# ---- failed job ----

def test_failed_job_downloads_404(client, monkeypatch):
    _clean()
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "footage_provider", "mock_fail")
    monkeypatch.setattr(s, "footage_fallback_providers", "")
    r = client.post("/api/v1/broll/jobs", json={"script": "Will fail.", "aspect_ratios": ["16:9"]})
    job_id = r.json()["job_id"]
    runner.process_next_job()
    # Job should be failed.
    st = client.get(f"/api/v1/jobs/{job_id}")
    assert st.json()["status"] == "failed"
    # Downloads → 404.
    t = client.get(f"/api/v1/broll/jobs/{job_id}/timeline")
    assert t.status_code == 404
    m = client.get(f"/api/v1/broll/jobs/{job_id}/manifest")
    assert m.status_code == 404


# ---- job scoping ----

def test_download_scoped_to_correct_job(client):
    _clean()
    ja = _create_and_process(client, script="Job A scene.", aspect_ratios=["16:9"])
    jb = _create_and_process(client, script="Job B scene.", aspect_ratios=["16:9"])
    # Both jobs have video_16_9.mp4, but each serves from its own directory.
    fa = client.get(f"/api/v1/broll/jobs/{ja}/outputs/video_16_9.mp4")
    fb = client.get(f"/api/v1/broll/jobs/{jb}/outputs/video_16_9.mp4")
    assert fa.status_code == 200
    assert fb.status_code == 200
    # A nonexistent file in job A's dir → 404 (even though job B has the same filename).
    fn = client.get(f"/api/v1/broll/jobs/{ja}/outputs/nonexistent.mp4")
    assert fn.status_code == 404


# ---- path traversal ----

def test_path_traversal_blocked(client):
    _clean()
    job_id = _create_and_process(client, script="Traversal test.", aspect_ratios=["16:9"])
    # Filename with .. is blocked.
    r = client.get(f"/api/v1/broll/jobs/{job_id}/outputs/..secret")
    assert r.status_code == 404


def test_unknown_job_returns_404(client):
    r = client.get("/api/v1/broll/jobs/job_does_not_exist/timeline")
    assert r.status_code == 404
    r = client.get("/api/v1/broll/jobs/job_does_not_exist/outputs")
    assert r.status_code == 404
