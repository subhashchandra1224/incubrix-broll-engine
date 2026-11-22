"""Phase 5 — improved safety: named people, brands, sensitive topics, alcohol,
and avoid terms. All tests use mock safety (no paid APIs).

Documents what the mock safety CAN and CANNOT detect (honest limits):
- CAN: keyword matching on hardcoded lists + user avoid terms.
- CANNOT: real face detection in video frames, NER on arbitrary text,
  brand logo detection in footage (needs vision model, Phase later).
"""
from __future__ import annotations

import pytest

from app.providers.mocks import MockSafety
from app.schemas.providers import FootageClip, LicenceInfo


def _clip(desc: str) -> FootageClip:
    return FootageClip(
        provider="mock", asset_id="t0", description=desc,
        licence=LicenceInfo(
            provider="mock", asset_id="t0",
            source_url="test-data://mock/t0",
            license_name="mock", license_url="test-data://",
            attribution="", commercial_use=True, ai_generated=False,
        ),
        test_data=True,
    )


safety = MockSafety()


# ---- avoid terms ----

def test_avoid_term_in_narration_blocks():
    r = safety.check("she drinks alcohol every evening", None, ["alcohol"])
    assert r.allowed is False
    assert any("alcohol" in reason for reason in r.reasons)


def test_avoid_term_in_clip_desc_blocks():
    r = safety.check("a celebration scene", _clip("beer and alcohol toast"), ["alcohol"])
    assert r.allowed is False


def test_avoid_terms_case_insensitive():
    r = safety.check("She enjoys Wine with dinner", None, ["wine"])
    assert r.allowed is False


def test_multiple_avoid_terms_all_checked():
    r = safety.check("alcohol and faces of people", None, ["alcohol", "faces"])
    assert r.allowed is False


def test_no_avoid_terms_allowed():
    r = safety.check("saving money", None, [])
    assert r.allowed is True


# ---- named real people (keyword, text-only) ----

def test_named_person_in_narration_produces_warning_not_block():
    # Named person in narration: warn but don't block (rule: allow if clip doesn't mention them)
    r = safety.check("according to elon musk, EVs are the future", None, [])
    assert r.allowed is True           # narration mention: warn not block
    assert any("musk" in w.lower() or "elon musk" in w.lower() for w in r.warnings)


def test_named_person_in_clip_desc_blocks():
    r = safety.check("according to elon musk, EVs are the future",
                     _clip("elon musk speaking at conference"), [])
    assert r.allowed is False
    assert any("musk" in reason.lower() for reason in r.reasons)


def test_named_person_produces_warning_in_result():
    r = safety.check("biden announced new policies", None, [])
    assert r.allowed is True
    assert any("Biden" in w or "biden" in w for w in r.warnings)


# ---- brand names ----

def test_brand_in_narration_warns_not_blocks():
    r = safety.check("apple announced a new product today", None, [])
    assert r.allowed is True
    assert any("apple" in w.lower() for w in r.warnings)


def test_brand_in_clip_desc_blocks():
    r = safety.check("apple announced a product",
                     _clip("apple logo and store front"), [])
    assert r.allowed is False


# ---- sensitive/sad news ----

def test_sensitive_topic_warns_not_blocks():
    r = safety.check("the terrorist attack caused many deaths", None, [])
    assert r.allowed is True
    assert len(r.warnings) >= 1
    # Both 'terrorist' and 'death' may trigger warnings
    assert any("terrorist" in w.lower() or "death" in w.lower() or "sensitive" in w.lower()
               for w in r.warnings)


def test_sad_news_warns_respects_visuals():
    r = safety.check("many people died in the flood disaster", None, [])
    assert r.allowed is True
    assert len(r.warnings) >= 1


# ---- alcohol (hard block even without user avoid) ----

def test_alcohol_in_narration_blocked_by_default():
    r = safety.check("they enjoyed beer and whiskey all evening", None, [])
    assert r.allowed is False


def test_alcohol_in_clip_blocked():
    r = safety.check("a party scene", _clip("cocktails and vodka on the table"), [])
    assert r.allowed is False


# ---- clean scenes pass ----

def test_clean_financial_scene_passes():
    r = safety.check("saving money requires careful budgeting", None, [])
    assert r.allowed is True
    assert r.reasons == []


def test_test_data_flag_set():
    r = safety.check("any text", None, [])
    assert r.test_data is True


# ---- documented limits ----

def test_cannot_detect_unnamed_real_person():
    """The mock safety cannot detect a real person not on the hardcoded list.
    This test DOCUMENTS the limitation, not a passing feature."""
    r = safety.check("a photo of an unnamed politician", None, [])
    # No warning because 'politician' is not on the person list.
    assert r.allowed is True
    # Document: keyword-only, not NER.


def test_cannot_detect_novel_brand():
    """The mock safety cannot detect a brand not on the hardcoded list."""
    r = safety.check("the company QuantumWidgets dominates the market", None, [])
    assert r.allowed is True  # 'quantumwidgets' not in hardcoded brand list


def test_cannot_detect_faces_in_footage():
    """The mock cannot detect actual faces in video frames — documented limitation."""
    # A clip described as 'generic scene' with no mention of faces passes,
    # even if real footage contained faces. Vision model needed for real detection.
    r = safety.check("interview with a subject", _clip("generic office scene"), [])
    assert r.allowed is True  # text-only: no face detection capability
