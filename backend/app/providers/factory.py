"""Provider selection by configuration.

Each get_*_provider() reads the matching *_PROVIDER setting (default "mock") and
returns the adapter instance. Selecting a real provider that is not wired yet
(or has no API keys) raises ProviderNotConfiguredError, so a job fails clearly
instead of silently making a paid call.

Footage is special: the footage service tries a chain (primary + fallbacks),
so it calls get_footage_provider(name) per name in the chain.

Phase 5: the "local-minilm" embeddings adapter is registered here if fastembed
is installed (import-time check). If not installed, selecting it raises
ProviderNotConfiguredError cleanly.
"""
from __future__ import annotations

from app.api.errors import ProviderNotConfiguredError
from app.config import get_settings
from app.providers.base import (
    EmbeddingsProvider,
    FootageProvider,
    SafetyProvider,
    SceneUnderstandingProvider,
    STTProvider,
    TTSProvider,
)
from app.providers.mocks import (
    MockEmbeddings,
    MockFootage,
    MockFootageEmpty,
    MockFootageFail,
    MockSafety,
    MockSceneUnderstanding,
    MockSTT,
    MockTTS,
)

_STT: dict[str, type[STTProvider]] = {"mock": MockSTT}
_TTS: dict[str, type[TTSProvider]] = {"mock": MockTTS}
_SCENE: dict[str, type[SceneUnderstandingProvider]] = {"mock": MockSceneUnderstanding}
_EMBEDDINGS: dict[str, type[EmbeddingsProvider]] = {"mock": MockEmbeddings}
_FOOTAGE: dict[str, type[FootageProvider]] = {
    "mock": MockFootage,
    "mock_fail": MockFootageFail,
    "mock_empty": MockFootageEmpty,
}
_SAFETY: dict[str, type[SafetyProvider]] = {"mock": MockSafety}

# Register local-minilm only when fastembed is installed; fail cleanly otherwise.
try:
    from app.providers.local_embeddings import LocalMiniLMEmbeddings
    _EMBEDDINGS["local-minilm"] = LocalMiniLMEmbeddings
except ImportError:
    pass


def _select(registry: dict, name: str, kind: str):
    cls = registry.get(name)
    if cls is None:
        raise ProviderNotConfiguredError(
            f"{kind} provider '{name}' is not available. "
            "Use 'mock' or configure a real provider.",
            {"provider": name, "kind": kind},
        )
    return cls()


def get_stt_provider(name: str | None = None) -> STTProvider:
    return _select(_STT, name or get_settings().stt_provider, "STT")


def get_tts_provider(name: str | None = None) -> TTSProvider:
    return _select(_TTS, name or get_settings().tts_provider, "TTS")


def get_scene_provider(name: str | None = None) -> SceneUnderstandingProvider:
    return _select(_SCENE, name or get_settings().scene_provider, "Scene")


def get_embeddings_provider(name: str | None = None) -> EmbeddingsProvider:
    return _select(_EMBEDDINGS, name or get_settings().embeddings_provider, "Embeddings")


def get_footage_provider(name: str) -> FootageProvider:
    return _select(_FOOTAGE, name, "Footage")


def get_safety_provider(name: str | None = None) -> SafetyProvider:
    return _select(_SAFETY, name or get_settings().safety_provider, "Safety")


def is_local_minilm_available() -> bool:
    """True when fastembed is installed, local-minilm is registered, AND the
    model ONNX files are already cached on disk (no network needed to run tests).

    This is the skip guard: real-embeddings tests are skipped if the model
    has not been downloaded yet, keeping the default test suite fully offline.
    """
    if "local-minilm" not in _EMBEDDINGS:
        return False
    try:
        from app.providers.local_embeddings import _is_model_cached
        return _is_model_cached()
    except Exception:
        return False
