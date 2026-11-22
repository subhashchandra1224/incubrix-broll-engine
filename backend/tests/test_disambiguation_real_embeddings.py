"""Phase 5 — context disambiguation with real local embeddings (local-minilm).

These tests use sentence-transformers/all-MiniLM-L6-v2 via fastembed (ONNX,
Apache-2.0). They are SKIPPED automatically when fastembed is not installed or
the model has not been downloaded, so the default offline test suite still passes.

When the model IS available, these tests:
1. Run the same paired examples as test_disambiguation_mock.py.
2. Assert that the semantically correct clip ranks higher (real semantic test).
3. Record the actual cosine scores so the results can be reported honestly.

Comparison with mock results documents the improvement from real embeddings.
"""
from __future__ import annotations

import pytest

# Skip the entire module if local-minilm is not available.
try:
    from app.providers.factory import is_local_minilm_available
    _available = is_local_minilm_available()
except Exception:
    _available = False

pytestmark = pytest.mark.skipif(
    not _available,
    reason="local-minilm not available (fastembed not installed or model not downloaded)",
)


def _get_emb():
    from app.providers.local_embeddings import LocalMiniLMEmbeddings
    return LocalMiniLMEmbeddings()


def _rank(emb, query: str, descs: list[str]) -> list[tuple[float, str]]:
    qv = emb.embed(query)
    scored = [(emb.cosine(qv, emb.embed(d)), d) for d in descs]
    scored.sort(reverse=True)
    return scored


# ---------- Financial bank vs river bank ----------

def test_real_emb_financial_bank_ranks_higher():
    emb = _get_emb()
    financial = "bank account savings deposit money finance"
    riverbank = "river bank flowing water nature landscape"
    query = "depositing money at the bank for savings"
    ranked = _rank(emb, query, [financial, riverbank])
    top, score = ranked[0][1], ranked[0][0]
    # Record result honestly
    print(f"\nFinancial bank query: top='{top[:40]}' score={score:.4f}")
    print(f"  financial score: {_rank(emb, query, [financial, riverbank])[-1][0]:.4f} -> river")
    assert top == financial, (
        f"Expected financial clip to rank first. Scores: {[(round(s,4),d[:30]) for s,d in ranked]}"
    )


def test_real_emb_riverbank_ranks_higher():
    emb = _get_emb()
    financial = "bank account savings deposit money finance"
    riverbank = "river bank flowing water nature landscape"
    query = "walking along the peaceful river bank at sunset"
    ranked = _rank(emb, query, [financial, riverbank])
    print(f"\nRiverbank query: top='{ranked[0][1][:40]}' score={ranked[0][0]:.4f}")
    assert ranked[0][1] == riverbank, (
        f"Expected riverbank clip to rank first. Scores: {[(round(s,4),d[:30]) for s,d in ranked]}"
    )


# ---------- Cloud computing vs weather cloud ----------

def test_real_emb_cloud_computing_ranks_higher():
    emb = _get_emb()
    computing = "cloud computing infrastructure server AWS deployment"
    weather = "cloudy sky weather forecast atmosphere storm rain"
    query = "deploying applications to cloud computing infrastructure"
    ranked = _rank(emb, query, [computing, weather])
    print(f"\nCloud computing query: top='{ranked[0][1][:40]}' score={ranked[0][0]:.4f}")
    assert ranked[0][1] == computing


def test_real_emb_weather_cloud_ranks_higher():
    emb = _get_emb()
    computing = "cloud computing infrastructure server AWS deployment"
    weather = "cloudy sky weather forecast atmosphere storm rain"
    query = "dark storm clouds gathering in the sky"
    ranked = _rank(emb, query, [computing, weather])
    print(f"\nWeather cloud query: top='{ranked[0][1][:40]}' score={ranked[0][0]:.4f}")
    assert ranked[0][1] == weather


# ---------- Python programming vs snake ----------

def test_real_emb_python_programming_ranks_higher():
    emb = _get_emb()
    code = "python programming language software developer code"
    snake = "python snake reptile wildlife tropical jungle"
    query = "writing python code for a web application"
    ranked = _rank(emb, query, [code, snake])
    print(f"\nPython code query: top='{ranked[0][1][:40]}' score={ranked[0][0]:.4f}")
    assert ranked[0][1] == code


def test_real_emb_python_snake_ranks_higher():
    emb = _get_emb()
    code = "python programming language software developer code"
    snake = "python snake reptile wildlife tropical jungle"
    query = "a large python snake hunting in the jungle"
    ranked = _rank(emb, query, [code, snake])
    print(f"\nPython snake query: top='{ranked[0][1][:40]}' score={ranked[0][0]:.4f}")
    assert ranked[0][1] == snake


# ---------- Abstract line ----------

def test_real_emb_abstract_trust_gives_meaningful_relevance():
    emb = _get_emb()
    trust = "handshake business agreement trust credibility"
    unrelated = "fish swimming in the ocean deep sea"
    query = "trust is earned slowly over many years"
    ranked = _rank(emb, query, [trust, unrelated])
    print(f"\nAbstract trust: top='{ranked[0][1][:40]}' score={ranked[0][0]:.4f}")
    assert ranked[0][1] == trust, (
        f"Expected trust/credibility clip to rank first. "
        f"Scores: {[(round(s,4),d[:30]) for s,d in ranked]}"
    )


# ---------- Statistics ----------

def test_real_emb_statistics_ranks_analytics_higher():
    emb = _get_emb()
    analytics = "bar chart sales growth business analytics performance"
    flowers = "flowers blooming spring garden nature beauty"
    query = "sales grew 40 percent in 2025 hitting record numbers"
    ranked = _rank(emb, query, [analytics, flowers])
    print(f"\nStatistics: top='{ranked[0][1][:40]}' score={ranked[0][0]:.4f}")
    assert ranked[0][1] == analytics
