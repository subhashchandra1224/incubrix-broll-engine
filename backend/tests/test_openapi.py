"""Tests for the OpenAPI contract (Integration Standard point 2).

The committed openapi.yaml must match the running service exactly.
"""
from __future__ import annotations

import os

import yaml

from app.main import app


def _project_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))  # backend/tests
    backend = os.path.dirname(here)                     # backend
    return os.path.dirname(backend)                     # project root


def test_openapi_version_is_3_1():
    assert app.openapi()["openapi"].startswith("3.1"), "expected OpenAPI 3.1"


def test_openapi_has_health_and_ready():
    paths = app.openapi()["paths"]
    assert "/health" in paths
    assert "/ready" in paths


def test_openapi_yaml_matches_live():
    path = os.path.join(_project_root(), "openapi.yaml")
    assert os.path.exists(path), "openapi.yaml missing; run: python scripts/export_openapi.py"
    with open(path, encoding="utf-8") as fh:
        committed = yaml.safe_load(fh)
    live = app.openapi()
    assert committed == live, "openapi.yaml is stale; run: python scripts/export_openapi.py"
