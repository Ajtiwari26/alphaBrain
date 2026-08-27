from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.db.models import ApprovalRecord, AttemptRecord, TaskRecord
from alpha_core.self_development import SelfImprovementRequest, create_self_improvement_task
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import AgentType, TaskEnvelope, TaskResult, TaskStatus, compute_packet_digest


@pytest_asyncio.fixture
async def db_session():
    from alpha_core.db.connection import get_session_factory

    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


@pytest.fixture
def test_envelope() -> TaskEnvelope:
    import uuid

    return TaskEnvelope(
        task_id=f"task_{uuid.uuid4().hex[:8]}",
        project_id="prj_test",
        repo="/tmp/test_repo",
        base_commit="HEAD",
        objective="Test binding",
        allowed_paths=["."],
        require_packet_binding=True,
        requires_approval=True,
    )


def test_canonical_digest_determinism(test_envelope: TaskEnvelope):
    """1. Canonical digest determinism."""
    digest1 = compute_packet_digest(test_envelope)

    # Re-create exact same semantics
    envelope2 = TaskEnvelope.model_validate(test_envelope.model_dump())
    digest2 = compute_packet_digest(envelope2)

    assert digest1 == digest2
    assert len(digest1) == 64


@pytest.mark.asyncio
async def test_self_task_stores_digest(
    db_session: AsyncSession, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """2. Self-task stores digest on task and pending approval."""
    from alpha_core.config import settings

    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))
    repo = tmp_path / "repo"
    repo.mkdir()
    import subprocess

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo, check=True)

    req = SelfImprovementRequest(
        source_repo=repo,
        allowed_paths=(".",),
        founder_identity="founder1",
        requires_approval=True,
    )

    import uuid

    t_id = f"t_{uuid.uuid4().hex[:8]}"
    task = await create_self_improvement_task(
        db_session, req, project_id=f"prj_{uuid.uuid4().hex[:8]}", task_id=t_id, objective="Test"
    )
    assert task.packet_sha256 is not None

    from sqlalchemy import select

    appr = await db_session.scalar(select(ApprovalRecord).where(ApprovalRecord.task_id == t_id))
    assert appr is not None
    assert appr.scope_sha256 == task.packet_sha256


@pytest.mark.asyncio
async def test_correct_founder_digest_approves(
    db_session: AsyncSession, test_envelope: TaskEnvelope
):
    """3. Correct founder digest approves."""
    task = await TaskEngine.submit_task(db_session, test_envelope)
    digest = task.packet_sha256

    approved = await TaskEngine.decide_task_approval(
        db_session, task.id, approved=True, decided_by="founder", packet_sha256=digest
    )
    assert approved is not None
    assert approved.status == TaskStatus.QUEUED.value


@pytest.mark.asyncio
async def test_wrong_founder_digest_fails(db_session: AsyncSession, test_envelope: TaskEnvelope):
    """4. Missing/wrong founder digest fails without state mutation."""
    task = await TaskEngine.submit_task(db_session, test_envelope)

    with pytest.raises(ValueError, match="Task packet digest mismatch or missing"):
        await TaskEngine.decide_task_approval(
            db_session, task.id, approved=True, decided_by="founder", packet_sha256="wrong"
        )

    with pytest.raises(ValueError, match="Task packet digest mismatch or missing"):
        await TaskEngine.decide_task_approval(
            db_session, task.id, approved=True, decided_by="founder", packet_sha256=None
        )


@pytest.mark.asyncio
async def test_mutation_after_approval_fails_to_lease(
    db_session: AsyncSession, test_envelope: TaskEnvelope
):
    """5. Stored packet mutation after approval cannot lease."""
    task = await TaskEngine.submit_task(db_session, test_envelope)
    digest = task.packet_sha256

    await TaskEngine.decide_task_approval(
        db_session, task.id, approved=True, decided_by="founder", packet_sha256=digest
    )

    new_details = dict(task.details_json)
    new_details["objective"] = "Mutated objective"
    task.details_json = new_details
    await db_session.flush()

    print(f"MUTATED: old sha: {task.packet_sha256}")

    leased = await TaskEngine.lease_next_task(db_session, "worker1")
    # Because digest doesn't match mutated json, it should block and return None
    assert leased is None

    from sqlalchemy import select

    task_after = await db_session.scalar(select(TaskRecord).where(TaskRecord.id == task.id))
    assert task_after.status == TaskStatus.BLOCKED.value


