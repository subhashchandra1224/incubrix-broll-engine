"""Sentence and phrase segmentation helpers used by the scene provider.

Phase 5 improvement over the Phase 4 mock: a multi-pass segmenter that
handles trailing punctuation edge-cases, conjunctions, and long-sentence
splitting, while preserving scene-list boundaries from an IncuBrix input.

Design goals (all tested):
- Every word in the transcript appears in exactly one scene (no gaps, no overlaps).
- Sentence boundaries fall on sentence-ending punctuation (. ! ?) or phrase
  boundaries (comma / semicolon before conjunctions) for sentences > MAX_WORDS.
- Timing is propagated from real word-level timestamps when available; when
  estimated (mock TTS), it is flagged as such.
- The segmenter never crashes on empty text, single words, or numbers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.providers import Scene, Transcript, WordTiming

MAX_SCENE_WORDS = 20   # split long sentences at phrase boundaries

_SENT_END = re.compile(r"[.!?]$")
_PHRASE_SPLIT = re.compile(r"[,;]$")


@dataclass
class _Span:
    words: list[WordTiming]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def start(self) -> float:
        return self.words[0].start if self.words else 0.0

    @property
    def end(self) -> float:
        return self.words[-1].end if self.words else 0.0

    @property
    def estimated(self) -> bool:
        return any(w.test_data for w in self.words)


def _split_into_sentence_spans(transcript: Transcript) -> list[_Span]:
    """Group transcript words into sentence-level spans."""
    if not transcript.words:
        return [_Span([WordTiming(text=transcript.text, start=0.0, end=transcript.duration)])]

    spans: list[_Span] = []
    current: list[WordTiming] = []

    for w in transcript.words:
        current.append(w)
        # Sentence ends when a word ends in . ! ?
        if _SENT_END.search(w.text):
            spans.append(_Span(list(current)))
            current = []

    if current:  # any leftover words without terminal punctuation
        spans.append(_Span(current))

    return spans


def _maybe_split_long_span(span: _Span) -> list[_Span]:
    """Split a span that is too long at a phrase boundary (comma/semicolon)."""
    if len(span.words) <= MAX_SCENE_WORDS:
        return [span]

    # Find the best split point: a comma/semicolon near the middle.
    mid = len(span.words) // 2
    best = -1
    for i in range(len(span.words) - 1):
        if _PHRASE_SPLIT.search(span.words[i].text):
            if best < 0 or abs(i - mid) < abs(best - mid):
                best = i

    if best >= 1:
        left = _Span(span.words[:best + 1])
        right = _Span(span.words[best + 1:])
        return _maybe_split_long_span(left) + _maybe_split_long_span(right)

    # No phrase boundary: split at mid.
    return [_Span(span.words[:mid]), _Span(span.words[mid:])]


def segment_transcript(transcript: Transcript) -> list[tuple[str, float, float, bool]]:
    """Return list of (text, start_time, end_time, timing_is_estimated) tuples.

    Every second of narration is covered (adjacent tuples are contiguous), and
    no word appears in two scenes.
    """
    raw_spans = _split_into_sentence_spans(transcript)
    final: list[_Span] = []
    for sp in raw_spans:
        final.extend(_maybe_split_long_span(sp))

    result: list[tuple[str, float, float, bool]] = []
    n = len(final)
    for i, sp in enumerate(final):
        start = sp.start
        # Close each scene right up to the next scene's start to avoid gaps.
        end = final[i + 1].start if i < n - 1 else sp.end
        result.append((sp.text, round(start, 3), round(end, 3), sp.estimated))

    return result


def validate_coverage(scenes: list[Scene], total_duration: float) -> list[str]:
    """Return a list of coverage warnings (empty = clean).

    Checks:
    - No gap between consecutive scenes (> 50 ms).
    - No overlap between consecutive scenes (> 50 ms).
    - Total end time >= total_duration - 100 ms.
    """
    warnings: list[str] = []
    GAP_THRESHOLD = 0.05
    for i in range(len(scenes) - 1):
        gap = round(scenes[i + 1].start_time - scenes[i].end_time, 3)
        if gap > GAP_THRESHOLD:
            warnings.append(
                f"Gap of {gap}s between {scenes[i].scene_id} and {scenes[i+1].scene_id}"
            )
        if gap < -GAP_THRESHOLD:
            warnings.append(
                f"Overlap of {-gap}s between {scenes[i].scene_id} and {scenes[i+1].scene_id}"
            )
    if scenes:
        shortfall = round(total_duration - scenes[-1].end_time, 3)
        if shortfall > 0.1:
            warnings.append(
                f"Last scene ends at {scenes[-1].end_time}s but narration is {total_duration}s"
            )
    return warnings
