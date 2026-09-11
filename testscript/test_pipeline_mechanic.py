"""
testscript/test_pipeline_mechanic.py
Unit tests for Gemini 3.1 Pro-Powered Pipeline Mechanic in AlphaBrain.
"""

from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

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
    mock_proc.poll.return_value = None  # Running/hanging worker process

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


def test_tempfile_cleanup_on_subprocess_timeout(temp_dir):
    """Verifies that prompt_file is cleanly deleted even when subprocess.run raises TimeoutExpired."""
    fake_agy = temp_dir / "agy"
    fake_agy.touch()

    mechanic = PipelineMechanic(agy_bin=fake_agy, llm_invoker=None)
    snapshot = TaskStallSnapshot(
        task_id="tsk_timeout_leak",
        elapsed_seconds=300.0,
        timeout_seconds=300.0,
        process_alive=True,
    )

    created_tempfiles = []
    real_named_temp = tempfile.NamedTemporaryFile

    def tracking_tempfile(*args, **kwargs):
        tf = real_named_temp(*args, **kwargs)
        created_tempfiles.append(Path(tf.name))
        return tf

    with (
        patch("tempfile.NamedTemporaryFile", side_effect=tracking_tempfile),
        patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="agy", timeout=60)),
    ):
        diag = mechanic.diagnose_stall(snapshot)

    assert diag is not None
    assert len(created_tempfiles) == 1
    assert not created_tempfiles[0].exists()


def test_handle_timeouts_race_condition_aborts_resumption(temp_queue):
    """Verifies that if task finishes naturally during LLM diagnosis, resumption is safely aborted."""
    prov = TaskProvenance(
        meeting_id="meet_race",
        speaker_id="speaker_1",
        utterance_timestamp=1000.0,
        transcript_excerpt="test",
        extraction_model="test-model",
        extraction_confidence=1.0,
        eva_session_id="sess_race",
        created_at=1000.0,
        content_hash="hash_race",
    )
    temp_queue.enqueue_task(
        task_id="tsk_race_test",
        envelope={"project_id": "alphabrain_dogfood"},
        provenance=prov,
        initial_status=TriageStatus.EXECUTING,
    )

    proc_ref = MagicMock()
    proc_ref.poll.return_value = None  # Hanging initially

    def slow_llm_invoker(model: str, prompt: str) -> dict[str, Any]:
        # Task completes naturally while LLM is generating diagnosis
        proc_ref.poll.return_value = 0
        return {
            "is_recoverable": True,
            "action": "RESUME_CHECKPOINT",
            "reason": "Old stall diagnosis",
            "checkpoint_phase": "phase_init",
        }

    mechanic = PipelineMechanic(queue=temp_queue, llm_invoker=slow_llm_invoker)
    dispatcher = ParallelWorkerDispatcher(
        queue=temp_queue,
        max_workers=2,
        timeout_seconds=50.0,
        pipeline_mechanic=mechanic,
        enable_pipeline_mechanic=True,
    )

    execution = ActiveTaskExecution(
        task_id="tsk_race_test",
        started_at=time.time() - 100.0,
        worker_id="wrk_test_race",
        process=proc_ref,
    )
    dispatcher._active_tasks["tsk_race_test"] = execution

    timed_out_ids = dispatcher.handle_timeouts()

    assert timed_out_ids == []
    assert "tsk_race_test" in dispatcher.active_tasks
    assert dispatcher.active_tasks["tsk_race_test"].process is proc_ref
    row = temp_queue.get_task("tsk_race_test")
    assert row["status"] != TriageStatus.FAILED.value


