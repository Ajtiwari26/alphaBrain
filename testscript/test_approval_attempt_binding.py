import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.db.connection import get_session_factory
from alpha_core.db.models import ApprovalRecord, AttemptRecord, TaskRecord
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import (
    AcceptancePlan,
    AgentType,
    ApprovalStatus,
    GateCommand,
    GateEvidence,
    GateResult,
    GateType,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
    compute_packet_digest,
    compute_review_digest,
)


@pytest_asyncio.fixture
async def db_session():
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


def make_test_envelope(require_packet_binding: bool = True) -> TaskEnvelope:
    task_id = f"tsk_{uuid.uuid4().hex[:8]}"
    return TaskEnvelope(
        task_id=task_id,
        project_id="prj_approval_bind",
        repo="/tmp/test_repo",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        objective="Verify attempt binding for founder review",
        allowed_paths=["src/"],
        require_packet_binding=require_packet_binding,
        requires_approval=False,
        acceptance_plan=AcceptancePlan(
            required_gates=[GateType.UNIT_TEST],
            commands=[GateCommand(gate_type=GateType.UNIT_TEST, executable="pytest", args=["-q"])],
        ),
    )


def make_passing_result(task: TaskEnvelope, attempt_id: str | None = None) -> TaskResult:
    att_id = attempt_id or f"att_{uuid.uuid4().hex[:6]}"
    digest = compute_packet_digest(task) if task.require_packet_binding else None
    return TaskResult(
        attempt_id=att_id,
        task_id=task.task_id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="test-model",
        base_commit=task.base_commit,
        result_commit="commit_abc123",
        packet_sha256=digest,
        files_changed=["src/app.py"],
        gate_result=GateResult(
            task_id=task.task_id,
            attempt_id=att_id,
            all_passed=True,
            evidence_items=[
                GateEvidence(
                    evidence_id=f"ev_{uuid.uuid4().hex[:6]}",
                    gate_type=GateType.UNIT_TEST,
                    passed=True,
                    summary="Unit tests passed",
                    metrics={"command_argv": ["pytest", "-q"], "exit_code": 0},
                )
            ],
        ),
    )


@pytest.mark.asyncio
async def test_task_review_approval_stores_exact_attempt_id(db_session: AsyncSession):
    env = make_test_envelope(require_packet_binding=True)
    await TaskEngine.submit_task(db_session, env)

    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "worker-1") is True

    appr_res = await db_session.execute(
        select(ApprovalRecord).where(
            ApprovalRecord.task_id == task_rec.id,
            ApprovalRecord.approval_type == "task_review",
        )
    )
    apprs = appr_res.scalars().all()
    assert len(apprs) == 1
    approval = apprs[0]

    assert approval.attempt_id == res.attempt_id
    assert approval.status == ApprovalStatus.PENDING.value
    expected_digest = compute_review_digest(res, "worker-1")
    assert approval.scope_sha256 == expected_digest


@pytest.mark.asyncio
async def test_null_legacy_binding_fails_closed(db_session: AsyncSession):
    env = make_test_envelope(require_packet_binding=True)
    await TaskEngine.submit_task(db_session, env)

    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "worker-1") is True

    approval = (
        await db_session.execute(
            select(ApprovalRecord).where(
                ApprovalRecord.task_id == task_rec.id,
                ApprovalRecord.approval_type == "task_review",
            )
        )
    ).scalar_one()

    # Clear attempt_id to simulate null legacy binding
    approval.attempt_id = None
    db_session.add(approval)
    await db_session.commit()

    with pytest.raises(ValueError, match="Null legacy binding is unsupported"):
        await TaskEngine.decide_task_approval(
            db_session,
            task_rec.id,
            approved=True,
            decided_by="founder",
            reason="lgtm",
            review_sha256=approval.scope_sha256,
        )


