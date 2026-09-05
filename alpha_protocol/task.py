"""
Alpha Protocol Task Schemas v1
===============================
Versioned task envelope, DAG dependencies, retry/concurrency policies,
attempts, results, and approval contracts.

Protocol version: 1
"""

import json
from datetime import UTC, datetime
from enum import Enum
from pathlib import PurePosixPath
from typing import Any, Literal, Optional

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
# Review Attestation
# ---------------------------------------------------------------------------


class ReviewAttestation(BaseModel):
    """Cryptographic attestation of senior review execution."""

    task_id: str
    result_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    base_commit: str = Field(pattern=r"^[a-f0-9]{40}$")
    pro_verdict: str
    opus_verdict: str
    approved: bool
    reviewed_at: float
    evidence_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    signer_identity: str = "SYSTEM_SENIOR_REVIEW_ENGINE"
    signature: str = Field(pattern=r"^[a-f0-9]{64}$")

    def compute_digest(self) -> str:
        import hashlib

        data = self.model_dump(exclude={"signature"})
        canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @staticmethod
    def compute_evidence_digest(evidence: Any) -> str:
        import hashlib

        # Assuming evidence is JSON serializable
        canonical_json = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def sign(self, secret: bytes | str) -> str:
        import hashlib
        import hmac

        if isinstance(secret, str):
            secret = secret.encode("utf-8")
        digest = self.compute_digest().encode("utf-8")
        return hmac.new(secret, digest, hashlib.sha256).hexdigest()

    def verify(self, secret: bytes | str) -> bool:
        import hmac

        expected_signature = self.sign(secret)
        return hmac.compare_digest(self.signature, expected_signature)

    @classmethod
    def create(
        cls,
        task_id: str,
        result_sha: str,
        base_commit: str,
        pro_verdict: str,
        opus_verdict: str,
        approved: bool,
        reviewed_at: float,
        evidence: Any,
        secret: bytes | str,
    ) -> "ReviewAttestation":
        evidence_digest = cls.compute_evidence_digest(evidence)
        att = cls(
            task_id=task_id,
            result_sha=result_sha,
            base_commit=base_commit,
            pro_verdict=pro_verdict,
            opus_verdict=opus_verdict,
            approved=approved,
            reviewed_at=reviewed_at,
            evidence_digest=evidence_digest,
            signature="0" * 64,  # Placeholder to satisfy validation
        )
        att.signature = att.sign(secret)
        return att


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

    protocol_version: Literal["1"] = Field(
        default=PROTOCOL_VERSION, description="Protocol version (must be '1')"
    )
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
        pattern=r"^[a-f0-9]{40}$",
        description="Git base commit SHA (strict 40-chars)",
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
    require_packet_binding: bool = Field(
        default=False,
        description="If true, enforces exact digest equality throughout the task lifecycle.",
    )

    # Timestamps
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("base_commit", mode="before")
    @classmethod
    def validate_base_commit(cls, v: Any) -> str:
        if not v or str(v) == "HEAD":
            raise ValueError("base_commit must be a resolved 40-char SHA, not HEAD or empty")
        return str(v)

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


def compute_packet_digest(envelope: TaskEnvelope) -> str:
    """Produce deterministic SHA-256 hex digest from canonical task-envelope JSON."""
    import hashlib

    data = envelope.model_dump(mode="json")
    canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def compute_review_digest(result: "TaskResult", worker_id: str) -> str:
    """Produce deterministic SHA-256 digest for founder review binding."""
    import hashlib

    # Extract only authority fields
    data = {
        "task_id": result.task_id,
        "attempt_id": result.attempt_id,
        "packet_sha256": result.packet_sha256,
        "base_commit": result.base_commit,
        "result_commit": result.result_commit,
        "files_changed": sorted(result.files_changed) if result.files_changed else [],
        "agent": result.agent.value if result.agent else None,
        "model": result.model,
        "worker_id": worker_id,
        "gate_result": result.gate_result.model_dump(mode="json") if result.gate_result else None,
    }

    canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


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
# Task Checkpoint
# ---------------------------------------------------------------------------


class SideEffectState(str, Enum):
    NONE = "none"
    PREPARED = "prepared"
    STARTED = "started"
    COMMITTED = "committed"
    COMPENSATED = "compensated"
    UNKNOWN = "unknown"


