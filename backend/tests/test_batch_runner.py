"""Phase 9 — batch runner tests.

Tests the batch runner's submit + poll + download cycle using the test
API (via TestClient) and actual worker processing.

These tests verify the batch_runner.py logic against the live test server.
They do not require the Docker Compose stack to be running.
"""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import patch

import pytest

from app.utils.ffmpeg import ffmpeg_available, ffprobe_available

pytestmark = pytest.mark.skipif(
    not ffmpeg_available() or not ffprobe_available(),
    reason="ffmpeg/ffprobe not available",
)


def _make_input(out_dir: str, name: str, body: dict) -> str:
    p = os.path.join(out_dir, f"{name}.json")
    with open(p, "w") as fh:
        json.dump(body, fh)
    return p


def test_batch_runner_single_input(tmp_path):
    """Submits one input, processes it, and checks summary.json."""
    from sqlalchemy import text
    from app.db.database import SessionLocal, init_db
    from app.workers import runner as runner_mod

    # Seed the DB clean.
    init_db()
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM jobs"))
        db.commit()
    finally:
        db.close()

    input_dir = tmp_path / "inputs"
    out_dir = tmp_path / "out"
    input_dir.mkdir()

    _make_input(str(input_dir), "job1", {
        "script": "A batch test scene.", "aspect_ratios": ["16:9"],
    })

    # We patch batch_runner._post / _get to use the test client.
    from starlette.testclient import TestClient
    from app.main import app

    test_client = TestClient(app, raise_server_exceptions=False)

    def fake_post(url, body, idem_key):
        path = url.split("http://localhost:8000", 1)[-1] if "http://localhost:8000" in url else url
        resp = test_client.post(path, json=body, headers={"Idempotency-Key": idem_key})
        return resp.json()

    def fake_get(url):
        path = url.split("http://localhost:8000", 1)[-1] if "http://localhost:8000" in url else url
        return test_client.get(path).json()

    def fake_download(url, dest):
        path = url.split("http://localhost:8000", 1)[-1] if "http://localhost:8000" in url else url
        resp = test_client.get(path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(resp.content)

    import scripts.batch_runner as br

    with patch.object(br, "_post", fake_post), \
         patch.object(br, "_get", fake_get), \
         patch.object(br, "_download", fake_download):
        # We need to process the job in the middle of polling.
        original_get = fake_get

        poll_count = [0]
        def patched_get(url):
            result = original_get(url)
            # On first poll, trigger the worker to process the job.
            if poll_count[0] == 0 and "/api/v1/jobs/" in url:
                poll_count[0] += 1
                runner_mod.process_next_job()
                return original_get(url)
            poll_count[0] += 1
            return result

        with patch.object(br, "_get", patched_get):
            br.run(str(input_dir), str(out_dir))

    summary_path = str(out_dir / "summary.json")
    assert os.path.isfile(summary_path)
    with open(summary_path) as fh:
        summary = json.load(fh)
    assert summary["total"] == 1
    assert summary["succeeded"] == 1, f"Expected success, got: {summary}"


def test_batch_runner_loads_multiple_inputs(tmp_path):
    """Verifies that a folder of JSON files is loaded correctly."""
    input_dir = tmp_path / "inputs"
    input_dir.mkdir()
    for i in range(3):
        _make_input(str(input_dir), f"job{i}", {
            "script": f"Scene {i}.", "aspect_ratios": ["16:9"],
        })
    import scripts.batch_runner as br
    inputs = br.load_inputs(str(input_dir))
    assert len(inputs) == 3


def test_batch_runner_stable_idempotency_keys(tmp_path):
    """Same file + same body => same key every run (deterministic)."""
    import scripts.batch_runner as br
    body = {"script": "stable key test", "aspect_ratios": ["16:9"]}
    k1 = br._stable_key("/path/to/input.json", body)
    k2 = br._stable_key("/path/to/input.json", body)
    assert k1 == k2
    k3 = br._stable_key("/path/to/other.json", body)
    assert k1 != k3
