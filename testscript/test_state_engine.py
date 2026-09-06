"""
testscript/test_state_engine.py
Automated tests for database engine, task lifecycle, atomic leasing, and evidence gates.
"""

from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alpha_core.db.models import ApprovalRecord, AttemptRecord, AuditEventRecord, Base
from alpha_core.state.task_engine import TaskEngine, utc_now
from alpha_protocol import (
    AcceptancePlan,
    AgentType,
    ConcurrencyPolicy,
    GateEvidence,
    GateResult,
    GateType,
    RiskClass,
    TaskDependency,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
)


def make_default_gate_result(task_id: str, attempt_id: str) -> GateResult:
    return GateResult(
        task_id=task_id,
        attempt_id=attempt_id,
        all_passed=True,
        evidence_items=[
            GateEvidence(
                evidence_id=f"evi_lint_{task_id}",
                gate_type=GateType.LINT,
                passed=True,
                summary="Lint passed",
            ),
            GateEvidence(
                evidence_id=f"evi_unit_{task_id}",
                gate_type=GateType.UNIT_TEST,
                passed=True,
                summary="Tests passed",
            ),
        ],
    )


@pytest_asyncio.fixture
async def test_db_session():
    # Use in-memory SQLite for superfast isolated tests
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_task_submission_and_leasing(test_db_session):
    envelope = TaskEnvelope(
        task_id="tsk_state_001",
        project_id="prj_state",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Create core database models",
        allowed_paths=["."],
        risk_class=RiskClass.LOW,
        acceptance_plan=AcceptancePlan(required_gates=[GateType.UNIT_TEST]),
        preferred_agent=AgentType.ANTIGRAVITY,
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )

    # 1. Submit task
    task = await TaskEngine.submit_task(test_db_session, envelope)
    assert task.id == "tsk_state_001"
    assert task.status == TaskStatus.QUEUED.value

    # 2. Lease task
    leased_tuple = await TaskEngine.lease_next_task(test_db_session, worker_id="mac_worker_1")
    assert leased_tuple is not None
    leased_task, leased_envelope = leased_tuple
    assert leased_task.id == "tsk_state_001"
    assert leased_task.status == TaskStatus.LEASED.value
    assert leased_task.lease_token is not None
    assert leased_envelope.objective == "Create core database models"

    # 3. Trying to lease again should return None (already leased)
    empty_lease = await TaskEngine.lease_next_task(test_db_session, worker_id="mac_worker_2")
    assert empty_lease is None


