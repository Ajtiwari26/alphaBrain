import json
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.db.connection import get_session_factory
from alpha_core.db.models import ApprovalRecord, AttemptRecord, GateEvidenceRecord, TaskRecord
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import (
    AcceptancePlan,
    AgentType,
    ApprovalStatus,
    GateEvidence,
    GateResult,
    GateType,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
    compute_packet_digest,
    compute_review_digest,
)

BASE_COMMIT = "1111111111111111111111111111111111111111"
RESULT_COMMIT = "2222222222222222222222222222222222222222"


@pytest_asyncio.fixture
async def db_session():
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


def make_test_envelope(
    required_gates: list[GateType] | None = None,
    require_packet_binding: bool = False,
    require_independent_review: bool | None = None,
) -> TaskEnvelope:
    task_id = f"tsk_{uuid.uuid4().hex[:8]}"
    gates = required_gates if required_gates is not None else [GateType.UNIT_TEST]
    req_review = (
        require_independent_review
        if require_independent_review is not None
        else (GateType.INDEPENDENT_REVIEW in gates)
    )
    return TaskEnvelope(
        task_id=task_id,
        project_id="prj_gate_integrity",
        repo="/tmp/test_repo",
        base_commit=BASE_COMMIT,
        objective="Verify gate evidence integrity",
        allowed_paths=["src"],
        require_packet_binding=require_packet_binding,
        requires_approval=False,
        acceptance_plan=AcceptancePlan(
            required_gates=gates,
            commands=[],
            require_independent_review=req_review,
        ),
    )


def make_result_with_evidence(
    envelope: TaskEnvelope,
    evidence_items: list[GateEvidence],
    attempt_id: str | None = None,
    all_passed: bool = True,
    status: TaskStatus = TaskStatus.COMPLETED,
) -> TaskResult:
    att_id = attempt_id or f"att_{uuid.uuid4().hex[:6]}"
    digest = compute_packet_digest(envelope) if envelope.require_packet_binding else None
    return TaskResult(
        attempt_id=att_id,
        task_id=envelope.task_id,
        status=status,
        agent=AgentType.ANTIGRAVITY,
        model="test-model",
        base_commit=envelope.base_commit,
        result_commit=RESULT_COMMIT,
        packet_sha256=digest,
        files_changed=["src/code.py"],
        gate_result=GateResult(
            task_id=envelope.task_id,
            attempt_id=att_id,
            all_passed=all_passed,
            evidence_items=evidence_items,
        ),
    )


@pytest.mark.asyncio
async def test_empty_evidence_rejection(db_session: AsyncSession):
    """Requirement 1: If required_gates has executable gates, evidence_items cannot be empty."""
    envelope = make_test_envelope(required_gates=[GateType.UNIT_TEST])
    await TaskEngine.submit_task(db_session, envelope)
    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    # TaskResult with empty evidence_items
    result = make_result_with_evidence(envelope, evidence_items=[])
    success = await TaskEngine.submit_result(db_session, result, task_rec.lease_token, "worker-1")
    assert success is False

    # Assert task state remains in LEASED/RUNNING, not completed
    task = await db_session.get(TaskRecord, envelope.task_id)
    assert task is not None
    assert task.status != TaskStatus.COMPLETED.value
    assert task.status != TaskStatus.VERIFIED.value


@pytest.mark.asyncio
async def test_missing_required_gate_evidence_rejection(db_session: AsyncSession):
    """Requirement 2: Every executable gate listed in required_gates MUST have a passing evidence item."""
    envelope = make_test_envelope(required_gates=[GateType.UNIT_TEST, GateType.LINT])
    await TaskEngine.submit_task(db_session, envelope)
    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    # Missing GateType.LINT evidence
    evidence = [
        GateEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:6]}",
            gate_type=GateType.UNIT_TEST,
            passed=True,
            summary="Unit tests passed",
        )
    ]
    result = make_result_with_evidence(envelope, evidence_items=evidence)
    success = await TaskEngine.submit_result(db_session, result, task_rec.lease_token, "worker-1")
    assert success is False

    task = await db_session.get(TaskRecord, envelope.task_id)
    assert task is not None
    assert task.status != TaskStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_duplicate_evidence_same_gate_type_rejection(db_session: AsyncSession):
    """Requirement 3: There cannot be multiple evidence items for the same gate_type."""
    envelope = make_test_envelope(required_gates=[GateType.UNIT_TEST])
    await TaskEngine.submit_task(db_session, envelope)
    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    # Two distinct evidence items both for GateType.UNIT_TEST
    evidence = [
        GateEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:6]}",
            gate_type=GateType.UNIT_TEST,
            passed=True,
            summary="Unit tests pass 1",
        ),
        GateEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:6]}",
            gate_type=GateType.UNIT_TEST,
            passed=True,
            summary="Unit tests pass 2",
        ),
    ]
    result = make_result_with_evidence(envelope, evidence_items=evidence)
    success = await TaskEngine.submit_result(db_session, result, task_rec.lease_token, "worker-1")
    assert success is False


