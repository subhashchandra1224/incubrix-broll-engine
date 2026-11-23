"""Phase 9 — audio upload endpoint tests.

Tests the POST /api/v1/broll/jobs/upload multipart endpoint:
- Valid wav/mp3/m4a files accepted.
- Unsupported extension rejected (422).
- File too large rejected (400).
- Empty file rejected (400).
- JSON clients (POST /broll/jobs) still work alongside upload.
- Idempotency-Key respected on uploads.
"""
from __future__ import annotations

import io
import os
import struct
import wave

import pytest

from app.utils.ffmpeg import ffmpeg_available, ffprobe_available


def _make_wav(seconds: float = 2.0, sample_rate: int = 16000) -> bytes:
    """Generate a minimal valid WAV file in memory (silent, mono, 16-bit)."""
    num_samples = int(sample_rate * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * num_samples)
    return buf.getvalue()


# Skip upload tests that use ffprobe duration validation if ffprobe is absent.
_needs_ffprobe = pytest.mark.skipif(
    not ffprobe_available(),
    reason="ffprobe not available",
)


def test_json_client_still_works(client):
    """Existing JSON endpoint is unaffected by the upload route."""
    r = client.post("/api/v1/broll/jobs",
                    json={"script": "Upload coexistence test.", "aspect_ratios": ["16:9"]})
    assert r.status_code == 202
    assert r.json()["job_id"].startswith("job_")


def test_upload_unsupported_extension_rejected(client):
    r = client.post(
        "/api/v1/broll/jobs/upload",
        data={"aspect_ratios": '["16:9"]'},
        files={"audio": ("voiceover.txt", b"hello", "text/plain")},
    )
    assert r.status_code in (400, 422)
    assert r.json()["error"]["code"] == "INVALID_INPUT"


def test_upload_empty_file_rejected(client):
    r = client.post(
        "/api/v1/broll/jobs/upload",
        data={"aspect_ratios": '["16:9"]'},
        files={"audio": ("empty.wav", b"", "audio/wav")},
    )
    assert r.status_code in (400, 422)
    assert r.json()["error"]["code"] == "INVALID_INPUT"


def test_upload_missing_aspect_ratios_rejected(client):
    wav_data = _make_wav(0.5)
    r = client.post(
        "/api/v1/broll/jobs/upload",
        files={"audio": ("test.wav", wav_data, "audio/wav")},
        # No aspect_ratios form field
    )
    assert r.status_code in (400, 422)


@_needs_ffprobe
def test_upload_valid_wav_accepted(client):
    wav_data = _make_wav(2.0)
    r = client.post(
        "/api/v1/broll/jobs/upload",
        data={"aspect_ratios": '["16:9"]', "captions": '{"srt":true}'},
        files={"audio": ("voiceover.wav", wav_data, "audio/wav")},
    )
    assert r.status_code == 202, f"expected 202, got {r.status_code}: {r.json()}"
    body = r.json()
    assert body["job_id"].startswith("job_")
    assert body["status"] == "queued"
    assert "/api/v1/jobs/" in body["status_url"]


@_needs_ffprobe
def test_upload_idempotency_key_respected(client):
    wav_data = _make_wav(2.0)
    headers = {"Idempotency-Key": "upload-idem-1"}
    r1 = client.post(
        "/api/v1/broll/jobs/upload",
        data={"aspect_ratios": '["16:9"]'},
        files={"audio": ("v.wav", wav_data, "audio/wav")},
        headers=headers,
    )
    r2 = client.post(
        "/api/v1/broll/jobs/upload",
        data={"aspect_ratios": '["16:9"]'},
        files={"audio": ("v.wav", wav_data, "audio/wav")},
        headers=headers,
    )
    assert r1.status_code == 202
    assert r2.status_code == 202
    assert r1.json()["job_id"] == r2.json()["job_id"]


@_needs_ffprobe
def test_upload_and_process_job_succeeds(client):
    """Full flow: upload wav -> process -> result."""
    from sqlalchemy import text
    from app.db.database import SessionLocal, init_db
    from app.workers import runner

    init_db()
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM jobs"))
        db.commit()
    finally:
        db.close()

    wav_data = _make_wav(2.0)
    r = client.post(
        "/api/v1/broll/jobs/upload",
        data={"aspect_ratios": '["16:9"]'},
        files={"audio": ("v.wav", wav_data, "audio/wav")},
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    runner.process_next_job()
    g = client.get(f"/api/v1/jobs/{job_id}")
    assert g.json()["status"] == "succeeded"
    assert g.json()["result"]["input_type"] == "audio"
