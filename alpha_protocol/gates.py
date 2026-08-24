from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .enums import GateType


def utc_now() -> datetime:
    return datetime.now(UTC)


class GateEvidence(BaseModel):
    """Specific evidence item proving a gate passed."""
    evidence_id: str = Field(description="Unique ID for this evidence record")
    gate_type: GateType
    passed: bool
    summary: str
    output_log: str = Field(default="", description="Scrubbed stdout/stderr or tool output")
    metrics: dict[str, Any] = Field(default_factory=dict, description="e.g. coverage, duration, exit_code")
    artifacts_created: list[str] = Field(default_factory=list, description="Relative paths to produced artifacts")
    timestamp: datetime = Field(default_factory=utc_now)


class GateResult(BaseModel):
    """Aggregate result of running all declared acceptance gates on a task."""
    task_id: str
    attempt_id: str
    all_passed: bool
    evidence_items: list[GateEvidence] = Field(default_factory=list)
    defect_summary: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class GateCommand(BaseModel):
    """Typed no-shell command used to produce evidence for one gate."""

    gate_type: GateType
    executable: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")
    args: list[str] = Field(default_factory=list, max_length=64)
    timeout_seconds: int = Field(default=300, ge=1, le=900)


class AcceptancePlan(BaseModel):
    """Declared acceptance criteria that must be satisfied before task completion."""
    required_gates: list[GateType] = Field(default_factory=lambda: [GateType.LINT, GateType.UNIT_TEST])
    commands: list[GateCommand] = Field(default_factory=list)
    custom_commands: list[str] = Field(
        default_factory=list,
        exclude=True,
        description="Removed unsafe compatibility field; non-empty values are rejected",
    )
    require_independent_review: bool = False
    browser_smoke_url: str | None = None

    @model_validator(mode="after")
    def reject_unsafe_custom_commands(self):
        if self.custom_commands:
            raise ValueError("custom_commands is unsafe; use typed commands")
        return self
