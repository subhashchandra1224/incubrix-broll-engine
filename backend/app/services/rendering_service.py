"""Video rendering service: normalise clips, concatenate, mix narration, produce outputs.

This is the core of Must-have 4 (correct, consistent video). It orchestrates
app.utils.ffmpeg operations and produces the deliverable MP4 files.

Design decisions:
- narration audio is the master duration reference; video adapts to it.
- Each clip is individually normalised (scale+pad, fps, pixel format, codec)
  before concatenation so the concat step never inherits format mismatches.
- 9:16 and 1:1 ratios use scale+pad (not crop+stretch) so subjects are never
  cut off, satisfying 'preserve important subject during reframing'.
- apad + -shortest in the concat ensures the output matches narration duration
  even when clips are slightly shorter or longer.
- Burn-in captions are a post-process on the finished 16:9 render; other ratios
  get separate burn-in passes when requested.

RESOLUTION MAP (from config):
  16:9  -> 1920 x 1080
  9:16  -> 1080 x 1920
  1:1   -> 1080 x 1080
"""
from __future__ import annotations

import logging
import os
import tempfile

from app.config import get_settings
from app.services.caption_service import write_srt
from app.utils.ffmpeg import (
    burn_captions,
    concat_clips_with_audio,
    normalise_clip,
    validate_output,
)

log = logging.getLogger(__name__)
settings = get_settings()

_RATIO_TO_RES: dict[str, tuple[int, int]] = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
}


def render_job(
    *,
    scene_plan: list[dict],
    narration_path: str,
    total_duration: float,
    aspect_ratios: list[str],
    out_dir: str,
    burn_in_captions: bool = False,
    write_srt_file: bool = True,
    test_data: bool = True,
) -> dict:
    """Render one or more aspect-ratio outputs from a scene plan + narration audio.

    Args:
        scene_plan: list of scene dicts (from pipeline.py); each has
                    start_time, end_time, text, and clip.local_path or
                    clip.video_path (fixture path).
        narration_path: path to the full narration audio file (AAC/WAV).
        total_duration: expected narration duration in seconds (reference).
        aspect_ratios: e.g. ["16:9", "9:16"].
        out_dir: directory where output files are written.
        burn_in_captions: if True, also produce a *_burned.mp4 for each ratio.
        write_srt_file: if True, write captions.srt.
        test_data: if True, label SRT and outputs as test data.

    Returns:
        dict with 'outputs' (list of paths), 'srt_path', 'validation_results',
        'warnings', 'test_data'.
    """
    from app.schemas.providers import Scene

    os.makedirs(out_dir, exist_ok=True)
    warnings: list[str] = []
    outputs: list[dict] = []

    # Build Scene objects for captioning from the scene plan.
    scenes: list[Scene] = [
        Scene(
            scene_id=sc["scene_id"],
            text=sc["text"],
            start_time=sc["start_time"],
            end_time=sc["end_time"],
            visual_description=sc.get("visual_description", ""),
            search_query=sc.get("search_query", ""),
        )
        for sc in scene_plan if sc.get("clip") is not None
    ]

    # Write SRT.
    srt_path: str | None = None
    if write_srt_file and scenes:
        srt_path = os.path.join(out_dir, "captions.srt")
        write_srt(scenes, srt_path, test_data=test_data)
        log.info("SRT written: %s", srt_path)

    # Per aspect ratio.
    for ratio in aspect_ratios:
        if ratio not in _RATIO_TO_RES:
            warnings.append(f"Unknown aspect ratio {ratio!r}; skipped.")
            continue
        width, height = _RATIO_TO_RES[ratio]
        ratio_slug = ratio.replace(":", "_")

        with tempfile.TemporaryDirectory(prefix=f"norm_{ratio_slug}_") as norm_dir:
            normalised_clips: list[str] = []
            for i, sc in enumerate(scene_plan):
                clip = sc.get("clip")
                if clip is None:
                    warnings.append(f"Scene {sc['scene_id']} has no clip; skipped in render.")
                    continue
                # Clip may come from a fixture (video_path) or a future real download.
                clip_src = clip.get("video_path") or clip.get("local_path")
                if not clip_src or not os.path.isfile(clip_src):
                    warnings.append(
                        f"Scene {sc['scene_id']} clip path missing or not found "
                        f"({clip_src!r}); skipped in render."
                    )
                    continue
                clip_dur = round(sc["end_time"] - sc["start_time"], 3)
                norm_path = os.path.join(norm_dir, f"scene_{i:03d}_{ratio_slug}.mp4")
                try:
                    normalise_clip(
                        clip_src, norm_path,
                        width=width, height=height,
                        fps=30, duration=clip_dur,
                    )
                    normalised_clips.append(norm_path)
                except Exception as exc:  # noqa: BLE001
                    warnings.append(
                        f"Scene {sc['scene_id']} normalisation failed: {exc}; skipped."
                    )
                    continue

            if not normalised_clips:
                warnings.append(f"No clips normalised for ratio {ratio!r}; skipped.")
                continue

            out_path = os.path.join(out_dir, f"video_{ratio_slug}.mp4")
            try:
                concat_clips_with_audio(
                    normalised_clips, narration_path, out_path,
                    narration_duration=total_duration,
                    fps=30, timeout=300,
                )
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Render failed for {ratio!r}: {exc}")
                continue

        # Validate.
        v_errors = validate_output(out_path, expected_duration=total_duration,
                                   duration_tolerance=0.5)
        outputs.append({
            "ratio": ratio,
            "path": out_path,
            "validation_errors": v_errors,
            "test_data": test_data,
        })

        # Optional burn-in captions.
        if burn_in_captions and srt_path:
            burned_path = os.path.join(out_dir, f"video_{ratio_slug}_burned.mp4")
            try:
                burn_captions(out_path, burned_path, srt_path)
                b_errors = validate_output(burned_path)
                outputs.append({
                    "ratio": ratio,
                    "path": burned_path,
                    "burned_in": True,
                    "validation_errors": b_errors,
                    "test_data": test_data,
                })
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"Burn-in failed for {ratio!r}: {exc}")

    return {
        "outputs": outputs,
        "srt_path": srt_path,
        "warnings": warnings,
        "test_data": test_data,
    }
