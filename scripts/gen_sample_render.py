"""Generate a keepable sample render into test_data/sample_render/.

Run from the project root:
    python scripts/gen_sample_render.py

Produces three MP4 files (16:9, 9:16, 1:1) + captions.srt using deterministic
test fixtures (sine-tone narration + colour-bar video).  Outputs are labelled
TEST-DATA.  FFprobe verification results are printed.

This is NOT an automated test — it is a manual step to produce the
keepable sample required by the brief ("keep a playable sample and its
verification output").
"""
from __future__ import annotations

import os
import sys

# --- path setup ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BACKEND = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND)

from app.utils.ffmpeg import ffmpeg_available, ffprobe_available, video_info, validate_output
from app.utils.fixtures import generate_fixtures
from app.services.rendering_service import render_job

OUT_DIR = os.path.join(PROJECT_ROOT, "test_data", "sample_render")
FIX_DIR = os.path.join(PROJECT_ROOT, "test_data", "fixtures")


def main() -> None:
    if not ffmpeg_available():
        sys.exit("ffmpeg not found. Install via: winget install Gyan.FFmpeg")
    if not ffprobe_available():
        sys.exit("ffprobe not found. Install via: winget install Gyan.FFmpeg")

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(FIX_DIR, exist_ok=True)

    print("Generating test fixtures …")
    fs = generate_fixtures(FIX_DIR)
    print(f"  {len(fs.scenes)} scenes, narration duration={fs.total_duration}s")

    plan = []
    for sc in fs.scenes:
        plan.append({
            "scene_id": f"scene_{sc.index + 1:03d}",
            "text": sc.text,
            "start_time": sc.start_time,
            "end_time": sc.end_time,
            "visual_description": f"TEST-DATA colour-bar fixture scene {sc.index}",
            "search_query": f"test fixture scene {sc.index}",
            "clip": {
                "asset_id": f"fixture_{sc.index}",
                "provider": "mock",
                "source_url": "test-data://fixture",
                "local_path": None,
                "license_name": "Mock test-data licence (not a real licence)",
                "license_url": "test-data://mock/licence",
                "attribution": "TEST-DATA generated fixture",
                "commercial_use": True,
                "ai_generated": False,
                "test_data": True,
                "video_path": sc.video_path,
            },
        })

    print("Rendering …")
    result = render_job(
        scene_plan=plan,
        narration_path=fs.narration_path,
        total_duration=fs.total_duration,
        aspect_ratios=["16:9", "9:16", "1:1"],
        out_dir=OUT_DIR,
        burn_in_captions=False,
        write_srt_file=True,
        test_data=True,
    )

    print("\n=== Rendered outputs ===")
    all_ok = True
    for out in result["outputs"]:
        info = video_info(out["path"])
        v = info["video"]
        a = info["audio"]
        errors = out.get("validation_errors", [])
        status = "OK" if not errors else f"ERRORS: {errors}"
        print(
            f"  [{out['ratio']:5s}] {os.path.basename(out['path'])}"
            f"  {v['width']}x{v['height']}  {v['fps']:.0f}fps  "
            f"codec={v['codec']}  audio={a['codec'] if a else 'none'}"
            f"  dur={info['duration']:.2f}s  {status}"
        )
        if errors:
            all_ok = False

    if result.get("srt_path"):
        print(f"\n  SRT: {result['srt_path']}")
    if result.get("warnings"):
        print("\n  Warnings:")
        for w in result["warnings"]:
            print(f"    - {w}")

    print(f"\n{'All outputs valid.' if all_ok else 'Some outputs have validation errors.'}")
    print(f"Sample render saved to: {OUT_DIR}")


if __name__ == "__main__":
    main()
