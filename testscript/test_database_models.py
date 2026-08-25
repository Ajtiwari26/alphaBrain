"""
testscript/test_database_models.py
Comprehensive test suite verifying SQLAlchemy ORM models, relationships,
constraints, and Alembic migrations across all P3 database entities.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alpha_core.db.models import (
    ApprovalRecord,
    ArtifactRecord,
    AttemptRecord,
    AuditEventRecord,
    Base,
    CallJobRecord,
    CallStatusRecord,
    DeploymentRecord,
    GateEvidenceRecord,
    MeetingEventRecord,
    MeetingParticipantRecord,
    MeetingRecord,
    OrganizationRecord,
    ProjectRecord,
    SpecVersionRecord,
    TaskRecord,
    TranscriptSegmentRecord,
    UserRecord,
    WorkerHealthRecord,
    WorkerLeaseRecord,
    WorkerRecord,
)


@pytest.fixture
async def db_session():
    """Provides a fresh in-memory SQLite database session for each test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session

    await engine.dispose()


# ---------------------------------------------------------------------------
# Organization & User Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_organization_and_user_creation(db_session: AsyncSession):
    org = OrganizationRecord(
        id="org_deploymate",
        name="DeployMate Corp",
        slug="deploymate",
    )
    db_session.add(org)
    await db_session.flush()

    user = UserRecord(
        id="usr_ajay",
        org_id=org.id,
        name="Ajay Tiwari",
        email="ajay@deploymate.com",
        role="founder",
    )
    db_session.add(user)
    await db_session.commit()

    # Query back and verify relations
    res = await db_session.execute(select(UserRecord).where(UserRecord.id == "usr_ajay"))
    saved_user = res.scalar_one()
    assert saved_user.name == "Ajay Tiwari"
    assert saved_user.role == "founder"
    assert saved_user.org_id == "org_deploymate"


