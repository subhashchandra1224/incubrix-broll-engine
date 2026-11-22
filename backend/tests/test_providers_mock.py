"""Determinism and test-data labelling for the mock providers.

The mocks must be reproducible (same input -> same output) using stable hashes,
and every output must carry test_data=True.
"""
from __future__ import annotations

from app.providers.factory import (
    get_embeddings_provider,
    get_footage_provider,
    get_scene_provider,
    get_safety_provider,
    get_stt_provider,
    get_tts_provider,
)


def test_mock_stt_is_deterministic_and_labelled():
    stt = get_stt_provider()
    a = stt.transcribe("https://e/a.mp3")
    b = stt.transcribe("https://e/a.mp3")
    assert a.text == b.text and a.duration == b.duration
    assert [w.model_dump() for w in a.words] == [w.model_dump() for w in b.words]
    assert a.test_data is True


def test_mock_tts_is_deterministic_and_labelled():
    tts = get_tts_provider()
    a = tts.synthesize("hello world", "v")
    b = tts.synthesize("hello world", "v")
    assert a.duration == b.duration
    assert [w.model_dump() for w in a.words] == [w.model_dump() for w in b.words]
    assert a.test_data is True


def test_mock_scene_is_deterministic_and_segments():
    from app.schemas.providers import Transcript
    scene = get_scene_provider()
    tts = get_tts_provider()
    text = "Saving money. Building wealth. Staying secure."
    synth = tts.synthesize(text, None)
    t = Transcript(text=text, words=synth.words, duration=synth.duration,
                   provider=tts.name, test_data=True)
    scs = scene.segment(t)
    assert len(scs) == 3
    assert scs[0].text == "Saving money."
    assert scs[0].start_time == 0.0
    assert scs[-1].end_time <= t.duration + 0.01
    # repeatable
    assert [s.model_dump() for s in scs] == [s.model_dump() for s in scene.segment(t)]


def test_mock_embeddings_deterministic_and_similarity():
    emb = get_embeddings_provider()
    v1 = emb.embed("saving money budget")
    assert v1 == emb.embed("saving money budget")  # deterministic
    assert 0.0 <= emb.cosine(v1, v1) <= 1.0
    assert abs(emb.cosine(v1, v1) - 1.0) < 1e-9      # identical -> 1.0
    v3 = emb.embed("zzzqqqxxx")
    assert emb.cosine(v1, v3) < 1.0                   # different -> not identical


def test_mock_footage_deterministic_and_licenced_test_data():
    fp = get_footage_provider("mock")
    a = fp.search("household budget")
    assert a == fp.search("household budget")  # repeatable objects
    assert len(a) >= 1
    clip = a[0]
    assert clip.test_data is True
    assert clip.licence.commercial_use is True
    assert "test-data" in clip.licence.source_url
    assert "not a real licence" in clip.licence.license_name


def test_mock_safety_applies_avoid_terms():
    sp = get_safety_provider()
    assert sp.check("a calm scene", None, ["alcohol"]).allowed is True
    blocked = sp.check("pour a glass of wine", None, ["wine"])
    assert blocked.allowed is False
    assert any("wine" in r for r in blocked.reasons)
    assert blocked.test_data is True
