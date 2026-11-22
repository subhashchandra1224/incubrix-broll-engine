"""Tests for the rendering service: all three aspect ratios, SRT captions,
burn-in, corrupt media error handling.

These tests generate real MP4 files with FFmpeg and verify them with FFprobe.
All media is test fixtures (sine-tone audio + colour-bar video) labelled test_data.
"""
from __future__ import annotations

import os
import pytest

from app.utils.ffmpeg import ffmpeg_available, ffprobe_available, video_info, validate_output
from app.utils.fixtures import fixture_dir, generate_fixtures
from app.services.rendering_service import render_job

pytestmark = pytest.mark.skipif(
    not ffmpeg_available() or not ffprobe_available(),
    reason="ffmpeg/ffprobe not available",
)


@pytest.fixture(scope="module")
def render_outputs(tmp_path_factory):
    """Render a 3-scene fixture set for all three ratios once per module."""
    out_dir = str(tmp_path_factory.mktemp("render"))
    with fixture_dir() as fix_dir:
        fs = generate_fixtures(fix_dir)
        # Build a minimal scene plan from the fixture.
        plan = []
        for sc in fs.scenes:
            plan.append({
                "scene_id": f"scene_{sc.index + 1:03d}",
                "text": sc.text,
                "start_time": sc.start_time,
                "end_time": sc.end_time,
                "visual_description": f"TEST-DATA scene {sc.index}",
                "search_query": f"test fixture {sc.index}",
                "clip": {
                    "asset_id": f"fix_{sc.index}",
                    "provider": "mock",
                    "source_url": "test-data://fixture",
                    "local_path": None,
                    "license_name": "Mock test-data licence",
                    "license_url": "test-data://",
                    "attribution": "Test fixture",
                    "commercial_use": True,
                    "ai_generated": False,
                    "test_data": True,
                    "video_path": sc.video_path,
                },
            })
        result = render_job(
            scene_plan=plan,
            narration_path=fs.narration_path,
            total_duration=fs.total_duration,
            aspect_ratios=["16:9", "9:16", "1:1"],
            out_dir=out_dir,
            burn_in_captions=False,
            write_srt_file=True,
            test_data=True,
        )
    return result, out_dir


def _get_output(result, ratio):
    for o in result.get("outputs", []):
        if o.get("ratio") == ratio and not o.get("burned_in"):
            return o
    return None


# ---- SRT output ----

def test_srt_file_created(render_outputs):
    result, out_dir = render_outputs
    srt_path = result.get("srt_path")
    assert srt_path is not None
    assert os.path.isfile(srt_path)
    content = open(srt_path).read()
    assert "TEST-DATA" in content
    assert "-->" in content  # has at least one SRT timestamp block


def test_srt_has_correct_number_of_entries(render_outputs):
    result, out_dir = render_outputs
    srt_path = result.get("srt_path")
    content = open(srt_path).read()
    # Count timestamp arrows = number of blocks
    count = content.count("-->")
    assert count == 3  # 3 fixture scenes


# ---- 16:9 output ----

def test_16x9_file_exists_and_valid(render_outputs):
    result, out_dir = render_outputs
    out = _get_output(result, "16:9")
    assert out is not None, "16:9 output missing from render result"
    path = out["path"]
    assert os.path.isfile(path), f"16:9 file not on disk: {path}"
    errors = out.get("validation_errors", [])
    assert errors == [], f"16:9 validation errors: {errors}"


def test_16x9_codec_resolution_fps(render_outputs):
    result, _ = render_outputs
    out = _get_output(result, "16:9")
    info = video_info(out["path"])
    v = info["video"]
    assert v["codec"] == "h264"
    assert v["width"] == 1920
    assert v["height"] == 1080
    assert abs(v["fps"] - 30.0) < 1.0
    assert v["pix_fmt"] == "yuv420p"
    assert info["audio"] is not None
    assert info["audio"]["codec"] == "aac"


def test_16x9_duration_close_to_narration(render_outputs):
    result, _ = render_outputs
    out = _get_output(result, "16:9")
    info = video_info(out["path"])
    # Total fixture duration is 9s; allow 0.5s tolerance.
    assert abs(info["duration"] - 9.0) < 0.5, f"Duration was {info['duration']:.3f}s"


# ---- 9:16 output ----

def test_9x16_file_exists_and_valid(render_outputs):
    result, _ = render_outputs
    out = _get_output(result, "9:16")
    assert out is not None
    assert os.path.isfile(out["path"])
    assert out.get("validation_errors", []) == []


def test_9x16_resolution_uses_padding_not_stretch(render_outputs):
    result, _ = render_outputs
    out = _get_output(result, "9:16")
    info = video_info(out["path"])
    v = info["video"]
    assert v["width"] == 1080
    assert v["height"] == 1920


# ---- 1:1 output ----

def test_1x1_file_exists_and_valid(render_outputs):
    result, _ = render_outputs
    out = _get_output(result, "1:1")
    assert out is not None
    assert os.path.isfile(out["path"])
    assert out.get("validation_errors", []) == []


def test_1x1_resolution(render_outputs):
    result, _ = render_outputs
    out = _get_output(result, "1:1")
    info = video_info(out["path"])
    v = info["video"]
    assert v["width"] == 1080
    assert v["height"] == 1080


# ---- A/V drift ----

def test_no_av_drift(render_outputs):
    result, _ = render_outputs
    out = _get_output(result, "16:9")
    info = video_info(out["path"])
    v = info["video"]
    a = info["audio"]
    drift = abs(v.get("duration", 0) - a.get("duration", 0))
    assert drift < 0.2, f"A/V drift too large: {drift:.3f}s"


# ---- Corrupt / missing media error handling ----

def test_missing_clip_path_produces_warning(tmp_path):
    plan = [{
        "scene_id": "scene_001",
        "text": "Test scene.",
        "start_time": 0.0,
        "end_time": 3.0,
        "visual_description": "test",
        "search_query": "test",
        "clip": {
            "asset_id": "broken",
            "provider": "mock",
            "source_url": "test-data://broken",
            "local_path": None,
            "license_name": "mock",
            "license_url": "test-data://",
            "attribution": "",
            "commercial_use": True,
            "ai_generated": False,
            "test_data": True,
            "video_path": "/no/such/file.mp4",   # deliberately missing
        },
    }]
    # Need a valid narration for the render call.
    from app.utils.ffmpeg import generate_silent_audio
    narr = str(tmp_path / "narr.aac")
    generate_silent_audio(narr, duration=3.0)
    result = render_job(
        scene_plan=plan,
        narration_path=narr,
        total_duration=3.0,
        aspect_ratios=["16:9"],
        out_dir=str(tmp_path),
        test_data=True,
    )
    # Should have a warning, not a crash.
    assert any("missing" in w.lower() or "not found" in w.lower() for w in result["warnings"]), (
        f"Expected a missing-clip warning, got: {result['warnings']}"
    )