@pytest.mark.asyncio
async def test_wrong_result_digest_fails(db_session: AsyncSession, test_envelope: TaskEnvelope):
    """6. Missing/wrong result digest fails without attempt/evidence or lease mutation."""
    task = await TaskEngine.submit_task(db_session, test_envelope)
    digest = task.packet_sha256
    await TaskEngine.decide_task_approval(
        db_session, task.id, approved=True, decided_by="founder", packet_sha256=digest
    )

    leased = await TaskEngine.lease_next_task(db_session, "worker1")
    assert leased is not None
    _, env = leased

    result = TaskResult(
        attempt_id="att1",
        task_id=task.id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="test",
        base_commit=env.base_commit,
        packet_sha256="0" * 64,
    )

    success = await TaskEngine.submit_result(db_session, result, task.lease_token, "worker1")
    assert success is False

    # attempt should not be persisted
    from sqlalchemy import select

    attempt = await db_session.scalar(select(AttemptRecord).where(AttemptRecord.id == "att1"))
    assert attempt is None

    # task should still be leased
    task_after = await db_session.scalar(select(TaskRecord).where(TaskRecord.id == task.id))
    assert task_after.status == TaskStatus.LEASED.value


@pytest.mark.asyncio
async def test_wrong_result_base_commit_fails(
    db_session: AsyncSession, test_envelope: TaskEnvelope
):
    """7. Wrong result base commit fails."""
    task = await TaskEngine.submit_task(db_session, test_envelope)
    digest = task.packet_sha256
    await TaskEngine.decide_task_approval(
        db_session, task.id, approved=True, decided_by="founder", packet_sha256=digest
    )

    leased = await TaskEngine.lease_next_task(db_session, "worker1")
    assert leased is not None

    result = TaskResult(
        attempt_id="att2",
        task_id=task.id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="test",
        base_commit="WRONGCOMMIT",
        packet_sha256=digest,
    )
    success = await TaskEngine.submit_result(db_session, result, task.lease_token, "worker1")
    assert success is False


@pytest.mark.asyncio
async def test_correct_bound_result_persists(db_session: AsyncSession, test_envelope: TaskEnvelope):
    """8. Correct bound result persists attempt digest."""
    task = await TaskEngine.submit_task(db_session, test_envelope)
    digest = task.packet_sha256
    await TaskEngine.decide_task_approval(
        db_session, task.id, approved=True, decided_by="founder", packet_sha256=digest
    )

    leased = await TaskEngine.lease_next_task(db_session, "worker1")
    assert leased is not None
    _, env = leased

    result = TaskResult(
        attempt_id="att3",
        task_id=task.id,
        status=TaskStatus.RETRYABLE_FAILED,  # simpler than providing gate evidence
        agent=AgentType.ANTIGRAVITY,
        model="test",
        base_commit=env.base_commit,
        packet_sha256=digest,
    )

    success = await TaskEngine.submit_result(db_session, result, task.lease_token, "worker1")
    assert success is True

    from sqlalchemy import select

    attempt = await db_session.scalar(select(AttemptRecord).where(AttemptRecord.id == "att3"))
    assert attempt is not None
    assert attempt.packet_sha256 == digest


@pytest.mark.asyncio
async def test_legacy_task_compatibility(db_session: AsyncSession):
    """9. Normal legacy task with require_packet_binding=False remains compatible."""
    import uuid

    task_id = f"legacy_{uuid.uuid4().hex[:8]}"
    env = TaskEnvelope(
        task_id=task_id,
        project_id=f"prj_{uuid.uuid4().hex[:8]}",
        repo="/tmp",
        base_commit="HEAD",
        objective="Legacy",
        allowed_paths=["."],
        require_packet_binding=False,
    )

    task = await TaskEngine.submit_task(db_session, env)
    # the digest helper might still set it on the task
    assert task.status == TaskStatus.QUEUED.value

    leased = await TaskEngine.lease_next_task(db_session, "worker1")
    assert leased is not None

    result = TaskResult(
        attempt_id="att_legacy",
        task_id=task.id,
        status=TaskStatus.RETRYABLE_FAILED,
        agent=AgentType.ANTIGRAVITY,
        model="test",
        base_commit=env.base_commit,
        # missing packet_sha256 should be fine
    )

    success = await TaskEngine.submit_result(db_session, result, task.lease_token, "worker1")
    assert success is True


@pytest.mark.asyncio
async def test_mutation_after_approval_creates_conflict(
    db_session: AsyncSession, test_envelope: TaskEnvelope
):
    """Extra: Existing task definition cannot be mutated after an approval has been created."""
    # Ensure requires_approval is true so we get an approval
    test_envelope.requires_approval = True
    await TaskEngine.submit_task(db_session, test_envelope)

    test_envelope.objective = "Mutated"
    with pytest.raises(
        ValueError, match="Cannot mutate task definition after execution approval is requested"
    ):
        await TaskEngine.submit_task(db_session, test_envelope)


def test_legal_transition_queued_to_blocked():
    """Extra: Explicitly test that QUEUED can transition to BLOCKED."""
    from alpha_protocol.enums import TaskStatus, is_legal_transition

    assert is_legal_transition(TaskStatus.QUEUED, TaskStatus.BLOCKED) is True