@pytest.mark.asyncio
async def test_wrong_task_attempt_fails_closed(db_session: AsyncSession):
    env1 = make_test_envelope(require_packet_binding=True)
    env2 = make_test_envelope(require_packet_binding=True)
    await TaskEngine.submit_task(db_session, env1)
    await TaskEngine.submit_task(db_session, env2)

    leased1 = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased1 is not None
    task_rec1, _ = leased1

    leased2 = await TaskEngine.lease_next_task(db_session, "worker-2")
    assert leased2 is not None
    task_rec2, _ = leased2

    res1 = make_passing_result(env1)
    res2 = make_passing_result(env2)
    assert (
        await TaskEngine.submit_result(db_session, res1, task_rec1.lease_token, "worker-1") is True
    )
    assert (
        await TaskEngine.submit_result(db_session, res2, task_rec2.lease_token, "worker-2") is True
    )

    approval1 = (
        await db_session.execute(
            select(ApprovalRecord).where(
                ApprovalRecord.task_id == task_rec1.id,
                ApprovalRecord.approval_type == "task_review",
            )
        )
    ).scalar_one()

    # Point approval1 to res2.attempt_id (which belongs to task2)
    approval1.attempt_id = res2.attempt_id
    db_session.add(approval1)
    await db_session.commit()

    with pytest.raises(ValueError, match="Bound attempt not found or belongs to a different task"):
        await TaskEngine.decide_task_approval(
            db_session,
            task_rec1.id,
            approved=True,
            decided_by="founder",
            reason="lgtm",
            review_sha256=approval1.scope_sha256,
        )


@pytest.mark.asyncio
async def test_missing_attempt_fails_closed(db_session: AsyncSession):
    env = make_test_envelope(require_packet_binding=True)
    await TaskEngine.submit_task(db_session, env)

    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "worker-1") is True

    approval = (
        await db_session.execute(
            select(ApprovalRecord).where(
                ApprovalRecord.task_id == task_rec.id,
                ApprovalRecord.approval_type == "task_review",
            )
        )
    ).scalar_one()

    approval.attempt_id = "nonexistent_attempt_id"
    db_session.add(approval)
    await db_session.commit()

    with pytest.raises(ValueError, match="Bound attempt not found or belongs to a different task"):
        await TaskEngine.decide_task_approval(
            db_session,
            task_rec.id,
            approved=True,
            decided_by="founder",
            reason="lgtm",
            review_sha256=approval.scope_sha256,
        )


@pytest.mark.asyncio
async def test_result_commit_mutation_fails_closed(db_session: AsyncSession):
    env = make_test_envelope(require_packet_binding=True)
    await TaskEngine.submit_task(db_session, env)

    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "worker-1") is True

    approval = (
        await db_session.execute(
            select(ApprovalRecord).where(
                ApprovalRecord.task_id == task_rec.id,
                ApprovalRecord.approval_type == "task_review",
            )
        )
    ).scalar_one()

    attempt = (
        await db_session.execute(select(AttemptRecord).where(AttemptRecord.id == res.attempt_id))
    ).scalar_one()

    # Mutate persisted attempt result_commit
    attempt.result_commit = "tampered_commit_xyz"
    db_session.add(attempt)
    await db_session.commit()

    with pytest.raises(ValueError, match="Founder review digest mismatch with recomputed state"):
        await TaskEngine.decide_task_approval(
            db_session,
            task_rec.id,
            approved=True,
            decided_by="founder",
            reason="lgtm",
            review_sha256=approval.scope_sha256,
        )


@pytest.mark.asyncio
async def test_files_changed_mutation_fails_closed(db_session: AsyncSession):
    env = make_test_envelope(require_packet_binding=True)
    await TaskEngine.submit_task(db_session, env)

    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "worker-1") is True

    approval = (
        await db_session.execute(
            select(ApprovalRecord).where(
                ApprovalRecord.task_id == task_rec.id,
                ApprovalRecord.approval_type == "task_review",
            )
        )
    ).scalar_one()

    attempt = (
        await db_session.execute(select(AttemptRecord).where(AttemptRecord.id == res.attempt_id))
    ).scalar_one()

    # Mutate persisted files_changed_json
    attempt.files_changed_json = ["src/app.py", "src/extra_tampered.py"]
    db_session.add(attempt)
    await db_session.commit()

    with pytest.raises(ValueError, match="Founder review digest mismatch with recomputed state"):
        await TaskEngine.decide_task_approval(
            db_session,
            task_rec.id,
            approved=True,
            decided_by="founder",
            reason="lgtm",
            review_sha256=approval.scope_sha256,
        )


