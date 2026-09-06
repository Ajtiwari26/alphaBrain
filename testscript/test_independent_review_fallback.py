"""
testscript/test_independent_review_fallback.py
Comprehensive test suite verifying Packet 3: Eliminate fabricated independent-review proof:
1. Adapter QA evidence creates no independent gate evidence.
2. Base gate runner does not mark local gates failed solely due to external independent gate.
3. TaskEngine no evidence -> WAITING_APPROVAL plus bound pending review approval.
4. Fake passed embedded evidence -> same WAITING_APPROVAL (no self-attestation bypass).
5. Founder review with exact digest completes the task.
6. Missing code_review_graph still fails verification normally.
"""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from alpha_core.config import settings
from alpha_core.db.models import ApprovalRecord, Base, TaskRecord
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
    is_legal_transition,
)
from alpha_worker.adapters.antigravity import AntigravityAdapter
from alpha_worker.adapters.base import BaseAgentAdapter


@pytest_asyncio.fixture
async def async_db() -> AsyncSession:
    engine = create_async_engine(
        f"sqlite+aiosqlite:///file:{uuid.uuid4().hex}?mode=memory&cache=shared&uri=true", echo=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


class DummyAdapter(BaseAgentAdapter):
    def __init__(self):
        super().__init__(AgentType.ANTIGRAVITY)

    def check_readiness(self) -> tuple[bool, str]:
        return True, "Ready"

    async def execute(
        self,
        task: TaskEnvelope,
        worktree_path: Path,
        base_commit: str,
    ) -> TaskResult:
        return TaskResult(
            attempt_id="att_dummy",
            task_id=task.task_id,
            status=TaskStatus.COMPLETED,
            agent=self.agent_type,
            model="test",
            base_commit=base_commit,
            result_commit=base_commit,
            files_changed=[],
            diff_summary="",
        )


# ---------------------------------------------------------------------------
# 1. Adapter QA evidence creates no independent gate
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_adapter_qa_evidence_creates_no_independent_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "ALLOWED_REPO_ROOTS", (tmp_path,))
    adapter = AntigravityAdapter()
    adapter.worktree_mgr = MagicMock()
    adapter.worktree_mgr.get_uncommitted_files = MagicMock(return_value=[])
    adapter.worktree_mgr.get_changed_files = MagicMock(return_value=[])
    adapter.worktree_mgr.get_diff_summary = MagicMock(return_value="")
    adapter.worktree_mgr.find_disallowed_changes = MagicMock(return_value=[])
    adapter.worktree_mgr.get_head_commit = MagicMock(return_value="head_commit_123")

    mock_dispatch = MagicMock()
    mock_dispatch.completed = True
    mock_dispatch.blocked_reason = None
    mock_dispatch.conversation_id = "conv_indep_01"
    mock_dispatch.tool_names = {"build_or_update_graph_tool", "get_review_context_tool"}
    mock_dispatch.transcript_path = tmp_path / "transcript.jsonl"
    monkeypatch.setattr(adapter.live_bridge, "dispatch", AsyncMock(return_value=mock_dispatch))

    task = TaskEnvelope(
        task_id="tsk_indep_qa_01",
        project_id="prj_indep",
        repo=str(tmp_path / "repo"),
        objective="Adapter execution QA evidence test",
        base_commit="a" * 40,
        allowed_paths=["."],
        acceptance_plan=AcceptancePlan(
            required_gates=[GateType.UNIT_TEST, GateType.INDEPENDENT_REVIEW],
            commands=[],
        ),
    )

    result = await adapter.execute(task, tmp_path / "worktree", "head_commit_123")
    assert result.gate_result is not None
    # Verify no INDEPENDENT_REVIEW evidence was synthesized or claimed passed by the adapter
    independent_evs = [
        ev
        for ev in result.gate_result.evidence_items
        if ev.gate_type == GateType.INDEPENDENT_REVIEW
    ]
    assert len(independent_evs) == 0


