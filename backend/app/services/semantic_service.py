"""Relevance scoring via the configured EmbeddingsProvider.

Cosine similarity between the scene search query and the clip description,
clamped to [0, 1]. With the mock bag-of-words embeddings this is deterministic;
real embeddings arrive later behind the same interface.
"""
from __future__ import annotations

from app.providers.factory import get_embeddings_provider
from app.schemas.providers import FootageClip


def relevance(query: str, clip: FootageClip) -> float:
    emb = get_embeddings_provider()
    qv = emb.embed(query)
    cv = emb.embed(clip.description)
    return max(0.0, min(1.0, emb.cosine(qv, cv)))