def test_handle_timeouts_sigkill_fallback_on_unresponsive_child(temp_queue):
    """Verifies that if a child process ignores SIGTERM during recoverable stall, SIGKILL fallback is invoked."""
    prov = TaskProvenance(
        meeting_id="meet_kill",
        speaker_id="speaker_1",
        utterance_timestamp=1000.0,
        transcript_excerpt="test",
        extraction_model="test-model",
        extraction_confidence=1.0,
        eva_session_id="sess_kill",
        created_at=1000.0,
        content_hash="hash_kill",
    )
    temp_queue.enqueue_task(
        task_id="tsk_sigkill_test",
        envelope={"project_id": "alphabrain_dogfood"},
        provenance=prov,
        initial_status=TriageStatus.EXECUTING,
    )

    stubborn_proc = MagicMock()
    stubborn_proc.poll.return_value = None

    def on_kill():
        stubborn_proc.poll.return_value = -9

    stubborn_proc.kill.side_effect = on_kill
    # First wait(timeout=1.0) on terminate raises TimeoutExpired, second wait on kill succeeds
    stubborn_proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="worker", timeout=1.0), 0]

    mechanic = PipelineMechanic(
        queue=temp_queue,
        llm_invoker=lambda m, p: {
            "is_recoverable": True,
            "action": "RESUME_CHECKPOINT",
            "reason": "Stubborn child process stall",
            "checkpoint_phase": "phase_compile",
        },
    )
    dispatcher = ParallelWorkerDispatcher(
        queue=temp_queue,
        max_workers=2,
        timeout_seconds=50.0,
        pipeline_mechanic=mechanic,
        enable_pipeline_mechanic=True,
    )

    new_proc = MagicMock()
    new_proc.poll.return_value = None
    dispatcher._spawn_worker_process = MagicMock(return_value=(new_proc, None, time.time()))

    execution = ActiveTaskExecution(
        task_id="tsk_sigkill_test",
        started_at=time.time() - 100.0,
        worker_id="wrk_stubborn",
        process=stubborn_proc,
    )
    dispatcher._active_tasks["tsk_sigkill_test"] = execution

    dispatcher.handle_timeouts()

    # Verify terminate was attempted, timed out, and kill was called as fallback
    assert stubborn_proc.terminate.called
    assert stubborn_proc.kill.called
    assert dispatcher.active_tasks["tsk_sigkill_test"].process is new_proc


def test_handle_timeouts_log_tail_capture_in_snapshot(temp_queue, tmp_path):
    """Verifies that stdout and stderr tails are extracted from disk logs and passed into TaskStallSnapshot."""
    prov = TaskProvenance(
        meeting_id="meet_logs",
        speaker_id="speaker_1",
        utterance_timestamp=1000.0,
        transcript_excerpt="test",
        extraction_model="test-model",
        extraction_confidence=1.0,
        eva_session_id="sess_logs",
        created_at=1000.0,
        content_hash="hash_logs",
    )
    temp_queue.enqueue_task(
        task_id="tsk_log_test",
        envelope={"project_id": "alphabrain_dogfood"},
        provenance=prov,
        initial_status=TriageStatus.EXECUTING,
    )

    stdout_file = tmp_path / "stdout.log"
    stderr_file = tmp_path / "stderr.log"
    stdout_file.write_text("Worker compilation progress 85%\n", encoding="utf-8")
    stderr_file.write_text("Warning: resource contention detected\n", encoding="utf-8")

    captured_snapshots = []

    def mock_invoker(model: str, prompt: str) -> dict[str, Any]:
        return {
            "is_recoverable": True,
            "action": "RESUME_CHECKPOINT",
            "reason": "Log test diagnosis",
            "checkpoint_phase": "phase_compile",
        }

    mechanic = PipelineMechanic(queue=temp_queue, llm_invoker=mock_invoker)
    orig_diagnose = mechanic.diagnose_stall

    def wrapped_diagnose(snapshot):
        captured_snapshots.append(snapshot)
        return orig_diagnose(snapshot)

    mechanic.diagnose_stall = wrapped_diagnose

    dispatcher = ParallelWorkerDispatcher(
        queue=temp_queue,
        max_workers=2,
        timeout_seconds=50.0,
        pipeline_mechanic=mechanic,
        enable_pipeline_mechanic=True,
    )

    proc_ref = MagicMock()
    proc_ref.poll.return_value = None
    proc_ref.wait.return_value = 0
    new_proc = MagicMock()
    new_proc.poll.return_value = None
    dispatcher._spawn_worker_process = MagicMock(return_value=(new_proc, None, time.time()))

    execution = ActiveTaskExecution(
        task_id="tsk_log_test",
        started_at=time.time() - 100.0,
        worker_id="wrk_log_test",
        process=proc_ref,
        stdout_path=stdout_file,
        stderr_path=stderr_file,
    )
    dispatcher._active_tasks["tsk_log_test"] = execution

    dispatcher.handle_timeouts()

    assert len(captured_snapshots) == 1
    assert "Worker compilation progress 85%" in captured_snapshots[0].stdout_tail
    assert "Warning: resource contention detected" in captured_snapshots[0].stderr_tail


