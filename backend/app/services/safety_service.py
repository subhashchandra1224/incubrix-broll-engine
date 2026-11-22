"""Safety checks via the configured SafetyProvider."""
from __future__ import annotations

from app.providers.factory import get_safety_provider
from app.schemas.providers import FootageClip, SafetyResult


def check(scene_text: str, clip: FootageClip | None, avoid: list[str]) -> SafetyResult:
    return get_safety_provider().check(scene_text, clip, avoid or [])
