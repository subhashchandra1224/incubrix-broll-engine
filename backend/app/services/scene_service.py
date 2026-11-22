"""Build scenes (with timing) from a transcript or a supplied IncuBrix scene list."""
from __future__ import annotations

import logging

from app.providers.factory import get_scene_provider
from app.schemas.providers import Scene, Transcript

log = logging.getLogger(__name__)


def build_scenes(request: dict, transcript: Transcript) -> list[Scene]:
    if request.get("scenes"):
        return _from_scene_list(request, transcript)
    return get_scene_provider().segment(transcript)


def _from_scene_list(request: dict, transcript: Transcript) -> list[Scene]:
    scene_prov = get_scene_provider()
    scenes_in = request["scenes"]
    out: list[Scene] = []
    wi = 0  # index into transcript.words (TTS produced them in scene order)
    for i, s in enumerate(scenes_in):
        s_text = s["text"]
        n = len(s_text.split())
        sw = transcript.words[wi:wi + n]
        wi += n
        start = sw[0].start if sw else 0.0
        end = sw[-1].end if sw else start
        hint = s.get("visual_hint")
        out.append(Scene(
            scene_id=f"scene_{i + 1:03d}", text=s_text,
            start_time=round(start, 3), end_time=round(end, 3),
            visual_description=scene_prov.describe_one(s_text, hint),
            search_query=scene_prov.query_for(s_text, hint),
        ))
    return out
