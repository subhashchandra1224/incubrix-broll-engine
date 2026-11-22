"""Data models passed between the pipeline and provider adapters.

Everything produced by a mock adapter carries test_data=True so it can never be
mistaken for real transcript/audio/footage/licence/score data.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class WordTiming(BaseModel):
    text: str
    start: float
    end: float
    test_data: bool = True


class Transcript(BaseModel):
    text: str
    words: list[WordTiming]
    language: str = "en"
    duration: float
    provider: str
    test_data: bool = True


class SynthesisResult(BaseModel):
    """Result of TTS: a duration + word timings (audio file comes in Phase 6)."""
    duration: float
    words: list[WordTiming]
    voice: str | None = None
    audio_path: str | None = None
    provider: str
    test_data: bool = True


class Scene(BaseModel):
    scene_id: str
    text: str
    start_time: float
    end_time: float
    visual_description: str
    search_query: str
    warnings: list[str] = Field(default_factory=list)


class LicenceInfo(BaseModel):
    provider: str
    asset_id: str
    source_url: str
    download_url: str | None = None
    local_path: str | None = None
    license_name: str
    license_url: str
    attribution: str
    commercial_use: bool
    ai_generated: bool


class FootageClip(BaseModel):
    provider: str
    asset_id: str
    description: str
    tags: list[str] = Field(default_factory=list)
    duration_seconds: float = 0.0
    width: int = 0
    height: int = 0
    licence: LicenceInfo
    test_data: bool = True


class SelectedClip(BaseModel):
    """The clip chosen for a scene, with the licence fields the brief requires
    in timeline.json (Must-have 3)."""
    asset_id: str
    provider: str
    source_url: str
    local_path: str | None = None
    license_name: str
    license_url: str
    attribution: str
    commercial_use: bool
    ai_generated: bool
    test_data: bool = True


class ClipSelection(BaseModel):
    clip: SelectedClip
    relevance_score: float
    selection_reason: str
    test_data: bool = True


class SafetyResult(BaseModel):
    allowed: bool
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    test_data: bool = True
