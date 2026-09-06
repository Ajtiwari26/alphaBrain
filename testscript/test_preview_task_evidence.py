import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import AgentType, GateResult, TaskEnvelope, TaskResult, TaskStatus
from alpha_worker.daemon import AlphaWorkerDaemon
from alpha_worker.preview import PreviewMetadata, PreviewStatus, PreviewSupervisor


def make_daemon(tmp_path, monkeypatch):
    d = AlphaWorkerDaemon(worker_id="test")
    d.preview_supervisor._state_dir = tmp_path / "previews"
    d.preview_supervisor._state_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        d.worktree_mgr, "create_or_resume_worktree", MagicMock(return_value=tmp_path / "worktree")
    )
    monkeypatch.setattr(
        d.health_checker, "evaluate_worker_health", MagicMock(return_value=("online", {}))
    )
    return d


@pytest.mark.asyncio
async def test_healthy_retained_preview_evidence(tmp_path, monkeypatch):
    daemon = make_daemon(tmp_path, monkeypatch)
    mock_start_preview = MagicMock(
        return_value=PreviewMetadata(
            task_id="tsk_1",
            project_id="p1",
            worktree_path=tmp_path / "worktree",
            port=8080,
            url="http://local:8080/",
            status=PreviewStatus.HEALTHY,
        )
    )
    monkeypatch.setattr(daemon.preview_supervisor, "start_preview", mock_start_preview)

    # Non-preview task
    mock_result = TaskResult(
        attempt_id="a",
        task_id="tsk_1",
        status=TaskStatus.VERIFIED,
        agent=AgentType.ANTIGRAVITY,
        model="x",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    monkeypatch.setattr(
        daemon,
        "select_adapter",
        MagicMock(return_value=MagicMock(execute=AsyncMock(return_value=mock_result))),
    )

    mock_submit = AsyncMock()
    monkeypatch.setattr(TaskEngine, "submit_result", mock_submit)

    envelope = TaskEnvelope(
        task_id="tsk_1",
        project_id="p1",
        repo="r",
        objective="o",
        allowed_paths=["."],
        retain_worktree_for_preview=True,
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    monkeypatch.setattr(
        TaskEngine,
        "lease_next_task",
        AsyncMock(return_value=(MagicMock(lease_token="t"), envelope)),
    )

    await daemon.execute_task_cycle(AsyncMock())

    mock_start_preview.assert_called_once()
    sub_res = mock_submit.call_args[0][1]
    assert sub_res.preview_evidence is not None
    assert sub_res.preview_evidence["url"] == "http://local:8080/"
    assert sub_res.preview_evidence["status"] == "healthy"


@pytest.mark.asyncio
async def test_non_preview_task_behavior(tmp_path, monkeypatch):
    daemon = make_daemon(tmp_path, monkeypatch)
    mock_start_preview = MagicMock()
    monkeypatch.setattr(daemon.preview_supervisor, "start_preview", mock_start_preview)

    mock_result = TaskResult(
        attempt_id="a",
        task_id="tsk_2",
        status=TaskStatus.VERIFIED,
        agent=AgentType.ANTIGRAVITY,
        model="x",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    monkeypatch.setattr(
        daemon,
        "select_adapter",
        MagicMock(return_value=MagicMock(execute=AsyncMock(return_value=mock_result))),
    )
    mock_submit = AsyncMock()
    monkeypatch.setattr(TaskEngine, "submit_result", mock_submit)

    envelope = TaskEnvelope(
        task_id="tsk_2",
        project_id="p1",
        repo="r",
        objective="o",
        allowed_paths=["."],
        retain_worktree_for_preview=False,
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    monkeypatch.setattr(
        TaskEngine,
        "lease_next_task",
        AsyncMock(return_value=(MagicMock(lease_token="t"), envelope)),
    )

    await daemon.execute_task_cycle(AsyncMock())

    mock_start_preview.assert_not_called()
    sub_res = mock_submit.call_args[0][1]
    assert sub_res.preview_evidence is None


@pytest.mark.asyncio
async def test_failed_http_preview_startup(tmp_path, monkeypatch):
    daemon = make_daemon(tmp_path, monkeypatch)
    mock_start_preview = MagicMock(side_effect=RuntimeError("Crash"))
    monkeypatch.setattr(daemon.preview_supervisor, "start_preview", mock_start_preview)

    mock_result = TaskResult(
        attempt_id="a",
        task_id="tsk_3",
        status=TaskStatus.VERIFIED,
        agent=AgentType.ANTIGRAVITY,
        model="x",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    monkeypatch.setattr(
        daemon,
        "select_adapter",
        MagicMock(return_value=MagicMock(execute=AsyncMock(return_value=mock_result))),
    )
    mock_submit = AsyncMock()
    monkeypatch.setattr(TaskEngine, "submit_result", mock_submit)

    envelope = TaskEnvelope(
        task_id="tsk_3",
        project_id="p1",
        repo="r",
        objective="o",
        allowed_paths=["."],
        retain_worktree_for_preview=True,
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    monkeypatch.setattr(
        TaskEngine,
        "lease_next_task",
        AsyncMock(return_value=(MagicMock(lease_token="t"), envelope)),
    )

    await daemon.execute_task_cycle(AsyncMock())

    sub_res = mock_submit.call_args[0][1]
    assert sub_res.status == TaskStatus.RETRYABLE_FAILED
    assert any("Crash" in str(b) for b in sub_res.blockers)
    assert sub_res.preview_evidence is None


@pytest.mark.asyncio
async def test_restart_recovery(tmp_path, monkeypatch):
    daemon = make_daemon(tmp_path, monkeypatch)
    meta = PreviewMetadata(
        task_id="tsk_4",
        project_id="p1",
        worktree_path=tmp_path,
        port=80,
        url="",
        status=PreviewStatus.HEALTHY,
    )
    (daemon.preview_supervisor._state_dir / "tsk_4.json").write_text(json.dumps(meta.to_dict()))

    monkeypatch.setattr(daemon.preview_supervisor, "check_health", MagicMock(return_value=False))
    monkeypatch.setattr(daemon.preview_supervisor, "restart_unhealthy_preview", MagicMock())

    mock_block = AsyncMock()
    monkeypatch.setattr(TaskEngine, "block_task", mock_block)

    await daemon._check_managed_previews(AsyncMock())

    daemon.preview_supervisor.restart_unhealthy_preview.assert_called_once()
    mock_block.assert_not_called()


@pytest.mark.asyncio
async def test_restart_limit_failure(tmp_path, monkeypatch):
    daemon = make_daemon(tmp_path, monkeypatch)
    meta = PreviewMetadata(
        task_id="tsk_5",
        project_id="p1",
        worktree_path=tmp_path,
        port=80,
        url="",
        status=PreviewStatus.HEALTHY,
        restart_count=3,
        health_error="Bad",
    )
    (daemon.preview_supervisor._state_dir / "tsk_5.json").write_text(json.dumps(meta.to_dict()))

    monkeypatch.setattr(daemon.preview_supervisor, "check_health", MagicMock(return_value=False))
    monkeypatch.setattr(daemon.preview_supervisor, "terminate_preview", MagicMock())

    mock_block = AsyncMock()
    monkeypatch.setattr(TaskEngine, "block_task", mock_block)

    await daemon._check_managed_previews(AsyncMock())

    daemon.preview_supervisor.terminate_preview.assert_called_once()
    mock_block.assert_called_once()
    assert "exceeded max restarts (3)" in mock_block.call_args[1]["reason"]


@pytest.mark.asyncio
async def test_durable_evidence_restored_after_new_supervisor(tmp_path, monkeypatch):
    daemon = make_daemon(tmp_path, monkeypatch)
    meta = PreviewMetadata(
        task_id="tsk_6",
        project_id="p1",
        worktree_path=tmp_path,
        port=80,
        url="",
        status=PreviewStatus.HEALTHY,
    )
    daemon.preview_supervisor.save_persisted_metadata(meta)

    # New instance
    new_supervisor = PreviewSupervisor(state_dir=daemon.preview_supervisor._state_dir)
    loaded = new_supervisor.load_persisted_metadata("tsk_6")

    assert loaded is not None
    assert loaded.status == PreviewStatus.HEALTHY
    assert loaded.task_id == "tsk_6"


@pytest.mark.asyncio
async def test_preview_eligibility_verified_without_gate():
    d = AlphaWorkerDaemon(worker_id="test")
    env = TaskEnvelope(
        task_id="t1",
        project_id="p1",
        objective="obj",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        preferred_agent=AgentType.ANTIGRAVITY,
        repo="repo",
        allowed_paths=["src/"],
        retain_worktree_for_preview=True,
    )
    # Verified without gate result -> eligible
    res = TaskResult(
        attempt_id="a1",
        task_id="t1",
        status=TaskStatus.VERIFIED,
        agent=AgentType.ANTIGRAVITY,
        model="x",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    assert d._is_eligible_for_preview(env, res) is True


@pytest.mark.asyncio
async def test_preview_eligibility_completed_missing_or_failed_gates():
    d = AlphaWorkerDaemon(worker_id="test")
    env = TaskEnvelope(
        task_id="t1",
        project_id="p1",
        objective="obj",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        preferred_agent=AgentType.ANTIGRAVITY,
        repo="repo",
        allowed_paths=["src/"],
        retain_worktree_for_preview=True,
    )
    # Missing gate result -> not eligible
    res = TaskResult(
        attempt_id="a1",
        task_id="t1",
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="x",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    assert d._is_eligible_for_preview(env, res) is False

    # Failed gates -> not eligible
    res.gate_result = GateResult(task_id="t1", attempt_id="a1", all_passed=False, evidence_items=[])
    assert d._is_eligible_for_preview(env, res) is False


@pytest.mark.asyncio
async def test_preview_eligibility_completed_passed_gates():
    d = AlphaWorkerDaemon(worker_id="test")
    env = TaskEnvelope(
        task_id="t1",
        project_id="p1",
        objective="obj",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        preferred_agent=AgentType.ANTIGRAVITY,
        repo="repo",
        allowed_paths=["src/"],
        retain_worktree_for_preview=True,
    )
    # Passed gates -> eligible
    res = TaskResult(
        attempt_id="a1",
        task_id="t1",
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="x",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        gate_result=GateResult(task_id="t1", attempt_id="a1", all_passed=True, evidence_items=[]),
    )
    assert d._is_eligible_for_preview(env, res) is True


@pytest.mark.asyncio
async def test_preview_eligibility_failed_status_denied():
    d = AlphaWorkerDaemon(worker_id="test")
    env = TaskEnvelope(
        task_id="t1",
        project_id="p1",
        objective="obj",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        preferred_agent=AgentType.ANTIGRAVITY,
        repo="repo",
        allowed_paths=["src/"],
        retain_worktree_for_preview=True,
    )
    res = TaskResult(
        attempt_id="a1",
        task_id="t1",
        status=TaskStatus.RETRYABLE_FAILED,
        agent=AgentType.ANTIGRAVITY,
        model="x",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    assert d._is_eligible_for_preview(env, res) is False


@pytest.mark.asyncio
async def test_preview_eligibility_remote_path_same_predicate(monkeypatch):
    d = AlphaWorkerDaemon(worker_id="test")
    d.preview_supervisor = MagicMock()
    d.control_plane = MagicMock()
    d.control_plane.submit_result = AsyncMock()
    d.spool = MagicMock()
    d.worktree_mgr = MagicMock()
    from alpha_protocol.worker import WorkerHealth

    d.health_checker.evaluate_worker_health = MagicMock(
        return_value=(
            WorkerHealth.ONLINE,
            {"battery_percentage": 100, "is_ac_power": True, "thermal_state": "nominal"},
        )
    )

    env = TaskEnvelope(
        task_id="t1",
        project_id="p1",
        objective="obj",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        preferred_agent=AgentType.ANTIGRAVITY,
        repo="repo",
        allowed_paths=["src/"],
        retain_worktree_for_preview=True,
    )
    res = TaskResult(
        attempt_id="a1",
        task_id="t1",
        status=TaskStatus.COMPLETED,
        agent=AgentType.ANTIGRAVITY,
        model="x",
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        gate_result=GateResult(task_id="t1", attempt_id="a1", all_passed=True, evidence_items=[]),
    )

    # We bypass actual adapter logic to inject the verified response directly into _execute_remote_cycle
    monkeypatch.setattr(
        d, "select_adapter", MagicMock(return_value=MagicMock(execute=AsyncMock(return_value=res)))
    )

    class FakeLease:
        task = env
        lease_token = "token1"

    monkeypatch.setattr(d.control_plane, "lease_next", AsyncMock(return_value=FakeLease()))
    monkeypatch.setattr(d.control_plane, "report_health", AsyncMock())
    monkeypatch.setattr(d.control_plane, "register", AsyncMock())
    monkeypatch.setattr(d.spool, "replay", AsyncMock())
    d.control_store = MagicMock()
    d.control_store.read().paused = False

    await d.execute_remote_cycle()

    d.preview_supervisor.start_preview.assert_called_once()
    assert d.worktree_mgr.remove_worktree.call_count == 0
