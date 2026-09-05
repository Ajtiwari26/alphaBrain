"""Conformance harness for adapter parity and normalizations."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alpha_core.config import settings
from alpha_protocol import (
    AcceptancePlan,
    AgentType,
    GateResult,
    GateType,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
)
from alpha_worker.adapters.antigravity import AntigravityAdapter
from alpha_worker.daemon import AlphaWorkerDaemon

FAKE_BASE_COMMIT = "a" * 40


@pytest.fixture
def fake_task() -> TaskEnvelope:
    return TaskEnvelope(
        task_id="task_123",
        project_id="proj_123",
        objective="Test objective",
        base_commit=FAKE_BASE_COMMIT,
        repo="https://github.com/test/repo.git",
        allowed_paths=["src", "tests"],
        preferred_agent=AgentType.ANTIGRAVITY,
        acceptance_plan=AcceptancePlan(required_gates=[GateType.CODE_REVIEW_GRAPH], commands=[]),
    )


@pytest.fixture
def fake_worktree(tmp_path: Path) -> Path:
    wt = tmp_path / "worktree"
    wt.mkdir()
    return wt


@pytest.mark.asyncio
async def test_antigravity_normalized_success(fake_task: TaskEnvelope, fake_worktree: Path):
    adapter = AntigravityAdapter()

    # Fake the dependencies
    adapter.setup_session_in_memory_graph = MagicMock(return_value=fake_worktree / "session")

    mock_dispatch = MagicMock()
    mock_dispatch.completed = True
    mock_dispatch.blocked_reason = None
    mock_dispatch.conversation_id = "conv_123"
    mock_dispatch.tool_names = {"tool1", "tool2"}
    mock_dispatch.transcript_path = fake_worktree / "session" / "transcript.md"
    mock_dispatch.qa_evidence = "Some QA evidence"
    adapter.live_bridge.dispatch = AsyncMock(return_value=mock_dispatch)

    mock_gate_result = GateResult(
        task_id=fake_task.task_id,
        attempt_id="att_123",
        all_passed=True,
        evidence_items=[],
    )
    adapter.run_acceptance_gates = MagicMock(return_value=mock_gate_result)

    adapter.worktree_mgr.get_uncommitted_files = MagicMock(return_value=["file1.py"])
    adapter.worktree_mgr.get_changed_files = MagicMock(return_value=["file1.py"])
    adapter.worktree_mgr.get_diff_summary = MagicMock(return_value="Diff summary")
    adapter.worktree_mgr.find_disallowed_changes = MagicMock(return_value=[])
    adapter.worktree_mgr.commit_changes = MagicMock(return_value="commit456")
    adapter.worktree_mgr.get_head_commit = MagicMock(return_value="commit456")

    result = await adapter.execute(fake_task, fake_worktree, fake_task.base_commit)

    assert isinstance(result, TaskResult)
    assert result.task_id == fake_task.task_id
    assert result.attempt_id.startswith("att_task_123_")
    assert result.status == TaskStatus.COMPLETED
    assert result.agent == AgentType.ANTIGRAVITY
    assert result.model == f"antigravity-{settings.ANTIGRAVITY_MODEL}"
    assert result.base_commit == FAKE_BASE_COMMIT
    assert result.result_commit == "commit456"
    assert result.files_changed == ["file1.py"]
    assert result.diff_summary == "Diff summary"
    assert result.blockers == []
    assert len(result.provenance_notes) == 2
    assert result.gate_result is not None
    assert result.gate_result.all_passed is True


@pytest.mark.asyncio
async def test_antigravity_missing_qa_manifest(fake_task: TaskEnvelope, fake_worktree: Path):
    adapter = AntigravityAdapter()
    adapter.setup_session_in_memory_graph = MagicMock(return_value=fake_worktree / "session")

    mock_dispatch = MagicMock()
    mock_dispatch.completed = True
    mock_dispatch.blocked_reason = None
    mock_dispatch.qa_evidence = None  # Missing QA manifest
    mock_dispatch.conversation_id = "conv_123"
    mock_dispatch.tool_names = set()
    mock_dispatch.transcript_path = None
    adapter.live_bridge.dispatch = AsyncMock(return_value=mock_dispatch)

    mock_gate_result = GateResult(
        task_id=fake_task.task_id,
        attempt_id="att_123",
        all_passed=True,  # Will be made False by daemon if evidence is missing
        evidence_items=[],
    )
    adapter.run_acceptance_gates = MagicMock(return_value=mock_gate_result)

    adapter.worktree_mgr.get_uncommitted_files = MagicMock(return_value=["file1.py"])
    adapter.worktree_mgr.get_changed_files = MagicMock(return_value=["file1.py"])
    adapter.worktree_mgr.get_diff_summary = MagicMock(return_value="Diff")
    adapter.worktree_mgr.find_disallowed_changes = MagicMock(return_value=[])
    adapter.worktree_mgr.commit_changes = MagicMock(return_value="commit456")
    adapter.worktree_mgr.get_head_commit = MagicMock(return_value="commit456")

    result = await adapter.execute(fake_task, fake_worktree, fake_task.base_commit)

    assert isinstance(result, TaskResult)
    # The adapter returns COMPLETED (since it doesn't enforce daemon rules), but
    # we should check that independent review evidence is missing.
    assert not any(
        e.gate_type == GateType.INDEPENDENT_REVIEW for e in result.gate_result.evidence_items
    )


@pytest.mark.asyncio
async def test_antigravity_disallowed_changes(fake_task: TaskEnvelope, fake_worktree: Path):
    adapter = AntigravityAdapter()
    adapter.setup_session_in_memory_graph = MagicMock(return_value=fake_worktree / "session")

    mock_dispatch = MagicMock()
    mock_dispatch.completed = True
    mock_dispatch.blocked_reason = None
    mock_dispatch.qa_evidence = "evidence"
    mock_dispatch.conversation_id = "conv_123"
    mock_dispatch.tool_names = set()
    mock_dispatch.transcript_path = None
    adapter.live_bridge.dispatch = AsyncMock(return_value=mock_dispatch)

    mock_gate_result = GateResult(
        task_id=fake_task.task_id,
        attempt_id="att_123",
        all_passed=True,
        evidence_items=[],
    )
    adapter.run_acceptance_gates = MagicMock(return_value=mock_gate_result)

    adapter.worktree_mgr.get_uncommitted_files = MagicMock(return_value=["secret.txt"])
    adapter.worktree_mgr.get_changed_files = MagicMock(return_value=["secret.txt"])
    adapter.worktree_mgr.get_diff_summary = MagicMock(return_value="Diff")
    adapter.worktree_mgr.find_disallowed_changes = MagicMock(return_value=["secret.txt"])
    adapter.worktree_mgr.get_head_commit = MagicMock(return_value="commit123")

    result = await adapter.execute(fake_task, fake_worktree, fake_task.base_commit)

    assert result.status == TaskStatus.RETRYABLE_FAILED
    assert result.gate_result.all_passed is False
    assert any(
        e.gate_type == GateType.SECURITY_SCAN and e.passed is False
        for e in result.gate_result.evidence_items
    )


@pytest.mark.asyncio
async def test_antigravity_nonzero_exit(fake_task: TaskEnvelope, fake_worktree: Path):
    adapter = AntigravityAdapter()
    adapter.setup_session_in_memory_graph = MagicMock(return_value=fake_worktree / "session")

    mock_dispatch = MagicMock()
    mock_dispatch.completed = False
    mock_dispatch.blocked_reason = "nonzero exit code 1"
    mock_dispatch.conversation_id = "conv_123"
    mock_dispatch.tool_names = set()
    mock_dispatch.transcript_path = None
    mock_dispatch.qa_evidence = None
    adapter.live_bridge.dispatch = AsyncMock(return_value=mock_dispatch)

    mock_gate_result = GateResult(
        task_id=fake_task.task_id,
        attempt_id="att_123",
        all_passed=False,
        evidence_items=[],
    )
    adapter.run_acceptance_gates = MagicMock(return_value=mock_gate_result)

    adapter.worktree_mgr.get_uncommitted_files = MagicMock(return_value=[])
    adapter.worktree_mgr.get_changed_files = MagicMock(return_value=[])
    adapter.worktree_mgr.get_diff_summary = MagicMock(return_value="")
    adapter.worktree_mgr.find_disallowed_changes = MagicMock(return_value=[])
    adapter.worktree_mgr.get_head_commit = MagicMock(return_value="commit123")

    result = await adapter.execute(fake_task, fake_worktree, fake_task.base_commit)
    assert result.status == TaskStatus.RETRYABLE_FAILED


@pytest.mark.asyncio
async def test_antigravity_timeout(fake_task: TaskEnvelope, fake_worktree: Path):
    adapter = AntigravityAdapter()
    adapter.setup_session_in_memory_graph = MagicMock(return_value=fake_worktree / "session")
    adapter.live_bridge.dispatch = AsyncMock(side_effect=TimeoutError("timeout"))

    # The adapter should catch this and return a TaskResult instead of propagating
    try:
        result = await adapter.execute(fake_task, fake_worktree, fake_task.base_commit)
        assert result.status == TaskStatus.RETRYABLE_FAILED
    except Exception:
        # If it propagates, the test fails, which means we need to fix the adapter
        pytest.fail("Adapter did not fail closed on timeout")


@pytest.mark.asyncio
async def test_antigravity_rate_limit(fake_task: TaskEnvelope, fake_worktree: Path):
    adapter = AntigravityAdapter()
    adapter.setup_session_in_memory_graph = MagicMock(return_value=fake_worktree / "session")

    # We might simulate a rate limit exception from the bridge
    class RateLimitError(Exception):
        pass

    adapter.live_bridge.dispatch = AsyncMock(side_effect=RateLimitError("rate limited"))

    try:
        result = await adapter.execute(fake_task, fake_worktree, fake_task.base_commit)
        assert result.status == TaskStatus.RETRYABLE_FAILED
    except Exception:
        pytest.fail("Adapter did not fail closed on rate limit")


@pytest.mark.asyncio
async def test_antigravity_approval_block(fake_task: TaskEnvelope, fake_worktree: Path):
    # E.g. worker kill switch active
    adapter = AntigravityAdapter()
    from alpha_core.security import worker_kill_switch

    with patch.object(worker_kill_switch, "can_execute", return_value=False):
        result = await adapter.execute(fake_task, fake_worktree, fake_task.base_commit)
        assert result.status == TaskStatus.BLOCKED
        assert any("kill switch active" in b for b in result.blockers)


@pytest.mark.asyncio
async def test_daemon_unsupported_adapters_blocked(fake_task: TaskEnvelope):
    daemon = AlphaWorkerDaemon()

    for agent in [AgentType.CLAUDE_CODE, AgentType.CODEX]:
        task_copy = fake_task.model_copy(update={"preferred_agent": agent})
        adapter = daemon.select_adapter(agent)
        result = await adapter.execute(task_copy, Path("/"), task_copy.base_commit)
        assert result.status == TaskStatus.BLOCKED
        assert any(agent.value in b for b in result.blockers)
