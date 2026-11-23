"""Phase 6 pipeline: full render path using FFmpeg.

The pipeline now:
  1. Builds narration (mock TTS or STT — audio file from fixtures in test mode).
  2. Segments into scenes.
  3. Selects footage (mock provider returns fixture video paths in test mode).
  4. Renders all requested aspect ratios with FFmpeg.
  5. Generates SRT captions and optionally burns them in.
  6. Validates outputs with FFprobe.
  7. Returns a result dict with per-scene plan + rendered output paths.

IMPORTANT: in automated tests the narration audio and video clips are
deterministic test fixtures (sine-tone audio + colour-bar video) generated
locally by FFmpeg. They are labelled test_data=True throughout. No real
footage or real speech is produced until a live TTS / footage provider is
wired (see SOURCES.md for the TTS candidates under evaluation).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time as _time

from app.api.errors import FootageUnavailableError
from app.config import get_settings
from app.schemas.providers import ClipSelection, Scene
from app.services import footage_service, narration_service, scene_service
from app.services.manifest_service import build_manifest, write_manifest
from app.services.rendering_service import render_job
from app.services.segmentation import validate_coverage
from app.services.timeline_service import build_timeline, write_timeline

log = logging.getLogger(__name__)
settings = get_settings()


def run_pipeline(job, progress) -> dict:
    log.info("Phase 6 pipeline: job %s", job.id)
    request = job.request or {}
    avoid = request.get("avoid") or []
    aspect_ratios = request.get("aspect_ratios") or ["16:9"]
    burn_in = (request.get("captions") or {}).get("burn_in", False)
    write_srt = (request.get("captions") or {}).get("srt", True)
    pipeline_start = _time.monotonic()

    progress(5)
    transcript, duration, input_type = narration_service.build_narration(request)

    progress(15)
    scenes = scene_service.build_scenes(request, transcript)
    coverage_warnings = validate_coverage(scenes, duration)

    progress(30)
    plan: list[dict] = []
    used_ids: set[str] = set()
    unavailable: list[str] = []
    for sc in scenes:
        try:
            sel = footage_service.select_clip(sc, used_ids, avoid)
            used_ids.add(f"{sel.clip.provider}:{sel.clip.asset_id}")
            plan.append(_scene_plan(sc, sel))
        except FootageUnavailableError as exc:
            unavailable.append(sc.scene_id)
            plan.append(_scene_plan_unavailable(sc, exc.message))
            log.warning("Scene %s has no footage: %s", sc.scene_id, exc.message)

    if not any(p["clip"] for p in plan):
        raise FootageUnavailableError(
            "No footage could be obtained for any scene.",
            details={"unavailable_scenes": unavailable},
        )

    # --- Obtain narration audio and per-clip video paths ---
    # In test mode the TTS SynthesisResult.audio_path may be a fixture path.
    # We build the narration audio from fixtures when no real audio is available.
    progress(45)
    narration_audio, out_dir, using_fixtures = _resolve_media(request, transcript, plan, job.id)

    # --- Render ---
    progress(55)
    render_result = render_job(
        scene_plan=plan,
        narration_path=narration_audio,
        total_duration=duration,
        aspect_ratios=aspect_ratios,
        out_dir=out_dir,
        burn_in_captions=burn_in,
        write_srt_file=write_srt,
        test_data=using_fixtures,
    )

    progress(90)
    all_warnings = coverage_warnings + (
        [f"{len(unavailable)} scene(s) without footage: {unavailable}"]
        if unavailable else []
    ) + render_result.get("warnings", [])

    # Collect any validation errors from rendered outputs.
    render_validation: list[dict] = []
    for out in render_result.get("outputs", []):
        if out.get("validation_errors"):
            render_validation.append({
                "path": out["path"],
                "errors": out["validation_errors"],
            })

    # Compute deterministic seed from the request (for reproducibility).
    seed = hashlib.sha256(
        json.dumps(request, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:16]

    # Collect fallback info (scenes where the primary provider was not used).
    chain = settings.footage_provider_chain
    fallbacks = _collect_fallbacks(plan, chain)

    # Build the result dict.
    result: dict = {
        "pipeline": "phase7-metadata",
        "test_data": using_fixtures,
        "note": (
            "Phase 7 pipeline. Rendered with FFmpeg using test fixtures (sine-tone "
            "audio + colour-bar video). No real narration or footage."
            if using_fixtures else
            "Phase 7 pipeline. Rendered with real narration and footage."
        ),
        "input_type": input_type,
        "narration_duration": round(duration, 3),
        "scene_count": len(scenes),
        "seed": seed,
        "coverage_warnings": coverage_warnings,
        "scenes": plan,
        "outputs": render_result.get("outputs", []),
        "srt_path": render_result.get("srt_path"),
        "render_validation": render_validation,
        "warnings": all_warnings,
        "providers": {
            "stt": settings.stt_provider,
            "tts": settings.tts_provider,
            "scene": settings.scene_provider,
            "embeddings": settings.embeddings_provider,
            "footage": settings.footage_provider_chain,
            "safety": settings.safety_provider,
        },
    }

    # --- Generate timeline.json ---
    timeline = build_timeline(
        job_id=job.id,
        scene_plan=plan,
        total_duration=duration,
        narration_duration=duration,
        test_data=using_fixtures,
        warnings=all_warnings,
        fallbacks=fallbacks,
    )
    timeline_path = os.path.join(out_dir, "timeline.json")
    write_timeline(timeline, timeline_path)
    result["timeline_path"] = timeline_path

    # --- Generate manifest.json ---
    pipeline_end = _time.monotonic()
    manifest = build_manifest(
        job_id=job.id,
        job_result=result,
        request=request,
        pipeline_start=pipeline_start,
        pipeline_end=pipeline_end,
        test_data=using_fixtures,
        seed=seed,
    )
    manifest_path = os.path.join(out_dir, "manifest.json")
    write_manifest(manifest, manifest_path)
    result["manifest_path"] = manifest_path

    # --- Upload artifacts to storage (local or MinIO / S3) ---
    from app.utils.storage import get_storage
    store = get_storage()
    upload_errors: list[str] = []
    artifact_urls: dict[str, str] = {}
    # Collect all artifact paths: videos, SRT, timeline, manifest, narration audio.
    artifacts: list[tuple[str, str]] = []
    for out in result.get("outputs", []):
        p = out.get("path")
        if p and os.path.isfile(p):
            fname = os.path.basename(p)
            artifacts.append((p, f"jobs/{job.id}/{fname}"))
    for name, key_field in [
        ("srt_path", "captions.srt"),
        ("timeline_path", "timeline.json"),
        ("manifest_path", "manifest.json"),
    ]:
        p = result.get(name)
        if p and os.path.isfile(p):
            artifacts.append((p, f"jobs/{job.id}/{key_field}"))
    for local_path, key in artifacts:
        try:
            url = store.store(local_path, key)
            artifact_urls[os.path.basename(key)] = url
        except Exception as exc:  # noqa: BLE001
            msg = f"Storage upload failed for {os.path.basename(key)}: {exc}"
            upload_errors.append(msg)
            log.warning(msg)
    if upload_errors:
        result.setdefault("warnings", []).extend(upload_errors)
    result["artifact_urls"] = artifact_urls

    progress(100)
    return result


def _resolve_media(request: dict, transcript, plan: list[dict], job_id: str) -> tuple[str, str, bool]:
    """Return (narration_audio_path, output_dir, using_fixtures).

    For tests (mock TTS, no audio_path): generate fixture audio and attach
    fixture video paths to the plan in-place.
    For real TTS / STT: use the audio path returned by the provider.
    """
    from app.utils.fixtures import generate_fixtures, DEFAULT_SCENE_DURATIONS

    out_dir = os.path.join(settings.storage_local_root, "jobs", job_id)
    os.makedirs(out_dir, exist_ok=True)

    # Check if TTS produced a real audio file.
    audio_path = getattr(transcript, "audio_path", None)
    if not audio_path:
        # Mock TTS: generate fixture media.
        fix_dir = os.path.join(out_dir, "fixtures")
        # Build per-scene durations from the plan.
        durations = [
            round(p["end_time"] - p["start_time"], 3)
            for p in plan if p.get("clip") is not None
        ] or DEFAULT_SCENE_DURATIONS

        fixtures = generate_fixtures(fix_dir, scene_durations=durations)
        # Attach fixture video paths to each plan entry that has a clip.
        fix_idx = 0
        for entry in plan:
            if entry.get("clip") is not None and fix_idx < len(fixtures.scenes):
                entry["clip"]["video_path"] = fixtures.scenes[fix_idx].video_path
                fix_idx += 1
        return fixtures.narration_path, out_dir, True

    return audio_path, out_dir, False


def _scene_plan(sc: Scene, sel: ClipSelection) -> dict:
    return {
        "scene_id": sc.scene_id,
        "text": sc.text,
        "start_time": round(sc.start_time, 3),
        "end_time": round(sc.end_time, 3),
        "duration": round(sc.end_time - sc.start_time, 3),
        "visual_description": sc.visual_description,
        "search_query": sc.search_query,
        "clip": sel.clip.model_dump(mode="json"),
        "relevance_score": round(sel.relevance_score, 4),
        "selection_reason": sel.selection_reason,
        "warnings": list(sc.warnings),
    }


def _scene_plan_unavailable(sc: Scene, reason: str) -> dict:
    return {
        "scene_id": sc.scene_id,
        "text": sc.text,
        "start_time": round(sc.start_time, 3),
        "end_time": round(sc.end_time, 3),
        "duration": round(sc.end_time - sc.start_time, 3),
        "visual_description": sc.visual_description,
        "search_query": sc.search_query,
        "clip": None,
        "relevance_score": None,
        "selection_reason": None,
        "warnings": [f"footage unavailable: {reason}"],
    }


def _collect_fallbacks(plan: list[dict], chain: list[str]) -> list[dict]:
    """Record scenes where the primary footage provider was not used (fallback).

    Returns a list of {scene_id, primary_provider, used_provider, reason} dicts
    for the timeline.json `fallbacks` field.
    """
    fallbacks: list[dict] = []
    primary = chain[0] if chain else "mock"
    for sc in plan:
        clip = sc.get("clip")
        if clip and clip.get("provider") != primary:
            fallbacks.append({
                "scene_id": sc["scene_id"],
                "primary_provider": primary,
                "used_provider": clip.get("provider"),
                "reason": (
                    f"Primary provider '{primary}' failed or returned no results; "
                    f"used fallback '{clip.get('provider')}'."
                ),
            })
    return fallbacks
