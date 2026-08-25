"""
Alpha Protocol Deployment Schemas v1
======================================
Deployment request, result, rollback, and preview contracts.

Protocol version: 1
"""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from .enums import PROTOCOL_VERSION, DeploymentStatus


def utc_now() -> datetime:
    return datetime.now(UTC)


class DeploymentRequest(BaseModel):
    """Request to deploy a verified build to a target environment."""

    protocol_version: str = Field(default=PROTOCOL_VERSION)
    deployment_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    project_id: str
    task_id: str
    attempt_id: str
    target_environment: str = Field(description="e.g. preview, staging, production")
    source_commit: str
    gate_evidence_ids: list[str] = Field(
        default_factory=list,
        description="IDs of passing gate evidence required before deployment",
    )
    requires_approval: bool = Field(default=True)
    requested_by: str = Field(description="Identity of requester")
    status: DeploymentStatus = DeploymentStatus.REQUESTED
    created_at: datetime = Field(default_factory=utc_now)


class DeploymentResult(BaseModel):
    """Result of a deployment attempt."""

    deployment_id: str
    status: DeploymentStatus
    deploy_url: str | None = Field(default=None, description="Live preview/production URL")
    deploy_log: str | None = None
    deployed_at: datetime | None = None
    smoke_test_passed: bool | None = None
    rollback_available: bool = Field(default=True)
    previous_commit: str | None = Field(default=None, description="Commit to rollback to if needed")


class RollbackRequest(BaseModel):
    """Request to rollback a deployment to a previous known-good state."""

    deployment_id: str
    project_id: str
    target_commit: str = Field(description="Commit hash to rollback to")
    reason: str
    requested_by: str
    created_at: datetime = Field(default_factory=utc_now)
