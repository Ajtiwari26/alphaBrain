"""
testscript/test_pipeline_mechanic.py
Unit tests for Gemini 3.1 Pro-Powered Pipeline Mechanic in AlphaBrain.
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue, TriageStatus
from alpha_worker.adaptive_manager import (
    MechanicAction,
    PipelineMechanic,
    TaskStallSnapshot,
)
from alpha_worker.parallel_dispatcher import ActiveTaskExecution, ParallelWorkerDispatcher


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def temp_queue(temp_dir):
    db_path = temp_dir / "test_triage.db"
    return TaskTriageQueue(db_path=db_path)


def test_checkpoint_save_and_load(temp_dir):
    """Verifies checkpoint state saving and retrieval."""
    cp_path = PipelineMechanic.save_checkpoint(
        checkpoint_dir=temp_dir,
        task_id="tsk_test_cp",
        phase="phase_worker_code_edit",
        state_data={"modified_files": ["alpha_worker/health.py"], "step": 3},
    )
    assert cp_path.exists()

    loaded = PipelineMechanic.load_checkpoint(temp_dir, "tsk_test_cp")
    assert loaded is not None
    assert loaded["task_id"] == "tsk_test_cp"
    assert loaded["phase"] == "phase_worker_code_edit"
    assert loaded["state_data"]["modified_files"] == ["alpha_worker/health.py"]


def test_gemini_stall_diagnosis_recoverable(temp_dir):
    """Verifies Gemini 3.1 Pro diagnoses recoverable stalls and prescribes RESUME_CHECKPOINT."""
    captured_model = []

    def mock_gemini_invoker(model: str, prompt: str) -> dict[str, Any]:
        captured_model.append(model)
        assert "AlphaBrain Gemini 3.1 Pro Pipeline Mechanic" in prompt
        assert "tsk_stalled_101" in prompt
        return {
            "is_recoverable": True,
            "action": "RESUME_CHECKPOINT",
            "reason": "Process stalled during test runner; worktree changes intact",
            "checkpoint_phase": "phase_tests",
            "suggested_fix": "Resume directly from test step without discarding worktree",
        }

    mechanic = PipelineMechanic(
        model="gemini-3.1-pro-high",
        llm_invoker=mock_gemini_invoker,
    )

    snapshot = TaskStallSnapshot(
        task_id="tsk_stalled_101",
        elapsed_seconds=310.0,
        timeout_seconds=300.0,
        process_alive=True,
        last_phase="phase_tests",
        worktree_path=temp_dir / "worktree_tsk_101",
        checkpoint_file=temp_dir / "checkpoint_tsk_101.json",
        stdout_tail="Running pytest testscript/test_health.py...",
    )

    diagnosis = mechanic.diagnose_stall(snapshot)
    assert captured_model == ["gemini-3.1-pro-high"]
    assert diagnosis.is_recoverable is True
    assert diagnosis.action == MechanicAction.RESUME_CHECKPOINT
    assert diagnosis.checkpoint_phase == "phase_tests"
    assert "intact" in diagnosis.reason


def test_gemini_stall_diagnosis_extend_lease(temp_dir):
    """Verifies Gemini 3.1 Pro prescribes EXTEND_LEASE for actively progressing workers."""
    def mock_gemini_invoker(model: str, prompt: str) -> dict[str, Any]:
        return {
            "is_recoverable": True,
            "action": "EXTEND_LEASE",
            "reason": "Worker is making steady progress downloading dependencies",
            "checkpoint_phase": "phase_install",
            "suggested_fix": "Extend task timeout window by 180 seconds",
        }

    mechanic = PipelineMechanic(llm_invoker=mock_gemini_invoker)
    snapshot = TaskStallSnapshot(
        task_id="tsk_slow_worker",
        elapsed_seconds=301.0,
        timeout_seconds=300.0,
        process_alive=True,
        last_phase="phase_install",
        stdout_tail="Collecting large dependency package 92%...",
    )

    diagnosis = mechanic.diagnose_stall(snapshot)
    assert diagnosis.is_recoverable is True
    assert diagnosis.action == MechanicAction.EXTEND_LEASE


def test_gemini_stall_diagnosis_unrecoverable():
    """Verifies Gemini 3.1 Pro prescribes TERMINATE on fatal unrecoverable crashes."""
    def mock_gemini_invoker(model: str, prompt: str) -> dict[str, Any]:
        return {
            "is_recoverable": False,
            "action": "TERMINATE",
            "reason": "Fatal memory exhaustion and unhandled segmentation fault",
            "checkpoint_phase": None,
            "suggested_fix": "Abort execution and route to CI healing",
        }

    mechanic = PipelineMechanic(llm_invoker=mock_gemini_invoker)
    snapshot = TaskStallSnapshot(
        task_id="tsk_fatal_crash",
        elapsed_seconds=305.0,
        timeout_seconds=300.0,
        process_alive=False,
        last_phase="phase_compile",
        stderr_tail="Fatal: Segmentation fault (core dumped) - Out of Memory",
    )

    diagnosis = mechanic.diagnose_stall(snapshot)
    assert diagnosis.is_recoverable is False
    assert diagnosis.action == MechanicAction.TERMINATE


def test_deterministic_fallback_when_gemini_offline(temp_dir):
    """Verifies rule-based diagnostic engine when external Gemini endpoint is unavailable."""
    # No llm_invoker, nonexistent agy_bin
    mechanic = PipelineMechanic(
        agy_bin=Path("/nonexistent/bin/agy"),
        llm_invoker=None,
    )

    # 1. Recoverable case (active worktree/checkpoint present)
    snap_rec = TaskStallSnapshot(
        task_id="tsk_offline_rec",
        elapsed_seconds=320.0,
        timeout_seconds=300.0,
        process_alive=True,
        last_phase="phase_edit",
        worktree_path=temp_dir,
    )
    diag_rec = mechanic.diagnose_stall(snap_rec)
    assert diag_rec.is_recoverable is True
    assert diag_rec.action == MechanicAction.RESUME_CHECKPOINT

    # 2. Unrecoverable case (fatal syntax error)
    snap_unrec = TaskStallSnapshot(
        task_id="tsk_offline_unrec",
        elapsed_seconds=320.0,
        timeout_seconds=300.0,
        process_alive=False,
        stderr_tail="SyntaxError: invalid syntax at line 42",
    )
    diag_unrec = mechanic.diagnose_stall(snap_unrec)
    assert diag_unrec.is_recoverable is False
    assert diag_unrec.action == MechanicAction.TERMINATE


def test_surgical_resumption_execution_zero_restart(temp_queue, temp_dir):
    """Verifies execute_surgical_resumption updates task envelope and invokes callback."""
    prov = TaskProvenance(
        meeting_id="meet_1",
        speaker_id="speaker_1",
        utterance_timestamp=1000.0,
        transcript_excerpt="test excerpt",
        extraction_model="test-model",
        extraction_confidence=1.0,
        eva_session_id="sess_1",
        created_at=1000.0,
        content_hash="hash_1",
    )
    temp_queue.enqueue_task(
        task_id="tsk_surgical_1",
        envelope={"project_id": "alphabrain_dogfood", "title": "Surgical Task"},
        provenance=prov,
        initial_status=TriageStatus.APPROVED,
    )

    mechanic = PipelineMechanic(queue=temp_queue)

    snapshot = TaskStallSnapshot(
        task_id="tsk_surgical_1",
        elapsed_seconds=310.0,
        timeout_seconds=300.0,
        process_alive=True,
        last_phase="phase_test_execution",
        worktree_path=temp_dir,
        envelope={"project_id": "alphabrain_dogfood"},
    )

    from alpha_worker.adaptive_manager import MechanicDiagnosis

    diagnosis = MechanicDiagnosis(
        is_recoverable=True,
        action=MechanicAction.RESUME_CHECKPOINT,
        reason="Preserving checkpoint for surgical resumption",
        checkpoint_phase="phase_test_execution",
    )

    callback_called = []

    def mock_resume_cb(task_id: str, phase: str, envelope: dict[str, Any]) -> bool:
        callback_called.append((task_id, phase))
        return True

    success = mechanic.execute_surgical_resumption(
        snapshot, diagnosis, resume_callback=mock_resume_cb
    )

    assert success is True
    assert callback_called == [("tsk_surgical_1", "phase_test_execution")]

    # Check that queue envelope records the zero-restart mechanic intervention
    updated_task = temp_queue.get_task("tsk_surgical_1")
    env = updated_task["envelope"]
    assert env["last_checkpoint_phase"] == "phase_test_execution"
    interventions = env.get("mechanic_interventions", [])
    assert len(interventions) == 1
    assert interventions[0]["zero_restart"] is True
    assert interventions[0]["action"] == "RESUME_CHECKPOINT"


def test_dispatcher_timeout_interception_zero_restart(temp_queue):
    """
    Verifies that ParallelWorkerDispatcher.handle_timeouts intercepts a stalled worker,
    executes surgical resumption via PipelineMechanic, and avoids full restart/termination.
    """
    prov = TaskProvenance(
        meeting_id="meet_timeout",
        speaker_id="speaker_1",
        utterance_timestamp=1000.0,
        transcript_excerpt="test",
        extraction_model="test-model",
        extraction_confidence=1.0,
        eva_session_id="sess_timeout",
        created_at=1000.0,
        content_hash="hash_timeout",
    )
    temp_queue.enqueue_task(
        task_id="tsk_timeout_intercept",
        envelope={"project_id": "alphabrain_dogfood", "title": "Timeout Intercept"},
        provenance=prov,
        initial_status=TriageStatus.APPROVED,
    )

    def mock_gemini_invoker(model: str, prompt: str) -> dict[str, Any]:
        return {
            "is_recoverable": True,
            "action": "RESUME_CHECKPOINT",
            "reason": "Recoverable stall detected: test runner hung",
            "checkpoint_phase": "phase_tests",
            "suggested_fix": "Surgically resume from checkpoint phase",
        }

    mechanic = PipelineMechanic(queue=temp_queue, llm_invoker=mock_gemini_invoker)

    mock_ci_healing = MagicMock()
    mock_senior_review = MagicMock()
    mock_senior_review.execute_senior_review.return_value = MagicMock(to_dict=lambda: {"verdict": "APPROVE"})

    dispatcher = ParallelWorkerDispatcher(
        queue=temp_queue,
        max_workers=2,
        timeout_seconds=50.0,
        pipeline_mechanic=mechanic,
        enable_pipeline_mechanic=True,
        ci_healing_daemon=mock_ci_healing,
        senior_review_engine=mock_senior_review,
    )

    # 1. Setup old stalled process
    old_proc = MagicMock()
    old_proc.poll.return_value = None  # Initially hanging

    def fake_terminate():
        old_proc.poll.return_value = -15  # Process died from SIGTERM

    old_proc.terminate.side_effect = fake_terminate

    old_execution = ActiveTaskExecution(
        task_id="tsk_timeout_intercept",
        started_at=time.time() - 100.0,  # Exceeds 50s timeout limit
        worker_id="wrk_test_old",
        process=old_proc,
        envelope={"phase": "phase_tests"},
    )
    dispatcher._active_tasks["tsk_timeout_intercept"] = old_execution

    # 2. Setup mock for newly spawned process upon surgical resumption
    new_proc = MagicMock()
    new_proc.poll.return_value = None  # Newly spawned process is alive and running
    new_proc.pid = 88888
    new_rq = MagicMock()
    new_rq.empty.return_value = True

    dispatcher._spawn_worker_process = MagicMock(
        return_value=(new_proc, new_rq, time.time())
    )

    # 3. Run handle_timeouts
    timed_out_ids = dispatcher.handle_timeouts()

    # Verify old process was terminated cleanly
    assert old_proc.terminate.called
    assert old_proc.poll() == -15

    # Zero full restarts on recoverable stall:
    # A. Timed out list is empty because the task was surgically resumed
    assert timed_out_ids == []

    # B. Task remains active in pool and has been assigned the newly spawned process
    assert "tsk_timeout_intercept" in dispatcher.active_tasks
    resumed_exec = dispatcher.active_tasks["tsk_timeout_intercept"]
    assert resumed_exec.process is not old_proc
    assert resumed_exec.process is new_proc
    assert resumed_exec.process.poll() is None
    assert resumed_exec.envelope.get("surgically_resumed") is True
    assert resumed_exec.envelope.get("last_checkpoint_phase") == "phase_tests"
    assert (time.time() - resumed_exec.started_at) < 5.0

    # C. Verify reap_completed_tasks does NOT falsely fail the task as a zombie
    reap_res = dispatcher.reap_completed_tasks()
    assert reap_res["failed"] == []
    assert reap_res["completed"] == []
    assert "tsk_timeout_intercept" in dispatcher.active_tasks

    # D. Simulate the newly spawned process completing its resumed cycle successfully
    new_proc.poll.return_value = 0
    new_rq.empty.return_value = False
    new_rq.get_nowait.return_value = {"success": True, "result": {"resumed": True}}

    final_reap = dispatcher.reap_completed_tasks()
    assert "tsk_timeout_intercept" in final_reap["completed"]
    assert final_reap["failed"] == []
    assert "tsk_timeout_intercept" not in dispatcher.active_tasks
    mock_senior_review.execute_senior_review.assert_called_with("tsk_timeout_intercept")


def test_dispatcher_timeout_unrecoverable_termination(temp_queue):
    """
    Verifies that unrecoverable stalls diagnosed by Pipeline Mechanic are terminated
    and routed to CI healing as expected.
    """
    prov = TaskProvenance(
        meeting_id="meet_unrec",
        speaker_id="speaker_1",
        utterance_timestamp=1000.0,
        transcript_excerpt="test",
        extraction_model="test-model",
        extraction_confidence=1.0,
        eva_session_id="sess_unrec",
        created_at=1000.0,
        content_hash="hash_unrec",
    )
    temp_queue.enqueue_task(
        task_id="tsk_unrecoverable",
        envelope={"project_id": "alphabrain_dogfood"},
        provenance=prov,
        initial_status=TriageStatus.EXECUTING,
    )

    def mock_gemini_invoker(model: str, prompt: str) -> dict[str, Any]:
        return {
            "is_recoverable": False,
            "action": "TERMINATE",
            "reason": "Irrecoverable crash",
            "checkpoint_phase": None,
        }

    mechanic = PipelineMechanic(queue=temp_queue, llm_invoker=mock_gemini_invoker)

    dispatcher = ParallelWorkerDispatcher(
        queue=temp_queue,
        max_workers=2,
        timeout_seconds=50.0,
        pipeline_mechanic=mechanic,
        enable_pipeline_mechanic=True,
        ci_healing_daemon=MagicMock(),
    )

    mock_proc = MagicMock()
    mock_proc.poll.return_value = 1  # Exited with error

    execution = ActiveTaskExecution(
        task_id="tsk_unrecoverable",
        started_at=time.time() - 100.0,
        worker_id="wrk_test_unrec",
        process=mock_proc,
    )
    dispatcher._active_tasks["tsk_unrecoverable"] = execution

    timed_out_ids = dispatcher.handle_timeouts()

    assert "tsk_unrecoverable" in timed_out_ids
    assert "tsk_unrecoverable" not in dispatcher.active_tasks
    row = temp_queue.get_task("tsk_unrecoverable")
    assert row["status"] == TriageStatus.FAILED.value
