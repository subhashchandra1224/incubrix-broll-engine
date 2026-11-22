"""Abstract provider interfaces (the "small adapter" contract).

Every external AI capability sits behind one of these interfaces and is chosen
by configuration (see app.providers.factory). A mock implementation exists for
each so the whole pipeline runs with zero API keys. Real adapters are added
behind the same interfaces only after their commercial-use terms are verified.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod

from app.schemas.providers import (
    FootageClip,
    SafetyResult,
    Scene,
    SynthesisResult,
    Transcript,
)


class STTProvider(ABC):
    name = "stt"

    @abstractmethod
    def transcribe(self, audio_ref: str, language: str | None = None) -> Transcript:
        """Transcribe audio (a path or URL) and return text + word timings."""


class TTSProvider(ABC):
    name = "tts"

    @abstractmethod
    def synthesize(self, text: str, voice: str | None = None) -> SynthesisResult:
        """Synthesize narration; return duration + word timings (audio file in Phase 6)."""


class SceneUnderstandingProvider(ABC):
    name = "scene"

    @abstractmethod
    def segment(self, transcript: Transcript, hints: list[dict] | None = None) -> list[Scene]:
        """Segment a transcript into scenes with timing + visual description + query."""

    # Helpers used when an IncuBrix scene list is supplied (text + visual hint).
    def describe_one(self, text: str, hint: str | None = None) -> str:
        return hint or f"footage illustrating {text[:60]}"

    def query_for(self, text: str, hint: str | None = None) -> str:
        return hint or text[:80]


class EmbeddingsProvider(ABC):
    name = "embeddings"
    dimension: int = 256

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return a fixed-dimension vector for the text."""

    def cosine(self, a: list[float], b: list[float]) -> float:
        if not a or not b:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return max(-1.0, min(1.0, dot / (na * nb)))


class FootageProvider(ABC):
    name = "footage"

    @abstractmethod
    def search(self, query: str, aspect_ratio: str | None = None, max_results: int = 5) -> list[FootageClip]:
        """Search for commercially-usable footage clips matching the query."""


class SafetyProvider(ABC):
    name = "safety"

    @abstractmethod
    def check(self, scene_text: str, clip: FootageClip | None, avoid: list[str]) -> SafetyResult:
        """Decide whether a scene/clip is safe to use, given user avoid terms."""