class TaskCheckpoint(BaseModel):
    """Durable checkpoint of agent progress for crash recovery."""

    checkpoint_id: str = Field(
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$", description="Unique checkpoint ID"
    )
    task_id: str
    attempt_id: str
    worker_id: str
    attempt_number: int
    sequence: int
    project_id: str
    repo_reference: str
    base_commit: str
    worktree_path: str
    worktree_head: str
    conversation_id: str
    execution_stage: str
    lease_token_hash: str = Field(description="SHA-256 hash of the worker lease token")
    side_effect_state: SideEffectState
    scrubbed_payload: dict[str, Any] = Field(description="Agent state (no secrets/prompts)")
    payload_digest: str
    idempotency_key: str
    created_at: datetime = Field(default_factory=utc_now)


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
    packet_sha256: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
        description="Canonical task packet digest verified by worker",
    )
    files_changed: list[str] = Field(default_factory=list)
    diff_summary: str | None = None
    gate_result: GateResult | None = None
    artifacts: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    provenance_notes: list[str] = Field(default_factory=list)
    preview_evidence: dict[str, Any] | None = None
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


class AppendCheckpointRequest(BaseModel):
    checkpoint: TaskCheckpoint
    raw_lease_token: str


class ResumeDecisionRequest(BaseModel):
    worker_id: str
    attempt_id: str
    project_id: str
    repo_reference: str
    base_commit: str
    worktree_path: str
    conversation_id: str
    latest_checkpoint_digest: str


class ResumeDecisionResponse(BaseModel):
    safe_to_resume: bool
    reason: str | None = None
    new_lease_token: str | None = None


# ---------------------------------------------------------------------------
# Promotion Protocol
# ---------------------------------------------------------------------------


class PromotionRequest(BaseModel):
    """Worker-fetched approved promotion directive."""

    task_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    project_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
    attempt_id: str = Field(pattern=r"^att_[A-Za-z0-9._-]{1,100}$")
    worker_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
    repo: str = Field(min_length=1, max_length=512)
    base_commit: str = Field(pattern=r"^[a-f0-9]{40}$")
    result_commit: str = Field(pattern=r"^[a-f0-9]{40}$")
    files_changed: list[str] = Field(min_length=0)
    allowed_paths: list[str] = Field(min_length=1)
    review_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("files_changed")
    @classmethod
    def validate_files_changed(cls, paths: list[str]) -> list[str]:
        seen = set()
        for raw_path in paths:
            if not raw_path or "\\" in raw_path:
                raise ValueError("Empty or backslash not allowed")
            if raw_path == ".":
                raise ValueError("Dot not allowed in files_changed")
            path = PurePosixPath(raw_path)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Paths must be safe relative paths")
            normalized = str(path)
            if normalized != raw_path:
                raise ValueError(f"Path must be normalized, expected {normalized}")
            if normalized in seen:
                raise ValueError(f"Duplicate path '{normalized}'")
            seen.add(normalized)
        return paths

    @field_validator("allowed_paths")
    @classmethod
    def validate_allowed_paths(cls, paths: list[str]) -> list[str]:
        seen = set()
        for raw_path in paths:
            if not raw_path or "\\" in raw_path:
                raise ValueError("Empty or backslash not allowed")
            if raw_path == ".":
                if raw_path in seen:
                    raise ValueError("Duplicate path '.'")
                seen.add(raw_path)
                continue
            path = PurePosixPath(raw_path)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Paths must be safe relative paths")
            normalized = str(path)
            if normalized != raw_path:
                raise ValueError(f"Path must be normalized, expected {normalized}")
            if normalized in seen:
                raise ValueError(f"Duplicate path '{normalized}'")
            seen.add(normalized)
        return paths


def compute_promotion_digest(request: PromotionRequest) -> str:
    """Canonical promotion digest required for founder approval."""
    import hashlib

    data = {
        "task_id": request.task_id,
        "project_id": request.project_id,
        "attempt_id": request.attempt_id,
        "worker_id": request.worker_id,
        "repo": request.repo,
        "base_commit": request.base_commit,
        "result_commit": request.result_commit,
        "files_changed": sorted(request.files_changed) if request.files_changed else [],
        "review_sha256": request.review_sha256,
    }
    canonical_json = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class PromotionResult(BaseModel):
    """Result of worker applying a promotion."""

    task_id: str
    worker_id: str
    promotion_digest: str
    status: Literal["succeeded", "failed"]
    reason: str | None = None