def test_transactional_resumption_failure_preserves_envelope(temp_queue, tmp_path):
    """Verifies that if resume_callback fails, execute_surgical_resumption aborts without modifying envelope."""
    prov = TaskProvenance(
        meeting_id="meet_tx",
        speaker_id="speaker_1",
        utterance_timestamp=1000.0,
        transcript_excerpt="test",
        extraction_model="test-model",
        extraction_confidence=1.0,
        eva_session_id="sess_tx",
        created_at=1000.0,
        content_hash="hash_tx",
    )
    temp_queue.enqueue_task(
        task_id="tsk_tx_fail",
        envelope={"project_id": "alphabrain_dogfood", "title": "Untouched Task"},
        provenance=prov,
        initial_status=TriageStatus.APPROVED,
    )

    mechanic = PipelineMechanic(queue=temp_queue)
    snapshot = TaskStallSnapshot(
        task_id="tsk_tx_fail",
        elapsed_seconds=150.0,
        timeout_seconds=100.0,
        process_alive=True,
        last_phase="phase_build",
        worktree_path=tmp_path,
    )
    from alpha_worker.adaptive_manager import MechanicDiagnosis

    diagnosis = MechanicDiagnosis(
        is_recoverable=True,
        action=MechanicAction.RESUME_CHECKPOINT,
        reason="Test failure transactional preservation",
        checkpoint_phase="phase_build",
    )

    def failing_cb(task_id: str, phase: str, envelope: dict[str, Any]) -> bool:
        return False

    success = mechanic.execute_surgical_resumption(
        snapshot, diagnosis, resume_callback=failing_cb
    )

    assert success is False
    # Verify task envelope in DB was not polluted with mechanic intervention
    task_row = temp_queue.get_task("tsk_tx_fail")
    assert "mechanic_interventions" not in task_row["envelope"]
    assert "last_checkpoint_phase" not in task_row["envelope"]


def test_scrub_secrets_masks_sensitive_credentials():
    """Verifies that PipelineMechanic._scrub_secrets masks API keys and tokens before prompt construction."""
    sample_text = (
        "Server starting with GEMINI_API_KEY=AIzaSyD-1234567890abcdefghijklmnopqr\n"
        "Connecting with Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThisSignature\n"
        "AWS credentials: AKIAIOSFODNN7EXAMPLE and secret_key: 1234567890abcdef\n"
        "Stitch token: AQ.Ab8RN6deadbeef123456789\n"
        "Normal log: Task compilation step 3 passed in 1.4s"
    )

    scrubbed = PipelineMechanic._scrub_secrets(sample_text)

    assert "AIza" not in scrubbed
    assert "AKIA" not in scrubbed
    assert "AQ.Ab8RN6" not in scrubbed
    assert "doNotLeakThisSignature" not in scrubbed
    assert "1234567890abcdef" not in scrubbed
    assert "[REDACTED_SECRET]" in scrubbed
    assert "Normal log: Task compilation step 3 passed in 1.4s" in scrubbed


def test_handle_timeouts_binary_safe_tail_multibyte_utf8(temp_queue, tmp_path):
    """Verifies that binary-mode log tailing safely decodes multibyte UTF-8 characters without crash."""
    prov = TaskProvenance(
        meeting_id="meet_utf8",
        speaker_id="speaker_1",
        utterance_timestamp=1000.0,
        transcript_excerpt="test",
        extraction_model="test-model",
        extraction_confidence=1.0,
        eva_session_id="sess_utf8",
        created_at=1000.0,
        content_hash="hash_utf8",
    )
    temp_queue.enqueue_task(
        task_id="tsk_utf8_test",
        envelope={"project_id": "alphabrain_dogfood"},
        provenance=prov,
        initial_status=TriageStatus.EXECUTING,
    )

    stdout_file = tmp_path / "stdout_utf8.log"
    # Write a repeating multibyte emoji pattern > 5000 bytes so that a 4096-byte seek hits a multibyte boundary
    multibyte_text = "🚀 AlphaBrain pipeline worker heartbeat 🌟\n" * 150
    stdout_file.write_bytes(multibyte_text.encode("utf-8"))

    captured_snapshots = []

    def mock_invoker(model: str, prompt: str) -> dict[str, Any]:
        return {
            "is_recoverable": True,
            "action": "RESUME_CHECKPOINT",
            "reason": "Multibyte test diagnosis",
            "checkpoint_phase": "phase_utf8",
        }

    mechanic = PipelineMechanic(queue=temp_queue, llm_invoker=mock_invoker)
    orig_diagnose = mechanic.diagnose_stall

    def wrapped_diagnose(snapshot):
        captured_snapshots.append(snapshot)
        return orig_diagnose(snapshot)

    mechanic.diagnose_stall = wrapped_diagnose

    dispatcher = ParallelWorkerDispatcher(
        queue=temp_queue,
        max_workers=2,
        timeout_seconds=50.0,
        pipeline_mechanic=mechanic,
        enable_pipeline_mechanic=True,
    )

    proc_ref = MagicMock()
    proc_ref.poll.return_value = None
    proc_ref.wait.return_value = 0
    new_proc = MagicMock()
    new_proc.poll.return_value = None
    dispatcher._spawn_worker_process = MagicMock(return_value=(new_proc, None, time.time()))

    execution = ActiveTaskExecution(
        task_id="tsk_utf8_test",
        started_at=time.time() - 100.0,
        worker_id="wrk_utf8",
        process=proc_ref,
        stdout_path=stdout_file,
    )
    dispatcher._active_tasks["tsk_utf8_test"] = execution

    dispatcher.handle_timeouts()

    assert len(captured_snapshots) == 1
    assert "AlphaBrain pipeline worker heartbeat" in captured_snapshots[0].stdout_tail


