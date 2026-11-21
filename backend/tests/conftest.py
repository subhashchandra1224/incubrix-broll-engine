"""Pytest configuration shared by all tests.

Forces a clean, safe test environment BEFORE the app is imported:
- all providers are set to "mock" (no API keys, no paid calls)
- any credentials in the shell are blanked
- the SQLite DB and the storage dir live in a temp folder (never in the repo)

This guarantees the default suite runs with zero external services and never
accidentally spends money.
"""
from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile

# Make `app` importable when tests run from backend/ (pytest.ini also sets
# pythonpath=., but this is explicit safety).
HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.dirname(HERE)
sys.path.insert(0, BACKEND)

# ---- Force a clean test environment BEFORE importing the app ----
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("LOG_JSON", "false")
# All providers mock -> no API keys needed, no paid calls.
for _prov in (
    "STT_PROVIDER", "TTS_PROVIDER", "EMBEDDINGS_PROVIDER",
    "SCENE_PROVIDER", "FOOTAGE_PROVIDER", "SAFETY_PROVIDER",
):
    os.environ[_prov] = "mock"
# Blank out any credentials that might be set in the shell.
for _cred in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "PEXELS_API_KEY", "PIXABAY_API_KEY"):
    os.environ[_cred] = ""

# Put the SQLite DB and the storage dir in a temp folder so tests never write
# into the repository.
_TMP = tempfile.mkdtemp(prefix="broll_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TMP, 'test_broll.db')}"
os.environ["STORAGE_LOCAL_ROOT"] = _TMP
atexit.register(shutil.rmtree, _TMP, ignore_errors=True)

# Drop cached settings so the env above takes effect, then import the app.
from app.config import reset_settings  # noqa: E402

reset_settings()

from app.main import app  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    """A TestClient that runs the app lifespan (creates DB + storage dir).

    raise_server_exceptions=False so that an unhandled server error is returned
    as a 500 response (using our standard error envelope) instead of being
    re-raised in the test. Other tests still fail loudly because they assert
    specific status codes and bodies, so a masked 500 would surface as a clear
    assertion mismatch rather than silently passing.
    """
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
