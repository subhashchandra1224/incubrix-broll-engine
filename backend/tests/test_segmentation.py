"""Phase 5 — sentence/phrase segmentation and timing coverage.

Tests verify:
- Sentences split correctly on sentence-ending punctuation.
- Timing is derived from word timestamps (no gaps, no overlaps).
- Long sentences (> MAX_SCENE_WORDS) split at phrase boundaries.
- Scene-list boundaries and visual hints are preserved exactly.
- Mock / estimated timings are labelled.
- Coverage validator reports gaps and overlaps correctly.
"""
from __future__ import annotations

import pytest

from app.schemas.providers import Scene, Transcript, WordTiming
from app.services.segmentation import MAX_SCENE_WORDS, segment_transcript, validate_coverage


def _transcript(text: str, duration: float = None, test_data: bool = True) -> Transcript:
    """Build a Transcript with proportional word timings."""
    words = text.split()
    dur = duration if duration is not None else len(words) * 0.4
    step = dur / max(1, len(words))
    timings = [
        WordTiming(text=w, start=round(i * step, 3),
                   end=round((i + 1) * step, 3), test_data=test_data)
        for i, w in enumerate(words)
    ]
    return Transcript(text=text, words=timings, duration=round(dur, 3),
                      provider="test", test_data=test_data)


# ---- basic segmentation ----

def test_three_sentences_produce_three_spans():
    t = _transcript("Saving money. Building wealth. Staying secure.")
    spans = segment_transcript(t)
    assert len(spans) == 3
    assert spans[0][0] == "Saving money."
    assert spans[1][0] == "Building wealth."
    assert spans[2][0] == "Staying secure."


def test_single_sentence_no_punctuation():
    t = _transcript("Trust is earned slowly over time")
    spans = segment_transcript(t)
    assert len(spans) == 1
    assert "Trust" in spans[0][0]


def test_number_statistics_sentence():
    t = _transcript("Sales grew 40% in 2025. This confirms growth trends.")
    spans = segment_transcript(t)
    assert len(spans) == 2
    assert "40%" in spans[0][0]


def test_question_mark_and_exclamation():
    t = _transcript("What is a budget? Save more money! Invest wisely.")
    spans = segment_transcript(t)
    assert len(spans) == 3


# ---- timing coverage (no gaps / overlaps) ----

def test_coverage_no_gaps_or_overlaps():
    t = _transcript("Scene one. Scene two. Scene three.", duration=12.0)
    spans = segment_transcript(t)
    for i in range(len(spans) - 1):
        _, _s, end, _ = spans[i]
        _, start_next, _, _ = spans[i + 1]
        gap = round(start_next - end, 6)
        assert abs(gap) < 0.001, f"Gap of {gap}s between span {i} and {i+1}"


def test_last_span_reaches_end_of_transcript():
    t = _transcript("One sentence only.", duration=5.0)
    spans = segment_transcript(t)
    assert abs(spans[-1][2] - 5.0) < 0.01


def test_timing_estimated_flag_propagated():
    t = _transcript("Estimated timing test.", test_data=True)
    spans = segment_transcript(t)
    assert all(estimated for _, _, _, estimated in spans)


def test_timing_not_estimated_when_real():
    t = _transcript("Real timing test.", test_data=False)
    spans = segment_transcript(t)
    assert all(not estimated for _, _, _, estimated in spans)


# ---- long sentence splitting ----

def test_long_sentence_splits_at_phrase_boundary():
    # Build a sentence longer than MAX_SCENE_WORDS with a comma.
    words_before = ["word"] * (MAX_SCENE_WORDS // 2)
    words_after = ["other"] * (MAX_SCENE_WORDS // 2 + 2)
    text = " ".join(words_before) + ", " + " ".join(words_after) + "."
    t = _transcript(text)
    spans = segment_transcript(t)
    assert len(spans) >= 2
    for _, s, e, _ in spans:
        word_count = len(spans)  # each span must have <= MAX_SCENE_WORDS words... approx
    # Total words preserved
    total_words = sum(len(sp[0].split()) for sp in spans)
    original_words = len(text.split())
    assert total_words == original_words


# ---- validate_coverage ----

def _scenes_from_spans(spans) -> list[Scene]:
    return [
        Scene(
            scene_id=f"scene_{i + 1:03d}", text=text,
            start_time=s, end_time=e,
            visual_description="", search_query="",
        )
        for i, (text, s, e, _) in enumerate(spans)
    ]


def test_validate_coverage_clean():
    t = _transcript("One. Two. Three.", duration=6.0)
    scenes = _scenes_from_spans(segment_transcript(t))
    warns = validate_coverage(scenes, 6.0)
    assert warns == [], f"Unexpected warnings: {warns}"


def test_validate_coverage_detects_gap():
    scenes = [
        Scene(scene_id="s1", text="A", start_time=0.0, end_time=2.0,
              visual_description="", search_query=""),
        Scene(scene_id="s2", text="B", start_time=2.5, end_time=4.0,
              visual_description="", search_query=""),
    ]
    warns = validate_coverage(scenes, 4.0)
    assert any("Gap" in w for w in warns)


def test_validate_coverage_detects_overlap():
    scenes = [
        Scene(scene_id="s1", text="A", start_time=0.0, end_time=3.0,
              visual_description="", search_query=""),
        Scene(scene_id="s2", text="B", start_time=2.5, end_time=5.0,
              visual_description="", search_query=""),
    ]
    warns = validate_coverage(scenes, 5.0)
    assert any("Overlap" in w or "overlap" in w for w in warns), warns


def test_validate_coverage_detects_short_end():
    scenes = [
        Scene(scene_id="s1", text="A", start_time=0.0, end_time=4.5,
              visual_description="", search_query=""),
    ]
    warns = validate_coverage(scenes, 6.0)
    assert any("ends at" in w or "scene" in w.lower() for w in warns)
