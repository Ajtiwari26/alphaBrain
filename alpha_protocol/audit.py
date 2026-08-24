"""
Alpha Protocol Audit & Provenance v1
=====================================
Immutable audit events, provenance records, and structured usage tracking.

Protocol version: 1
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from .enums import PROTOCOL_VERSION


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProvenanceRecord(BaseModel):
    """Immutable provenance trail for any AI-generated output."""
    agent: str
    model: str
    prompt_hash: str | None = None
    tools_used: list[str] = Field(default_factory=list)
    session_id: str | None = None
    input_commit: str | None = Field(
        default=None, description="Git commit of input state"
    )
    output_commit: str | None = Field(
        default=None, description="Git commit of output state"
    )
    input_artifacts: list[str] = Field(
        default_factory=list, description="Input artifact references"
    )


class AuditEvent(BaseModel):
    """Immutable, append-only audit record for every significant system action."""
    protocol_version: str = Field(default=PROTOCOL_VERSION)
    event_id: str
    event_type: str = Field(
        description="e.g. task_leased, gate_passed, approval_granted, call_placed, "
        "deployment_started, worker_registered, spec_approved"
    )
    org_id: str | None = None
    project_id: str | None = None
    task_id: str | None = None
    actor: str = Field(description="system, founder, client, worker, service, or agent identity")
    actor_role: str | None = Field(
        default=None, description="Principal role of the actor"
    )
    details: dict[str, Any] = Field(default_factory=dict)
    provenance: ProvenanceRecord | None = None
    timestamp: datetime = Field(default_factory=utc_now)
