"""Phase 4 pipeline: a mock-provider pipeline that exercises STT/TTS, scene
understanding, footage search (with fallback), safety, and relevance, and
produces a draft scene plan.

IMPORTANT: no video is rendered yet (that is Phase 6). Every transcript, timing,
footage clip, licence and relevance score produced here is TEST DATA (labelled),
from mock adapters. Real adapters are added later behind the same interfaces.

The job API contract is unchanged: this still returns a result dict stored on
the job; the worker still drives it via run_pipeline(job, progress).
"""
from __future__ import annotations

import logging

from app.api.errors import FootageUnavailableError
from app.config import get_settings
from app.schemas.providers import ClipSelection, Scene
from app.services import footage_service, narration_service, scene_service

log = logging.getLogger(__name__)
settings = get_settings()


def run_pipeline(job, progress) -> dict:
    log.info("Phase 4 provider pipeline running for job %s (mock providers; no rendering)", job.id)
    request = job.request or {}
    avoid = request.get("avoid") or []

    progress(5)
    transcript, duration, input_type = narration_service.build_narration(request)

    progress(20)
    scenes = scene_service.build_scenes(request, transcript)

    progress(40)
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

    progress(80)
    if not any(p["clip"] for p in plan):
        # Every scene failed to get footage -> fail the job with a clear error.
        raise FootageUnavailableError(
            "No footage could be obtained for any scene (all providers failed or returned no usable results).",
            details={"unavailable_scenes": unavailable},
        )

    progress(100)
    return {
        "pipeline": "phase4-mock-providers",
        "test_data": True,
        "note": (
            "Phase 4 provider pipeline using mock adapters. No video was rendered. "
            "All transcripts, timings, footage and scores are test data."
        ),
        "input_type": input_type,
        "narration_duration": round(duration, 3),
        "scene_count": len(scenes),
        "scenes": plan,
        "warnings": [] if not unavailable else [f"{len(unavailable)} scene(s) without footage: {unavailable}"],
        "providers": {
            "stt": settings.stt_provider,
            "tts": settings.tts_provider,
            "scene": settings.scene_provider,
            "embeddings": settings.embeddings_provider,
            "footage": settings.footage_provider_chain,
            "safety": settings.safety_provider,
        },
    }


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