@pytest.mark.asyncio
async def test_unexpected_gate_type_rejection(db_session: AsyncSession):
    """Requirement 4: An evidence item cannot have a gate_type that was not requested in required_gates."""
    envelope = make_test_envelope(required_gates=[GateType.UNIT_TEST])
    await TaskEngine.submit_task(db_session, envelope)
    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    # Evidence contains UNIT_TEST + extra unexpected SECURITY_SCAN
    evidence = [
        GateEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:6]}",
            gate_type=GateType.UNIT_TEST,
            passed=True,
            summary="Unit tests passed",
        ),
        GateEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:6]}",
            gate_type=GateType.SECURITY_SCAN,
            passed=True,
            summary="Security scan passed (unexpected gate)",
        ),
    ]
    result = make_result_with_evidence(envelope, evidence_items=evidence)
    success = await TaskEngine.submit_result(db_session, result, task_rec.lease_token, "worker-1")
    assert success is False


@pytest.mark.asyncio
async def test_valid_gate_evidence_passes(db_session: AsyncSession):
    """Sanity verification: Exact match of passing evidence items for declared required gates succeeds."""
    envelope = make_test_envelope(required_gates=[GateType.UNIT_TEST, GateType.LINT])
    await TaskEngine.submit_task(db_session, envelope)
    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    evidence = [
        GateEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:6]}",
            gate_type=GateType.UNIT_TEST,
            passed=True,
            summary="Unit tests passed",
        ),
        GateEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:6]}",
            gate_type=GateType.LINT,
            passed=True,
            summary="Lint passed",
        ),
    ]
    result = make_result_with_evidence(envelope, evidence_items=evidence)
    success = await TaskEngine.submit_result(db_session, result, task_rec.lease_token, "worker-1")
    assert success is True

    # Assert task state in DB transitions to VERIFIED
    task = await db_session.get(TaskRecord, envelope.task_id)
    assert task is not None
    assert task.status == TaskStatus.VERIFIED.value

    # Assert evidence records in DB
    ev_query = await db_session.execute(
        select(GateEvidenceRecord).where(GateEvidenceRecord.task_id == envelope.task_id)
    )
    records = ev_query.scalars().all()
    assert len(records) == 2
    assert {r.gate_type for r in records} == {"unit_test", "lint"}


# ---------------------------------------------------------------------------
# P4.1-R1 New Test Cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deferred_review_gate_accepted_without_evidence(db_session: AsyncSession):
    """Test 1: required_gates=[UNIT_TEST, INDEPENDENT_REVIEW], executor submits UNIT_TEST only -> accepted."""
    envelope = make_test_envelope(
        required_gates=[GateType.UNIT_TEST, GateType.INDEPENDENT_REVIEW],
    )
    await TaskEngine.submit_task(db_session, envelope)
    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    # Executor supplies only UNIT_TEST evidence (INDEPENDENT_REVIEW is deferred)
    evidence = [
        GateEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:6]}",
            gate_type=GateType.UNIT_TEST,
            passed=True,
            summary="Unit tests passed",
        )
    ]
    result = make_result_with_evidence(envelope, evidence_items=evidence)
    success = await TaskEngine.submit_result(db_session, result, task_rec.lease_token, "worker-1")
    assert success is True

    # Database assertions: Task is in WAITING_APPROVAL pending independent review
    task = await db_session.get(TaskRecord, envelope.task_id)
    assert task is not None
    assert task.status == TaskStatus.WAITING_APPROVAL.value

    # Attempt record exists
    attempt = await db_session.get(AttemptRecord, result.attempt_id)
    assert attempt is not None

    # Pending review approval record is created
    appr = await db_session.scalar(
        select(ApprovalRecord).where(
            ApprovalRecord.task_id == envelope.task_id,
            ApprovalRecord.attempt_id == result.attempt_id,
            ApprovalRecord.approval_type == "task_review",
            ApprovalRecord.status == ApprovalStatus.PENDING.value,
        )
    )
    assert appr is not None


