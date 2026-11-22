"""Provider selection by configuration (Integration Standard #6 + swappable providers)."""
from __future__ import annotations

import pytest

from app.api.errors import ProviderNotConfiguredError
from app.config import get_settings
from app.providers import factory
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


def test_default_providers_are_mock():
    assert isinstance(factory.get_stt_provider(), MockSTT)
    assert isinstance(factory.get_tts_provider(), MockTTS)
    assert isinstance(factory.get_scene_provider(), MockSceneUnderstanding)
    assert isinstance(factory.get_embeddings_provider(), MockEmbeddings)
    assert isinstance(factory.get_safety_provider(), MockSafety)


def test_footage_provider_variants():
    assert isinstance(factory.get_footage_provider("mock"), MockFootage)
    assert isinstance(factory.get_footage_provider("mock_fail"), MockFootageFail)
    assert isinstance(factory.get_footage_provider("mock_empty"), MockFootageEmpty)


def test_unknown_provider_raises_not_configured():
    with pytest.raises(ProviderNotConfiguredError):
        factory.get_stt_provider("openai")
    with pytest.raises(ProviderNotConfiguredError):
        factory.get_footage_provider("pexels")
    # error code is UPPER_SNAKE
    with pytest.raises(ProviderNotConfiguredError) as ei:
        factory.get_tts_provider("elevenlabs")
    assert ei.value.code == "PROVIDER_NOT_CONFIGURED"


def test_footage_provider_chain_default():
    assert get_settings().footage_provider_chain == ["mock"]


def test_footage_provider_chain_with_fallbacks(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "footage_provider", "mock_fail")
    monkeypatch.setattr(s, "footage_fallback_providers", "mock,mock_empty")
    assert s.footage_provider_chain == ["mock_fail", "mock", "mock_empty"]


def test_footage_provider_chain_dedups(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "footage_provider", "mock")
    monkeypatch.setattr(s, "footage_fallback_providers", "mock,mock_fail")
    assert s.footage_provider_chain == ["mock", "mock_fail"]
