"""Local embeddings adapter using fastembed + all-MiniLM-L6-v2.

Model: sentence-transformers/all-MiniLM-L6-v2
Backend: fastembed 0.9.1 (Apache-2.0) with ONNX Runtime — no torch required.
Licence: Apache-2.0 (commercial use permitted). See SOURCES.md.

The model (~90 MB) is downloaded once from Hugging Face to
~/.cache/fastembed on first use and cached permanently. Subsequent imports
are instant (model is already on disk).

IMPORTANT — offline guard:
If fastembed is not installed, this module still imports cleanly (returns None
from get_local_embeddings_provider). The factory registers this adapter only
when fastembed is importable. The default test suite uses mock embeddings and
runs entirely offline; real-embeddings tests are skipped when this adapter is
unavailable or the model is not cached.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from app.providers.base import EmbeddingsProvider

log = logging.getLogger(__name__)

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_VERSION = "2024-07-26"            # fastembed model snapshot date (see SOURCES.md)
ADAPTER_NAME = "local-minilm"
DIMENSION = 384

# Whether the model files already exist on disk (populated lazily).
_model_cached: Optional[bool] = None


def _is_model_cached() -> bool:
    """Check the fastembed cache directory for the model ONNX file."""
    global _model_cached
    if _model_cached is not None:
        return _model_cached
    import pathlib
    cache = pathlib.Path.home() / ".cache" / "fastembed"
    # fastembed stores models as <cache>/<safe_model_name>/.../*.onnx
    # It replaces / and - with _ in the directory name.
    safe = MODEL_NAME.replace("/", "_").replace("-", "_")
    found = list(cache.rglob("*.onnx")) if cache.exists() else []
    _model_cached = any(safe.lower() in str(f).lower() for f in found)
    return _model_cached


def reset_cache_check() -> None:
    """Force _is_model_cached() to re-check (for tests that download the model)."""
    global _model_cached
    _model_cached = None


class LocalMiniLMEmbeddings(EmbeddingsProvider):
    """sentence-transformers/all-MiniLM-L6-v2 via fastembed (ONNX, no torch).

    Licence:  Apache-2.0 — commercial use permitted.
    Provider: fastembed 0.9.1 (Apache-2.0).
    Model:    sentence-transformers/all-MiniLM-L6-v2 (Apache-2.0).
    See SOURCES.md for full details.
    """

    name = ADAPTER_NAME
    dimension = DIMENSION
    test_data = False   # real model; not test data

    def __init__(self) -> None:
        from fastembed import TextEmbedding  # noqa: F401 — imported lazily

        self._model = TextEmbedding(model_name=MODEL_NAME)
        reset_cache_check()
        log.info(
            "LocalMiniLMEmbeddings loaded: model=%s version=%s via fastembed",
            MODEL_NAME, MODEL_VERSION,
        )

    def embed(self, text: str) -> list[float]:
        # fastembed returns a generator of numpy arrays.
        result = list(self._model.embed([text or " "]))
        return result[0].tolist()


def get_local_embeddings_provider() -> Optional[LocalMiniLMEmbeddings]:
    """Return a LocalMiniLMEmbeddings if fastembed is available, else None."""
    try:
        import fastembed  # noqa: F401
        return LocalMiniLMEmbeddings()
    except ImportError:
        log.warning("fastembed not installed; local-minilm embeddings unavailable")
        return None
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not load LocalMiniLMEmbeddings: %s", exc)
        return None
