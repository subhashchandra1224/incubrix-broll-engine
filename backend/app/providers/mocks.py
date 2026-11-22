"""Deterministic mock implementations of every provider interface.

Every output is reproducible (same input -> same output, using stable sha256
hashes - never Python's randomized hash()) and carries test_data=True so it can
never be mistaken for real transcript/audio/footage/licence/score data.

These are the ONLY providers wired by default; no API keys, no network, no paid
calls. Real providers are added behind the same interfaces later, after their
commercial-use terms are recorded in SOURCES.md.
"""
from __future__ import annotations

import hashlib
import logging
import re

from app.api.errors import UpstreamProviderError
from app.providers.base import (
    EmbeddingsProvider,
    FootageProvider,
    SafetyProvider,
    SceneUnderstandingProvider,
    STTProvider,
    TTSProvider,
)
from app.schemas.providers import (
    FootageClip,
    LicenceInfo,
    SafetyResult,
    Scene,
    SynthesisResult,
    Transcript,
    WordTiming,
)

log = logging.getLogger(__name__)

_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "to", "of", "in", "on", "for",
    "and", "or", "with", "your", "you", "it", "this", "that", "as", "at", "by",
}

# A fixed sample narration used by the mock STT so audio-input jobs still
# produce a segmentable transcript (clearly test data).
_SAMPLE_TRANSCRIPT = (
    "Saving money starts with small decisions. "
    "Track your monthly expenses carefully. "
    "A clear budget builds long term security."
)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _seed_int(text: str, mod: int) -> int:
    return int(_digest(text), 16) % max(1, mod)


def _significant(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in toks if t not in _STOPWORDS][:5]


# --------------------------------------------------------------------------- STT
class MockSTT(STTProvider):
    name = "mock"

    def transcribe(self, audio_ref: str, language: str | None = None) -> Transcript:
        text = _SAMPLE_TRANSCRIPT
        duration = 15.0 + _seed_int(audio_ref or "", 20)  # 15..35s, deterministic
        words = text.split()
        step = duration / max(1, len(words))
        timings = [
            WordTiming(text=w, start=round(i * step, 3), end=round((i + 1) * step, 3))
            for i, w in enumerate(words)
        ]
        return Transcript(text=text, words=timings, language=language or "en",
                          duration=round(duration, 3), provider=self.name, test_data=True)


# --------------------------------------------------------------------------- TTS
class MockTTS(TTSProvider):
    name = "mock"

    def synthesize(self, text: str, voice: str | None = None) -> SynthesisResult:
        words = text.split()
        duration = max(1.0, len(words) * 0.4)  # ~0.4s/word, deterministic
        step = duration / max(1, len(words))
        timings = [
            WordTiming(text=w, start=round(i * step, 3), end=round((i + 1) * step, 3))
            for i, w in enumerate(words)
        ]
        return SynthesisResult(duration=round(duration, 3), words=timings, voice=voice,
                               audio_path=None, provider=self.name, test_data=True)


# -------------------------------------------------------------------- Scene U.
class MockSceneUnderstanding(SceneUnderstandingProvider):
    """Phase 5 improved mock: uses the segmentation module for consistent
    boundary detection, gap-free timing, and long-sentence splitting."""

    name = "mock"

    def segment(self, transcript: Transcript, hints: list[dict] | None = None) -> list[Scene]:
        from app.services.segmentation import segment_transcript

        spans = segment_transcript(transcript)
        scenes: list[Scene] = []
        for i, (text, start, end, estimated) in enumerate(spans):
            vd, sq = self._describe(text)
            w: list[str] = []
            if estimated:
                w.append("timing is estimated (mock TTS — not from real audio)")
            scenes.append(Scene(
                scene_id=f"scene_{i + 1:03d}",
                text=text,
                start_time=start,
                end_time=end,
                visual_description=vd,
                search_query=sq,
                warnings=w,
            ))
        return scenes

    def describe_one(self, text: str, hint: str | None = None) -> str:
        if hint:
            return hint
        vd, _ = self._describe(text)
        return vd

    def query_for(self, text: str, hint: str | None = None) -> str:
        if hint:
            return hint
        _, sq = self._describe(text)
        return sq

    @staticmethod
    def _describe(sent: str) -> tuple[str, str]:
        sig = _significant(sent)
        sq = " ".join(sig) if sig else sent.strip()
        vd = f"footage illustrating {sq}"
        return vd, sq


# -------------------------------------------------------------------- Embeddings
class MockEmbeddings(EmbeddingsProvider):
    name = "mock"
    dimension = 256

    def embed(self, text: str) -> list[float]:
        # Bag-of-words into a fixed dim via a stable hash: shared tokens raise
        # cosine similarity, so relevance scoring works deterministically.
        vec = [0.0] * self.dimension
        for tok in re.findall(r"[a-z0-9]+", (text or "").lower()):
            idx = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16) % self.dimension
            vec[idx] += 1.0
        return vec


# ----------------------------------------------------------------------- Footage
def _mock_licence(query: str, idx: int) -> LicenceInfo:
    asset_id = f"mock_{_digest(query)[:8]}_{idx}"
    return LicenceInfo(
        provider="mock",
        asset_id=asset_id,
        source_url=f"test-data://mock/asset/{asset_id}",
        download_url=None,
        local_path=None,
        license_name="Mock test-data licence (not a real licence)",
        license_url="test-data://mock/licence",
        attribution="Mock footage provider - test data",
        commercial_use=True,
        ai_generated=False,
    )


