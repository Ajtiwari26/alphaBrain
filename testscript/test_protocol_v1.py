"""
testscript/test_protocol_v1.py
Tests for the expanded Alpha Protocol v1 schemas:
state transitions, DAG dependencies, retry policies, approvals,
artifacts, deployments, meeting events, and worker contracts.
"""

import pytest
from pydantic import ValidationError

from alpha_protocol import (
    PROTOCOL_VERSION,
    AgentReadiness,
    AgentType,
    ApprovalRequest,
    ApprovalResult,
    ApprovalStatus,
    ArtifactMetadata,
    ConcurrencyPolicy,
    DeploymentRequest,
    DeploymentResult,
    DeploymentStatus,
    MeetingEvent,
    MeetingEventType,
    MeetingSession,
    RetryPolicy,
    RiskClass,
    RollbackRequest,
    TaskDependency,
    TaskEnvelope,
    TaskStatus,
    TranscriptSegment,
    UsageRecord,
    WorkerCapability,
    WorkerHealthReport,
    WorkerRegistration,
    WorkflowPhase,
    is_legal_transition,
)

# ---------------------------------------------------------------------------
# Protocol Version
# ---------------------------------------------------------------------------

def test_protocol_version_is_1():
    assert PROTOCOL_VERSION == "1"


def test_task_envelope_carries_version():
    task = TaskEnvelope(
        task_id="tsk_v1_check",
        project_id="prj_alpha",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Version check",
        allowed_paths=["."],
    )
    assert task.protocol_version == "1"


# ---------------------------------------------------------------------------
# State Transition Table
# ---------------------------------------------------------------------------

class TestStateTransitions:
    def test_queued_can_become_leased(self):
        assert is_legal_transition(TaskStatus.QUEUED, TaskStatus.LEASED) is True

    def test_queued_cannot_become_completed(self):
        assert is_legal_transition(TaskStatus.QUEUED, TaskStatus.COMPLETED) is False

    def test_running_can_become_verified(self):
        assert is_legal_transition(TaskStatus.RUNNING, TaskStatus.VERIFIED) is True

    def test_completed_is_terminal(self):
        assert is_legal_transition(TaskStatus.COMPLETED, TaskStatus.QUEUED) is False
        assert is_legal_transition(TaskStatus.COMPLETED, TaskStatus.RUNNING) is False

    def test_cancelled_is_terminal(self):
        assert is_legal_transition(TaskStatus.CANCELLED, TaskStatus.QUEUED) is False

    def test_verified_can_become_completed(self):
        assert is_legal_transition(TaskStatus.VERIFIED, TaskStatus.COMPLETED) is True

    def test_retryable_can_requeue(self):
        assert is_legal_transition(TaskStatus.RETRYABLE_FAILED, TaskStatus.QUEUED) is True


# ---------------------------------------------------------------------------
# DAG Dependencies
# ---------------------------------------------------------------------------

class TestDAGDependencies:
    def test_task_with_dependencies(self):
        task = TaskEnvelope(
            task_id="tsk_downstream",
            project_id="prj_alpha",
            repo="/repo",
            objective="Downstream task",
            allowed_paths=["."],
            dependencies=[
                TaskDependency(task_id="tsk_upstream_1"),
                TaskDependency(
                    task_id="tsk_upstream_2",
                    required_status=TaskStatus.VERIFIED,
                ),
            ],
        )
        assert len(task.dependencies) == 2
        assert task.dependencies[1].required_status == TaskStatus.VERIFIED

    def test_task_without_dependencies_is_valid(self):
        task = TaskEnvelope(
            task_id="tsk_standalone",
            project_id="prj_alpha",
            repo="/repo",
            objective="No deps",
            allowed_paths=["."],
        )
        assert task.dependencies == []


# ---------------------------------------------------------------------------
# Retry & Concurrency Policies
# ---------------------------------------------------------------------------

class TestRetryPolicy:
    def test_default_policy(self):
        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.backoff_base_seconds == 60
        assert policy.deadline_seconds == 86400

    def test_custom_policy(self):
        policy = RetryPolicy(max_attempts=5, backoff_base_seconds=120)
        assert policy.max_attempts == 5

    def test_invalid_attempts_rejected(self):
        with pytest.raises(ValidationError):
            RetryPolicy(max_attempts=0)
        with pytest.raises(ValidationError):
            RetryPolicy(max_attempts=11)


class TestConcurrencyPolicy:
    def test_default_limits(self):
        policy = ConcurrencyPolicy()
        assert policy.max_per_project == 5
        assert policy.max_per_worker == 2


# ---------------------------------------------------------------------------
# Approval Contracts
# ---------------------------------------------------------------------------

class TestApprovalContracts:
    def test_approval_request_creation(self):
        req = ApprovalRequest(
            approval_id="apr_001",
            task_id="tsk_deploy",
            project_id="prj_alpha",
            action_type="production_deployment",
            description="Deploy v1.2 to production",
            risk_class=RiskClass.CRITICAL,
            requested_by="system",
        )
        assert req.status == ApprovalStatus.PENDING
        assert req.required_approver_role == "founder"

    def test_approval_result(self):
        result = ApprovalResult(
            approval_id="apr_001",
            status=ApprovalStatus.APPROVED,
            decided_by="ajay",
            reason="LGTM",
        )
        assert result.status == ApprovalStatus.APPROVED


# ---------------------------------------------------------------------------
# Artifact Metadata
# ---------------------------------------------------------------------------

