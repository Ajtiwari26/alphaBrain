"""Tests for daemon preview eligibility and evidence ordering."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from alpha_protocol import (
    AgentType,
    GateResult,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
)
from alpha_worker.daemon import AlphaWorkerDaemon


@pytest.fixture
def base_task() -> TaskEnvelope:
    return TaskEnvelope(
        task_id="task_preview_1",
        project_id="proj_preview_1",
        objective="Preview test",
        base_commit="abc1234",
        preferred_agent=AgentType.ANTIGRAVITY,
        repo="https://github.com/test/repo.git",
        allowed_paths=["src/"],
        retain_worktree_for_preview=True,
    )


@pytest.fixture
def fake_gate_result_passed(base_task: TaskEnvelope) -> GateResult:
    return GateResult(
        task_id=base_task.task_id,
        attempt_id="att_1",
        all_passed=True,
        evidence_items=[],
    )


@pytest.fixture
def fake_gate_result_failed(base_task: TaskEnvelope) -> GateResult:
    return GateResult(
        task_id=base_task.task_id,
        attempt_id="att_1",
        all_passed=False,
        evidence_items=[],
    )


@pytest.fixture
def mock_daemon() -> AlphaWorkerDaemon:
    # Disable actual control store and health checks

    daemon = AlphaWorkerDaemon(worker_id="worker_test_1")
    from alpha_protocol.worker import WorkerHealth

    daemon.health_checker.evaluate_worker_health = MagicMock(
        return_value=(
            WorkerHealth.ONLINE,
            {"battery_percentage": 100, "is_ac_power": True, "thermal_state": "nominal"},
        )
    )

    # Mock adapter
    mock_adapter = MagicMock()
    daemon.select_adapter = MagicMock(return_value=mock_adapter)  # type: ignore[method-assign]

    # Mock preview supervisor
    daemon.preview_supervisor = MagicMock()

    # Mock WorktreeManager
    daemon.worktree_mgr = MagicMock()
    daemon.worktree_mgr.create_or_resume_worktree = MagicMock(
        return_value=Path("/tmp/fake_worktree")
    )

    return daemon


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_completed_passed_gates_starts_preview_local(
    mock_daemon: AlphaWorkerDaemon, base_task: TaskEnvelope, fake_gate_result_passed: GateResult
):
    from alpha_core.state.task_engine import TaskEngine

    # Set up adapter to return COMPLETED with passed gates
    mock_result = TaskResult(
        attempt_id="att_1",
        task_id=base_task.task_id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="test",
        base_commit="abc1234",
        gate_result=fake_gate_result_passed,
    )
    mock_daemon.select_adapter(AgentType.ANTIGRAVITY).execute = AsyncMock(return_value=mock_result)

    # Setup preview_meta return
    mock_meta = MagicMock()
    mock_meta.to_dict.return_value = {"url": "http://fake.preview", "pid": 123}
    mock_daemon.preview_supervisor.start_preview = MagicMock(return_value=mock_meta)

    # Mock TaskEngine.submit_result
    with pytest.MonkeyPatch().context() as m:
        submit_mock = AsyncMock()
        m.setattr(TaskEngine, "submit_result", submit_mock)

        # Test execute_task_cycle
        session_mock = AsyncMock()

        # We need to simulate leasing a task first?
        # Actually execute_task_cycle fetches a task. It's easier to patch the fetch.
        fetch_mock = AsyncMock()

        class FakeTaskRecord:
            lease_token = "token1"

        fetch_mock.return_value = (FakeTaskRecord(), base_task)
        m.setattr(TaskEngine, "lease_next_task", fetch_mock)

        await mock_daemon.execute_task_cycle(session_mock)

        mock_daemon.preview_supervisor.start_preview.assert_called_once_with(
            worktree_path=Path("/tmp/fake_worktree"),
            task_id=base_task.task_id,
            project_id=base_task.project_id,
        )

        submit_mock.assert_called_once()
        submitted_result = submit_mock.call_args[0][1]
        assert submitted_result.preview_evidence == mock_meta.to_dict()
        assert not mock_daemon.worktree_mgr.remove_worktree.called


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_completed_failed_gates_no_preview(
    mock_daemon: AlphaWorkerDaemon, base_task: TaskEnvelope, fake_gate_result_failed: GateResult
):
    from alpha_core.state.task_engine import TaskEngine

    mock_result = TaskResult(
        attempt_id="att_1",
        task_id=base_task.task_id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="test",
        base_commit="abc1234",
        gate_result=fake_gate_result_failed,
    )
    mock_daemon.select_adapter(AgentType.ANTIGRAVITY).execute = AsyncMock(return_value=mock_result)

    with pytest.MonkeyPatch().context() as m:
        submit_mock = AsyncMock()
        m.setattr(TaskEngine, "submit_result", submit_mock)

        class FakeTaskRecord:
            lease_token = "token1"

        fetch_mock = AsyncMock(return_value=(FakeTaskRecord(), base_task))
        m.setattr(TaskEngine, "lease_next_task", fetch_mock)

        await mock_daemon.execute_task_cycle(AsyncMock())

        mock_daemon.preview_supervisor.start_preview.assert_not_called()
        submitted_result = submit_mock.call_args[0][1]
        assert submitted_result.preview_evidence is None
        mock_daemon.worktree_mgr.remove_worktree.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_retryable_failed_no_preview(
    mock_daemon: AlphaWorkerDaemon, base_task: TaskEnvelope, fake_gate_result_passed: GateResult
):
    from alpha_core.state.task_engine import TaskEngine

    mock_result = TaskResult(
        attempt_id="att_1",
        task_id=base_task.task_id,
        status=TaskStatus.RETRYABLE_FAILED,
        agent=AgentType.ANTIGRAVITY,
        model="test",
        base_commit="abc1234",
        gate_result=fake_gate_result_passed,
    )
    mock_daemon.select_adapter(AgentType.ANTIGRAVITY).execute = AsyncMock(return_value=mock_result)

    with pytest.MonkeyPatch().context() as m:
        submit_mock = AsyncMock()
        m.setattr(TaskEngine, "submit_result", submit_mock)

        class FakeTaskRecord:
            lease_token = "token1"

        fetch_mock = AsyncMock(return_value=(FakeTaskRecord(), base_task))
        m.setattr(TaskEngine, "lease_next_task", fetch_mock)

        await mock_daemon.execute_task_cycle(AsyncMock())

        mock_daemon.preview_supervisor.start_preview.assert_not_called()
        mock_daemon.worktree_mgr.remove_worktree.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.xfail(reason="R2-R6 gap pending")
async def test_completed_passed_gates_starts_preview_remote(
    mock_daemon: AlphaWorkerDaemon, base_task: TaskEnvelope, fake_gate_result_passed: GateResult
):
    # Remote path tests
    mock_daemon.control_plane = MagicMock()
    mock_daemon.control_plane.submit_result = AsyncMock()
    mock_daemon.control_plane.register = AsyncMock()
    mock_daemon.control_plane.report_health = AsyncMock()
    mock_daemon.spool = MagicMock()
    mock_daemon.spool.replay = AsyncMock()

    mock_result = TaskResult(
        attempt_id="att_1",
        task_id=base_task.task_id,
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="test",
        base_commit="abc1234",
        gate_result=fake_gate_result_passed,
    )
    mock_daemon.select_adapter(AgentType.ANTIGRAVITY).execute = AsyncMock(return_value=mock_result)

    mock_meta = MagicMock()
    mock_meta.to_dict.return_value = {"url": "http://fake.preview", "pid": 123}
    mock_daemon.preview_supervisor.start_preview = MagicMock(return_value=mock_meta)

    class FakeLease:
        task = base_task
        lease_token = "token1"

    mock_daemon.control_plane.lease_next = AsyncMock(return_value=FakeLease())

    # We need to bypass the _execute_remote_cycle check for paused control store
    mock_daemon.control_store.read = MagicMock()
    mock_daemon.control_store.read().paused = False

    await mock_daemon.execute_remote_cycle()

    mock_daemon.preview_supervisor.start_preview.assert_called_once()
    mock_daemon.control_plane.submit_result.assert_called_once()
    submitted_result = mock_daemon.control_plane.submit_result.call_args[0][0]
    assert submitted_result.preview_evidence == mock_meta.to_dict()
    assert not mock_daemon.worktree_mgr.remove_worktree.called
