from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from alpha_core.db.connection import Base, get_engine, get_session_factory
from alpha_core.db.models import AuditEventRecord
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import (
    AcceptancePlan,
    AgentType,
    GateEvidence,
    GateResult,
    GateType,
    RiskClass,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
)
from alpha_worker.daemon import AlphaWorkerDaemon
from alpha_worker.preview import PreviewMetadata, PreviewStatus


@pytest.fixture
async def memory_db():
    engine = get_engine()
    async with engine.begin() as conn:
        # This lifecycle module leases globally queued tasks. Reset first so
        # earlier modules cannot alter which task this proof executes.
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def fake_daemon(tmp_path, monkeypatch):
    d = AlphaWorkerDaemon(worker_id="test-worker")
    d.preview_supervisor._state_dir = tmp_path / "previews"
    d.preview_supervisor._state_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        d.worktree_mgr, "create_or_resume_worktree", MagicMock(return_value=tmp_path / "worktree")
    )
    monkeypatch.setattr(d.worktree_mgr, "remove_worktree", MagicMock())
    monkeypatch.setattr(
        d.health_checker, "evaluate_worker_health", MagicMock(return_value=("online", {}))
    )
    return d


@pytest.mark.asyncio
async def test_happy_path_kernel_proof(memory_db, fake_daemon, tmp_path, monkeypatch):
    session = memory_db
    proj = await TaskEngine.create_project(
        session, "prj_status", "Alpha Status Page", str(tmp_path / "repo")
    )

    envelope = TaskEnvelope(
        task_id="tsk_status_01",
        project_id=proj.id,
        repo=str(tmp_path / "repo"),
        objective="Build responsive status page",
        allowed_paths=["."],
        risk_class=RiskClass.LOW,
        preferred_agent=AgentType.ANTIGRAVITY,
        requires_approval=True,
        retain_worktree_for_preview=True,
        acceptance_plan=AcceptancePlan(
            require_independent_review=False, required_gates=[GateType.BROWSER_SMOKE]
        ), base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

    task = await TaskEngine.submit_task(session, envelope)
    assert task.status == TaskStatus.WAITING_APPROVAL.value

    await TaskEngine.decide_task_approval(session, task.id, approved=True, decided_by="founder")
    await session.refresh(task)
    assert task.status == TaskStatus.QUEUED.value

    gate_res = GateResult(
        task_id="tsk_status_01",
        attempt_id="att_1",
        all_passed=True,
        evidence_items=[
            GateEvidence(
                evidence_id="ev_1",
                gate_type=GateType.BROWSER_SMOKE,
                passed=True,
                summary="QA pass",
            )
        ],
    )
    mock_adapter_result = TaskResult(
        attempt_id="att_1",
        task_id="tsk_status_01",
        status=TaskStatus.VERIFIED,
        agent=AgentType.ANTIGRAVITY,
        model="test",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        result_commit="HEAD",
        gate_result=gate_res,
    )
    monkeypatch.setattr(
        fake_daemon,
        "select_adapter",
        MagicMock(return_value=MagicMock(execute=AsyncMock(return_value=mock_adapter_result))),
    )

    mock_meta = PreviewMetadata(
        task_id="tsk_status_01",
        project_id=proj.id,
        worktree_path=tmp_path / "wt",
        port=8080,
        url="http://127.0.0.1:8080",
        status=PreviewStatus.HEALTHY,
    )
    monkeypatch.setattr(
        fake_daemon.preview_supervisor, "start_preview", MagicMock(return_value=mock_meta)
    )

    processed = await fake_daemon.execute_task_cycle(session)
    assert processed is True

    await session.refresh(task)
    assert task.status == TaskStatus.VERIFIED.value

    # Check that AuditEventRecord for result_submitted contains preview_evidence
    res = await session.execute(
        select(AuditEventRecord).where(
            (AuditEventRecord.task_id == "tsk_status_01")
            & (AuditEventRecord.event_type == "result_submitted")
        )
    )
    audit = res.scalar_one_or_none()
    assert audit is not None
    assert "preview_evidence" in audit.details_json
    assert audit.details_json["preview_evidence"]["url"] == "http://127.0.0.1:8080"


@pytest.mark.asyncio
async def test_missing_approval(memory_db, fake_daemon, tmp_path):
    session = memory_db
    proj = await TaskEngine.create_project(session, "prj_status_2", "Status", str(tmp_path))

    envelope = TaskEnvelope(
        task_id="tsk_status_02",
        project_id=proj.id,
        repo=str(tmp_path),
        objective="Build",
        allowed_paths=["."],
        requires_approval=True, base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    task = await TaskEngine.submit_task(session, envelope)
    assert task.status == TaskStatus.WAITING_APPROVAL.value

    processed = await fake_daemon.execute_task_cycle(session)
    assert processed is False


@pytest.mark.asyncio
async def test_agy_nonzero_exit(memory_db, fake_daemon, tmp_path, monkeypatch):
    session = memory_db
    proj = await TaskEngine.create_project(session, "prj_status_3", "Status", str(tmp_path))

    envelope = TaskEnvelope(
        task_id="tsk_status_03",
        project_id=proj.id,
        repo=str(tmp_path),
        objective="Build",
        allowed_paths=["."],
        requires_approval=False, base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    task = await TaskEngine.submit_task(session, envelope)

    mock_adapter_result = TaskResult(
        attempt_id="att_1",
        task_id="tsk_status_03",
        status=TaskStatus.RETRYABLE_FAILED,
        agent=AgentType.ANTIGRAVITY,
        model="test",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        blockers=["Nonzero exit code 1"],
    )
    monkeypatch.setattr(
        fake_daemon,
        "select_adapter",
        MagicMock(return_value=MagicMock(execute=AsyncMock(return_value=mock_adapter_result))),
    )

    processed = await fake_daemon.execute_task_cycle(session)
    assert processed is True

    await session.refresh(task)
    assert task.status == TaskStatus.RETRYABLE_FAILED.value


@pytest.mark.asyncio
async def test_preview_unhealthy(memory_db, fake_daemon, tmp_path, monkeypatch):
    session = memory_db
    proj = await TaskEngine.create_project(session, "prj_status_4", "Status", str(tmp_path))

    envelope = TaskEnvelope(
        task_id="tsk_status_04",
        project_id=proj.id,
        repo=str(tmp_path),
        objective="Build",
        allowed_paths=["."],
        requires_approval=False,
        retain_worktree_for_preview=True, base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    task = await TaskEngine.submit_task(session, envelope)

    mock_adapter_result = TaskResult(
        attempt_id="att_1",
        task_id="tsk_status_04",
        status=TaskStatus.VERIFIED,
        agent=AgentType.ANTIGRAVITY,
        model="test",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        gate_result=GateResult(
            task_id="tsk_status_04",
            attempt_id="att_1",
            all_passed=True,
            evidence_items=[
                GateEvidence(
                    evidence_id="ev_1",
                    gate_type=GateType.BROWSER_SMOKE,
                    passed=True,
                    summary="QA pass",
                )
            ],
        ),
    )
    monkeypatch.setattr(
        fake_daemon,
        "select_adapter",
        MagicMock(return_value=MagicMock(execute=AsyncMock(return_value=mock_adapter_result))),
    )

    monkeypatch.setattr(
        fake_daemon.preview_supervisor,
        "start_preview",
        MagicMock(side_effect=Exception("Failed to bind port")),
    )

    processed = await fake_daemon.execute_task_cycle(session)
    assert processed is True

    await session.refresh(task)
    assert task.status == TaskStatus.RETRYABLE_FAILED.value


@pytest.mark.asyncio
async def test_unknown_listener(memory_db, fake_daemon, tmp_path, monkeypatch):
    session = memory_db
    proj = await TaskEngine.create_project(session, "prj_status_5", "Status", str(tmp_path))

    envelope = TaskEnvelope(
        task_id="tsk_status_05",
        project_id=proj.id,
        repo=str(tmp_path),
        objective="Build",
        allowed_paths=["."],
        requires_approval=False,
        retain_worktree_for_preview=True, base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    task = await TaskEngine.submit_task(session, envelope)

    mock_adapter_result = TaskResult(
        attempt_id="att_1",
        task_id="tsk_status_05",
        status=TaskStatus.VERIFIED,
        agent=AgentType.ANTIGRAVITY,
        model="test",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        gate_result=GateResult(
            task_id="tsk_status_05",
            attempt_id="att_1",
            all_passed=True,
            evidence_items=[
                GateEvidence(
                    evidence_id="ev_1",
                    gate_type=GateType.BROWSER_SMOKE,
                    passed=True,
                    summary="QA pass",
                )
            ],
        ),
    )
    monkeypatch.setattr(
        fake_daemon,
        "select_adapter",
        MagicMock(return_value=MagicMock(execute=AsyncMock(return_value=mock_adapter_result))),
    )

    monkeypatch.setattr(
        fake_daemon.preview_supervisor,
        "start_preview",
        MagicMock(side_effect=RuntimeError("unknown listener on port 4173")),
    )

    processed = await fake_daemon.execute_task_cycle(session)
    assert processed is True

    await session.refresh(task)
    assert task.status == TaskStatus.RETRYABLE_FAILED.value