# ---------------------------------------------------------------------------
# 2. Base gate runner does not mark local gates failed solely due to external independent gate
# ---------------------------------------------------------------------------
def test_base_gate_runner_does_not_fail_on_external_independent_gate(tmp_path: Path):
    adapter = DummyAdapter()
    task = TaskEnvelope(
        task_id="tsk_base_gate_01",
        project_id="prj_base",
        repo=str(tmp_path / "repo"),
        objective="Base gate runner test",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        allowed_paths=["."],
        acceptance_plan=AcceptancePlan(
            required_gates=[GateType.UNIT_TEST, GateType.INDEPENDENT_REVIEW],
            commands=[],
        ),
    )
    # Provide successful unit test evidence
    additional = [
        GateEvidence(
            evidence_id="evi_unit",
            gate_type=GateType.UNIT_TEST,
            passed=True,
            summary="Unit tests passed",
        )
    ]
    gate_result = adapter.run_acceptance_gates(
        task, tmp_path, "att_01", additional_evidence=additional
    )
    # Since UNIT_TEST passed and INDEPENDENT_REVIEW is an external process gate, local gates all_passed is True
    assert gate_result.all_passed is True
    assert not any(ev.gate_type == GateType.INDEPENDENT_REVIEW for ev in gate_result.evidence_items)


# ---------------------------------------------------------------------------
# 3. TaskEngine no evidence -> WAITING_APPROVAL plus bound pending review
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_task_engine_no_evidence_routes_to_waiting_approval_with_bound_review(
    async_db: AsyncSession,
):
    task_id = "tsk_fallback_01"
    envelope = TaskEnvelope(
        task_id=task_id,
        project_id="prj_fallback",
        repo="/repo/test",
        objective="Verify fallback without review evidence",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        allowed_paths=["."],
        require_packet_binding=True,
        acceptance_plan=AcceptancePlan(
            require_independent_review=True,
            required_gates=[GateType.UNIT_TEST],
            commands=[],
        ),
    )
    await TaskEngine.submit_task(async_db, envelope, "prj_fallback")
    lease = await TaskEngine.lease_next_task(async_db, "worker-1")
    assert lease is not None
    task_rec, _ = lease

    attempt_id = "att_fb_01"
    digest = compute_packet_digest(envelope)
    gate_res = GateResult(
        task_id=task_id,
        attempt_id=attempt_id,
        all_passed=True,
        evidence_items=[
            GateEvidence(
                evidence_id="ev_u1",
                gate_type=GateType.UNIT_TEST,
                passed=True,
                summary="Unit tests ok",
            )
        ],
    )
    result = TaskResult(
        task_id=task_id,
        attempt_id=attempt_id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="gemini-flash",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        result_commit="HEAD",
        files_changed=[],
        diff_summary="",
        gate_result=gate_res,
        packet_sha256=digest,
    )

    submitted = await TaskEngine.submit_result(async_db, result, task_rec.lease_token, "worker-1")
    assert submitted is True

    # Task transitions to WAITING_APPROVAL
    t = await async_db.get(TaskRecord, task_id)
    assert t is not None
    assert t.status == TaskStatus.WAITING_APPROVAL.value

    # Approval record is created and bound to attempt_id
    appr = await async_db.scalar(
        select(ApprovalRecord).where(
            ApprovalRecord.task_id == task_id,
            ApprovalRecord.approval_type == "task_review",
            ApprovalRecord.status == ApprovalStatus.PENDING.value,
        )
    )
    assert appr is not None
    assert appr.attempt_id == attempt_id
    expected_review_digest = compute_review_digest(result, "worker-1")
    assert appr.scope_sha256 == expected_review_digest


