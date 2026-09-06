"""
testscript/test_control_plane_p4.py
Comprehensive deterministic test suite for Alpha Brain P4:
- URL/body task-ID mismatch rejection (HTTP 400)
- ActionBroker typed deny-by-default & human approval enforcement
- NotificationPolicy AgentLine voice call vs portal routing
- Progress heartbeat watchdog & safe stall handling
- Checkpointed idempotent task resume
- Blocked, cancelled, and superseded task transitions
- Required gate evidence enforcement & independent reviewer policy
- Reporting snapshots for founder and client views
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alpha_core.api.app import app
from alpha_core.config import settings
from alpha_core.db.models import (
    Base,
    ProjectRecord,
    TaskRecord,
)
from alpha_core.policy.action_broker import (
    ActionBroker,
    ActionRequest,
    ActionType,
)
from alpha_core.policy.notification_policy import (
    NotificationChannel,
    NotificationEvent,
    NotificationPolicyEvaluator,
    NotificationTriggerType,
)
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import (
    AcceptancePlan,
    AgentType,
    GateCommand,
    GateEvidence,
    GateResult,
    GateType,
    RiskClass,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
)


@pytest.fixture
async def async_db():
    """Provides an isolated in-memory SQLite database session for each test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


# ===========================================================================
# 1. URL / Body Task ID Mismatch Rejection
# ===========================================================================


