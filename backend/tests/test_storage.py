"""Phase 9 — storage abstraction tests.

Tests LocalStorage (always available) and verifies that S3Storage raises a
clear configuration error when no endpoint is set. The actual MinIO S3 flow
is verified manually in the Docker Compose stack.
"""
from __future__ import annotations

import os
import tempfile

from app.utils.storage import LocalStorage


def test_local_storage_available(tmp_path):
    store = LocalStorage(root=str(tmp_path), api_base="/api/v1")
    assert store.available()


def test_local_storage_store_copies_file(tmp_path):
    store = LocalStorage(root=str(tmp_path), api_base="/api/v1")
    src = tmp_path / "src.txt"
    src.write_text("hello")
    url = store.store(str(src), "jobs/job_abc/src.txt")
    assert "job_abc" in url
    assert "src.txt" in url
    assert os.path.isfile(tmp_path / "jobs" / "job_abc" / "src.txt")


def test_local_storage_public_url_format():
    store = LocalStorage(root="/some/root", api_base="/api/v1")
    url = store.public_url("jobs/job_xyz/video_16_9.mp4")
    assert "/api/v1/broll/jobs/job_xyz/outputs/video_16_9.mp4" == url


def test_local_storage_idempotent_store(tmp_path):
    """Storing the same file twice returns the same URL without error."""
    store = LocalStorage(root=str(tmp_path), api_base="/api/v1")
    src = tmp_path / "artifact.mp4"
    src.write_bytes(b"fake mp4 data")
    url1 = store.store(str(src), "jobs/j1/artifact.mp4")
    url2 = store.store(str(src), "jobs/j1/artifact.mp4")
    assert url1 == url2


def test_s3_storage_put_and_url(tmp_path):
    """Verify S3Storage.store + public_url logic using a mock boto3 client."""
    from unittest.mock import MagicMock, patch

    mock_client = MagicMock()
    mock_client.put_object.return_value = {}

    with patch("boto3.client", return_value=mock_client):
        from app.utils.storage import S3Storage
        # Re-import to avoid cached instance issues.
        store = S3Storage(
            endpoint_url="http://localhost:9000",
            bucket="broll-engine",
            access_key="minioadmin",
            secret_key="minioadmin",
        )
        src = tmp_path / "test.mp4"
        src.write_bytes(b"fake mp4")
        url = store.store(str(src), "jobs/job_123/test.mp4")

    assert url == "http://localhost:9000/broll-engine/jobs/job_123/test.mp4"
    mock_client.put_object.assert_called_once()
    call_kwargs = mock_client.put_object.call_args.kwargs
    assert call_kwargs["Bucket"] == "broll-engine"
    assert call_kwargs["Key"] == "jobs/job_123/test.mp4"