@pytest.mark.asyncio
async def test_executor_supplied_review_evidence_rejected(db_session: AsyncSession):
    """Test 2: executor submits independent-review evidence -> rejected (submit_result returns False)."""
    envelope = make_test_envelope(
        required_gates=[GateType.UNIT_TEST, GateType.INDEPENDENT_REVIEW],
    )
    await TaskEngine.submit_task(db_session, envelope)
    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    # Executor tries to supply INDEPENDENT_REVIEW evidence
    evidence = [
        GateEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:6]}",
            gate_type=GateType.UNIT_TEST,
            passed=True,
            summary="Unit tests passed",
        ),
        GateEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:6]}",
            gate_type=GateType.INDEPENDENT_REVIEW,
            passed=True,
            summary="Self-signed independent review passed",
            metrics={"reviewer": "worker-1"},
        ),
    ]
    result = make_result_with_evidence(envelope, evidence_items=evidence)
    success = await TaskEngine.submit_result(db_session, result, task_rec.lease_token, "worker-1")
    assert success is False

    # Assert task did not complete or enter approval
    task = await db_session.get(TaskRecord, envelope.task_id)
    assert task is not None
    assert task.status not in {TaskStatus.COMPLETED.value, TaskStatus.VERIFIED.value, TaskStatus.WAITING_APPROVAL.value}


@pytest.mark.asyncio
async def test_trusted_review_approval_appends_evidence(db_session: AsyncSession):
    """Test 3: required_gates=[INDEPENDENT_REVIEW], executor submits empty evidence (accepted since deferred),
    then simulate trusted review approval using TaskEngine approval decision and verify evidence is appended
    and task becomes VERIFIED.
    """
    envelope = make_test_envelope(
        required_gates=[GateType.INDEPENDENT_REVIEW],
    )
    await TaskEngine.submit_task(db_session, envelope)
    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    # Executor submits empty evidence since the only required gate is deferred
    result = make_result_with_evidence(envelope, evidence_items=[])
    success = await TaskEngine.submit_result(db_session, result, task_rec.lease_token, "worker-1")
    assert success is True

    # Task is now in WAITING_APPROVAL
    task = await db_session.get(TaskRecord, envelope.task_id)
    assert task is not None
    assert task.status == TaskStatus.WAITING_APPROVAL.value

    # Compute expected review digest
    review_digest = compute_review_digest(result, "worker-1")

    # Simulate trusted review approval via TaskEngine approval method
    decide_fn = getattr(TaskEngine, "submit_approval", TaskEngine.decide_task_approval)
    approved_task = await decide_fn(
        db_session,
        task_id=envelope.task_id,
        approved=True,
        decided_by="trusted-reviewer-user",
        review_sha256=review_digest,
    )
    assert approved_task is not None
    assert approved_task.status == TaskStatus.VERIFIED.value

    # Verify attempt record in DB contains appended independent_review evidence
    attempt = await db_session.get(AttemptRecord, result.attempt_id)
    assert attempt is not None
    gate_res_data = attempt.gate_result_json
    if isinstance(gate_res_data, str):
        gate_res_data = json.loads(gate_res_data)
    evidence_items = gate_res_data.get("evidence_items", [])
    review_evs = [ev for ev in evidence_items if ev.get("gate_type") == "independent_review"]
    assert len(review_evs) == 1
    assert review_evs[0]["passed"] is True
    assert review_evs[0]["metrics"].get("reviewer_identity") == "trusted-reviewer-user"


@pytest.mark.asyncio
async def test_zero_required_gates_rejects_evidence(db_session: AsyncSession):
    """Test 4: required_gates=[] with unexpected evidence -> rejected (submit_result returns False)."""
    envelope = make_test_envelope(required_gates=[])
    await TaskEngine.submit_task(db_session, envelope)
    leased = await TaskEngine.lease_next_task(db_session, "worker-1")
    assert leased is not None
    task_rec, _ = leased

    # Submit unexpected evidence when zero gates were required
    evidence = [
        GateEvidence(
            evidence_id=f"ev_{uuid.uuid4().hex[:6]}",
            gate_type=GateType.UNIT_TEST,
            passed=True,
            summary="Unsolicited unit test",
        )
    ]
    result = make_result_with_evidence(envelope, evidence_items=evidence)
    success = await TaskEngine.submit_result(db_session, result, task_rec.lease_token, "worker-1")
    assert success is False

    # Assert task did not complete
    task = await db_session.get(TaskRecord, envelope.task_id)
    assert task is not None
    assert task.status != TaskStatus.COMPLETED.value
    assert task.status != TaskStatus.VERIFIED.value

    # Verify that submitting empty evidence for zero required gates succeeds
    result_empty = make_result_with_evidence(envelope, evidence_items=[])
    success_empty = await TaskEngine.submit_result(
        db_session, result_empty, task_rec.lease_token, "worker-1"
    )
    assert success_empty is True
    task_after = await db_session.get(TaskRecord, envelope.task_id)
    assert task_after is not None
    assert task_after.status == TaskStatus.VERIFIED.value
