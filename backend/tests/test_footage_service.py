"""Footage selection: fallback when the primary provider fails or returns no
results; clear error (FOOTAGE_UNAVAILABLE) when all providers fail; no repeats;
safety filtering.

These exercise Must-have 7 (resilient jobs / provider fallback) at the service
level; the worker integration is covered in test_pipeline_phase4.py.
"""
from __future__ import annotations

import pytest

from app.api.errors import FootageUnavailableError
from app.config import get_settings
from app.schemas.providers import Scene
from app.services import footage_service


def _scene(query: str = "household budget", text: str = "A household budget helps saving.") -> Scene:
    return Scene(scene_id="scene_001", text=text, start_time=0.0, end_time=3.0,
                  visual_description=f"footage illustrating {query}", search_query=query)


def _chain(monkeypatch, primary: str, fallback: str = "") -> None:
    s = get_settings()
    monkeypatch.setattr(s, "footage_provider", primary)
    monkeypatch.setattr(s, "footage_fallback_providers", fallback)


def test_fallback_when_primary_fails(monkeypatch):
    _chain(monkeypatch, "mock_fail", "mock")
    sel = footage_service.select_clip(_scene(), set(), [])
    assert sel.clip is not None
    assert sel.clip.provider == "mock"
    assert sel.clip.test_data is True
    assert sel.clip.commercial_use is True
    assert sel.selection_reason


def test_fallback_when_primary_returns_no_results(monkeypatch):
    _chain(monkeypatch, "mock_empty", "mock")
    sel = footage_service.select_clip(_scene(), set(), [])
    assert sel.clip is not None
    assert sel.clip.provider == "mock"


def test_all_providers_fail_raises(monkeypatch):
    _chain(monkeypatch, "mock_fail", "mock_fail")
    with pytest.raises(FootageUnavailableError) as ei:
        footage_service.select_clip(_scene(), set(), [])
    assert ei.value.code == "FOOTAGE_UNAVAILABLE"
    assert ei.value.retryable is False


def test_all_providers_empty_raises(monkeypatch):
    _chain(monkeypatch, "mock_empty", "mock_empty")
    with pytest.raises(FootageUnavailableError):
        footage_service.select_clip(_scene(), set(), [])


def test_no_repeats_across_scenes_with_same_query(monkeypatch):
    _chain(monkeypatch, "mock", "")
    used: set[str] = set()
    s1 = footage_service.select_clip(_scene("budget money"), used, [])
    used.add(f"{s1.clip.provider}:{s1.clip.asset_id}")
    s2 = footage_service.select_clip(_scene("budget money"), used, [])
    assert f"{s2.clip.provider}:{s2.clip.asset_id}" != f"{s1.clip.provider}:{s1.clip.asset_id}"


def test_safety_filters_blocked_clips_but_still_selects(monkeypatch):
    _chain(monkeypatch, "mock", "")
    # "background" is in the weak-match clip's description; it is skipped, the
    # exact-match clip (index 0) is selected.
    sel = footage_service.select_clip(_scene(query="budget", text="budget"), set(), avoid=["background"])
    assert sel.clip is not None
    assert sel.clip.asset_id.endswith("_0")


def test_all_clips_blocked_by_safety_raises(monkeypatch):
    _chain(monkeypatch, "mock", "")
    with pytest.raises(FootageUnavailableError):
        footage_service.select_clip(_scene(query="budget", text="budget"), set(), avoid=["budget"])


def test_selection_is_deterministic(monkeypatch):
    _chain(monkeypatch, "mock", "")
    sel1 = footage_service.select_clip(_scene("budget money"), set(), [])
    sel2 = footage_service.select_clip(_scene("budget money"), set(), [])
    assert sel1.clip.asset_id == sel2.clip.asset_id
    assert sel1.relevance_score == sel2.relevance_score