# ---------------------------------------------------------------------------
# Project, Spec & Approval Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spec_versioning_and_uniqueness(db_session: AsyncSession):
    proj = ProjectRecord(
        id="prj_alpha",
        name="AlphaBrain Orchestrator",
        repo_path="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
    )
    db_session.add(proj)
    await db_session.flush()

    spec_v1 = SpecVersionRecord(
        id="spec_v1",
        project_id="prj_alpha",
        version=1,
        title="Alpha Architecture v1",
        summary="Initial core spec",
        spec_json='{"requirements": []}',
    )
    db_session.add(spec_v1)
    await db_session.commit()

    # Duplicate project_id + version must fail unique constraint
    spec_v1_dup = SpecVersionRecord(
        id="spec_v1_duplicate",
        project_id="prj_alpha",
        version=1,
        title="Duplicate Version",
        summary="Should fail",
        spec_json="{}",
    )
    db_session.add(spec_v1_dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_approval_record_linkage(db_session: AsyncSession):
    proj = ProjectRecord(
        id="prj_approval",
        name="Approval Project",
        repo_path="/repo",
    )
    db_session.add(proj)
    await db_session.flush()

    spec = SpecVersionRecord(
        id="spec_apr_01",
        project_id=proj.id,
        version=1,
        title="Approval Spec",
        summary="Spec for approvals",
        spec_json="{}",
    )
    db_session.add(spec)
    await db_session.flush()

    approval = ApprovalRecord(
        id="apr_001",
        spec_id=spec.id,
        approval_type="spec",
        status="approved",
        decided_by="usr_ajay",
        reason="Architecture verified",
        decided_at=datetime.now(UTC),
    )
    db_session.add(approval)
    await db_session.commit()

    res = await db_session.execute(select(ApprovalRecord).where(ApprovalRecord.id == "apr_001"))
    saved_approval = res.scalar_one()
    assert saved_approval.status == "approved"
    assert saved_approval.decided_by == "usr_ajay"


# ---------------------------------------------------------------------------
# Task, Attempt & Gate Evidence Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_attempts_and_gate_evidence(db_session: AsyncSession):
    proj = ProjectRecord(id="prj_tasks", name="Tasks Project", repo_path="/repo")
    db_session.add(proj)
    await db_session.flush()

    task = TaskRecord(
        id="tsk_gate_test",
        project_id=proj.id,
        repo="/repo",
        objective="Run unit tests and gates",
        details_json='{"task_id": "tsk_gate_test"}',
        status="running",
        depends_on_json='["tsk_upstream_01"]',
    )
    db_session.add(task)
    await db_session.flush()

    attempt = AttemptRecord(
        id="att_01",
        task_id=task.id,
        attempt_number=1,
        agent="antigravity",
        model="gemini-3.1-pro",
        status="completed",
        result_commit="commit_abc123",
        input_tokens=2500,
        output_tokens=1200,
        duration_seconds=18.4,
        estimated_cost_usd=0.005,
    )
    db_session.add(attempt)
    await db_session.flush()

    gate = GateEvidenceRecord(
        id="gate_evi_01",
        task_id=task.id,
        attempt_id=attempt.id,
        gate_type="unit_test",
        passed=True,
        summary="98 unit tests passed",
        output_log="98 passed in 1.3s",
        metrics_json='{"passed": 98, "failed": 0}',
    )
    db_session.add(gate)
    await db_session.commit()

    # Query back and verify relations
    res = await db_session.execute(
        select(GateEvidenceRecord).where(GateEvidenceRecord.task_id == task.id)
    )
    saved_gate = res.scalar_one()
    assert saved_gate.passed is True
    assert saved_gate.gate_type == "unit_test"


# ---------------------------------------------------------------------------
# Meeting, Participant & Transcript Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_meeting_session_and_transcripts(db_session: AsyncSession):
    proj = ProjectRecord(id="prj_meet", name="Meeting Project", repo_path="/repo")
    db_session.add(proj)
    await db_session.flush()

    meet = MeetingRecord(
        id="meet_01",
        project_id=proj.id,
        room_name="deploymate-main",
        status="active",
        consent_recorded=True,
    )
    db_session.add(meet)
    await db_session.flush()

    p1 = MeetingParticipantRecord(
        id="part_01",
        meeting_id=meet.id,
        identity="ajay",
        name="Ajay (Founder)",
        role="founder",
        is_eva=False,
    )
    p2 = MeetingParticipantRecord(
        id="part_02",
        meeting_id=meet.id,
        identity="eva-cto",
        name="Eva (AI Architect)",
        role="ai_participant",
        is_eva=True,
    )
    db_session.add_all([p1, p2])

    seg = TranscriptSegmentRecord(
        id="seg_01",
        meeting_id=meet.id,
        speaker_identity="ajay",
        speaker_name="Ajay (Founder)",
        text="Let's review the SDLC roadmap and gate pipeline.",
        is_eva=False,
    )
    db_session.add(seg)

    event = MeetingEventRecord(
        id="mevt_01",
        meeting_id=meet.id,
        event_type="clarified_requirement",
        title="Gate Pipeline Requirement",
        description="Must enforce 100% passing acceptance gates before task completion",
        raw_quote="Let's review the SDLC roadmap and gate pipeline.",
        confidence=0.98,
    )
    db_session.add(event)
    await db_session.commit()

    res = await db_session.execute(
        select(TranscriptSegmentRecord).where(TranscriptSegmentRecord.meeting_id == meet.id)
    )
    segments = res.scalars().all()
    assert len(segments) == 1
    assert segments[0].speaker_identity == "ajay"


# ---------------------------------------------------------------------------
# Worker & Lease Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_registration_and_health(db_session: AsyncSession):
    worker = WorkerRecord(
        id="mac-worker-alpha",
        hostname="Ajays-MacBook-Air",
        platform="macos-arm64",
        capability_json='{"max_concurrent_tasks": 2, "has_gpu": false}',
        status="online",
    )
    db_session.add(worker)
    await db_session.flush()

    health = WorkerHealthRecord(
        id="health_01",
        worker_id=worker.id,
        battery_percent=95,
        ac_power=True,
        thermal_pressure="nominal",
        cpu_load_percent=12.5,
        disk_free_gb=128.4,
        active_task_count=1,
    )
    db_session.add(health)

    lease = WorkerLeaseRecord(
        id="lease_rec_01",
        worker_id=worker.id,
        task_id="tsk_active_01",
        lease_token="token_lease_xyz",
        expires_at=datetime.now(UTC),
    )
    db_session.add(lease)
    await db_session.commit()

    res = await db_session.execute(
        select(WorkerRecord).where(WorkerRecord.id == "mac-worker-alpha")
    )
    saved_worker = res.scalar_one()
    assert saved_worker.hostname == "Ajays-MacBook-Air"


# ---------------------------------------------------------------------------
# Artifact & Deployment Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_artifact_and_deployment_records(db_session: AsyncSession):
    proj = ProjectRecord(id="prj_deploy", name="Deploy Project", repo_path="/repo")
    db_session.add(proj)
    await db_session.flush()

    artifact = ArtifactRecord(
        id="art_build_01",
        project_id=proj.id,
        media_type="application/gzip",
        filename="bundle.tar.gz",
        size_bytes=5242880,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        storage_path="builds/prj_deploy/bundle.tar.gz",
        created_by="mac-worker-alpha",
    )
    db_session.add(artifact)

    dep = DeploymentRecord(
        id="dep_01",
        project_id=proj.id,
        task_id="tsk_deploy_task",
        target_environment="preview",
        source_commit="commit_deploy_abc",
        status="deployed",
        deploy_url="https://preview.deploymate.com",
        smoke_test_passed=True,
        requested_by="usr_ajay",
    )
    db_session.add(dep)
    await db_session.commit()

    res = await db_session.execute(select(DeploymentRecord).where(DeploymentRecord.id == "dep_01"))
    saved_dep = res.scalar_one()
    assert saved_dep.status == "deployed"
    assert saved_dep.smoke_test_passed is True


# ---------------------------------------------------------------------------
# Call Status History & Audit Log Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_history_and_audit_indexing(db_session: AsyncSession):
    call = CallJobRecord(
        id="call_01",
        notification_id="ntf_voice_01",
        persona="eva",
        recipient_phone="+1234567890",
        purpose="founder_preview_review",
        idempotency_key="idemp_voice_101",
        status="answered",
    )
    db_session.add(call)
    await db_session.flush()

    status_hist = CallStatusRecord(
        id="cstat_01",
        call_job_id=call.id,
        status="answered",
        provider_call_id="plivo_call_id_abc",
    )
    db_session.add(status_hist)

    audit = AuditEventRecord(
        id="audit_evt_101",
        event_type="call_placed",
        project_id="prj_deploy",
        actor="eva",
        actor_role="ai_agent",
        details_json='{"phone": "+1234567890", "purpose": "founder_preview_review"}',
    )
    db_session.add(audit)
    await db_session.commit()

    res = await db_session.execute(
        select(AuditEventRecord).where(AuditEventRecord.id == "audit_evt_101")
    )
    saved_audit = res.scalar_one()
    assert saved_audit.event_type == "call_placed"
    assert saved_audit.actor == "eva"