def test_handle_timeouts_preserves_mechanic_interventions_in_resumed_worker(temp_queue):
    """Verifies that newly spawned process receives task_dict containing updated mechanic_interventions."""
    prov = TaskProvenance(
        meeting_id="meet_audit",
        speaker_id="speaker_1",
        utterance_timestamp=1000.0,
        transcript_excerpt="test",
        extraction_model="test-model",
        extraction_confidence=1.0,
        eva_session_id="sess_audit",
        created_at=1000.0,
        content_hash="hash_audit",
    )
    temp_queue.enqueue_task(
        task_id="tsk_audit_test",
        envelope={"project_id": "alphabrain_dogfood", "phase": "phase_tests"},
        provenance=prov,
        initial_status=TriageStatus.EXECUTING,
    )

    mechanic = PipelineMechanic(
        queue=temp_queue,
        llm_invoker=lambda m, p: {
            "is_recoverable": True,
            "action": "RESUME_CHECKPOINT",
            "reason": "Audit preservation verification",
            "checkpoint_phase": "phase_tests",
        },
    )
    dispatcher = ParallelWorkerDispatcher(
        queue=temp_queue,
        max_workers=2,
        timeout_seconds=50.0,
        pipeline_mechanic=mechanic,
        enable_pipeline_mechanic=True,
    )

    spawned_tasks = []

    def mock_spawn(task_dict, worker_id):
        spawned_tasks.append(task_dict)
        proc = MagicMock()
        proc.poll.return_value = None
        return proc, None, time.time()

    dispatcher._spawn_worker_process = mock_spawn

    proc_ref = MagicMock()
    proc_ref.poll.return_value = None
    proc_ref.wait.return_value = 0

    execution = ActiveTaskExecution(
        task_id="tsk_audit_test",
        started_at=time.time() - 100.0,
        worker_id="wrk_audit",
        process=proc_ref,
        envelope={"project_id": "alphabrain_dogfood", "phase": "phase_tests"},
    )
    dispatcher._active_tasks["tsk_audit_test"] = execution

    dispatcher.handle_timeouts()

    assert len(spawned_tasks) == 1
    spawned_env = spawned_tasks[0].get("envelope", {})
    interventions = spawned_env.get("mechanic_interventions", [])
    assert len(interventions) >= 1
    assert interventions[0]["action"] == "RESUME_CHECKPOINT"
    assert interventions[0]["zero_restart"] is True


def test_spawn_worker_process_rejects_hyphen_task_id(temp_queue):
    """Verifies that _spawn_worker_process and dispatch_task reject task_id with leading hyphen."""
    dispatcher = ParallelWorkerDispatcher(queue=temp_queue)

    malicious_task = {"id": "--help", "envelope": {}}
    import pytest

    with pytest.raises(ValueError, match="cannot start with a hyphen"):
        dispatcher._spawn_worker_process(malicious_task, "wrk_malicious")

    # dispatch_task should safely reject and return None
    assert dispatcher.dispatch_task(malicious_task) is None



