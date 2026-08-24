"""
Alpha Protocol Artifact Schemas v1
====================================
Artifact metadata, hash verification, signed reference URLs, and
media type classification for secure artifact storage and retrieval.

Protocol version: 1
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from .enums import PROTOCOL_VERSION


def utc_now() -> datetime:
    return datetime.now(UTC)


class ArtifactMetadata(BaseModel):
    """Metadata for a stored artifact (log, screenshot, build, recording, spec doc)."""
    protocol_version: str = Field(default=PROTOCOL_VERSION)
    artifact_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$",
        description="Safe artifact identifier without path traversal",
    )
    project_id: str
    task_id: str | None = None
    attempt_id: str | None = None
    media_type: str = Field(
        description="MIME type, e.g. application/pdf, text/plain, image/png"
    )
    filename: str = Field(max_length=255)
    size_bytes: int = Field(ge=0)
    sha256_hash: str = Field(
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 hex digest of file contents",
    )
    storage_path: str = Field(
        description="Internal storage path (bucket/key or local path)"
    )
    signed_url: str | None = Field(
        default=None,
        description="Short-lived pre-signed download URL",
    )
    signed_url_expires_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    created_by: str = Field(description="Identity of creator (agent, worker, system)")
