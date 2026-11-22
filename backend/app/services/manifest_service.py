"""Generate manifest.json with provider/model versions, settings, timings,
cost estimates, warnings, and rights information.

The manifest describes the actual execution, not a predefined fictional
example. All costs are $0 and labelled "measured: false" when using mock
providers. When real providers are wired, actual costs will be measured and
the "measured" flag will be set to true.

Fixture records are clearly labelled with test_data=True.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from app.config import get_settings

log = logging.getLogger(__name__)


def build_manifest(
    job_id: str,
    job_result: dict,
    request: dict,
    *,
    pipeline_start: float,
    pipeline_end: float,
    test_data: bool = True,
    seed: str | None = None,
) -> dict:
    """Build the manifest.json structure.

    Args:
        job_id: the job identifier.
        job_result: the full result dict from the pipeline (outputs, scenes,
                    providers, warnings, etc.).
        request: the original request dict.
        pipeline_start: monotonic timestamp at pipeline start.
        pipeline_end: monotonic timestamp at pipeline end.
        test_data: whether all outputs are test data (mocks).
        seed: deterministic seed derived from the request (for reproducibility).
    """
    settings = get_settings()
    duration = job_result.get("narration_duration", 0)

    # Determine whether all providers are mock (affects cost labelling).
    all_mock = all(
        v == "mock"
        for v in [
            settings.stt_provider,
            settings.tts_provider,
            settings.embeddings_provider,
            settings.scene_provider,
            settings.safety_provider,
        ]
    )
    cost_note = (
        "All mock providers — no real cost incurred."
        if all_mock
        else "Mixed providers — see individual entries."
    )

    return {
        "job_id": job_id,
        "application_version": settings.app_version,
        "creation_time": datetime.now(timezone.utc).isoformat(),
        "test_data": test_data,
        "input": {
            "type": job_result.get("input_type"),
            "narration_duration_seconds": duration,
            "aspect_ratios": request.get("aspect_ratios", []),
            "style": request.get("style"),
            "avoid": request.get("avoid", []),
            "captions": request.get("captions"),
            "voice": request.get("voice"),
        },
        "outputs": {
            "videos": [
                {
                    "ratio": o.get("ratio"),
                    "filename": os.path.basename(o.get("path", "")),
                    "burned_in": o.get("burned_in", False),
                    "validation_errors": o.get("validation_errors", []),
                }
                for o in job_result.get("outputs", [])
            ],
            "srt": (
                os.path.basename(job_result["srt_path"])
                if job_result.get("srt_path")
                else None
            ),
            "timeline": "timeline.json",
            "manifest": "manifest.json",
        },
        "providers": job_result.get("providers", {}),
        "models": {
            "stt": {"name": settings.stt_provider, "version": "mock" if settings.stt_provider == "mock" else "pending"},
            "tts": {"name": settings.tts_provider, "version": "mock" if settings.tts_provider == "mock" else "pending"},
            "scene": {"name": settings.scene_provider, "version": "mock" if settings.scene_provider == "mock" else "pending"},
            "embeddings": {
                "name": settings.embeddings_provider,
                "version": "mock" if settings.embeddings_provider == "mock" else "pending",
            },
            "footage": {
                "name": settings.footage_provider,
                "version": "mock" if settings.footage_provider == "mock" else "pending",
            },
            "safety": {
                "name": settings.safety_provider,
                "version": "mock" if settings.safety_provider == "mock" else "pending",
            },
        },
        "settings": {
            "environment": settings.environment,
            "footage_provider_chain": settings.footage_provider_chain,
            "job_max_retries": settings.job_max_retries,
            "max_audio_duration_seconds": settings.max_audio_duration_seconds,
        },
        "rendering": {
            "fps": settings.video_fps,
            "video_codec": settings.video_codec,
            "audio_codec": settings.audio_codec,
            "sample_rate": settings.audio_sample_rate,
            "resolutions": {
                "16:9": settings.resolution_16_9,
                "9:16": settings.resolution_9_16,
                "1:1": settings.resolution_1_1,
            },
        },
        "seed": seed,
        "timings": {
            "pipeline_total_seconds": round(pipeline_end - pipeline_start, 3),
            "narration_duration_seconds": duration,
        },
        "cost": {
            "footage": {"amount": 0.0, "currency": "USD", "measured": False, "note": "mock provider — no real cost"},
            "tts": {"amount": 0.0, "currency": "USD", "measured": False, "note": "mock TTS — no real cost"},
            "transcription": {"amount": 0.0, "currency": "USD", "measured": False, "note": "mock STT — no real cost"},
            "embeddings": {"amount": 0.0, "currency": "USD", "measured": False, "note": "mock embeddings — no real cost"},
            "compute": {"amount": 0.0, "currency": "USD", "measured": False, "note": "local execution"},
            "total": {"amount": 0.0, "currency": "USD", "measured": False, "note": cost_note},
            "per_minute": {
                "amount": 0.0,
                "currency": "USD",
                "measured": False,
                "note": f"narration_duration={duration}s",
            },
        },
        "rights": {
            "all_clips_test_data": test_data,
            "licence": "Mock test-data licence (not a real licence)" if test_data else "Pending verification in SOURCES.md",
            "commercial_use": True,
            "ai_generated": False,
            "note": (
                "All footage is test data from mock providers. No real footage rights apply."
                if test_data
                else "Real footage rights pending verification in SOURCES.md."
            ),
        },
        "warnings": job_result.get("warnings", []),
        "errors": job_result.get("render_validation", []),
        "validation": {
            "coverage_warnings": job_result.get("coverage_warnings", []),
            "render_validation": job_result.get("render_validation", []),
        },
    }


def write_manifest(manifest: dict, out_path: str) -> str:
    """Write manifest.json to disk and return the path."""
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    log.info("Wrote manifest.json to %s", out_path)
    return out_path
