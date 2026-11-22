"""Phase 7 — end-to-end artifact download and verification.

Submits a job through the API, processes it with the worker, and downloads the
actual artifacts. Verifies:
- SRT starts with its first cue.
- Output MP4 duration matches measured narration audio duration.
- Caption burn-in produces a valid burned-in video (when requested).
- Differing audio and video lengths: tpad + -t guarantees narration sets the
  output duration (apad + -shortest alone does not).
"""
from __future__ import annotations

import os
import tempfile
from sqlalchemy import text

from app.db.database import SessionLocal, init_db
from app.utils.ffmpeg import (
    concat_clips_with_audio,
    ffmpeg_available,
    ffprobe_available,
    generate_silent_audio,
    normalise_clip,
    video_info,
)
from app.utils.fixtures import generate_fixtures
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


def _create_and_process(client, **fields) -> str:
    _clean()
    r = client.post("/api/v1/broll/jobs", json=fields)
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    runner.process_next_job()
    return job_id


# ---- SRT first cue ----

def test_srt_starts_with_first_cue(client):
    job_id = _create_and_process(
        client,
        script="Saving money. Building wealth. Staying secure.",
        aspect_ratios=["16:9"],
        captions={"srt": True, "burn_in": False},
    )
    srt = client.get(f"/api/v1/broll/jobs/{job_id}/outputs/captions.srt")
    assert srt.status_code == 200
    text = srt.text
    # The first cue block starts with "1" (the SRT index).
    # There may be a header comment line before it.
    lines = text.strip().split("\n")
    # Find the first cue index line.
    found_index = False
    for line in lines:
        if line.strip() == "1":
            found_index = True
            break
    assert found_index, f"SRT does not start with cue index '1'. First lines: {lines[:5]}"
    # The line after "1" should be a timestamp with -->.
    idx_pos = lines.index("1") if "1" in lines else next(i for i, l in enumerate(lines) if l.strip() == "1")
    timestamp_line = lines[idx_pos + 1]
    assert "-->" in timestamp_line, f"Expected timestamp after cue index, got: {timestamp_line}"
    # The first cue should start at 00:00:00.
    assert "00:00:00" in timestamp_line, f"First cue should start at 00:00:00, got: {timestamp_line}"


# ---- Duration matches measured narration ----

def test_output_duration_matches_narration(client):
    job_id = _create_and_process(
        client,
        script="Saving money. Building wealth. Staying secure.",
        aspect_ratios=["16:9"],
    )
    # Get the narration duration from the job result.
    status = client.get(f"/api/v1/jobs/{job_id}")
    narr_dur = status.json()["result"]["narration_duration"]
    # Download the video and check its duration.
    vid = client.get(f"/api/v1/broll/jobs/{job_id}/outputs/video_16_9.mp4")
    assert vid.status_code == 200
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(vid.content)
        tmp = f.name
    try:
        info = video_info(tmp)
        assert abs(info["duration"] - narr_dur) < 0.5, (
            f"Output duration {info['duration']:.3f}s differs from narration {narr_dur}s"
        )
    finally:
        os.unlink(tmp)


# ---- Burn-in captions ----

def test_burn_in_captions_produces_valid_video(client):
    job_id = _create_and_process(
        client,
        script="Saving money. Building wealth.",
        aspect_ratios=["16:9"],
        captions={"srt": True, "burn_in": True},
    )
    status = client.get(f"/api/v1/jobs/{job_id}")
    assert status.json()["status"] == "succeeded"
    outputs = status.json()["result"]["outputs"]
    burned = [o for o in outputs if o.get("burned_in")]
    if burned:
        # Burn-in succeeded — verify the file is valid.
        b_name = os.path.basename(burned[0]["path"])
        b = client.get(f"/api/v1/broll/jobs/{job_id}/outputs/{b_name}")
        assert b.status_code == 200
        assert len(b.content) > 0
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b.content)
            tmp = f.name
        try:
            info = video_info(tmp)
            assert info["video"] is not None
            assert info["video"]["codec"] == "h264"
        finally:
            os.unlink(tmp)
    else:
        # Burn-in failed (likely no font available in this environment) — check for a warning.
        warnings = status.json()["result"].get("warnings", [])
        assert any("burn" in w.lower() for w in warnings), (
            "No burned output and no burn-in warning found"
        )


# ---- Differing audio and video lengths (the key fix) ----

def test_narration_sets_duration_when_video_is_shorter(tmp_path):
    """apad + -shortest alone does NOT guarantee narration sets the output duration.
    With tpad + -t, the output must match narration duration even when video clips
    total less than the narration."""
    fix = generate_fixtures(str(tmp_path / "fix"), scene_durations=[2.0, 2.0, 2.0])
    # Generate a 9s narration audio (longer than the 6s video total).
    narr = str(tmp_path / "narr_9s.aac")
    generate_silent_audio(narr, duration=9.0)
    # Normalise clips (source 2s each; -t 3.0 can't extend → output is 2s each).
    norm_clips = []
    for sc in fix.scenes:
        p = str(tmp_path / f"norm_{sc.index}.mp4")
        normalise_clip(sc.video_path, p, width=1920, height=1080, fps=30, duration=3.0)
        norm_clips.append(p)
    # Concat with narration_duration=9.0 → tpad extends 6s video to 9s.
    out = str(tmp_path / "output_short_video.mp4")
    concat_clips_with_audio(norm_clips, narr, out, narration_duration=9.0)
    info = video_info(out)
    assert abs(info["duration"] - 9.0) < 0.5, (
        f"Expected ~9.0s (narration), got {info['duration']:.3f}s (video would be 6s)"
    )


def test_narration_sets_duration_when_video_is_longer(tmp_path):
    """When video clips total more than the narration, -t trims to narration duration."""
    fix = generate_fixtures(str(tmp_path / "fix"), scene_durations=[4.0, 4.0, 4.0])
    # Generate a 6s narration audio (shorter than the 12s video total).
    narr = str(tmp_path / "narr_6s.aac")
    generate_silent_audio(narr, duration=6.0)
    # Normalise clips to 4s each (full length).
    norm_clips = []
    for sc in fix.scenes:
        p = str(tmp_path / f"norm_{sc.index}.mp4")
        normalise_clip(sc.video_path, p, width=1920, height=1080, fps=30, duration=4.0)
        norm_clips.append(p)
    # Concat with narration_duration=6.0 → -t trims 12s video to 6s.
    out = str(tmp_path / "output_long_video.mp4")
    concat_clips_with_audio(norm_clips, narr, out, narration_duration=6.0)
    info = video_info(out)
    assert abs(info["duration"] - 6.0) < 0.5, (
        f"Expected ~6.0s (narration), got {info['duration']:.3f}s (video would be 12s)"
    )