class TestArtifactMetadata:
    def test_valid_artifact(self):
        artifact = ArtifactMetadata(
            artifact_id="builds/v1.2/output.tar.gz",
            project_id="prj_alpha",
            media_type="application/gzip",
            filename="output.tar.gz",
            size_bytes=1024000,
            sha256_hash="a" * 64,
            storage_path="s3://bucket/builds/v1.2/output.tar.gz",
            created_by="worker-01",
        )
        assert artifact.protocol_version == "1"

    def test_rejects_path_traversal_in_artifact_id(self):
        with pytest.raises(ValidationError):
            ArtifactMetadata(
                artifact_id="../escape/bad",
                project_id="prj_alpha",
                media_type="text/plain",
                filename="bad.txt",
                size_bytes=100,
                sha256_hash="b" * 64,
                storage_path="/tmp/bad",
                created_by="system",
            )


# ---------------------------------------------------------------------------
# Deployment Contracts
# ---------------------------------------------------------------------------

class TestDeploymentContracts:
    def test_deployment_request(self):
        req = DeploymentRequest(
            deployment_id="dep_001",
            project_id="prj_alpha",
            task_id="tsk_build_01",
            attempt_id="att_01",
            target_environment="preview",
            source_commit="abc123def456",
            requested_by="system",
        )
        assert req.status == DeploymentStatus.REQUESTED
        assert req.requires_approval is True

    def test_deployment_result(self):
        result = DeploymentResult(
            deployment_id="dep_001",
            status=DeploymentStatus.DEPLOYED,
            deploy_url="https://preview.deploymate.com",
            smoke_test_passed=True,
        )
        assert result.rollback_available is True

    def test_rollback_request(self):
        rb = RollbackRequest(
            deployment_id="dep_001",
            project_id="prj_alpha",
            target_commit="def789abc",
            reason="Smoke test regression",
            requested_by="ajay",
        )
        assert rb.reason == "Smoke test regression"


# ---------------------------------------------------------------------------
# Meeting Events
# ---------------------------------------------------------------------------

class TestMeetingEvents:
    def test_transcript_segment(self):
        seg = TranscriptSegment(
            segment_id="seg_001",
            room_name="deploymate-main",
            speaker_identity="ajay",
            speaker_name="Ajay (Founder)",
            text="We need real-time voice streaming",
        )
        assert seg.is_eva is False

    def test_meeting_event_types(self):
        event = MeetingEvent(
            event_id="mevt_001",
            room_name="deploymate-main",
            project_id="prj_alpha",
            event_type=MeetingEventType.CLARIFIED_REQUIREMENT,
            title="Voice latency requirement",
            description="Must achieve sub-200ms voice latency",
            raw_quote="We need under 200ms latency for the voice",
            confidence=0.95,
        )
        assert event.is_inference is False
        assert event.confidence == 0.95

    def test_meeting_session(self):
        session = MeetingSession(
            session_id="msess_001",
            room_name="deploymate-main",
            project_id="prj_alpha",
            participants=["ajay", "maya", "eva-cto"],
        )
        assert session.consent_recorded is False
        assert len(session.participants) == 3


# ---------------------------------------------------------------------------
# Worker Contracts
# ---------------------------------------------------------------------------

class TestWorkerContracts:
    def test_worker_registration(self):
        reg = WorkerRegistration(
            worker_id="mac-worker-01",
            hostname="Ajays-MacBook-Air",
        )
        assert reg.protocol_version == "1"
        assert reg.capability.max_concurrent_tasks == 2

    def test_worker_capability(self):
        cap = WorkerCapability(
            supported_agents=[AgentType.ANTIGRAVITY, AgentType.CLAUDE_CODE],
            max_concurrent_tasks=4,
        )
        assert len(cap.supported_agents) == 2

    def test_health_report_drain_on_low_battery(self):
        report = WorkerHealthReport(
            worker_id="mac-worker-01",
            battery_percent=15,
            ac_power=False,
        )
        assert report.should_drain is True

    def test_health_report_no_drain_on_ac(self):
        report = WorkerHealthReport(
            worker_id="mac-worker-01",
            battery_percent=15,
            ac_power=True,
        )
        assert report.should_drain is False

    def test_health_report_drain_on_thermal(self):
        report = WorkerHealthReport(
            worker_id="mac-worker-01",
            thermal_pressure="critical",
        )
        assert report.should_drain is True

    def test_health_report_nominal(self):
        report = WorkerHealthReport(
            worker_id="mac-worker-01",
            battery_percent=80,
            ac_power=True,
            thermal_pressure="nominal",
        )
        assert report.should_drain is False


# ---------------------------------------------------------------------------
# Usage / Cost Records
# ---------------------------------------------------------------------------

class TestUsageRecords:
    def test_usage_tracking(self):
        usage = UsageRecord(
            input_tokens=1500,
            output_tokens=800,
            duration_seconds=12.5,
            estimated_cost_usd=0.003,
            model="gemini-3.1-pro",
            provider="google",
        )
        assert usage.input_tokens == 1500
        assert usage.estimated_cost_usd == 0.003


# ---------------------------------------------------------------------------
# Agent Readiness & Workflow Phases
# ---------------------------------------------------------------------------

def test_agent_readiness_states():
    assert AgentReadiness.READY.value == "ready"
    assert AgentReadiness.RATE_LIMITED.value == "rate_limited"


def test_workflow_phases():
    assert WorkflowPhase.INTAKE.value == "intake"
    assert WorkflowPhase.DEPLOYED.value == "deployed"
    assert WorkflowPhase.MONITORING.value == "monitoring"