class MockFootage(FootageProvider):
    name = "mock"

    def search(self, query: str, aspect_ratio: str | None = None, max_results: int = 5) -> list[FootageClip]:
        q = (query or "").strip() or "generic"
        first = _significant(q)
        head = first[0] if first else q
        descriptions = [
            q,                       # exact match -> highest relevance
            f"related {q}",           # partial match
            f"abstract {head} background",  # weak match
        ]
        clips: list[FootageClip] = []
        for i, desc in enumerate(descriptions):
            aid = f"mock_{_digest(q)[:8]}_{i}"
            clips.append(FootageClip(
                provider="mock",
                asset_id=aid,
                description=desc,
                tags=_significant(desc),
                duration_seconds=8.0,
                width=1920, height=1080,
                licence=_mock_licence(q, i),
                test_data=True,
            ))
        return clips


class MockFootageFail(FootageProvider):
    """Always raises - used to exercise the fallback chain."""

    name = "mock_fail"

    def search(self, query: str, aspect_ratio: str | None = None, max_results: int = 5) -> list[FootageClip]:
        raise UpstreamProviderError("mock_fail: footage provider is down (test data)")


class MockFootageEmpty(FootageProvider):
    """Always returns no results - used to exercise the fallback chain."""

    name = "mock_empty"

    def search(self, query: str, aspect_ratio: str | None = None, max_results: int = 5) -> list[FootageClip]:
        return []


# ------------------------------------------------------------------------ Safety
class MockSafety(SafetyProvider):
    """Phase 5 improved mock safety: avoid terms + hard blocklist rules.

    Detects:
    - User-supplied avoid terms in narration or clip description.
    - Hardcoded safety categories: named real people, brand names,
      sensitive/sad news topics, alcohol, faces.

    What this mock CANNOT do (documented honestly):
    - It cannot identify real faces in actual video frames.
    - It cannot verify brand logos in footage.
    - It uses simple keyword matching on text, not vision or NER.
    - Named-people and brand detection covers only the hardcoded lists below;
      an NER model is needed for full coverage (Phase 5 / later).
    """

    name = "mock"

    # Hardcoded sensitive categories (keyword-based, text-only).
    _REAL_PEOPLE: frozenset[str] = frozenset({
        "modi", "biden", "trump", "obama", "elon musk", "musk", "zuckerberg",
        "putin", "xi jinping", "macron", "sunak", "gates", "bezos",
    })
    _BRANDS: frozenset[str] = frozenset({
        "apple", "google", "microsoft", "amazon", "facebook", "meta",
        "tesla", "samsung", "nike", "coca-cola", "coke", "mcdonalds",
        "mcdonald's", "pepsi", "starbucks",
    })
    _SENSITIVE_TOPICS: frozenset[str] = frozenset({
        "death", "murder", "suicide", "terrorist", "terrorism",
        "massacre", "genocide", "rape", "shooting", "bombing",
        "war", "explosion", "flood victims", "disaster",
    })
    _ALCOHOL: frozenset[str] = frozenset({
        "alcohol", "beer", "wine", "whiskey", "vodka", "liquor",
        "cocktail", "drunk", "drinking alcohol",
    })

    def check(
        self, scene_text: str, clip: "FootageClip | None", avoid: list[str]
    ) -> SafetyResult:
        reasons: list[str] = []
        warnings: list[str] = []
        hay = (scene_text or "").lower()
        hay_clip = (clip.description if clip else "").lower()

        # 1. User-supplied avoid terms.
        for term in avoid or []:
            t = (term or "").strip().lower()
            if not t:
                continue
            if t in hay:
                reasons.append(f"avoid term '{term}' found in narration")
            if clip and t in hay_clip:
                reasons.append(f"avoid term '{term}' found in clip description")

        # 2. Named real people (keyword-based, text-only).
        for person in self._REAL_PEOPLE:
            if person in hay:
                warnings.append(
                    f"Real person '{person}' detected in narration. "
                    "Prefer generic contextual footage; do not use their likeness."
                )
                # Allow but warn; block if the clip description also mentions them.
                if clip and person in hay_clip:
                    reasons.append(
                        f"Clip may show real person '{person}'. Blocked."
                    )

        # 3. Brand names.
        for brand in self._BRANDS:
            if brand in hay:
                warnings.append(
                    f"Brand '{brand}' detected in narration. "
                    "Do not invent brand logos; prefer neutral visuals."
                )
                if clip and brand in hay_clip:
                    reasons.append(
                        f"Clip may show brand '{brand}'. Blocked."
                    )

        # 4. Sensitive/sad news topics.
        for topic in self._SENSITIVE_TOPICS:
            if topic in hay:
                warnings.append(
                    f"Sensitive topic '{topic}' detected. "
                    "Use respectful, contextually appropriate visuals."
                )

        # 5. Alcohol.
        for term in self._ALCOHOL:
            if term in hay:
                reasons.append(f"Alcohol-related term '{term}' in narration.")
            if clip and term in hay_clip:
                reasons.append(f"Alcohol-related term '{term}' in clip description.")

        return SafetyResult(
            allowed=not reasons,
            reasons=reasons,
            warnings=warnings,
            test_data=True,
        )