# ---------------------------------------------------------------------------
# 4. Fake passed embedded evidence -> same WAITING_APPROVAL (no self-attestation)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fake_passed_embedded_evidence_routes_to_waiting_approval(
    async_db: AsyncSession,
):
    task_id = "tsk_fallback_fake_01"
    envelope = TaskEnvelope(
        task_id=task_id,
        project_id="prj_fallback",
        repo="/repo/test",
        objective="Verify fake evidence does not bypass review",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        allowed_paths=["."],
        require_packet_binding=True,
        acceptance_plan=AcceptancePlan(
            require_independent_review=True,
            required_gates=[GateType.UNIT_TEST],
            commands=[],
        ),
    )
    await TaskEngine.submit_task(async_db, envelope, "prj_fallback")
    lease = await TaskEngine.lease_next_task(async_db, "worker-fake")
    assert lease is not None
    task_rec, _ = lease

    attempt_id = "att_fb_fake_01"
    digest = compute_packet_digest(envelope)
    # Embedded fake independent review evidence claiming passed
    gate_res = GateResult(
        task_id=task_id,
        attempt_id=attempt_id,
        all_passed=True,
        evidence_items=[
            GateEvidence(
                evidence_id="ev_u1",
                gate_type=GateType.UNIT_TEST,
                passed=True,
                summary="Unit tests ok",
            ),
            GateEvidence(
                evidence_id="ev_fake_review",
                gate_type=GateType.INDEPENDENT_REVIEW,
                passed=True,
                summary="Self-signed fake independent review passed",
                metrics={"reviewer": "external-auditor-99", "score": 100},
            ),
        ],
    )
    result = TaskResult(
        task_id=task_id,
        attempt_id=attempt_id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="gemini-flash",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        result_commit="HEAD",
        files_changed=[],
        diff_summary="",
        gate_result=gate_res,
        packet_sha256=digest,
    )

    submitted = await TaskEngine.submit_result(
        async_db, result, task_rec.lease_token, "worker-fake"
    )
    # Embedded evidence does not bypass review, task routes to waiting_approval
    assert submitted is True

    # Task is not completed, routes to waiting_approval
    t = await async_db.get(TaskRecord, task_id)
    assert t is not None
    assert t.status == TaskStatus.WAITING_APPROVAL.value


# ---------------------------------------------------------------------------
# 5. Founder review with exact digest completes the task
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_founder_review_with_exact_digest_completes(async_db: AsyncSession):
    task_id = "tsk_founder_complete_01"
    envelope = TaskEnvelope(
        task_id=task_id,
        project_id="prj_founder",
        repo="/repo/test",
        objective="Founder decision completion",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        allowed_paths=["."],
        require_packet_binding=True,
        acceptance_plan=AcceptancePlan(
            require_independent_review=True,
            required_gates=[GateType.UNIT_TEST],
            commands=[],
        ),
    )
    await TaskEngine.submit_task(async_db, envelope, "prj_founder")
    lease = await TaskEngine.lease_next_task(async_db, "worker-f1")
    assert lease is not None
    task_rec, _ = lease

    attempt_id = "att_f1_01"
    digest = compute_packet_digest(envelope)
    gate_res = GateResult(
        task_id=task_id,
        attempt_id=attempt_id,
        all_passed=True,
        evidence_items=[
            GateEvidence(
                evidence_id="ev_u1",
                gate_type=GateType.UNIT_TEST,
                passed=True,
                summary="Unit tests ok",
            )
        ],
    )
    result = TaskResult(
        task_id=task_id,
        attempt_id=attempt_id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="gemini-flash",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        result_commit="HEAD",
        files_changed=[],
        diff_summary="",
        gate_result=gate_res,
        packet_sha256=digest,
    )

    await TaskEngine.submit_result(async_db, result, task_rec.lease_token, "worker-f1")
    review_digest = compute_review_digest(result, "worker-f1")

    # Wrong review digest fails
    with pytest.raises(ValueError, match="digest mismatch"):
        await TaskEngine.decide_task_approval(
            async_db,
            task_id=task_id,
            approved=True,
            decided_by="founder",
            review_sha256="wrong_digest" * 4,
        )

    # Exact review digest succeeds and transitions task to COMPLETED
    approved_task = await TaskEngine.decide_task_approval(
        async_db,
        task_id=task_id,
        approved=True,
        decided_by="founder",
        review_sha256=review_digest,
    )
    assert approved_task is not None
    assert approved_task.status == TaskStatus.COMPLETED.value


