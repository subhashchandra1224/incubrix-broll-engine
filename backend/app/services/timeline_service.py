"""Generate timeline.json from the scene plan and rendered outputs.

The timeline records, for every scene: narration text and times, the clip
used, its source, licence, attribution, AI-generated flag, test-data flag,
selection reason, relevance score, and any warnings. Substitutions and
fallbacks are recorded explicitly in a top-level `fallbacks` list.

Schema follows the brief's timeline.json example (Must-have 3, Integration
Standard #9).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def build_timeline(
    job_id: str,
    scene_plan: list[dict],
    total_duration: float,
    narration_duration: float,
    *,
    test_data: bool = True,
    warnings: list[str] | None = None,
    fallbacks: list[dict] | None = None,
) -> dict:
    """Build the timeline.json structure from the scene plan.

    Each scene entry includes: scene_id, text, start_time, end_time, duration,
    visual_description, search_query, clip (with full licence metadata),
    relevance_score, selection_reason, warnings.

    The top-level `fallbacks` list records any scene where the primary footage
    provider failed and a fallback was used.
    """
    scenes = []
    for sc in scene_plan:
        clip = sc.get("clip")
        scene_entry = {
            "scene_id": sc["scene_id"],
            "text": sc["text"],
            "start_time": sc["start_time"],
            "end_time": sc["end_time"],
            "duration": sc["duration"],
            "visual_description": sc.get("visual_description", ""),
            "search_query": sc.get("search_query", ""),
            "clip": clip,
            "relevance_score": sc.get("relevance_score"),
            "selection_reason": sc.get("selection_reason"),
            "warnings": sc.get("warnings", []),
        }
        scenes.append(scene_entry)

    return {
        "job_id": job_id,
        "total_duration": round(total_duration, 3),
        "narration_duration": round(narration_duration, 3),
        "test_data": test_data,
        "scene_count": len(scenes),
        "scenes": scenes,
        "fallbacks": fallbacks or [],
        "warnings": warnings or [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def write_timeline(timeline: dict, out_path: str) -> str:
    """Write timeline.json to disk and return the path."""
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(timeline, fh, indent=2, ensure_ascii=False)
    log.info("Wrote timeline.json to %s (%d scenes)", out_path, len(timeline.get("scenes", [])))
    return out_path
