import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProjectRecord(Base):
    __tablename__ = "projects"

    id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    repo_path = Column(String(512), nullable=False)
    active_spec_version = Column(Integer, default=1)
    status = Column(String(32), default="active")
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    specs = relationship("SpecVersionRecord", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("TaskRecord", back_populates="project", cascade="all, delete-orphan")


class SpecVersionRecord(Base):
    __tablename__ = "spec_versions"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    version = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    spec_json = Column(Text, nullable=False)  # Serialized SpecVersion Pydantic model
    status = Column(String(32), default="pending")
    founder_approved = Column(Boolean, default=False)
    client_approved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=utc_now)

    project = relationship("ProjectRecord", back_populates="specs")


class TaskRecord(Base):
    __tablename__ = "tasks"

    id = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    repo = Column(String(512), nullable=False)
    base_commit = Column(String(128), default="HEAD")
    objective = Column(Text, nullable=False)
    details_json = Column(Text, nullable=False)  # Serialized TaskEnvelope
    risk_class = Column(String(32), default="low")
    preferred_agent = Column(String(32), default="antigravity")
    status = Column(String(32), default="queued")
    lease_token = Column(String(128), nullable=True)
    leased_at = Column(DateTime(timezone=True), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    worker_id = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    project = relationship("ProjectRecord", back_populates="tasks")
    attempts = relationship("AttemptRecord", back_populates="task", cascade="all, delete-orphan")


class AttemptRecord(Base):
    __tablename__ = "task_attempts"

    id = Column(String(64), primary_key=True)
    task_id = Column(String(64), ForeignKey("tasks.id"), nullable=False)
    attempt_number = Column(Integer, default=1)
    agent = Column(String(32), nullable=False)
    model = Column(String(64), nullable=False)
    status = Column(String(32), default="running")
    result_commit = Column(String(128), nullable=True)
    files_changed_json = Column(Text, default="[]")
    gate_result_json = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    task = relationship("TaskRecord", back_populates="attempts")


class CallJobRecord(Base):
    __tablename__ = "call_jobs"

    id = Column(String(64), primary_key=True)
    notification_id = Column(String(64), nullable=False)
    persona = Column(String(32), default="kavya")
    recipient_phone = Column(String(32), nullable=False)
    purpose = Column(String(128), nullable=False)
    script_facts_json = Column(Text, default="{}")
    status = Column(String(32), default="queued")
    idempotency_key = Column(String(128), unique=True, nullable=False)
    call_id = Column(String(128), nullable=True)
    duration_seconds = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id = Column(String(64), primary_key=True)
    event_type = Column(String(64), nullable=False)
    project_id = Column(String(64), nullable=True)
    task_id = Column(String(64), nullable=True)
    actor = Column(String(64), nullable=False)
    details_json = Column(Text, default="{}")
    timestamp = Column(DateTime(timezone=True), default=utc_now)
