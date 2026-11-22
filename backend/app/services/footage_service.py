"""Footage selection with provider fallback, safety filtering, no repeats, and
relevance scoring.

Per scene, try each provider in the configured chain (primary then fallbacks):
- a provider that raises is logged and skipped (fallback);
- a provider that returns no clips is skipped (fallback);
- clips returned are filtered by commercial licence, the safety/avoid check,
  and the no-repeat rule, then scored by semantic relevance; the best is chosen.
If every provider is exhausted with no usable clip, raise FootageUnavailableError
so the pipeline can mark the scene unavailable (or fail the job if none work).
"""
from __future__ import annotations

import logging

from app.api.errors import FootageUnavailableError
from app.config import get_settings
from app.providers.factory import get_footage_provider
from app.schemas.providers import ClipSelection, Scene, SelectedClip
from app.services import safety_service, semantic_service

log = logging.getLogger(__name__)


def select_clip(scene: Scene, used_ids: set[str], avoid: list[str]) -> ClipSelection:
    chain = get_settings().footage_provider_chain
    attempts: list[dict] = []

    for name in chain:
        try:
            provider = get_footage_provider(name)
            clips = provider.search(scene.search_query)
        except Exception as exc:  # noqa: BLE001 - any provider error -> fallback
            attempts.append({"provider": name, "result": "error", "detail": str(exc)})
            log.warning("Footage provider '%s' failed for scene %s: %s", name, scene.scene_id, exc)
            continue

        if not clips:
            attempts.append({"provider": name, "result": "empty"})
            continue

        scored: list[tuple[float, object]] = []
        for clip in clips:
            if not clip.licence or not clip.licence.commercial_use:
                continue
            cid = f"{clip.provider}:{clip.asset_id}"
            if cid in used_ids:
                continue
            if not safety_service.check(scene.text, clip, avoid).allowed:
                continue
            rel = semantic_service.relevance(scene.search_query, clip)
            scored.append((rel, clip))

        if scored:
            scored.sort(key=lambda x: x[0], reverse=True)
            best_rel, best_clip = scored[0]
            lic = best_clip.licence
            selected = SelectedClip(
                asset_id=best_clip.asset_id, provider=best_clip.provider,
                source_url=lic.source_url, local_path=lic.local_path,
                license_name=lic.license_name, license_url=lic.license_url,
                attribution=lic.attribution, commercial_use=lic.commercial_use,
                ai_generated=lic.ai_generated, test_data=best_clip.test_data,
            )
            reason = (
                f"Best semantic match (relevance {best_rel:.2f}) from '{best_clip.provider}'; "
                "licence permits commercial use; safety passed."
            )
            return ClipSelection(clip=selected, relevance_score=best_rel,
                                 selection_reason=reason, test_data=True)

        attempts.append({"provider": name, "result": "no_usable_clips"})

    raise FootageUnavailableError(
        f"No usable footage for scene {scene.scene_id} after trying providers {chain}.",
        details={"scene_id": scene.scene_id, "attempts": attempts},
    )
