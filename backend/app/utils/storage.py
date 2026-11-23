"""Storage backend abstraction — Integration Standard #7.

Two implementations:
  LocalStorage   — development / local testing; no deps beyond stdlib.
  S3Storage      — MinIO-compatible S3 storage; requires boto3.

Selected by STORAGE_BACKEND env var ("local" | "s3").

Output files are stored and their public (or presigned) download URLs are
returned so that job status responses can include clickable links. All
artifact paths recorded in the job result are these download URLs.
"""
from __future__ import annotations

import logging
import mimetypes
import os
from abc import ABC, abstractmethod
from pathlib import Path

log = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Interface for storing and retrieving job artifacts."""

    @abstractmethod
    def store(self, local_path: str, key: str) -> str:
        """Upload/copy local_path to key; return a public download URL."""

    @abstractmethod
    def public_url(self, key: str) -> str:
        """Return the URL for an already-stored key."""

    @abstractmethod
    def available(self) -> bool:
        """Return True if the storage is reachable."""


class LocalStorage(StorageBackend):
    """Serves files from a local directory at the /api/v1/.../outputs/... path.

    For the Docker Compose stack this directory is a named volume shared by the
    api and worker containers; the api serves it via the FileResponse endpoints.
    """

    def __init__(self, root: str, api_base: str = "/api/v1"):
        self.root = os.path.abspath(root)
        self.api_base = api_base.rstrip("/")

    def _full(self, key: str) -> str:
        return os.path.join(self.root, key)

    def store(self, local_path: str, key: str) -> str:
        dst = self._full(key)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        # If source and destination resolve to the same path, no copy needed.
        if os.path.abspath(local_path) != os.path.abspath(dst):
            import shutil
            shutil.copy2(local_path, dst)
        return self.public_url(key)

    def public_url(self, key: str) -> str:
        # key is e.g. "jobs/job_abc123/video_16_9.mp4"
        # derive the job_id and filename from the key.
        parts = key.replace("\\", "/").split("/")
        if len(parts) >= 3 and parts[0] == "jobs":
            job_id = parts[1]
            fname = "/".join(parts[2:])
            return f"{self.api_base}/broll/jobs/{job_id}/outputs/{fname}"
        return f"{self.api_base}/storage/{key}"

    def available(self) -> bool:
        try:
            os.makedirs(self.root, exist_ok=True)
            probe = os.path.join(self.root, ".probe")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            return True
        except Exception:
            return False


class S3Storage(StorageBackend):
    """MinIO-compatible S3 storage.

    Uses boto3 (included in requirements). The bucket is set to allow
    anonymous downloads (mc anonymous set download ...) from the MinIO console
    or from mc in the compose stack, so direct URLs are accessible from the
    browser without additional auth.
    """

    def __init__(self, endpoint_url: str, bucket: str, access_key: str,
                 secret_key: str, region: str = "us-east-1"):
        import boto3
        from botocore.config import Config
        self.bucket = bucket
        self.endpoint_url = endpoint_url.rstrip("/")
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )

    def store(self, local_path: str, key: str) -> str:
        mime, _ = mimetypes.guess_type(local_path)
        extra = {"ContentType": mime or "application/octet-stream"}
        with open(local_path, "rb") as fh:
            self._s3.put_object(
                Bucket=self.bucket, Key=key, Body=fh,
                **extra,
            )
        url = self.public_url(key)
        log.info("Stored %s → %s", local_path, url)
        return url

    def public_url(self, key: str) -> str:
        # Direct public URL works because the bucket allows anonymous downloads.
        return f"{self.endpoint_url}/{self.bucket}/{key}"

    def available(self) -> bool:
        try:
            self._s3.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            return False


def get_storage() -> StorageBackend:
    """Return the configured StorageBackend singleton."""
    from app.config import get_settings
    s = get_settings()
    if s.storage_backend == "s3":
        if not s.s3_endpoint_url:
            raise RuntimeError("S3_ENDPOINT_URL must be set when STORAGE_BACKEND=s3")
        return S3Storage(
            endpoint_url=s.s3_endpoint_url,
            bucket=s.s3_bucket,
            access_key=s.s3_access_key or "",
            secret_key=s.s3_secret_key or "",
            region=s.s3_region or "us-east-1",
        )
    return LocalStorage(
        root=s.storage_local_root,
        api_base=s.api_v1_prefix,
    )
