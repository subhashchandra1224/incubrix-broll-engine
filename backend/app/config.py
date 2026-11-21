"""Application configuration.

Every setting comes from an environment variable (or a .env file). Nothing is
hard-coded. Secrets are optional and default to None, so the app runs with no
API keys. The full list is mirrored in .env.example.

Why this module exists: Integration Standard point 6 requires all settings,
paths, model names and limits to come from configuration - never baked into
code. pydantic-settings reads env vars, validates types, and gives us one
typed `Settings` object used everywhere via `get_settings()`.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # ENVIRONMENT / Environment / environment all map to `environment`
        extra="ignore",  # ignore unknown env vars (e.g. set by the shell/IDE)
    )

    # --- Application ---
    app_name: str = "B-roll Engine"
    app_version: str = "0.1.0"
    # dev | test | prod  (test forces mock providers; prod hides debug routes)
    environment: str = Field("dev", pattern="^(dev|test|prod)$")
    log_level: str = "INFO"
    # true = structured JSON logs (production); false = human-readable (local dev)
    log_json: bool = True

    # --- API server ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_v1_prefix: str = "/api/v1"

    # --- Database ---
    # SQLite for the local demo (shared between api and worker via a volume).
    # Point this at a PostgreSQL URL for higher concurrency without code changes.
    database_url: str = "sqlite:///./data/broll.db"
    db_echo: bool = False

    # --- Storage ---
    # local | s3  (s3 uses MinIO in docker-compose)
    storage_backend: str = Field("local", pattern="^(local|s3)$")
    storage_local_root: str = "./storage"
    s3_endpoint_url: Optional[str] = None
    s3_bucket: str = "broll-engine"
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_region: Optional[str] = None

    # --- Job processing ---
    job_max_concurrency: int = 1
    job_poll_interval_seconds: float = 1.0
    job_ttl_days: int = 7
    # How many times a retryable error (e.g. UPSTREAM_PROVIDER_ERROR) re-queues
    # a job before it fails permanently.
    job_max_retries: int = 1
    # Anything expected to take longer than this runs as a background job
    # (POST returns 202). The brief sets this bar at 2 seconds.
    job_min_duration_seconds: float = 2.0
    # Optional HMAC secret to sign job-completion callbacks (X-IncuBrix-Signature).
    callback_hmac_secret: Optional[str] = None

    # --- Provider selection (which adapter runs for each capability) ---
    # "mock" needs no API keys; that is the default so tests run with no keys.
    stt_provider: str = "mock"
    tts_provider: str = "mock"
    embeddings_provider: str = "mock"
    scene_provider: str = "mock"
    footage_provider: str = "mock"
    safety_provider: str = "mock"

    # --- Provider credentials (all optional; never commit real values) ---
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    pexels_api_key: Optional[str] = None
    pixabay_api_key: Optional[str] = None

    # --- Input limits ---
    max_audio_duration_seconds: int = 600  # 10 minutes
    max_upload_bytes: int = 100 * 1024 * 1024  # 100 MB
    download_timeout_seconds: int = 60

    # --- Rendering (used from Phase 6) ---
    video_fps: int = 30
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    audio_sample_rate: int = 48000
    resolution_16_9: str = "1920x1080"
    resolution_9_16: str = "1080x1920"
    resolution_1_1: str = "1080x1080"

    @property
    def is_testing(self) -> bool:
        return self.environment == "test"

    @property
    def is_production(self) -> bool:
        return self.environment == "prod"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Call reset_settings() in tests after env changes."""
    return Settings()


def reset_settings() -> None:
    """Drop the cached settings so the next get_settings() re-reads env vars."""
    get_settings.cache_clear()