@pytest.mark.asyncio
async def test_result_submission_with_gates(test_db_session):
    envelope = TaskEnvelope(
        task_id="tsk_state_002",
        project_id="prj_state",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Implement authentication middleware",
        allowed_paths=["auth.py"],
        preferred_agent=AgentType.ANTIGRAVITY,
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    await TaskEngine.submit_task(test_db_session, envelope)
    lease = await TaskEngine.lease_next_task(test_db_session, worker_id="mac_worker_1")
    assert lease is not None
    leased_task, _ = lease

    result = TaskResult(
        attempt_id="att_state_002_1",
        task_id="tsk_state_002",
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="antigravity-flash",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        result_commit="commit_abc123",
        files_changed=["auth.py"],
        gate_result=make_default_gate_result("tsk_state_002", "att_state_002_1"),
    )

    # Submit result
    success = await TaskEngine.submit_result(
        test_db_session, result, leased_task.lease_token, "mac_worker_1"
    )
    assert success is True
    assert leased_task.status == TaskStatus.VERIFIED.value


@pytest.mark.asyncio
async def test_heartbeat_rejects_stolen_or_expired_lease(test_db_session):
    envelope = TaskEnvelope(
        task_id="tsk_state_heartbeat",
        project_id="prj_state",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Exercise heartbeat ownership",
        allowed_paths=["."],
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    await TaskEngine.submit_task(test_db_session, envelope)
    leased = await TaskEngine.lease_next_task(test_db_session, worker_id="worker_one")
    assert leased is not None
    leased_task, _ = leased

    assert not await TaskEngine.record_heartbeat(
        test_db_session, leased_task.id, leased_task.lease_token, "worker_two"
    )
    assert await TaskEngine.record_heartbeat(
        test_db_session, leased_task.id, leased_task.lease_token, "worker_one"
    )
    assert leased_task.status == TaskStatus.RUNNING.value

    leased_task.lease_expires_at = utc_now() - timedelta(seconds=1)
    assert not await TaskEngine.record_heartbeat(
        test_db_session, leased_task.id, leased_task.lease_token, "worker_one"
    )


@pytest.mark.asyncio
async def test_duplicate_result_is_idempotent_and_stale_result_is_rejected(test_db_session):
    envelope = TaskEnvelope(
        task_id="tsk_state_idempotent",
        project_id="prj_state",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Exercise idempotent result submission",
        allowed_paths=["."],
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    await TaskEngine.submit_task(test_db_session, envelope)
    leased = await TaskEngine.lease_next_task(test_db_session, worker_id="worker_one")
    assert leased is not None
    leased_task, _ = leased
    token = leased_task.lease_token
    result = TaskResult(
        attempt_id="att_state_idempotent_1",
        task_id=leased_task.id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="antigravity-flash",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        result_commit="HEAD",
        gate_result=make_default_gate_result(leased_task.id, "att_state_idempotent_1"),
    )

    assert await TaskEngine.submit_result(test_db_session, result, token, "worker_one")
    assert await TaskEngine.submit_result(test_db_session, result, token, "worker_one")
    assert not await TaskEngine.submit_result(test_db_session, result, token, "worker_two")

    attempts = await test_db_session.execute(
        select(AttemptRecord).where(AttemptRecord.task_id == leased_task.id)
    )
    audits = await test_db_session.execute(
        select(AuditEventRecord).where(
            AuditEventRecord.task_id == leased_task.id,
            AuditEventRecord.event_type == "result_submitted",
        )
    )
    assert len(attempts.scalars().all()) == 1
    assert len(audits.scalars().all()) == 1


@pytest.mark.asyncio
async def test_expired_lease_waits_for_backoff_then_blocks_at_retry_limit(test_db_session):
    envelope = TaskEnvelope(
        task_id="tsk_state_recovery",
        project_id="prj_state",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Recover abandoned work safely",
        allowed_paths=["."],
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    await TaskEngine.submit_task(test_db_session, envelope)
    leased = await TaskEngine.lease_next_task(test_db_session, worker_id="worker_one")
    assert leased is not None
    leased_task, _ = leased
    leased_task.lease_expires_at = utc_now() - timedelta(seconds=1)

    assert await TaskEngine.timeout_expired_leases(test_db_session) == 1
    assert leased_task.status == TaskStatus.RETRYABLE_FAILED.value
    assert leased_task.next_eligible_at is not None
    assert leased_task.lease_token is None
    assert leased_task.worker_id is None
    assert await TaskEngine.release_due_retries(test_db_session) == 0

    leased_task.next_eligible_at = utc_now() - timedelta(seconds=1)
    assert await TaskEngine.release_due_retries(test_db_session) == 1
    assert leased_task.status == TaskStatus.QUEUED.value

    leased_task.attempt_count = leased_task.max_attempts
    leased_task.status = TaskStatus.LEASED.value
    leased_task.lease_token = "lease_expired_limit"
    leased_task.worker_id = "worker_one"
    leased_task.lease_expires_at = utc_now() - timedelta(seconds=1)

    assert await TaskEngine.timeout_expired_leases(test_db_session) == 1
    assert leased_task.status == TaskStatus.BLOCKED.value


@pytest.mark.asyncio
async def test_watchdog_uses_latest_progress_heartbeat_not_original_lease_time(
    test_db_session,
):
    envelope = TaskEnvelope(
        task_id="tsk_state_watchdog_progress",
        project_id="prj_state",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Keep healthy heartbeat from false stall recovery",
        allowed_paths=["."],
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    await TaskEngine.submit_task(test_db_session, envelope)
    leased = await TaskEngine.lease_next_task(test_db_session, worker_id="worker_one")
    assert leased is not None
    task, _ = leased
    task.leased_at = utc_now() - timedelta(minutes=10)
    assert await TaskEngine.record_heartbeat(
        test_db_session,
        task.id,
        task.lease_token,
        "worker_one",
    )

    assert await TaskEngine.check_watchdog_stalls(test_db_session, 300) == []
    assert task.status == TaskStatus.RUNNING.value
    assert task.worker_id == "worker_one"


@pytest.mark.asyncio
async def test_watchdog_retries_task_with_stale_progress_heartbeat(test_db_session):
    envelope = TaskEnvelope(
        task_id="tsk_state_watchdog_stale",
        project_id="prj_state",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Recover task whose progress stopped",
        allowed_paths=["."],
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    await TaskEngine.submit_task(test_db_session, envelope)
    leased = await TaskEngine.lease_next_task(test_db_session, worker_id="worker_one")
    assert leased is not None
    task, _ = leased
    task.leased_at = utc_now() - timedelta(minutes=10)
    task.updated_at = utc_now() - timedelta(minutes=10)

    assert await TaskEngine.check_watchdog_stalls(test_db_session, 300) == [task.id]
    assert task.status == TaskStatus.RETRYABLE_FAILED.value
    assert task.lease_token is None
    assert task.worker_id is None
    assert task.next_eligible_at is not None


@pytest.mark.asyncio
async def test_resubmission_cannot_replace_verified_task(test_db_session):
    envelope = TaskEnvelope(
        task_id="tsk_state_immutable",
        project_id="prj_state",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Keep completed work immutable",
        allowed_paths=["."],
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    await TaskEngine.submit_task(test_db_session, envelope)
    leased = await TaskEngine.lease_next_task(test_db_session, worker_id="worker_one")
    assert leased is not None
    leased_task, _ = leased
    result = TaskResult(
        attempt_id="att_state_immutable_1",
        task_id=leased_task.id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="antigravity-flash",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        result_commit="HEAD",
        gate_result=make_default_gate_result(leased_task.id, "att_state_immutable_1"),
    )
    assert await TaskEngine.submit_result(
        test_db_session, result, leased_task.lease_token, "worker_one"
    )

    assert (
        await TaskEngine.submit_task(test_db_session, envelope)
    ).status == TaskStatus.VERIFIED.value
    with pytest.raises(ValueError, match="Cannot replace"):
        await TaskEngine.submit_task(
            test_db_session, envelope.model_copy(update={"objective": "Replace"})
        )


@pytest.mark.asyncio
async def test_dependency_blocks_downstream_then_verified_upstream_unblocks_it(test_db_session):
    downstream = TaskEnvelope(
        task_id="tsk_state_downstream",
        project_id="prj_state_dag",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Run only after upstream verification",
        allowed_paths=["."],
        dependencies=[TaskDependency(task_id="tsk_state_upstream")],
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    upstream = TaskEnvelope(
        task_id="tsk_state_upstream",
        project_id="prj_state_dag",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Create upstream evidence",
        allowed_paths=["."],
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    await TaskEngine.submit_task(test_db_session, downstream)
    await TaskEngine.submit_task(test_db_session, upstream)

    leased_up = await TaskEngine.lease_next_task(test_db_session, worker_id="worker_one")
    assert leased_up is not None
    leased_upstream, _ = leased_up
    assert leased_upstream.id == upstream.task_id
    assert TaskEnvelope.model_validate(
        (await TaskEngine.submit_task(test_db_session, downstream)).details_json
    ).dependencies

    upstream_result = TaskResult(
        attempt_id="att_state_upstream_1",
        task_id=upstream.task_id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="antigravity-flash",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        result_commit="HEAD",
        gate_result=make_default_gate_result(upstream.task_id, "att_state_upstream_1"),
    )
    assert await TaskEngine.submit_result(
        test_db_session, upstream_result, leased_upstream.lease_token, "worker_one"
    )

    leased_down = await TaskEngine.lease_next_task(test_db_session, worker_id="worker_two")
    assert leased_down is not None
    leased_downstream, _ = leased_down
    assert leased_downstream.id == downstream.task_id


@pytest.mark.asyncio
async def test_self_dependency_is_rejected(test_db_session):
    task = TaskEnvelope(
        task_id="tsk_state_self_dependency",
        project_id="prj_state_dag",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Invalid dependency graph",
        allowed_paths=["."],
        dependencies=[TaskDependency(task_id="tsk_state_self_dependency")],
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    with pytest.raises(ValueError, match="cannot depend on itself"):
        await TaskEngine.submit_task(test_db_session, task)


@pytest.mark.asyncio
async def test_approval_required_task_cannot_lease_until_approved(test_db_session):
    envelope = TaskEnvelope(
        task_id="tsk_state_approval",
        project_id="prj_state_approval",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Wait for founder review",
        allowed_paths=["."],
        requires_approval=True,
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    task = await TaskEngine.submit_task(test_db_session, envelope)
    assert task.status == TaskStatus.WAITING_APPROVAL.value
    assert await TaskEngine.lease_next_task(test_db_session, worker_id="worker_one") is None

    approval = await test_db_session.execute(
        select(ApprovalRecord).where(ApprovalRecord.task_id == task.id)
    )
    assert approval.scalar_one().status == "pending"
    approval_decision = await TaskEngine.decide_task_approval(
        test_db_session, task.id, True, "founder", "Approved"
    )
    assert approval_decision is not None
    assert approval_decision.status == TaskStatus.QUEUED.value
    assert await TaskEngine.lease_next_task(test_db_session, worker_id="worker_one") is not None
    assert await TaskEngine.decide_task_approval(test_db_session, task.id, True, "founder") is None


@pytest.mark.asyncio
async def test_high_risk_task_requires_approval_even_without_request_flag(test_db_session):
    task = await TaskEngine.submit_task(
        test_db_session,
        TaskEnvelope(
            task_id="tsk_state_high_risk",
            project_id="prj_state_approval",
            repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
            objective="Run high-impact change",
            allowed_paths=["."],
            risk_class=RiskClass.HIGH,
            base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        ),
    )
    assert task.status == TaskStatus.WAITING_APPROVAL.value


@pytest.mark.asyncio
async def test_project_and_worker_concurrency_limits_gate_leasing(test_db_session):
    project_policy = ConcurrencyPolicy(max_per_project=1, max_per_worker=2)
    first = TaskEnvelope(
        task_id="tsk_state_project_limit_one",
        project_id="prj_state_capacity",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="First project task",
        allowed_paths=["."],
        concurrency_policy=project_policy,
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    second = first.model_copy(
        update={"task_id": "tsk_state_project_limit_two", "objective": "Second project task"}
    )
    await TaskEngine.submit_task(test_db_session, first)
    second_task = await TaskEngine.submit_task(test_db_session, second)
    leased_f = await TaskEngine.lease_next_task(test_db_session, worker_id="worker_one")
    assert leased_f is not None
    leased_first, _ = leased_f
    assert leased_first.id == first.task_id
    assert await TaskEngine.lease_next_task(test_db_session, worker_id="worker_two") is None

    leased_first.status = TaskStatus.BLOCKED.value
    second_task.status = TaskStatus.CANCELLED.value
    other_project_policy = ConcurrencyPolicy(max_per_project=2, max_per_worker=1)
    third = TaskEnvelope(
        task_id="tsk_state_worker_limit_one",
        project_id="prj_state_other_capacity",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Worker capped task",
        allowed_paths=["."],
        concurrency_policy=other_project_policy,
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    fourth = third.model_copy(
        update={"task_id": "tsk_state_worker_limit_two", "objective": "Second worker capped task"}
    )
    await TaskEngine.submit_task(test_db_session, third)
    await TaskEngine.submit_task(test_db_session, fourth)
    leased_t = await TaskEngine.lease_next_task(test_db_session, worker_id="worker_one")
    assert leased_t is not None
    leased_third, _ = leased_t
    assert leased_third.id == third.task_id
    assert await TaskEngine.lease_next_task(test_db_session, worker_id="worker_one") is None
    leased_fo = await TaskEngine.lease_next_task(test_db_session, worker_id="worker_two")
    assert leased_fo is not None
    leased_fourth, _ = leased_fo
    assert leased_fourth.id == fourth.task_id


@pytest.mark.asyncio
async def test_task_engine_rejects_illegal_status_transition(test_db_session):
    task = await TaskEngine.submit_task(
        test_db_session,
        TaskEnvelope(
            task_id="tsk_state_illegal_transition",
            project_id="prj_state_transition",
            repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
            objective="Guard state table",
            allowed_paths=["."],
            base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        ),
    )
    with pytest.raises(ValueError, match="Illegal task transition: queued -> verified"):
        TaskEngine._transition(task, TaskStatus.VERIFIED)
    assert task.status == TaskStatus.QUEUED.value


@pytest.mark.asyncio
async def test_task_envelope_decoding_variants(test_db_session):
    envelope = TaskEnvelope(
        task_id="tsk_state_decoding_1",
        project_id="prj_state_decoding",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Decode dictionary",
        allowed_paths=["."],
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )

    # 1. Dictionary value parses
    assert TaskEngine._parse_task_envelope(envelope.model_dump())

    # 2. Valid JSON string parses
    assert TaskEngine._parse_task_envelope(envelope.model_dump_json())

    # 3. Malformed JSON string fails
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TaskEngine._parse_task_envelope("not a json string")

    # 4. Valid JSON containing invalid envelope fails
    with pytest.raises(ValidationError):
        TaskEngine._parse_task_envelope('{"task_id": "missing_required_fields"}')


@pytest.mark.asyncio
async def test_task_engine_string_backed_details_json(test_db_session):
    envelope = TaskEnvelope(
        task_id="tsk_state_decoding_lease",
        project_id="prj_state_decoding",
        repo="/Users/ajaytiwari/Desktop/Projects/alphaBrain",
        objective="Lease with string json",
        allowed_paths=["."],
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    task = await TaskEngine.submit_task(test_db_session, envelope)

    # Force string-backed details_json in DB (simulating bad dialect / parsing config)
    task.details_json = envelope.model_dump_json()
    await test_db_session.flush()

    # 5. lease_next_task works with string-backed details_json
    leased = await TaskEngine.lease_next_task(test_db_session, worker_id="worker_one")
    assert leased is not None
    leased_task, _ = leased
    assert leased_task.id == "tsk_state_decoding_lease"

    # 6. retry scheduling works with string-backed details_json
    task.details_json = envelope.model_dump_json()  # ensure it's still string
    await test_db_session.flush()

    from alpha_protocol import AgentType, TaskResult

    # Fail it to trigger retry scheduling
    result = TaskResult(
        attempt_id="att_state_decoding_1",
        task_id=task.id,
        status=TaskStatus.RETRYABLE_FAILED,
        agent=AgentType.ANTIGRAVITY,
        model="antigravity-flash",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        result_commit="HEAD",
    )
    await TaskEngine.submit_result(test_db_session, result, leased_task.lease_token, "worker_one")

    assert task.status == TaskStatus.RETRYABLE_FAILED.value
    assert task.next_eligible_at is not None
