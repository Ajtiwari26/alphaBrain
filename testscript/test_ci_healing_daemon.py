"""
testscript/test_ci_healing_daemon.py
Unit and integration tests for CIHealingDaemon, ParallelWorkerDispatcher, and TaskTriageQueue.

Verifies:
1. Failure Analysis: Extraction and signature generation from pytest and ruff failures.
2. Repair Synthesis: Generation of bounded repair envelopes, parent task linkage, and retry epochs.
3. Circuit Breaker: Escalation to human review on repeated identical signatures, bounding retry loops.
4. Retry Queuing & Parallel Dispatch: Automated queuing of repair tasks in APPROVED state and parallel worker leasing.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from alpha_core.healing.circuit_breaker import CircuitBreaker, TripReason
from alpha_core.healing.repair_synthesizer import RepairEnvelopeSynthesizer
from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue, TriageStatus
from alpha_worker.ci_healing_daemon import CIHealingDaemon
from alpha_worker.parallel_dispatcher import ParallelWorkerDispatcher
from testscript.planning_fixtures import attach_test_plan


@pytest.fixture
def triage_env(tmp_path: Path):
    db_path = tmp_path / "test_triage.db"
    emergency_lock = tmp_path / "test_emergency.lock"
    queue = TaskTriageQueue(db_path=db_path, emergency_lock_path=emergency_lock)
    return queue, tmp_path


def make_provenance(task_id: str) -> TaskProvenance:
    return TaskProvenance(
        meeting_id=f"meet_{task_id}",
        speaker_id="speaker_test",
        utterance_timestamp=time.time(),
        transcript_excerpt=f"Execute task {task_id}",
        extraction_model="test-model",
        extraction_confidence=1.0,
        eva_session_id=f"session_{task_id}",
        created_at=time.time(),
        content_hash=f"hash_{task_id}",
    )


# -----------------------------------------------------------------------------
# 1. Failure Analysis Tests
# -----------------------------------------------------------------------------
def test_failure_analysis_from_evidence_files(triage_env):
    """Verifies that CIHealingDaemon correctly extracts failure information from disk logs."""
    queue, tmp_path = triage_env
    worktree = tmp_path / "worktree_failure_files"
    evidence_dir = worktree / "evidence"
    evidence_dir.mkdir(parents=True)

    pytest_log = evidence_dir / "pytest_output.txt"
    pytest_log.write_text(
        "FAILED tests/test_core.py::test_calculation - AssertionError: assert 1 == 2\n"
    )

    ruff_log = evidence_dir / "ruff_output.txt"
    ruff_log.write_text(
        "src/core.py:10:1: F401 `os` imported but unused\n"
    )

    task_id = "tsk_fail_analysis_01"
    envelope = {
        "project_id": "alphabrain_dogfood",
        "allowed_paths": ["src/core.py", "tests/test_core.py"],
    }
    queue.enqueue_task(
        task_id=task_id,
        envelope=envelope,
        provenance=make_provenance(task_id),
        initial_status=TriageStatus.FAILED,
    )

    daemon = CIHealingDaemon(queue=queue, project_id="alphabrain_dogfood")
    task_data = queue.get_task(task_id)
    task_data["worktree_path"] = str(worktree)

    outcome = daemon.process_failed_task(task_data)

    assert outcome["status"] == "repair_enqueued"
    assert outcome["task_id"] == task_id
    assert outcome["repair_task_id"] == f"{task_id}_repair_1"
    assert outcome["signature"] != "unknown"
    assert outcome["epoch"] == 1


def test_failure_analysis_fallback_from_task_payload(triage_env):
    """Verifies fallback failure extraction when logs are in task result evidence instead of disk files."""
    queue, tmp_path = triage_env
    worktree = tmp_path / "worktree_fallback"
    worktree.mkdir()

    task_id = "tsk_fail_analysis_02"
    envelope = {
        "project_id": "alphabrain_dogfood",
        "allowed_paths": ["src/service.py"],
    }
    queue.enqueue_task(
        task_id=task_id,
        envelope=envelope,
        provenance=make_provenance(task_id),
        initial_status=TriageStatus.FAILED,
    )

    task_data = queue.get_task(task_id)
    task_data["worktree_path"] = str(worktree)
    task_data["result"] = {
        "evidence": [
            {
                "gate_type": "unit_test",
                "stdout_snippet": "FAILED tests/test_service.py::test_run - ValueError",
                "stderr_snippet": "",
            },
            {
                "gate_type": "lint",
                "stdout_snippet": "src/service.py:5:1: E302 expected 2 blank lines",
                "stderr_snippet": "",
            },
        ]
    }

    daemon = CIHealingDaemon(queue=queue, project_id="alphabrain_dogfood")
    outcome = daemon.process_failed_task(task_data)

    assert outcome["status"] == "repair_enqueued"
    assert outcome["signature"] != "unknown"
    assert outcome["epoch"] == 1


# -----------------------------------------------------------------------------
# 2. Repair Synthesis Tests
# -----------------------------------------------------------------------------
def test_repair_synthesis_bounds_paths_and_links_lineage(triage_env):
    """Verifies that RepairEnvelopeSynthesizer bounds paths, links parent task, and advances epoch."""
    queue, tmp_path = triage_env
    worktree = tmp_path / "worktree_synth"
    evidence_dir = worktree / "evidence"
    evidence_dir.mkdir(parents=True)

    (evidence_dir / "pytest_output.txt").write_text(
        "FAILED alpha_worker/task_runner.py::test_run - RuntimeError: failure\n"
    )

    task_id = "tsk_synth_01"
    original_paths = ["alpha_worker/task_runner.py", "docs/README.md", "scripts/deploy.sh"]
    envelope = {
        "project_id": "alphabrain_dogfood",
        "allowed_paths": original_paths,
    }
    queue.enqueue_task(
        task_id=task_id,
        envelope=envelope,
        provenance=make_provenance(task_id),
        initial_status=TriageStatus.FAILED,
    )

    daemon = CIHealingDaemon(queue=queue, project_id="alphabrain_dogfood")
    task_data = queue.get_task(task_id)
    task_data["worktree_path"] = str(worktree)

    outcome = daemon.process_failed_task(task_data)
    assert outcome["status"] == "repair_enqueued"
    repair_id = outcome["repair_task_id"]

    # Verify repair task in queue
    repair_task = queue.get_task(repair_id)
    assert repair_task is not None
    repair_env = repair_task["envelope"]

    # Bounded paths must include failing file and be a subset of original paths
    assert "alpha_worker/task_runner.py" in repair_env["allowed_paths"]
    assert len(repair_env["allowed_paths"]) <= len(original_paths)
    assert repair_env["parent_task_id"] == task_id
    assert repair_env["repair_epoch"] == 1
    assert "Actionable repair prompt" in repair_env["detailed_instructions"]

    # Original task must be marked REJECTED (superseded)
    orig_task = queue.get_task(task_id)
    assert orig_task["status"] == TriageStatus.REJECTED.value
    assert f"Superseded by {repair_id}" in orig_task["safety_reason"]


def test_repair_synthesis_rejects_invalid_envelope_shape(triage_env):
    """Verifies that invalid envelope synthesis output safely rejects the task without crashing."""
    queue, tmp_path = triage_env
    worktree = tmp_path / "worktree_invalid_synth"
    worktree.mkdir()
    evidence_dir = worktree / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "pytest_output.txt").write_text("FAILED test.py - error")

    task_id = "tsk_invalid_synth"
    queue.enqueue_task(
        task_id=task_id,
        envelope={"project_id": "alphabrain_dogfood", "allowed_paths": ["test.py"]},
        provenance=make_provenance(task_id),
        initial_status=TriageStatus.FAILED,
    )

    daemon = CIHealingDaemon(queue=queue, project_id="alphabrain_dogfood")
    task_data = queue.get_task(task_id)
    task_data["worktree_path"] = str(worktree)

    with patch.object(RepairEnvelopeSynthesizer, "synthesize", return_value={"malformed": True}):
        outcome = daemon.process_failed_task(task_data)

    assert outcome["status"] == "rejected"
    assert "invalid envelope shape" in outcome["reason"]


# -----------------------------------------------------------------------------
# 3. Circuit Breaker Protection Tests
# -----------------------------------------------------------------------------
def test_circuit_breaker_trips_on_repeated_identical_failures(triage_env):
    """Verifies that repeated identical failure signatures trip the circuit breaker and bound retries."""
    queue, tmp_path = triage_env
    worktree = tmp_path / "worktree_cb"
    evidence_dir = worktree / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "pytest_output.txt").write_text("FAILED test_foo.py::test_bar - AssertionError\n")

    root_id = "tsk_cb_repeat"
    queue.enqueue_task(
        task_id=root_id,
        envelope={"project_id": "alphabrain_dogfood", "allowed_paths": ["test_foo.py"]},
        provenance=make_provenance(root_id),
        initial_status=TriageStatus.FAILED,
    )

    daemon = CIHealingDaemon(queue=queue, project_id="alphabrain_dogfood", auto_approve_repairs=True)

    # First failure -> repair_1
    task_data = queue.get_task(root_id)
    task_data["worktree_path"] = str(worktree)
    res1 = daemon.process_failed_task(task_data)
    assert res1["status"] == "repair_enqueued"
    assert res1["repair_task_id"] == f"{root_id}_repair_1"

    # Second failure with same signature -> repair_2
    rep1_id = res1["repair_task_id"]
    rep1_data = queue.get_task(rep1_id)
    rep1_data["worktree_path"] = str(worktree)
    res2 = daemon.process_failed_task(rep1_data)
    assert res2["status"] == "repair_enqueued"
    assert res2["repair_task_id"] == f"{rep1_id}_repair_2"

    # Third failure with same signature -> exceeds max_identical_signatures (threshold=3) -> TRIPPED
    rep2_id = res2["repair_task_id"]
    rep2_data = queue.get_task(rep2_id)
    rep2_data["worktree_path"] = str(worktree)
    res3 = daemon.process_failed_task(rep2_data)

    assert res3["status"] == "circuit_breaker_tripped"
    assert res3["trip_reason"] == TripReason.ESCALATED_HUMAN_REVIEW.value

    # Check task is rejected for human intervention
    tripped_task = queue.get_task(rep2_id)
    assert tripped_task["status"] == TriageStatus.REJECTED.value
    assert "ESCALATED: Identical failures exceeded threshold" in tripped_task["safety_reason"]

    # No further repair task should be queued
    assert queue.get_task(f"{rep2_id}_repair_3") is None


def test_circuit_breaker_shared_lineage_across_epochs(triage_env):
    """Verifies that repair tasks share the root task lineage for circuit breaker state."""
    queue, tmp_path = triage_env
    root_id = "tsk_lineage_root"

    # Pre-populate circuit breaker state for root_id
    cb = CircuitBreaker()
    cb.attempts = 2
    cb.identical_count = 2
    cb.last_signature = "sig_stuck"
    queue.save_circuit_breaker(root_id, cb.to_dict())

    # Task is an epoch 2 repair task
    repair_task_id = f"{root_id}_repair_2"
    worktree = tmp_path / "worktree_lineage"
    worktree.mkdir()
    evidence_dir = worktree / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "pytest_output.txt").write_text("FAILED tests/test_lineage.py - AssertionError")

    queue.enqueue_task(
        task_id=repair_task_id,
        envelope={"project_id": "alphabrain_dogfood", "allowed_paths": ["tests/test_lineage.py"]},
        provenance=make_provenance(repair_task_id),
        initial_status=TriageStatus.FAILED,
    )

    daemon = CIHealingDaemon(queue=queue, project_id="alphabrain_dogfood")
    task_data = queue.get_task(repair_task_id)
    task_data["worktree_path"] = str(worktree)

    with patch.object(daemon.failure_analyzer, "analyze", return_value={"signature": "sig_stuck", "pytest_failures": []}):
        outcome = daemon.process_failed_task(task_data)

    assert outcome["status"] == "circuit_breaker_tripped"
    assert outcome["root_id"] == root_id


# -----------------------------------------------------------------------------
# 4. Retry Queuing & Parallel Dispatch Integration Tests
# -----------------------------------------------------------------------------
def test_auto_approve_repairs_enqueues_approved_status(triage_env):
    """Verifies that auto_approve_repairs=True creates repair tasks in APPROVED status."""
    queue, tmp_path = triage_env
    worktree = tmp_path / "worktree_auto_approve"
    evidence_dir = worktree / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "pytest_output.txt").write_text("FAILED test_a.py - error\n")

    task_id = "tsk_auto_app_01"
    queue.enqueue_task(
        task_id=task_id,
        envelope={"project_id": "alphabrain_dogfood", "allowed_paths": ["test_a.py"]},
        provenance=make_provenance(task_id),
        initial_status=TriageStatus.FAILED,
    )

    daemon = CIHealingDaemon(queue=queue, project_id="alphabrain_dogfood", auto_approve_repairs=True)
    task_data = queue.get_task(task_id)
    task_data["worktree_path"] = str(worktree)

    outcome = daemon.process_failed_task(task_data)
    assert outcome["status"] == "repair_enqueued"
    assert outcome["initial_status"] == TriageStatus.APPROVED.value

    # Verify task is immediately available in APPROVED status
    repair_task = queue.get_task(outcome["repair_task_id"])
    assert repair_task["status"] == TriageStatus.APPROVED.value


def test_parallel_dispatcher_integrates_with_ci_healing_repair_loop(triage_env):
    """
    End-to-end integration test:
    1. ParallelWorkerDispatcher dispatches initial task.
    2. Worker execution fails.
    3. Dispatcher reaps task, routes to CIHealingDaemon.
    4. CIHealingDaemon analyzes failure and enqueues repair task in APPROVED status with inherited plan.
    5. ParallelWorkerDispatcher leases and dispatches the repair task on subsequent turn.
    """
    queue, tmp_path = triage_env
    task_id = "tsk_integration_root"

    # Setup initial task with valid planning attestation and approved status
    queue.enqueue_task(
        task_id=task_id,
        envelope={"project_id": "alphabrain_dogfood", "allowed_paths": ["module.py"]},
        provenance=make_provenance(task_id),
        initial_status=TriageStatus.PENDING_REVIEW,
    )
    attach_test_plan(queue, task_id)
    queue.approve_task(task_id)

    import multiprocessing as mp
    executed_q = mp.get_context("fork").Queue()

    def mock_worker(leased_task):
        executed_q.put(leased_task["id"])
        if leased_task["id"] == task_id:
            # First turn fails
            t_id = leased_task["id"]
            wt_path = tmp_path / f"wt_{t_id}"
            evidence_dir = wt_path / "evidence"
            evidence_dir.mkdir(parents=True, exist_ok=True)
            (evidence_dir / "pytest_output.txt").write_text("FAILED test_module.py::test_run - Error\n")

            # Fail the task in the queue with evidence
            queue.fail_task(
                leased_task["id"],
                error_details={
                    "error": "Acceptance gates failed",
                    "evidence": [{"gate_type": "unit_test", "stdout_snippet": "FAILED test_module.py", "stderr_snippet": ""}],
                },
                allow_retry=False,
            )
            return None
        else:
            # Repair turn succeeds
            return {"status": "success", "task_id": leased_task["id"]}

    mock_worktree_mgr = MagicMock()
    mock_worktree_mgr.get_worktree_path.side_effect = lambda t_id: tmp_path / f"wt_{t_id}"

    daemon = CIHealingDaemon(
        queue=queue,
        project_id="alphabrain_dogfood",
    )

    dispatcher = ParallelWorkerDispatcher(
        queue=queue,
        max_workers=2,
        worktree_mgr=mock_worktree_mgr,
        ci_healing_daemon=daemon,
        worker_cycle_fn=mock_worker,
    )

    # 1. First dispatch cycle: dispatches initial task
    dispatched = dispatcher.dispatch_batch()
    assert task_id in dispatched
    assert dispatcher.active_count() == 1

    # Wait for execution to finish
    time.sleep(0.3)

    # 2. Reap cycle: detects failure, routes to CI healing, synthesizes repair_1
    reaped = dispatcher.reap_completed_tasks()
    assert task_id in reaped["failed"]

    # Verify repair task was synthesized and enqueued in PENDING_REVIEW status
    repair_id = f"{task_id}_repair_1"
    repair_row = queue.get_task(repair_id)
    assert repair_row is not None
    assert repair_row["status"] == TriageStatus.PENDING_REVIEW.value

    # Safety gate & planning attestation attaches and approves repair task
    attach_test_plan(queue, repair_id)
    assert queue.approve_task(repair_id) is True

    # 3. Second dispatch cycle: parallel dispatcher picks up repair task
    dispatched_repairs = dispatcher.dispatch_batch()
    assert repair_id in dispatched_repairs

    time.sleep(0.3)

    # 4. Reap repair task: finishes successfully
    reaped_repair = dispatcher.reap_completed_tasks()
    assert repair_id in reaped_repair["completed"]

    collected_executed = []
    while not executed_q.empty():
        collected_executed.append(executed_q.get_nowait())
    assert collected_executed == [task_id, repair_id]
    dispatcher.stop(wait=True)


def test_parallel_dispatcher_process_pending_heals(triage_env):
    """Verifies that ParallelWorkerDispatcher.process_pending_heals processes orphaned FAILED tasks."""
    queue, tmp_path = triage_env
    task_id = "tsk_orphaned_failed"
    worktree = tmp_path / f"alpha_{task_id}"
    evidence_dir = worktree / "evidence"
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "pytest_output.txt").write_text("FAILED test_orphan.py - AssertionError")

    queue.enqueue_task(
        task_id=task_id,
        envelope={"project_id": "alphabrain_dogfood", "allowed_paths": ["test_orphan.py"]},
        provenance=make_provenance(task_id),
        initial_status=TriageStatus.FAILED,
    )

    mock_worktree_mgr = MagicMock()
    mock_worktree_mgr.get_worktree_path.return_value = worktree

    daemon = CIHealingDaemon(queue=queue, project_id="alphabrain_dogfood", auto_approve_repairs=True)
    dispatcher = ParallelWorkerDispatcher(
        queue=queue,
        max_workers=2,
        worktree_mgr=mock_worktree_mgr,
        ci_healing_daemon=daemon,
    )

    results = dispatcher.process_pending_heals()
    assert len(results) == 1
    assert results[0]["task_id"] == task_id
    assert results[0]["result"]["status"] == "repair_enqueued"

    # Repair task was queued
    assert queue.get_task(f"{task_id}_repair_1") is not None
    dispatcher.stop(wait=True)
