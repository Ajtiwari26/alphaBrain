"""testscript/test_etta_adapter.py
Unit tests for ETTA v0.2.0 worker adapter, live bridge, config, and dispatcher wiring.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alpha_core.config import settings
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
from alpha_protocol.enums import EXECUTION_ENABLED_AGENTS
from alpha_worker.adapters import (
    AntigravityAdapter,
    AntigravityLiveBridge,
    EttaAdapter,
    EttaLiveBridge,
)
from alpha_worker.adapters.etta_live import EttaDispatch
from alpha_worker.triage_dispatcher import TriageTaskDispatcher

FAKE_BASE_COMMIT = "a" * 40


@pytest.fixture
def fake_task(tmp_path: Path) -> TaskEnvelope:
    return TaskEnvelope(
        task_id="tsk_etta_test_001",
        project_id="prj_alphabrain_test",
        objective="Integrate ETTA v0.2.0 autonomous worker",
        detailed_instructions="Implement adapter and bridge for ETTA",
        base_commit=FAKE_BASE_COMMIT,
        repo=str(tmp_path / "repo"),
        allowed_paths=["alpha_worker/adapters/etta.py"],
        allowed_tools=["edit_file", "view_file", "run_command"],
        preferred_agent=AgentType.ETTA,
        acceptance_plan=AcceptancePlan(
            required_gates=[GateType.UNIT_TEST],
            commands=[],
        ),
    )


def test_etta_enums_and_config():
    """Verify AgentType.ETTA is defined and registered in EXECUTION_ENABLED_AGENTS."""
    assert AgentType.ETTA == "etta"
    assert AgentType.ETTA in EXECUTION_ENABLED_AGENTS
    assert hasattr(settings, "ALPHA_WORKER_ENGINE")
    assert hasattr(settings, "ETTA_BIN")
    assert isinstance(settings.ETTA_BIN, Path)
    assert hasattr(settings, "ETTA_EXECUTION_ENABLED")
    assert isinstance(settings.ETTA_EXECUTION_ENABLED, bool)


def test_etta_live_bridge_readiness_binary_missing(tmp_path: Path):
    """Verify readiness check fails cleanly when ETTA binary does not exist."""
    bridge = EttaLiveBridge(bin_path=tmp_path / "nonexistent_etta")
    ready, reason = bridge.check_readiness()
    assert ready is False
    assert "not found" in reason.lower()


def test_etta_live_bridge_readiness_binary_present(tmp_path: Path):
    """Verify readiness check succeeds when binary exists and reports ready."""
    fake_bin = tmp_path / "etta"
    fake_bin.write_text("#!/bin/sh\nexit 0\n")
    fake_bin.chmod(0o755)

    bridge = EttaLiveBridge(bin_path=fake_bin)
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout='{"status": "Online"}')
        ready, reason = bridge.check_readiness()
        assert ready is True
        assert "ready" in reason.lower()


@pytest.mark.asyncio
async def test_etta_live_bridge_dispatch_success(fake_task: TaskEnvelope, tmp_path: Path):
    """Verify successful subprocess execution and JSON result parsing."""
    fake_bin = tmp_path / "etta"
    fake_bin.write_text("#!/bin/sh\nexit 0\n")
    fake_bin.chmod(0o755)

    session_dir = tmp_path / "session"
    session_dir.mkdir()

    bridge = EttaLiveBridge(bin_path=fake_bin)

    mock_proc = AsyncMock()
    mock_proc.pid = 9999
    mock_proc.returncode = 0
    json_output = (
        '{"exit_code": 0, "status": "Online", "tokens_used": 1500, "cost": 0.015, "error": null}\n'
    )
    mock_proc.communicate.return_value = (json_output.encode("utf-8"), b"")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        dispatch = await bridge.dispatch(
            task=fake_task,
            worktree_path=tmp_path,
            attempt_id="att_test_123",
            session_dir=session_dir,
        )

        assert dispatch.completed is True
        assert dispatch.exit_code == 0
        assert dispatch.tokens_used == 1500
        assert dispatch.cost == 0.015
        assert dispatch.status == "succeeded"
        assert dispatch.transcript_path is not None
        assert dispatch.transcript_path.exists()


@pytest.mark.asyncio
async def test_etta_live_bridge_dispatch_failure(fake_task: TaskEnvelope, tmp_path: Path):
    """Verify dispatch reports failure when ETTA returns non-zero code or error."""
    fake_bin = tmp_path / "etta"
    fake_bin.write_text("#!/bin/sh\nexit 1\n")
    fake_bin.chmod(0o755)

    bridge = EttaLiveBridge(bin_path=fake_bin)

    mock_proc = AsyncMock()
    mock_proc.pid = 9999
    mock_proc.returncode = 1
    json_output = '{"exit_code": 1, "status": "Failed", "error": "Policy veto violation"}\n'
    mock_proc.communicate.return_value = (json_output.encode("utf-8"), b"Error occurred")

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        dispatch = await bridge.dispatch(
            task=fake_task,
            worktree_path=tmp_path,
            attempt_id="att_test_123",
        )

        assert dispatch.completed is False
        assert dispatch.exit_code == 1
        assert dispatch.status == "failed"
        assert "Policy veto violation" in (dispatch.blocked_reason or "")


@pytest.mark.asyncio
async def test_etta_live_bridge_dispatch_timeout(fake_task: TaskEnvelope, tmp_path: Path):
    """Verify dispatch reports timeout when subprocess execution exceeds timeout."""
    fake_bin = tmp_path / "etta"
    fake_bin.write_text("#!/bin/sh\nsleep 10\n")
    fake_bin.chmod(0o755)

    bridge = EttaLiveBridge(bin_path=fake_bin, timeout_seconds=1)

    mock_proc = AsyncMock()
    mock_proc.pid = 8888
    mock_proc.communicate.side_effect = TimeoutError()
    mock_proc.kill = MagicMock()
    mock_proc.wait = AsyncMock()

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        dispatch = await bridge.dispatch(
            task=fake_task,
            worktree_path=tmp_path,
            attempt_id="att_test_timeout",
        )

        assert dispatch.completed is False
        assert dispatch.status == "timed_out"
        assert "timed out" in (dispatch.blocked_reason or "").lower()


def test_etta_adapter_session_setup(fake_task: TaskEnvelope, tmp_path: Path):
    """Verify memory graph session structure created by EttaAdapter."""
    adapter = EttaAdapter()
    adapter.memory_graph_path = tmp_path

    worktree_path = tmp_path / "worktree"
    worktree_path.mkdir(parents=True, exist_ok=True)

    session_dir = adapter.setup_session_in_memory_graph(fake_task, worktree_path)
    assert session_dir.exists()
    overview_file = session_dir / ".system_generated" / "logs" / "overview.txt"
    assert overview_file.exists()
    overview_data = overview_file.read_text(encoding="utf-8")
    assert "tsk_etta_test_001" in overview_data
    assert "etta" in overview_data


@pytest.mark.asyncio
async def test_etta_adapter_execute_success(fake_task: TaskEnvelope, tmp_path: Path):
    """Verify complete execution flow of EttaAdapter."""
    mock_bridge = MagicMock()
    mock_bridge.check_readiness.return_value = (True, "ETTA ready")

    mock_dispatch = EttaDispatch(
        conversation_id="att_etta_001",
        completed=True,
        blocked_reason=None,
        tool_names=("edit_file", "run_command"),
        final_message="ETTA finished goal",
        transcript_path=tmp_path / "transcript.json",
        pid=1234,
        exit_code=0,
        model="gemini-3.8-flash-high",
        status="succeeded",
        changed_files=("alpha_worker/adapters/etta.py",),
        tokens_used=500,
        cost=0.005,
    )
    mock_bridge.dispatch = AsyncMock(return_value=mock_dispatch)

    adapter = EttaAdapter(live_bridge=mock_bridge)
    adapter.memory_graph_path = tmp_path

    gate_result = GateResult(
        task_id=fake_task.task_id,
        attempt_id="att_etta_001",
        all_passed=True,
        evidence=[
            GateEvidence(
                evidence_id="evi_1",
                gate_type=GateType.UNIT_TEST,
                passed=True,
                summary="Tests passed",
            )
        ],
    )
    adapter.run_acceptance_gates = MagicMock(return_value=gate_result)
    adapter.worktree_mgr.get_uncommitted_files = MagicMock(return_value=["alpha_worker/adapters/etta.py"])
    adapter.worktree_mgr.find_disallowed_changes = MagicMock(return_value=[])
    adapter.worktree_mgr.commit_changes = MagicMock(return_value="commit_sha_123")

    result = await adapter.execute(fake_task, tmp_path, FAKE_BASE_COMMIT)

    assert isinstance(result, TaskResult)
    assert result.status == TaskStatus.VERIFIED
    assert result.agent == AgentType.ETTA
    assert result.result_commit == "commit_sha_123"
    assert "alpha_worker/adapters/etta.py" in result.files_changed


def test_triage_dispatcher_wiring_default():
    """Verify TriageTaskDispatcher defaults to Antigravity when ALPHA_WORKER_ENGINE is antigravity."""
    mock_queue = MagicMock()
    with patch.object(settings, "ALPHA_WORKER_ENGINE", "antigravity"):
        dispatcher = TriageTaskDispatcher(queue=mock_queue)
        assert isinstance(dispatcher.adapter, AntigravityAdapter)
        assert isinstance(dispatcher.live_bridge, AntigravityLiveBridge)


def test_triage_dispatcher_wiring_etta():
    """Verify TriageTaskDispatcher selects EttaAdapter when ALPHA_WORKER_ENGINE is etta."""
    mock_queue = MagicMock()
    with patch.object(settings, "ALPHA_WORKER_ENGINE", "etta"):
        dispatcher = TriageTaskDispatcher(queue=mock_queue)
        assert isinstance(dispatcher.adapter, EttaAdapter)
        assert isinstance(dispatcher.live_bridge, EttaLiveBridge)


def test_triage_dispatcher_build_envelope_preferred_agent():
    """Verify _build_task_envelope sets preferred_agent based on configured worker engine."""
    mock_queue = MagicMock()
    leased_task = {
        "id": "tsk_build_01",
        "envelope": {
            "objective": "Test objective",
            "base_commit": FAKE_BASE_COMMIT,
            "allowed_paths": ["alpha_worker/adapters/etta.py"],
        },
        "provenance": {},
    }

    with patch.object(settings, "ALPHA_WORKER_ENGINE", "etta"):
        dispatcher = TriageTaskDispatcher(queue=mock_queue)
        envelope = dispatcher._build_task_envelope(leased_task, Path("/tmp"))
        assert envelope.preferred_agent == AgentType.ETTA

    with patch.object(settings, "ALPHA_WORKER_ENGINE", "antigravity"):
        dispatcher = TriageTaskDispatcher(queue=mock_queue)
        envelope = dispatcher._build_task_envelope(leased_task, Path("/tmp"))
        assert envelope.preferred_agent == AgentType.ANTIGRAVITY