class TestTaskIDMismatch:
    async def test_rejects_url_body_task_id_mismatch(self, worker_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            payload = {
                "lease_token": "lease_123",
                "result": {
                    "task_id": "tsk_mismatched_id",
                    "attempt_id": "att_01",
                    "status": "completed",
                    "agent": "antigravity",
                    "model": "gemini-pro",
                    "base_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                },
            }
            # Send to URL /api/tasks/tsk_original_id/result but body has tsk_mismatched_id
            response = await client.post(
                "/api/tasks/tsk_original_id/result",
                json=payload,
                headers=worker_headers,
            )
            assert response.status_code == 400
            assert "Task ID mismatch" in response.json()["detail"]


# ===========================================================================
# 2. Action Broker Deny-By-Default & Human Approval Enforcement
# ===========================================================================


class TestActionBroker:
    def test_safe_actions_permitted_without_human_approval(self):
        broker = ActionBroker()
        req = ActionRequest(
            action_type=ActionType.SHELL_EXEC,
            target="pytest -v",
            command_or_params={"command": "pytest -v"},
            actor="worker-01",
            risk_class=RiskClass.LOW,
        )
        decision = broker.evaluate_action(req)
        assert decision.allowed is True
        assert decision.requires_human_approval is False

    def test_destructive_shell_command_requires_human_approval(self):
        broker = ActionBroker()
        req = ActionRequest(
            action_type=ActionType.SHELL_EXEC,
            target="rm -rf /tmp/data",
            command_or_params={"command": "rm -rf /tmp/data"},
            actor="worker-01",
        )
        decision = broker.evaluate_action(req)
        assert decision.allowed is False
        assert decision.requires_human_approval is True
        assert decision.action_type == ActionType.DESTRUCTIVE_COMMAND

    def test_production_deployment_requires_human_approval(self):
        broker = ActionBroker()
        req = ActionRequest(
            action_type=ActionType.PRODUCTION_DEPLOYMENT,
            target="https://api.alphabrain.ai",
            actor="deploy-agent",
        )
        # Without approval -> Denied
        decision1 = broker.evaluate_action(req)
        assert decision1.allowed is False
        assert decision1.requires_human_approval is True

        # With human approval -> Allowed
        decision2 = broker.evaluate_action(
            req, human_approval_granted=True, approver="founder-ajay"
        )
        assert decision2.allowed is True
        assert decision2.approver == "founder-ajay"

    def test_database_migration_requires_human_approval(self):
        broker = ActionBroker()
        req = ActionRequest(
            action_type=ActionType.DATABASE_MIGRATION,
            target="alembic upgrade head",
            actor="worker-01",
        )
        decision = broker.evaluate_action(req)
        assert decision.allowed is False
        assert decision.requires_human_approval is True


# ===========================================================================
# 3. Notification Policy: AgentLine Calls vs Portal Routing
# ===========================================================================


class TestNotificationPolicy:
    def test_routine_events_route_to_portal_only(self):
        evaluator = NotificationPolicyEvaluator()
        event = NotificationEvent(
            trigger_type=NotificationTriggerType.ROUTINE_TASK_COMPLETED,
            project_id="prj_01",
            title="Task 101 completed successfully",
        )
        decision = evaluator.evaluate(event)
        assert decision.channel == NotificationChannel.PORTAL
        assert decision.should_call_agentline is False
        assert decision.is_urgent is False

    def test_urgent_triggers_route_to_agentline_call(self):
        evaluator = NotificationPolicyEvaluator()

        # 1. Urgent approval needed
        ev1 = NotificationEvent(
            trigger_type=NotificationTriggerType.URGENT_APPROVAL_NEEDED,
            project_id="prj_01",
            title="Critical production migration approval requested",
            risk_class=RiskClass.HIGH,
        )
        d1 = evaluator.evaluate(ev1)
        assert d1.channel == NotificationChannel.AGENTLINE_CALL
        assert d1.should_call_agentline is True
        assert d1.is_urgent is True

        # 2. Repeated repair failure
        ev2 = NotificationEvent(
            trigger_type=NotificationTriggerType.REPEATED_REPAIR_FAILURE,
            project_id="prj_01",
            title="Task 202 blocked after 3 failed repair attempts",
        )
        d2 = evaluator.evaluate(ev2)
        assert d2.channel == NotificationChannel.AGENTLINE_CALL
        assert d2.should_call_agentline is True


# ===========================================================================
# 4. Progress Heartbeat Watchdog & Stalled Tasks
# ===========================================================================


class TestProgressHeartbeatWatchdog:
    async def test_watchdog_detects_stalled_task_and_retries(self, async_db: AsyncSession):
        proj = ProjectRecord(id="prj_wd", name="Watchdog Proj", repo_path="/repo/wd")
        stalled_time = datetime.now(UTC) - timedelta(seconds=400)
        envelope = TaskEnvelope(
            task_id="tsk_stalled_01",
            project_id="prj_wd",
            repo="/repo/wd",
            objective="Stalled Task",
            allowed_paths=["."],
            base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        task = TaskRecord(
            id="tsk_stalled_01",
            project_id="prj_wd",
            repo="/repo/wd",
            objective="Stalled Task",
            details_json=envelope.model_dump(mode="json"),
            status=TaskStatus.RUNNING.value,
            lease_token="lease_old",
            worker_id="worker-01",
            leased_at=stalled_time,
            updated_at=stalled_time,
            attempt_count=1,
            max_attempts=3,
        )
        async_db.add_all([proj, task])
        await async_db.commit()

        # Run watchdog with 300s timeout
        stalled_ids = await TaskEngine.check_watchdog_stalls(async_db, stall_timeout_seconds=300)
        assert "tsk_stalled_01" in stalled_ids

        # Verify task is now RETRYABLE_FAILED with lease cleared and backoff scheduled
        res = await async_db.execute(select(TaskRecord).where(TaskRecord.id == "tsk_stalled_01"))
        updated_task = res.scalar_one()
        assert updated_task.status == TaskStatus.RETRYABLE_FAILED.value
        assert updated_task.lease_token is None
        assert updated_task.next_eligible_at is not None

    async def test_watchdog_escalates_to_blocked_at_max_attempts(self, async_db: AsyncSession):
        proj = ProjectRecord(id="prj_wd2", name="Watchdog Proj 2", repo_path="/repo/wd2")
        stalled_time = datetime.now(UTC) - timedelta(seconds=400)
        envelope = TaskEnvelope(
            task_id="tsk_stalled_02",
            project_id="prj_wd2",
            repo="/repo/wd2",
            objective="Stalled Task Max",
            allowed_paths=["."],
            base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        task = TaskRecord(
            id="tsk_stalled_02",
            project_id="prj_wd2",
            repo="/repo/wd2",
            objective="Stalled Task Max",
            details_json=envelope.model_dump(mode="json"),
            status=TaskStatus.RUNNING.value,
            lease_token="lease_old2",
            worker_id="worker-01",
            leased_at=stalled_time,
            updated_at=stalled_time,
            attempt_count=3,
            max_attempts=3,
        )
        async_db.add_all([proj, task])
        await async_db.commit()

        stalled_ids = await TaskEngine.check_watchdog_stalls(async_db, stall_timeout_seconds=300)
        assert "tsk_stalled_02" in stalled_ids

        res = await async_db.execute(select(TaskRecord).where(TaskRecord.id == "tsk_stalled_02"))
        updated_task = res.scalar_one()
        assert updated_task.status == TaskStatus.BLOCKED.value


# ===========================================================================
# 5. Checkpointed Idempotent Task Resume
# ===========================================================================


class TestCheckpointedTaskResume:
    async def test_resumes_valid_checkpointed_task(self, async_db: AsyncSession):
        proj = ProjectRecord(id="prj_res", name="Resume Proj", repo_path="/repo/res")
        task = TaskRecord(
            id="tsk_res_01",
            project_id="prj_res",
            repo="/repo/res",
            objective="Resume Task",
            details_json={},
            status=TaskStatus.LEASED.value,
            lease_token="lease_res_token",
        )
        async_db.add_all([proj, task])
        await async_db.commit()

        checkpoint = {
            "task_id": "tsk_res_01",
            "project_id": "prj_res",
            "lease_token": "lease_res_token",
            "worker_id": "worker-01",
            "step_index": 4,
        }
        res = await TaskEngine.resume_checkpointed_task(async_db, "tsk_res_01", checkpoint)
        assert res is True

        res_t = await async_db.execute(select(TaskRecord).where(TaskRecord.id == "tsk_res_01"))
        assert res_t.scalar_one().status == TaskStatus.RUNNING.value

    async def test_rejects_checkpoint_with_mismatched_lease(self, async_db: AsyncSession):
        proj = ProjectRecord(id="prj_res2", name="Resume Proj 2", repo_path="/repo/res2")
        task = TaskRecord(
            id="tsk_res_02",
            project_id="prj_res2",
            repo="/repo/res2",
            objective="Resume Task 2",
            details_json={},
            status=TaskStatus.LEASED.value,
            lease_token="lease_correct_token",
        )
        async_db.add_all([proj, task])
        await async_db.commit()

        checkpoint = {
            "task_id": "tsk_res_02",
            "project_id": "prj_res2",
            "lease_token": "lease_WRONG_token",
        }
        res = await TaskEngine.resume_checkpointed_task(async_db, "tsk_res_02", checkpoint)
        assert res is False


# ===========================================================================
# 6. Task State Transitions: Cancelled, Blocked, Superseded
# ===========================================================================


class TestTaskStateTransitions:
    async def test_task_cancellation_and_blocking(self, async_db: AsyncSession):
        proj = ProjectRecord(id="prj_st", name="State Proj", repo_path="/repo/st")
        task1 = TaskRecord(
            id="tsk_c1",
            project_id="prj_st",
            repo="/repo/st",
            objective="T1",
            details_json={},
            status=TaskStatus.QUEUED.value,
        )
        task2 = TaskRecord(
            id="tsk_b1",
            project_id="prj_st",
            repo="/repo/st",
            objective="T2",
            details_json={},
            status=TaskStatus.LEASED.value,
        )
        async_db.add_all([proj, task1, task2])
        await async_db.commit()

        # Cancel task 1
        assert await TaskEngine.cancel_task(async_db, "tsk_c1", reason="No longer needed") is True
        res1 = await async_db.execute(select(TaskRecord).where(TaskRecord.id == "tsk_c1"))
        assert res1.scalar_one().status == TaskStatus.CANCELLED.value

        # Block task 2
        assert (
            await TaskEngine.block_task(async_db, "tsk_b1", reason="Upstream dependency failure")
            is True
        )
        res2 = await async_db.execute(select(TaskRecord).where(TaskRecord.id == "tsk_b1"))
        assert res2.scalar_one().status == TaskStatus.BLOCKED.value

    async def test_task_superseding(self, async_db: AsyncSession):
        proj = ProjectRecord(id="prj_st2", name="State Proj 2", repo_path="/repo/st2")
        task = TaskRecord(
            id="tsk_v1",
            project_id="prj_st2",
            repo="/repo/st2",
            objective="T1",
            details_json={},
            status=TaskStatus.VERIFIED.value,
        )
        async_db.add_all([proj, task])
        await async_db.commit()

        assert await TaskEngine.supersede_task(async_db, "tsk_v1", new_task_id="tsk_v2") is True
        res = await async_db.execute(select(TaskRecord).where(TaskRecord.id == "tsk_v1"))
        assert res.scalar_one().status == TaskStatus.SUPERSEDED.value


# ===========================================================================
# 7. Required Gate Evidence & Independent Reviewer Policy
# ===========================================================================


class TestGateEvidenceAndIndependentReview:
    async def test_missing_required_gate_evidence_fails_verification(self, async_db: AsyncSession):
        envelope = TaskEnvelope(
            task_id="tsk_gate_01",
            project_id="prj_gate",
            repo="/repo/gate",
            objective="Gate Task",
            allowed_paths=["."],
            acceptance_plan=AcceptancePlan(
                required_gates=[GateType.LINT, GateType.UNIT_TEST],
                commands=[
                    GateCommand(gate_type=GateType.LINT, executable="ruff"),
                    GateCommand(gate_type=GateType.UNIT_TEST, executable="pytest"),
                ],
            ),
            base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        await TaskEngine.submit_task(async_db, envelope, "prj_gate")
        lease_res = await TaskEngine.lease_next_task(async_db, "worker-01")
        assert lease_res is not None
        leased_task, _leased_env = lease_res
        lease_token = leased_task.lease_token
        assert lease_token is not None

        # Result only has LINT evidence, missing UNIT_TEST
        incomplete_result = TaskResult(
            task_id="tsk_gate_01",
            attempt_id="att_gate_01",
            agent=AgentType.ANTIGRAVITY,
            model="gemini-pro",
            base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            status=TaskStatus.COMPLETED,
            gate_result=GateResult(
                task_id="tsk_gate_01",
                attempt_id="att_gate_01",
                all_passed=True,
                evidence_items=[
                    GateEvidence(
                        evidence_id="ev_lint",
                        gate_type=GateType.LINT,
                        passed=True,
                        summary="Lint passed",
                    )
                ],
            ),
        )

        res = await TaskEngine.submit_result(async_db, incomplete_result, lease_token, "worker-01")
        assert res is False

        # Task should be rejected and remain leased (or unchanged) rather than automatically failing
        res_t = await async_db.execute(select(TaskRecord).where(TaskRecord.id == "tsk_gate_01"))
        assert res_t.scalar_one().status == TaskStatus.LEASED.value

    @pytest.mark.xfail(reason="R2-R6 gap pending")
    async def test_high_risk_task_requires_different_independent_reviewer(
        self, async_db: AsyncSession
    ):
        envelope = TaskEnvelope(
            task_id="tsk_hr_01",
            project_id="prj_hr",
            repo="/repo/hr",
            objective="High Risk Task",
            allowed_paths=["."],
            risk_class=RiskClass.HIGH,
            requires_approval=True,
            base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        await TaskEngine.submit_task(async_db, envelope, "prj_hr")

        # Approve task so it can be leased
        await TaskEngine.decide_approval(
            async_db, "tsk_hr_01", approved=True, decided_by="founder-01"
        )
        lease_res = await TaskEngine.lease_next_task(async_db, "worker-01")
        assert lease_res is not None
        leased_task, _leased_env = lease_res
        lease_token = leased_task.lease_token
        assert lease_token is not None

        # 1. Result with self-review (reviewer == worker-01) -> moves to WAITING_APPROVAL
        self_reviewed_result = TaskResult(
            task_id="tsk_hr_01",
            attempt_id="att_hr_01",
            agent=AgentType.ANTIGRAVITY,
            model="gemini-pro",
            base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            result_commit="HEAD",
            status=TaskStatus.COMPLETED,
            gate_result=GateResult(
                task_id="tsk_hr_01",
                attempt_id="att_hr_01",
                all_passed=True,
                evidence_items=[
                    GateEvidence(
                        evidence_id="ev_lint_hr",
                        gate_type=GateType.LINT,
                        passed=True,
                        summary="Lint passed",
                    ),
                    GateEvidence(
                        evidence_id="ev_unit_hr",
                        gate_type=GateType.UNIT_TEST,
                        passed=True,
                        summary="Unit tests passed",
                    ),
                    GateEvidence(
                        evidence_id="ev_rev1",
                        gate_type=GateType.INDEPENDENT_REVIEW,
                        passed=True,
                        summary="Self review",
                        metrics={"reviewer": "worker-01"},
                    ),
                ],
            ),
        )
        res1 = await TaskEngine.submit_result(
            async_db, self_reviewed_result, lease_token, "worker-01"
        )
        assert res1 is True
        res_t1 = await async_db.execute(select(TaskRecord).where(TaskRecord.id == "tsk_hr_01"))
        assert res_t1.scalar_one().status == TaskStatus.WAITING_APPROVAL.value

        # 2. Result with claimed different reviewer (reviewer == worker-02) -> also moves to WAITING_APPROVAL
        envelope2 = TaskEnvelope(
            task_id="tsk_hr_02",
            project_id="prj_hr",
            repo="/repo/hr",
            objective="High Risk Task 2",
            allowed_paths=["."],
            risk_class=RiskClass.HIGH,
            requires_approval=True,
            base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        await TaskEngine.submit_task(async_db, envelope2, "prj_hr")
        await TaskEngine.decide_approval(
            async_db, "tsk_hr_02", approved=True, decided_by="founder-01"
        )
        lease_res2 = await TaskEngine.lease_next_task(async_db, "worker-02")
        assert lease_res2 is not None
        leased_task2, _ = lease_res2
        assert leased_task2.lease_token is not None

        diff_reviewed_result = TaskResult(
            task_id="tsk_hr_02",
            attempt_id="att_hr_02",
            agent=AgentType.ANTIGRAVITY,
            model="gemini-pro",
            base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            result_commit="HEAD",
            status=TaskStatus.COMPLETED,
            gate_result=GateResult(
                task_id="tsk_hr_02",
                attempt_id="att_hr_02",
                all_passed=True,
                evidence_items=[
                    GateEvidence(
                        evidence_id="ev_lint_hr2",
                        gate_type=GateType.LINT,
                        passed=True,
                        summary="Lint passed",
                    ),
                    GateEvidence(
                        evidence_id="ev_unit_hr2",
                        gate_type=GateType.UNIT_TEST,
                        passed=True,
                        summary="Unit tests passed",
                    ),
                    GateEvidence(
                        evidence_id="ev_rev2",
                        gate_type=GateType.INDEPENDENT_REVIEW,
                        passed=True,
                        summary="Claimed independent review",
                        metrics={"reviewer": "external-auditor-99"},
                    ),
                ],
            ),
        )
        res2 = await TaskEngine.submit_result(
            async_db, diff_reviewed_result, leased_task2.lease_token, "worker-02"
        )
        assert res2 is True
        res_t2 = await async_db.execute(select(TaskRecord).where(TaskRecord.id == "tsk_hr_02"))
        assert res_t2.scalar_one().status == TaskStatus.WAITING_APPROVAL.value


# ===========================================================================
# 8. Reporting Snapshots for Founder and Client
# ===========================================================================


class TestReportingSnapshots:
    async def test_founder_and_client_reporting_snapshots(self, async_db: AsyncSession):
        proj = ProjectRecord(id="prj_rep", name="Report Proj", repo_path="/repo/rep")
        task = TaskRecord(
            id="tsk_rep_01",
            project_id="prj_rep",
            repo="/repo/rep",
            objective="R1",
            details_json={},
            status=TaskStatus.VERIFIED.value,
        )
        async_db.add_all([proj, task])
        await async_db.commit()

        # Founder snapshot includes internal event actors
        founder_snap = await TaskEngine.generate_reporting_snapshot(
            async_db, "prj_rep", viewer_role="founder"
        )
        assert founder_snap is not None
        assert founder_snap["completed_tasks"] == 1
        assert "metrics" in founder_snap

        # Client snapshot scrubs internal actors
        client_snap = await TaskEngine.generate_reporting_snapshot(
            async_db, "prj_rep", viewer_role="client"
        )
        assert client_snap is not None
        assert client_snap["project_name"] == "Report Proj"

    async def test_changed_files_outside_allowed_paths_fails_verification(
        self, async_db: AsyncSession
    ):
        envelope = TaskEnvelope(
            task_id="tsk_path_01",
            project_id="prj_path",
            repo="/repo/path",
            objective="Path Escape Task",
            allowed_paths=["docs/", "src/allowed.py"],
            acceptance_plan=AcceptancePlan(
                required_gates=[GateType.UNIT_TEST],
                commands=[GateCommand(gate_type=GateType.UNIT_TEST, executable="pytest")],
            ),
            base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        )
        await TaskEngine.submit_task(async_db, envelope, "prj_path")
        lease_res = await TaskEngine.lease_next_task(async_db, "worker-01")
        assert lease_res is not None
        leased_task, _leased_env = lease_res

        result = TaskResult(
            task_id="tsk_path_01",
            attempt_id="att_path_01",
            agent=AgentType.ANTIGRAVITY,
            model="gemini-pro",
            base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            result_commit="newcommit",
            status=TaskStatus.COMPLETED,
            files_changed=["docs/readme.md", "src/not_allowed.py"],
            gate_result=GateResult(
                task_id="tsk_path_01",
                attempt_id="att_path_01",
                all_passed=True,
                evidence_items=[
                    GateEvidence(
                        evidence_id="ev_unit",
                        gate_type=GateType.UNIT_TEST,
                        passed=True,
                        summary="Pass",
                    )
                ],
            ),
        )

        res = await TaskEngine.submit_result(async_db, result, leased_task.lease_token, "worker-01")
        assert res is False

        res_t = await async_db.execute(select(TaskRecord).where(TaskRecord.id == "tsk_path_01"))
        assert res_t.scalar_one().status == TaskStatus.LEASED.value


@pytest.mark.asyncio
async def test_lease_endpoint_zero_watchdog_calls(async_db, monkeypatch, worker_headers):
    # Mock TaskEngine.check_watchdog_stalls and TaskEngine.lease_next_task
    mock_watchdog = AsyncMock()
    mock_lease = AsyncMock(return_value=None)
    monkeypatch.setattr(TaskEngine, "check_watchdog_stalls", mock_watchdog)
    monkeypatch.setattr(TaskEngine, "lease_next_task", mock_lease)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Submit 50 concurrent requests
        tasks = [
            client.post(
                "/api/tasks/lease", headers=worker_headers, json={"worker_id": "alpha_worker"}
            )
            for _ in range(50)
        ]
        await asyncio.gather(*tasks)

    # Watchdog should not be called at all from the lease endpoint
    assert mock_watchdog.call_count == 0
    # Lease should be called 50 times
    assert mock_lease.call_count == 50
    # Check lease was called with proper duration
    assert (
        mock_lease.call_args[1]["lease_duration_seconds"] == settings.WORKER_LEASE_DURATION_SECONDS
    )


@pytest.mark.asyncio
async def test_lease_endpoint_zero_recovery_calls(async_db, monkeypatch, worker_headers):
    # Monkeypatch to ensure they are never called
    mock_stalls = AsyncMock(side_effect=Exception("check_watchdog_stalls called!"))
    mock_retries = AsyncMock(side_effect=Exception("release_due_retries called!"))
    mock_expired = AsyncMock(side_effect=Exception("timeout_expired_leases called!"))

    monkeypatch.setattr(TaskEngine, "check_watchdog_stalls", mock_stalls)
    monkeypatch.setattr(TaskEngine, "release_due_retries", mock_retries)
    monkeypatch.setattr(TaskEngine, "timeout_expired_leases", mock_expired)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Submit 50 concurrent requests
        tasks = [
            client.post(
                "/api/tasks/lease", headers=worker_headers, json={"worker_id": "alpha_worker"}
            )
            for _ in range(50)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                raise r


@pytest.mark.asyncio
async def test_application_lifespan_scheduler(monkeypatch):
    import sys

    app_module = sys.modules["alpha_core.api.app"]
    from fastapi import FastAPI

    scheduler_started = asyncio.Event()
    scheduler_cancelled = asyncio.Event()
    scheduler_finalized = asyncio.Event()
    original_call_count = 0

    async def tracking_scheduler():
        nonlocal original_call_count
        original_call_count += 1
        scheduler_started.set()
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            scheduler_cancelled.set()
            raise
        finally:
            scheduler_finalized.set()

    monkeypatch.setattr(app_module, "watchdog_scheduler", tracking_scheduler)

    test_app = FastAPI(lifespan=app_module.lifespan)
    async with test_app.router.lifespan_context(test_app):
        # Wait for scheduler to actually start
        await asyncio.wait_for(scheduler_started.wait(), timeout=1.0)
        assert not scheduler_cancelled.is_set()
        assert not scheduler_finalized.is_set()

    # Scheduler was called exactly once
    assert original_call_count == 1
    # After lifespan exits, the task should have been cancelled and awaited
    assert scheduler_cancelled.is_set()
    assert scheduler_finalized.is_set()


@pytest.mark.asyncio
async def test_scheduler_transient_failure_does_not_terminate(monkeypatch):
    import sys
    from contextlib import asynccontextmanager

    app_module = sys.modules["alpha_core.api.app"]

    @asynccontextmanager
    async def mock_session_factory():
        yield AsyncMock()

    mock_check = AsyncMock(side_effect=[Exception("Transient DB error"), None, Exception("stop")])
    monkeypatch.setattr(TaskEngine, "check_watchdog_stalls", mock_check)
    monkeypatch.setattr(TaskEngine, "release_due_retries", AsyncMock())
    monkeypatch.setattr(TaskEngine, "timeout_expired_leases", AsyncMock())
    monkeypatch.setattr(app_module, "get_session_factory", lambda: mock_session_factory)
    monkeypatch.setattr(settings, "TASK_WATCHDOG_SCAN_INTERVAL_SECONDS", 0.01)

    # Run the scheduler task for a short time
    task = asyncio.create_task(app_module.watchdog_scheduler())
    await asyncio.sleep(0.05)
    task.cancel()

    import contextlib

    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert mock_check.call_count >= 2


@pytest.mark.asyncio
async def test_watchdog_row_locks_postgres(async_db, monkeypatch):
    """Prove PostgreSQL check_watchdog_stalls uses skip_locked."""
    monkeypatch.setattr(async_db.bind.dialect, "name", "postgresql")

    with patch("sqlalchemy.sql.selectable.Select.with_for_update") as mock_update:
        # Mock to return query
        mock_update.return_value = select(TaskRecord)
        await TaskEngine.check_watchdog_stalls(async_db)
        # It's hard to test the internal builder perfectly here without deep mocking,
        # but the assert provides unit level protection.
        mock_update.assert_called_with(skip_locked=True)


@pytest.mark.asyncio
async def test_timeout_expired_leases_row_locks_postgres(async_db, monkeypatch):
    """Prove PostgreSQL timeout_expired_leases uses skip_locked."""
    monkeypatch.setattr(async_db.bind.dialect, "name", "postgresql")

    with patch("sqlalchemy.sql.selectable.Select.with_for_update") as mock_update:
        mock_update.return_value = select(TaskRecord)
        await TaskEngine.timeout_expired_leases(async_db)
        mock_update.assert_called_with(skip_locked=True)


@pytest.mark.asyncio
async def test_release_due_retries_row_locks_postgres(async_db, monkeypatch):
    """Prove PostgreSQL release_due_retries uses skip_locked."""
    monkeypatch.setattr(async_db.bind.dialect, "name", "postgresql")

    with patch("sqlalchemy.sql.selectable.Select.with_for_update") as mock_update:
        mock_update.return_value = select(TaskRecord)
        await TaskEngine.release_due_retries(async_db)
        mock_update.assert_called_with(skip_locked=True)