# ---------------------------------------------------------------------------
# 6. Missing code_review_graph still fails normally
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_missing_code_review_graph_fails_verification(async_db: AsyncSession):
    task_id = "tsk_crg_fail_01"
    envelope = TaskEnvelope(
        task_id=task_id,
        project_id="prj_crg",
        repo="/repo/test",
        objective="Missing code review graph failure",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        allowed_paths=["."],
        require_packet_binding=True,
        acceptance_plan=AcceptancePlan(
            required_gates=[GateType.UNIT_TEST, GateType.CODE_REVIEW_GRAPH],
            commands=[],
        ),
    )
    await TaskEngine.submit_task(async_db, envelope, "prj_crg")
    lease = await TaskEngine.lease_next_task(async_db, "worker-crg")
    assert lease is not None
    task_rec, _ = lease

    attempt_id = "att_crg_01"
    digest = compute_packet_digest(envelope)
    # Only UNIT_TEST evidence provided, CODE_REVIEW_GRAPH missing
    gate_res = GateResult(
        task_id=task_id,
        attempt_id=attempt_id,
        all_passed=True,
        evidence_items=[
            GateEvidence(
                evidence_id="ev_u1",
                gate_type=GateType.UNIT_TEST,
                passed=True,
                summary="Unit tests ok",
            )
        ],
    )
    result = TaskResult(
        task_id=task_id,
        attempt_id=attempt_id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="gemini-flash",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        result_commit="HEAD",
        files_changed=[],
        diff_summary="",
        gate_result=gate_res,
        packet_sha256=digest,
    )

    # Missing required gate CODE_REVIEW_GRAPH is rejected
    submitted = await TaskEngine.submit_result(async_db, result, task_rec.lease_token, "worker-crg")
    assert submitted is False


# ---------------------------------------------------------------------------
# 7. Canonical WAITING_APPROVAL state transitions
# ---------------------------------------------------------------------------
def test_canonical_waiting_approval_transitions():
    # Legal post-result founder review transitions
    assert is_legal_transition(TaskStatus.WAITING_APPROVAL, TaskStatus.COMPLETED) is True
    assert is_legal_transition(TaskStatus.WAITING_APPROVAL, TaskStatus.BLOCKED) is True
    # WAITING_APPROVAL -> VERIFIED is strictly NOT allowed
    assert is_legal_transition(TaskStatus.WAITING_APPROVAL, TaskStatus.VERIFIED) is False
    # Pre-execution transitions are preserved
    assert is_legal_transition(TaskStatus.WAITING_APPROVAL, TaskStatus.RUNNING) is True
    assert is_legal_transition(TaskStatus.WAITING_APPROVAL, TaskStatus.QUEUED) is True
    assert is_legal_transition(TaskStatus.WAITING_APPROVAL, TaskStatus.CANCELLED) is True


# ---------------------------------------------------------------------------
# 8. Founder review rejection blocks task
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_founder_review_rejection_blocks_task(async_db: AsyncSession):
    task_id = "tsk_founder_reject_01"
    envelope = TaskEnvelope(
        task_id=task_id,
        project_id="prj_founder_rej",
        repo="/repo/test",
        objective="Founder rejection test",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        allowed_paths=["."],
        require_packet_binding=True,
        acceptance_plan=AcceptancePlan(
            require_independent_review=True,
            required_gates=[GateType.UNIT_TEST],
            commands=[],
        ),
    )
    await TaskEngine.submit_task(async_db, envelope, "prj_founder_rej")
    lease = await TaskEngine.lease_next_task(async_db, "worker-rej")
    assert lease is not None
    task_rec, _ = lease

    attempt_id = "att_rej_01"
    digest = compute_packet_digest(envelope)
    gate_res = GateResult(
        task_id=task_id,
        attempt_id=attempt_id,
        all_passed=True,
        evidence_items=[
            GateEvidence(
                evidence_id="ev_u1",
                gate_type=GateType.UNIT_TEST,
                passed=True,
                summary="Unit tests ok",
            )
        ],
    )
    result = TaskResult(
        task_id=task_id,
        attempt_id=attempt_id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="gemini-flash",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        result_commit="HEAD",
        files_changed=[],
        diff_summary="",
        gate_result=gate_res,
        packet_sha256=digest,
    )

    await TaskEngine.submit_result(async_db, result, task_rec.lease_token, "worker-rej")
    review_digest = compute_review_digest(result, "worker-rej")

    # Rejecting with exact review digest transitions task to BLOCKED
    rejected_task = await TaskEngine.decide_task_approval(
        async_db,
        task_id=task_id,
        approved=False,
        decided_by="founder-reviewer",
        reason="Does not meet quality bar",
        review_sha256=review_digest,
    )
    assert rejected_task is not None
    assert rejected_task.status == TaskStatus.BLOCKED.value

    appr = await async_db.scalar(
        select(ApprovalRecord).where(
            ApprovalRecord.task_id == task_id,
            ApprovalRecord.approval_type == "task_review",
        )
    )
    assert appr is not None
    assert appr.status == ApprovalStatus.REJECTED.value
    assert appr.decided_by == "founder-reviewer"
