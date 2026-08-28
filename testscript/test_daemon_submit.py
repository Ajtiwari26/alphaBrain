from unittest.mock import AsyncMock, MagicMock

import pytest

from alpha_core.db.models import TaskRecord
from alpha_protocol.enums import RiskClass
from alpha_protocol.task import AcceptancePlan, TaskEnvelope, TaskResult, TaskStatus
from alpha_worker.daemon import AlphaWorkerDaemon


@pytest.mark.asyncio
async def test_daemon_failed_submit_returns_false_and_does_not_log_completed(monkeypatch):
    daemon = AlphaWorkerDaemon(worker_id="test_worker")
    daemon.health_checker = MagicMock()
    daemon.health_checker.evaluate_worker_health.return_value = ("ok", {})
    daemon.worktree_mgr = MagicMock()
    daemon.worktree_mgr.create_or_resume_worktree.return_value = "/tmp/worktree"

    task_record = TaskRecord(
        id="tsk_123",
        project_id="prj_1",
        repo="repo",
        objective="obj",
        details_json="{}",
        lease_token="token",
    )
    envelope = TaskEnvelope(
        task_id="tsk_123",
        project_id="prj_1",
        repo="repo",
        objective="obj",
        base_commit="abcd",
        allowed_paths=["."],
        acceptance_plan=AcceptancePlan(commands=[]),
        risk_class=RiskClass.LOW,
    )

    from alpha_core.state.task_engine import TaskEngine

    monkeypatch.setattr(
        TaskEngine, "lease_next_task", AsyncMock(return_value=(task_record, envelope))
    )

    mock_adapter = MagicMock()
    result = TaskResult(
        attempt_id="att_1",
        task_id="tsk_123",
        status=TaskStatus.COMPLETED,
        agent="antigravity",
        model="gemini",
        base_commit="abcd",
    )
    mock_adapter.execute = AsyncMock(return_value=result)
    monkeypatch.setattr(daemon, "select_adapter", MagicMock(return_value=mock_adapter))

    # Mock submit_result to return False
    monkeypatch.setattr(TaskEngine, "submit_result", AsyncMock(return_value=False))

    # Capture logger
    import logging

    logger = logging.getLogger("alpha_worker")
    from io import StringIO

    stream = StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)

    # We need a dummy session
    session = MagicMock()

    res = await daemon.execute_task_cycle(session)

    assert res is False
    log_output = stream.getvalue()
    assert "Failed to persistently submit result for task tsk_123" in log_output
    assert "Completed task tsk_123" not in log_output
    logger.removeHandler(handler)
