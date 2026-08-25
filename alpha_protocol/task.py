"""
Alpha Protocol Task Schemas v1
===============================
Versioned task envelope, DAG dependencies, retry/concurrency policies,
attempts, results, and approval contracts.

Protocol version: 1
"""

from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .enums import (
    EXECUTION_ENABLED_AGENTS,
    PROTOCOL_VERSION,
    AgentType,
    ApprovalStatus,
    RiskClass,
    TaskStatus,
)
from .gates import AcceptancePlan, GateResult


def utc_now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# DAG Dependency Contract
# ---------------------------------------------------------------------------


class TaskDependency(BaseModel):
    """Declares that this task depends on another task reaching a required status."""

    task_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    required_status: TaskStatus = TaskStatus.COMPLETED


# ---------------------------------------------------------------------------
# Retry & Concurrency Policy
# ---------------------------------------------------------------------------


class RetryPolicy(BaseModel):
    """Controls how failed tasks are retried."""

    max_attempts: int = Field(default=3, ge=1, le=10)
    backoff_base_seconds: int = Field(default=60, ge=10, le=3600)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    deadline_seconds: int = Field(
        default=86400,
        ge=300,
        le=604800,
        description="Maximum total time allowed for all retries (default 24h)",
    )


class ConcurrencyPolicy(BaseModel):
    """Per-project and per-worker concurrency limits."""

    max_per_project: int = Field(default=5, ge=1, le=50)
    max_per_worker: int = Field(default=2, ge=1, le=10)


# ---------------------------------------------------------------------------
# Approval Request/Result
# ---------------------------------------------------------------------------


class ApprovalRequest(BaseModel):
    """Request for human approval before a high-risk action proceeds."""

    approval_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    task_id: str
    project_id: str
    action_type: str = Field(
        description="e.g. production_deployment, db_migration, destructive_cmd"
    )
    description: str
    risk_class: RiskClass
    requested_by: str = Field(description="system, agent, or worker identity")
    required_approver_role: str = Field(default="founder")
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None


class ApprovalResult(BaseModel):
    """Result of a human approval decision."""

    approval_id: str
    status: ApprovalStatus
    decided_by: str
    reason: str | None = None
    decided_at: datetime = Field(default_factory=utc_now)


# ---------------------------------------------------------------------------
# Task Envelope v1
# ---------------------------------------------------------------------------


class TaskEnvelope(BaseModel):
    """Versioned task dispatched to worker plane."""

    protocol_version: str = Field(default=PROTOCOL_VERSION, description="Protocol version")
    task_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$",
        description="Unique task identifier, e.g. tsk_101",
    )
    project_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$",
        description="Parent project ID, e.g. prj_alpha",
    )
    org_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$",
        description="Organization scope",
    )
    repo: str = Field(min_length=1, max_length=512, description="Repository path or identifier")
    base_commit: str = Field(
        default="HEAD",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/@{}~^+-]{0,127}$",
        description="Git base commit/branch",
    )
    objective: str = Field(description="Clear, actionable task objective")
    detailed_instructions: str | None = Field(
        default=None, description="Detailed markdown instructions"
    )
    inputs: list[str] = Field(default_factory=list, description="Input artifact references")
    allowed_paths: list[str] = Field(
        min_length=1,
        description="Scoped relative paths allowed to be touched; use '.' for whole repo",
    )
    allowed_tools: list[str] = Field(default_factory=list, description="Allowed tool or MCP names")
    risk_class: RiskClass = RiskClass.LOW
    acceptance_plan: AcceptancePlan = Field(default_factory=AcceptancePlan)
    preferred_agent: AgentType = AgentType.ANTIGRAVITY
    session_id: str | None = Field(
        default=None, description="Dedicated Antigravity or memory_graph session ID"
    )
    lease_timeout_seconds: int = Field(
        default=1800, description="Task lease timeout (default 30 mins)"
    )
    retain_worktree_for_preview: bool = Field(
        default=False,
        description="Keep successful isolated worktree available for a local preview server",
    )

    # DAG dependency and retry/concurrency controls
    dependencies: list[TaskDependency] = Field(
        default_factory=list,
        description="Tasks that must complete before this task can be leased",
    )
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    concurrency_policy: ConcurrencyPolicy = Field(default_factory=ConcurrencyPolicy)
    requires_approval: bool = Field(
        default=False,
        description="If true, task enters WAITING_APPROVAL before execution",
    )

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("allowed_paths")
    @classmethod
    def validate_allowed_paths(cls, paths: list[str]) -> list[str]:
        for raw_path in paths:
            if raw_path == ".":
                continue
            path = PurePosixPath(raw_path)
            if path.is_absolute() or ".." in path.parts or not path.parts:
                raise ValueError("allowed_paths must contain safe relative paths")
        return paths

    @field_validator("preferred_agent")
    @classmethod
    def validate_enabled_agent(cls, agent: AgentType) -> AgentType:
        if agent not in EXECUTION_ENABLED_AGENTS:
            enabled = ", ".join(sorted(item.value for item in EXECUTION_ENABLED_AGENTS))
            raise ValueError(
                f"Agent '{agent.value}' is disabled; enabled execution agents: {enabled}"
            )
        return agent


# ---------------------------------------------------------------------------
# Task Attempt
# ---------------------------------------------------------------------------


class TaskAttempt(BaseModel):
    """Represents a single execution attempt by an agent adapter."""

    attempt_id: str = Field(description="Unique attempt ID, e.g. att_101_1")
    task_id: str
    attempt_number: int = Field(default=1, ge=1)
    agent: AgentType
    model: str
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    status: TaskStatus = TaskStatus.RUNNING
    worktree_path: str | None = None


# ---------------------------------------------------------------------------
# Task Result
# ---------------------------------------------------------------------------


class TaskResult(BaseModel):
    """Structured result returned by an agent adapter upon completing an attempt."""

    attempt_id: str
    task_id: str
    status: TaskStatus
    agent: AgentType
    model: str
    base_commit: str
    result_commit: str | None = None
    files_changed: list[str] = Field(default_factory=list)
    diff_summary: str | None = None
    gate_result: GateResult | None = None
    artifacts: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    provenance_notes: list[str] = Field(default_factory=list)
    usage: Optional["UsageRecord"] = None
    completed_at: datetime = Field(default_factory=utc_now)


# ---------------------------------------------------------------------------
# Usage / Cost / Quota
# ---------------------------------------------------------------------------


class UsageRecord(BaseModel):
    """Structured usage/cost tracking per task attempt."""

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    duration_seconds: float = Field(default=0.0, ge=0.0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    model: str = ""
    provider: str = ""


# Resolve forward reference
TaskResult.model_rebuild()