@pytest.mark.asyncio
async def test_gate_evidence_mutation_fails_closed(db_session: AsyncSession):
    env = make_test_envelope(require_packet_binding=True)
    await TaskEngine.submit_task(db_session, env)

    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "worker-1") is True

    approval = (
        await db_session.execute(
            select(ApprovalRecord).where(
                ApprovalRecord.task_id == task_rec.id,
                ApprovalRecord.approval_type == "task_review",
            )
        )
    ).scalar_one()

    attempt = (
        await db_session.execute(select(AttemptRecord).where(AttemptRecord.id == res.attempt_id))
    ).scalar_one()

    # Mutate gate_result_json
    mutated_gate = res.gate_result.model_copy(deep=True)
    mutated_gate.evidence_items[0].summary = "Tampered summary"
    attempt.gate_result_json = mutated_gate.model_dump(mode="json")
    db_session.add(attempt)
    await db_session.commit()

    with pytest.raises(ValueError, match="Founder review digest mismatch with recomputed state"):
        await TaskEngine.decide_task_approval(
            db_session,
            task_rec.id,
            approved=True,
            decided_by="founder",
            reason="lgtm",
            review_sha256=approval.scope_sha256,
        )


@pytest.mark.asyncio
async def test_unchanged_bound_digest_approves_and_completes(db_session: AsyncSession):
    env = make_test_envelope(require_packet_binding=True)
    await TaskEngine.submit_task(db_session, env)

    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    res.result_commit = env.base_commit
    res.files_changed = []
    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "worker-1") is True

    approval = (
        await db_session.execute(
            select(ApprovalRecord).where(
                ApprovalRecord.task_id == task_rec.id,
                ApprovalRecord.approval_type == "task_review",
            )
        )
    ).scalar_one()

    completed_task = await TaskEngine.decide_task_approval(
        db_session,
        task_rec.id,
        approved=True,
        decided_by="founder-01",
        reason="Looks great",
        review_sha256=approval.scope_sha256,
    )
    assert completed_task is not None
    assert completed_task.status == TaskStatus.COMPLETED.value

    t = await db_session.get(TaskRecord, task_rec.id)
    assert t is not None
    assert t.status == TaskStatus.COMPLETED.value

    refreshed_appr = await db_session.get(ApprovalRecord, approval.id)
    assert refreshed_appr is not None
    assert refreshed_appr.status == ApprovalStatus.APPROVED.value
    assert refreshed_appr.decided_by == "founder-01"


@pytest.mark.asyncio
async def test_task_review_rejection_blocks_task(db_session: AsyncSession):
    env = make_test_envelope(require_packet_binding=True)
    await TaskEngine.submit_task(db_session, env)

    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "worker-1") is True

    approval = (
        await db_session.execute(
            select(ApprovalRecord).where(
                ApprovalRecord.task_id == task_rec.id,
                ApprovalRecord.approval_type == "task_review",
            )
        )
    ).scalar_one()

    blocked_task = await TaskEngine.decide_task_approval(
        db_session,
        task_rec.id,
        approved=False,
        decided_by="founder-01",
        reason="Needs significant rework",
        review_sha256=approval.scope_sha256,
    )
    assert blocked_task is not None
    assert blocked_task.status == TaskStatus.BLOCKED.value

    t = await db_session.get(TaskRecord, task_rec.id)
    assert t is not None
    assert t.status == TaskStatus.BLOCKED.value

    refreshed_appr = await db_session.get(ApprovalRecord, approval.id)
    assert refreshed_appr is not None
    assert refreshed_appr.status == ApprovalStatus.REJECTED.value
