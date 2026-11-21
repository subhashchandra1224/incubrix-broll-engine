"""Request/response schemas for the job API."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class SceneItem(BaseModel):
    """One pre-segmented scene (IncuBrix scene list support)."""
    text: str = Field(..., min_length=1, description="Narration text for the scene.")
    visual_hint: Optional[str] = Field(None, description="Optional visual guidance.")


class Captions(BaseModel):
    burn_in: bool = False
    srt: bool = True


class JobCreateRequest(BaseModel):
    """Create a B-roll job. Exactly one of audio_url / script / scenes."""
    audio_url: Optional[str] = None
    script: Optional[str] = None
    scenes: Optional[list[SceneItem]] = None
    voice: Optional[str] = None  # used only when the input is text
    aspect_ratios: list[Literal["16:9", "9:16", "1:1"]] = Field(..., min_length=1)
    style: Optional[str] = None
    avoid: Optional[list[str]] = None
    captions: Optional[Captions] = None
    callback_url: Optional[str] = None  # optional signed callback (Integration Standard #3)

    @field_validator("audio_url")
    @classmethod
    def _validate_audio_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("audio_url must be an http(s) URL")
        return v

    @field_validator("callback_url")
    @classmethod
    def _validate_callback_url(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("callback_url must be an http(s) URL")
        return v

    @field_validator("script")
    @classmethod
    def _validate_script(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError("script must not be empty/whitespace")
        return v


class JobAcceptedResponse(BaseModel):
    """Returned by POST /api/v1/broll/jobs (HTTP 202)."""
    job_id: str
    status: str
    status_url: str


class JobStatusResponse(BaseModel):
    """Returned by GET /api/v1/jobs/{job_id}."""
    job_id: str
    status: str
    progress: int
    result: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None
