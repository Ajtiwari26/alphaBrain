"""
Alpha Brain Database Models
============================
Authoritative SQLAlchemy ORM models for all durable state:
organizations, users, clients, memberships, consents, specifications,
decisions, open questions, change requests, workflows, normalized task dependencies,
tasks, attempts, gates, artifacts, deployments, meetings, workers, calls, and audit events.

Uses JSON columns for structured data instead of stringified Python representations.
Enforces append-only immutable audit log guarantees via ORM event listeners.
"""

import enum
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Organization, User, Client, Membership & Consent Models
# ---------------------------------------------------------------------------


class OrganizationRecord(Base):
    __tablename__ = "organizations"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(64), unique=True, nullable=False)
    status = Column(String(32), default="active")
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    members = relationship("UserRecord", back_populates="organization")
    clients = relationship("ClientRecord", back_populates="organization")
    projects = relationship("ProjectRecord", back_populates="organization")


class UserRecord(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organizations.id"), nullable=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(String(32), nullable=False, default="client")  # founder, admin, client, worker
    is_active = Column(Boolean, default=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    organization = relationship("OrganizationRecord", back_populates="members")
    memberships = relationship(
        "MembershipRecord", back_populates="user", cascade="all, delete-orphan"
    )


class ClientRecord(Base):
    __tablename__ = "clients"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    company = Column(String(255), nullable=True)
    status = Column(String(32), default="active")
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    organization = relationship("OrganizationRecord", back_populates="clients")
    projects = relationship("ProjectRecord", back_populates="client")


class MembershipRecord(Base):
    __tablename__ = "memberships"

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=False)
    org_id = Column(String(64), ForeignKey("organizations.id"), nullable=False)
    role = Column(
        String(32), nullable=False, default="client"
    )  # founder, admin, client, worker, service
    created_at = Column(DateTime(timezone=True), default=utc_now)

    user = relationship("UserRecord", back_populates="memberships")
    organization = relationship("OrganizationRecord")

    __table_args__ = (UniqueConstraint("user_id", "org_id", name="uq_membership_user_org"),)


class ConsentRecord(Base):
    __tablename__ = "consents"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organizations.id"), nullable=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=True)
    consent_type = Column(
        String(64), nullable=False
    )  # voice_recording, telephonic_outreach, ai_processing, data_retention
    granted = Column(Boolean, nullable=False, default=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)
    recorded_at = Column(DateTime(timezone=True), default=utc_now)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_consent_project_user", "project_id", "user_id"),)


# ---------------------------------------------------------------------------
# Project Model
# ---------------------------------------------------------------------------


class ProjectRecord(Base):
    __tablename__ = "projects"

    id = Column(String(64), primary_key=True)
    org_id = Column(String(64), ForeignKey("organizations.id"), nullable=True)
    client_id = Column(String(64), ForeignKey("clients.id"), nullable=True)
    name = Column(String(255), nullable=False)
    repo_path = Column(String(512), nullable=False)
    active_spec_version = Column(Integer, default=1)
    status = Column(String(32), default="active")
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    organization = relationship("OrganizationRecord", back_populates="projects")
    client = relationship("ClientRecord", back_populates="projects")
    specs = relationship(
        "SpecVersionRecord", back_populates="project", cascade="all, delete-orphan"
    )
    decisions = relationship(
        "DecisionRecord", back_populates="project", cascade="all, delete-orphan"
    )
    open_questions = relationship(
        "OpenQuestionRecord", back_populates="project", cascade="all, delete-orphan"
    )
    change_requests = relationship(
        "ChangeRequestRecord", back_populates="project", cascade="all, delete-orphan"
    )
    workflows = relationship(
        "WorkflowRecord", back_populates="project", cascade="all, delete-orphan"
    )
    tasks = relationship("TaskRecord", back_populates="project", cascade="all, delete-orphan")
    meetings = relationship("MeetingRecord", back_populates="project", cascade="all, delete-orphan")
    deployments = relationship(
        "DeploymentRecord", back_populates="project", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Specification, Decision, Open Question & Change Request Models
# ---------------------------------------------------------------------------


class SpecVersionRecord(Base):
    __tablename__ = "spec_versions"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    version = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    spec_json = Column(JSON, nullable=False)  # Full SpecVersion JSON/JSONB
    status = Column(String(32), default="pending")
    founder_approved = Column(Boolean, default=False)
    client_approved = Column(Boolean, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("ProjectRecord", back_populates="specs")
    approvals = relationship("ApprovalRecord", back_populates="spec", cascade="all, delete-orphan")
    decisions = relationship("DecisionRecord", back_populates="spec")
    open_questions = relationship("OpenQuestionRecord", back_populates="spec")

    __table_args__ = (UniqueConstraint("project_id", "version", name="uq_spec_project_version"),)


class DecisionRecord(Base):
    __tablename__ = "decisions"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    spec_id = Column(String(64), ForeignKey("spec_versions.id"), nullable=True)
    meeting_id = Column(String(64), ForeignKey("meetings.id"), nullable=True)
    topic = Column(String(255), nullable=False)
    decision = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    alternatives_json = Column(JSON, default=list)
    created_by = Column(String(64), nullable=False, default="founder")
    status = Column(String(32), default="approved")  # proposed, approved, rejected, superseded
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    project = relationship("ProjectRecord", back_populates="decisions")
    spec = relationship("SpecVersionRecord", back_populates="decisions")
    meeting = relationship("MeetingRecord")


class OpenQuestionRecord(Base):
    __tablename__ = "open_questions"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    spec_id = Column(String(64), ForeignKey("spec_versions.id"), nullable=True)
    meeting_id = Column(String(64), ForeignKey("meetings.id"), nullable=True)
    question = Column(Text, nullable=False)
    context = Column(Text, nullable=False)
    owner = Column(String(32), default="founder")  # founder or client
    resolved = Column(Boolean, default=False)
    answer = Column(Text, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    project = relationship("ProjectRecord", back_populates="open_questions")
    spec = relationship("SpecVersionRecord", back_populates="open_questions")
    meeting = relationship("MeetingRecord")


class ChangeRequestRecord(Base):
    __tablename__ = "change_requests"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    requested_by = Column(String(64), nullable=False)
    impact_summary = Column(Text, nullable=True)
    status = Column(
        String(32), default="submitted"
    )  # submitted, reviewed, approved, rejected, applied
    created_at = Column(DateTime(timezone=True), default=utc_now)
    decided_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("ProjectRecord", back_populates="change_requests")


# ---------------------------------------------------------------------------
# Workflow & Task Dependency Models
# ---------------------------------------------------------------------------


class WorkflowRecord(Base):
    __tablename__ = "workflows"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    phase = Column(
        String(32), nullable=False, default="intake"
    )  # intake, spec_drafting, spec_approved, in_progress, qa_review, deployed, monitoring
    status = Column(String(32), default="active")
    details_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    project = relationship("ProjectRecord", back_populates="workflows")


class TaskDependencyRecord(Base):
    __tablename__ = "task_dependencies"

    id = Column(String(64), primary_key=True)
    task_id = Column(String(64), ForeignKey("tasks.id"), nullable=False)
    depends_on_task_id = Column(String(64), ForeignKey("tasks.id"), nullable=False)
    required_status = Column(String(32), default="completed")
    created_at = Column(DateTime(timezone=True), default=utc_now)

    task = relationship(
        "TaskRecord", foreign_keys=[task_id], back_populates="declared_dependencies"
    )
    depends_on_task = relationship("TaskRecord", foreign_keys=[depends_on_task_id])

    __table_args__ = (UniqueConstraint("task_id", "depends_on_task_id", name="uq_task_dependency"),)


class ApprovalRecord(Base):
    __tablename__ = "approvals"

    id = Column(String(64), primary_key=True)
    spec_id = Column(String(64), ForeignKey("spec_versions.id"), nullable=True)
    task_id = Column(String(64), ForeignKey("tasks.id"), nullable=True)
    attempt_id = Column(String(64), ForeignKey("task_attempts.id"), nullable=True)
    deployment_id = Column(String(64), ForeignKey("deployments.id"), nullable=True)
    approval_type = Column(String(32), nullable=False)  # spec, task, deployment
    scope_sha256 = Column(String(64), nullable=True)
    status = Column(String(32), default="pending")
    decided_by = Column(String(64), nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    decided_at = Column(DateTime(timezone=True), nullable=True)

    spec = relationship("SpecVersionRecord", back_populates="approvals")


# ---------------------------------------------------------------------------
# Task & Attempt Models
# ---------------------------------------------------------------------------


class TaskRecord(Base):
    __tablename__ = "tasks"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    org_id = Column(String(64), nullable=True)
    repo = Column(String(512), nullable=False)
    base_commit = Column(String(128), default="HEAD")
    objective = Column(Text, nullable=False)
    details_json = Column(JSON, nullable=False)  # Full TaskEnvelope JSON/JSONB
    packet_sha256 = Column(String(64), nullable=True)
    risk_class = Column(String(32), default="low")
    preferred_agent = Column(String(32), default="antigravity")
    status = Column(String(32), default="queued")
    attempt_count = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    lease_token = Column(String(128), nullable=True)
    leased_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    next_eligible_at = Column(DateTime(timezone=True), nullable=True)
    worker_id = Column(String(128), nullable=True)
    depends_on_json = Column(JSON, default=list)  # JSON array of dependency task IDs
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    project = relationship("ProjectRecord", back_populates="tasks")
    attempts = relationship("AttemptRecord", back_populates="task", cascade="all, delete-orphan")
    gates = relationship("GateEvidenceRecord", back_populates="task", cascade="all, delete-orphan")
    artifacts = relationship("ArtifactRecord", back_populates="task", cascade="all, delete-orphan")
    declared_dependencies = relationship(
        "TaskDependencyRecord",
        foreign_keys="TaskDependencyRecord.task_id",
        back_populates="task",
        cascade="all, delete-orphan",
    )


class AttemptRecord(Base):
    __tablename__ = "task_attempts"

    id = Column(String(64), primary_key=True)
    task_id = Column(String(64), ForeignKey("tasks.id"), nullable=False)
    worker_id = Column(String(128), nullable=True)
    attempt_number = Column(Integer, default=1)
    agent = Column(String(32), nullable=False)
    model = Column(String(64), nullable=False)
    status = Column(String(32), default="running")
    result_commit = Column(String(128), nullable=True)
    packet_sha256 = Column(String(64), nullable=True)
    files_changed_json = Column(JSON, default=list)
    gate_result_json = Column(JSON, nullable=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    duration_seconds = Column(Float, default=0.0)
    estimated_cost_usd = Column(Float, default=0.0)
    started_at = Column(DateTime(timezone=True), default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    task = relationship("TaskRecord", back_populates="attempts")


class SideEffectState(str, enum.Enum):
    NONE = "none"
    PREPARED = "prepared"
    STARTED = "started"
    COMMITTED = "committed"
    COMPENSATED = "compensated"
    UNKNOWN = "unknown"


class TaskCheckpointRecord(Base):
    __tablename__ = "task_checkpoints"

    id = Column(String(64), primary_key=True)
    task_id = Column(String(64), ForeignKey("tasks.id"), nullable=False)
    attempt_id = Column(String(64), nullable=False)
    worker_id = Column(String(64), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    sequence = Column(Integer, nullable=False)
    project_id = Column(String(64), nullable=False)
    repo_reference = Column(String(512), nullable=False)
    base_commit = Column(String(128), nullable=False)
    worktree_path = Column(String(512), nullable=False)
    worktree_head = Column(String(128), nullable=False)
    conversation_id = Column(String(64), nullable=False)
    execution_stage = Column(String(64), nullable=False)
    lease_token_hash = Column(String(64), nullable=False)
    side_effect_state = Column(String(32), nullable=False)
    scrubbed_payload = Column(JSON, nullable=False)
    payload_digest = Column(String(64), nullable=False)
    idempotency_key = Column(String(128), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    task = relationship("TaskRecord")
    attempt = relationship(
        "AttemptRecord", primaryjoin="TaskCheckpointRecord.attempt_id == foreign(AttemptRecord.id)"
    )

    __table_args__ = (
        UniqueConstraint("task_id", "attempt_number", "sequence", name="uq_task_attempt_seq"),
    )


class GateEvidenceRecord(Base):
    __tablename__ = "gate_evidence"

    id = Column(String(64), primary_key=True)
    task_id = Column(String(64), ForeignKey("tasks.id"), nullable=False)
    attempt_id = Column(String(64), nullable=False)
    gate_type = Column(String(32), nullable=False)
    passed = Column(Boolean, nullable=False)
    summary = Column(Text, nullable=False)
    output_log = Column(Text, default="")
    metrics_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    task = relationship("TaskRecord", back_populates="gates")


# ---------------------------------------------------------------------------
# Artifact Model
# ---------------------------------------------------------------------------


class ArtifactRecord(Base):
    __tablename__ = "artifacts"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    task_id = Column(String(64), ForeignKey("tasks.id"), nullable=True)
    attempt_id = Column(String(64), nullable=True)
    media_type = Column(String(128), nullable=False)
    filename = Column(String(255), nullable=False)
    size_bytes = Column(Integer, default=0)
    sha256_hash = Column(String(64), nullable=False)
    storage_path = Column(String(512), nullable=False)
    tags_json = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    created_by = Column(String(64), nullable=False)

    task = relationship("TaskRecord", back_populates="artifacts")


# ---------------------------------------------------------------------------
# Deployment Model
# ---------------------------------------------------------------------------


class DeploymentRecord(Base):
    __tablename__ = "deployments"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    task_id = Column(String(64), nullable=False)
    attempt_id = Column(String(64), nullable=True)
    target_environment = Column(String(32), nullable=False)
    source_commit = Column(String(128), nullable=False)
    previous_commit = Column(String(128), nullable=True)
    status = Column(String(32), default="requested")
    deploy_url = Column(String(512), nullable=True)
    smoke_test_passed = Column(Boolean, nullable=True)
    requires_approval = Column(Boolean, default=True)
    requested_by = Column(String(64), nullable=False)
    approved_by = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    deployed_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("ProjectRecord", back_populates="deployments")


# ---------------------------------------------------------------------------
# Meeting Models
# ---------------------------------------------------------------------------


class MeetingRecord(Base):
    __tablename__ = "meetings"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    room_name = Column(String(128), nullable=False)
    status = Column(String(32), default="active")
    consent_recorded = Column(Boolean, default=False)
    started_at = Column(DateTime(timezone=True), default=utc_now)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    project = relationship("ProjectRecord", back_populates="meetings")
    participants = relationship(
        "MeetingParticipantRecord", back_populates="meeting", cascade="all, delete-orphan"
    )
    transcript_segments = relationship(
        "TranscriptSegmentRecord", back_populates="meeting", cascade="all, delete-orphan"
    )
    meeting_events = relationship(
        "MeetingEventRecord", back_populates="meeting", cascade="all, delete-orphan"
    )


class MeetingParticipantRecord(Base):
    __tablename__ = "meeting_participants"

    id = Column(String(64), primary_key=True)
    meeting_id = Column(String(64), ForeignKey("meetings.id"), nullable=False)
    identity = Column(String(128), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(32), default="client")
    is_eva = Column(Boolean, default=False)
    joined_at = Column(DateTime(timezone=True), default=utc_now)
    left_at = Column(DateTime(timezone=True), nullable=True)

    meeting = relationship("MeetingRecord", back_populates="participants")


class TranscriptSegmentRecord(Base):
    __tablename__ = "transcript_segments"

    id = Column(String(64), primary_key=True)
    meeting_id = Column(String(64), ForeignKey("meetings.id"), nullable=False)
    speaker_identity = Column(String(128), nullable=False)
    speaker_name = Column(String(255), nullable=False)
    text = Column(Text, nullable=False)
    is_eva = Column(Boolean, default=False)
    timestamp = Column(DateTime(timezone=True), default=utc_now)

    meeting = relationship("MeetingRecord", back_populates="transcript_segments")

    __table_args__ = (Index("ix_transcript_meeting_ts", "meeting_id", "timestamp"),)


class MeetingEventRecord(Base):
    __tablename__ = "meeting_events"

    id = Column(String(64), primary_key=True)
    meeting_id = Column(String(64), ForeignKey("meetings.id"), nullable=False)
    event_type = Column(String(32), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    raw_quote = Column(Text, nullable=True)
    speaker_identity = Column(String(128), nullable=True)
    is_inference = Column(Boolean, default=False)
    confidence = Column(Float, default=1.0)
    tags_json = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    meeting = relationship("MeetingRecord", back_populates="meeting_events")


# ---------------------------------------------------------------------------
# Worker Models
# ---------------------------------------------------------------------------


class WorkerRecord(Base):
    __tablename__ = "workers"

    id = Column(String(64), primary_key=True)
    hostname = Column(String(255), nullable=False)
    platform = Column(String(64), default="macos-arm64")
    capability_json = Column(JSON, default=dict)
    status = Column(String(32), default="online")
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    registered_at = Column(DateTime(timezone=True), default=utc_now)

    health_reports = relationship(
        "WorkerHealthRecord", back_populates="worker", cascade="all, delete-orphan"
    )
    leases = relationship(
        "WorkerLeaseRecord", back_populates="worker", cascade="all, delete-orphan"
    )


class WorkerHealthRecord(Base):
    __tablename__ = "worker_health_history"

    id = Column(String(64), primary_key=True)
    worker_id = Column(String(64), ForeignKey("workers.id"), nullable=False)
    battery_percent = Column(Integer, nullable=True)
    ac_power = Column(Boolean, nullable=True)
    thermal_pressure = Column(String(32), nullable=True)
    cpu_load_percent = Column(Float, nullable=True)
    disk_free_gb = Column(Float, nullable=True)
    active_task_count = Column(Integer, default=0)
    reported_at = Column(DateTime(timezone=True), default=utc_now)

    worker = relationship("WorkerRecord", back_populates="health_reports")


class WorkerLeaseRecord(Base):
    __tablename__ = "worker_leases"

    id = Column(String(64), primary_key=True)
    worker_id = Column(String(64), ForeignKey("workers.id"), nullable=False)
    task_id = Column(String(64), nullable=False)
    lease_token = Column(String(128), nullable=False)
    leased_at = Column(DateTime(timezone=True), default=utc_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    released_at = Column(DateTime(timezone=True), nullable=True)

    worker = relationship("WorkerRecord", back_populates="leases")


# ---------------------------------------------------------------------------
# Call / Notification Models
# ---------------------------------------------------------------------------


class CallJobRecord(Base):
    __tablename__ = "call_jobs"

    id = Column(String(64), primary_key=True)
    notification_id = Column(String(64), nullable=False)
    persona = Column(String(32), default="kavya")
    recipient_phone = Column(String(32), nullable=False)
    recipient_name = Column(String(255), nullable=True)
    project_id = Column(String(64), nullable=True)
    purpose = Column(String(128), nullable=False)
    script_facts_json = Column(JSON, default=dict)
    status = Column(String(32), default="queued")
    idempotency_key = Column(String(128), unique=True, nullable=False)
    call_id = Column(String(128), nullable=True)
    duration_seconds = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    status_history = relationship(
        "CallStatusRecord", back_populates="call_job", cascade="all, delete-orphan"
    )


class CallStatusRecord(Base):
    __tablename__ = "call_status_history"

    id = Column(String(64), primary_key=True)
    call_job_id = Column(String(64), ForeignKey("call_jobs.id"), nullable=False)
    status = Column(String(32), nullable=False)
    provider_call_id = Column(String(128), nullable=True)
    details_json = Column(JSON, default=dict)
    recorded_at = Column(DateTime(timezone=True), default=utc_now)

    call_job = relationship("CallJobRecord", back_populates="status_history")


# ---------------------------------------------------------------------------
# Audit Model (Immutable, Append-Only)
# ---------------------------------------------------------------------------


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id = Column(String(64), primary_key=True)
    event_type = Column(String(64), nullable=False)
    org_id = Column(String(64), nullable=True)
    project_id = Column(String(64), nullable=True)
    task_id = Column(String(64), nullable=True)
    actor = Column(String(64), nullable=False)
    actor_role = Column(String(32), nullable=True)
    details_json = Column(JSON, default=dict)
    timestamp = Column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        Index("ix_audit_project_ts", "project_id", "timestamp"),
        Index("ix_audit_type_ts", "event_type", "timestamp"),
    )


# ---------------------------------------------------------------------------
# Immutable Append-Only Audit Event Protection Listeners
# ---------------------------------------------------------------------------


@event.listens_for(AuditEventRecord, "before_update")
def prevent_audit_event_update(mapper: Any, connection: Any, target: AuditEventRecord) -> None:
    raise RuntimeError("AuditEventRecord is immutable and cannot be updated")


@event.listens_for(AuditEventRecord, "before_delete")
def prevent_audit_event_delete(mapper: Any, connection: Any, target: AuditEventRecord) -> None:
    raise RuntimeError("AuditEventRecord is append-only and cannot be deleted")
