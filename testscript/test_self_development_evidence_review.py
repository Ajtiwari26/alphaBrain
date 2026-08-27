import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.db.models import (
    ApprovalRecord,
    TaskRecord,
)
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import (
    AcceptancePlan,
    AgentType,
    GateEvidence,
    GateResult,
    GateType,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
)


@pytest_asyncio.fixture
async def db_session():
    from alpha_core.db.connection import get_session_factory

    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


def make_test_envelope(require_packet_binding=True) -> TaskEnvelope:
    import uuid

    from alpha_protocol.gates import GateCommand

    return TaskEnvelope(
        task_id=f"tsk_{uuid.uuid4().hex[:8]}",
        project_id="prj_test",
        repo="/tmp/test",
        base_commit="HEAD",
        objective="Test review",
        allowed_paths=["src/"],
        require_packet_binding=require_packet_binding,
        requires_approval=False,
        acceptance_plan=AcceptancePlan(
            required_gates=[GateType.UNIT_TEST],
            commands=[GateCommand(gate_type=GateType.UNIT_TEST, executable="pytest", args=["-q"])],
        ),
    )


def make_passing_result(task: TaskEnvelope) -> TaskResult:
    import uuid

    from alpha_protocol import compute_packet_digest

    digest = compute_packet_digest(task) if task.require_packet_binding else None
    att_id = f"att_{uuid.uuid4().hex[:6]}"
    return TaskResult(
        attempt_id=att_id,
        task_id=task.task_id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="test",
        base_commit=task.base_commit,
        result_commit="newcommit",
        packet_sha256=digest,
        files_changed=["src/test.py"],
        gate_result=GateResult(
            task_id=task.task_id,
            attempt_id=att_id,
            all_passed=True,
            evidence_items=[
                GateEvidence(
                    evidence_id=f"ev_{uuid.uuid4().hex[:6]}",
                    gate_type=GateType.UNIT_TEST,
                    passed=True,
                    summary="Passed",
                    metrics={"command_argv": ["pytest", "-q"], "exit_code": 0},
                )
            ],
        ),
    )


@pytest.mark.asyncio
async def test_exact_declared_argv_passes(db_session: AsyncSession):
    env = make_test_envelope(require_packet_binding=False)
    await TaskEngine.submit_task(db_session, env)
    leased = await TaskEngine.lease_next_task(db_session, "w1")
    assert leased is not None
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    success = await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "w1")
    assert success is True

    # task should be verified since binding=False doesn't automatically complete it
    t = await db_session.get(TaskRecord, task_rec.id)
    assert t.status == TaskStatus.VERIFIED.value


@pytest.mark.asyncio
async def test_wrong_argv_fails(db_session: AsyncSession):
    env = make_test_envelope()
    await TaskEngine.submit_task(db_session, env)
    leased = await TaskEngine.lease_next_task(db_session, "w1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    assert res.gate_result is not None
    res.gate_result.evidence_items[0].metrics = {"command_argv": ["pytest", "-v"], "exit_code": 0}

    success = await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "w1")
    assert success is False
    t = await db_session.get(TaskRecord, task_rec.id)
    assert t.status == TaskStatus.LEASED.value


@pytest.mark.asyncio
async def test_missing_required_gate_fails(db_session: AsyncSession):
    env = make_test_envelope()
    await TaskEngine.submit_task(db_session, env)
    leased = await TaskEngine.lease_next_task(db_session, "w1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    assert res.gate_result is not None
    res.gate_result.evidence_items[0].gate_type = GateType.LINT

    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "w1") is False


@pytest.mark.asyncio
async def test_mismatched_ids_fail(db_session: AsyncSession):
    env = make_test_envelope()
    await TaskEngine.submit_task(db_session, env)
    leased = await TaskEngine.lease_next_task(db_session, "w1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    assert res.gate_result is not None
    res.gate_result.task_id = "wrong_task"
    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "w1") is False

    res = make_passing_result(env)
    assert res.gate_result is not None
    res.gate_result.attempt_id = "wrong_att"
    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "w1") is False


@pytest.mark.asyncio
async def test_duplicate_evidence_ids_fail(db_session: AsyncSession):
    env = make_test_envelope()
    await TaskEngine.submit_task(db_session, env)
    leased = await TaskEngine.lease_next_task(db_session, "w1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    assert res.gate_result is not None
    ev = res.gate_result.evidence_items[0]
    res.gate_result.evidence_items.append(ev.model_copy())

    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "w1") is False


@pytest.mark.asyncio
async def test_outside_scope_paths_fail(db_session: AsyncSession):
    env = make_test_envelope()
    await TaskEngine.submit_task(db_session, env)
    leased = await TaskEngine.lease_next_task(db_session, "w1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    res.files_changed = ["outside/file.py"]
    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "w1") is False

    res.files_changed = ["/absolute/path"]
    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "w1") is False


@pytest.mark.asyncio
async def test_valid_bound_result_creates_review(db_session: AsyncSession):
    env = make_test_envelope(require_packet_binding=True)
    await TaskEngine.submit_task(db_session, env)
    leased = await TaskEngine.lease_next_task(db_session, "w1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "w1") is True

    t = await db_session.get(TaskRecord, task_rec.id)
    assert t.status == TaskStatus.VERIFIED.value

    from sqlalchemy import select

    appr_res = await db_session.execute(
        select(ApprovalRecord).where(ApprovalRecord.task_id == t.id)
    )
    apprs = appr_res.scalars().all()
    assert len(apprs) == 1
    assert apprs[0].approval_type == "task_review"
    assert apprs[0].status == "pending"


@pytest.mark.asyncio
async def test_duplicate_result_is_idempotent(db_session: AsyncSession):
    env = make_test_envelope(require_packet_binding=True)
    await TaskEngine.submit_task(db_session, env)
    leased = await TaskEngine.lease_next_task(db_session, "w1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "w1") is True
    assert await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "w1") is True

    from sqlalchemy import select

    appr_res = await db_session.execute(
        select(ApprovalRecord).where(ApprovalRecord.task_id == task_rec.id)
    )
    apprs = appr_res.scalars().all()
    assert len(apprs) == 1


@pytest.mark.asyncio
async def test_founder_review_completes_task(db_session: AsyncSession):
    env = make_test_envelope(require_packet_binding=True)
    await TaskEngine.submit_task(db_session, env)
    leased = await TaskEngine.lease_next_task(db_session, "w1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "w1")

    from sqlalchemy import select

    appr = (
        await db_session.execute(
            select(ApprovalRecord).where(ApprovalRecord.task_id == task_rec.id)
        )
    ).scalar_one()

    await TaskEngine.decide_task_approval(
        db_session, task_rec.id, True, "founder", "lgtm", review_sha256=appr.scope_sha256
    )

    t = await db_session.get(TaskRecord, task_rec.id)
    assert t.status == TaskStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_wrong_founder_review_digest_fails(db_session: AsyncSession):
    env = make_test_envelope(require_packet_binding=True)
    await TaskEngine.submit_task(db_session, env)
    leased = await TaskEngine.lease_next_task(db_session, "w1")
    assert leased is not None
    task_rec, _ = leased

    res = make_passing_result(env)
    await TaskEngine.submit_result(db_session, res, task_rec.lease_token, "w1")

    with pytest.raises(ValueError, match="Founder review digest mismatch"):
        await TaskEngine.decide_task_approval(
            db_session, task_rec.id, True, "founder", "lgtm", review_sha256="wrong"
        )
