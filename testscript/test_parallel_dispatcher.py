"""
testscript/test_parallel_dispatcher.py
Comprehensive concurrency and lifecycle tests for ParallelWorkerDispatcher.

Validates:
1. Retrieval of approved tasks from TaskTriageQueue.
2. Strict concurrency pool limits up to max_workers.
3. Execution of tasks in isolated git worktrees.
4. Termination and queue failure handling for execution timeouts.
5. Routing of completed tasks to Senior Review and CI Healing.
6. Routing of failed tasks to CI Healing.
7. Emergency stop tombstone enforcement.
8. Daemon cycle execution and graceful shutdown.
"""

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue, TriageStatus
from alpha_worker.parallel_dispatcher import ParallelWorkerDispatcher
from alpha_worker.triage_dispatcher import PRProposal


@pytest.fixture
def test_env(tmp_path: Path):
    db_path = tmp_path / "test_triage.db"
    emergency_lock = tmp_path / "test_emergency.lock"
    queue = TaskTriageQueue(db_path=db_path, emergency_lock_path=emergency_lock)
    return queue, tmp_path


def make_dummy_provenance(task_id: str) -> TaskProvenance:
    return TaskProvenance(
        meeting_id=f"meet_{task_id}",
        speaker_id="speaker_1",
        utterance_timestamp=time.time(),
        transcript_excerpt=f"Execute task {task_id}",
        extraction_model="test-model",
        extraction_confidence=1.0,
        eva_session_id=f"session_{task_id}",
        created_at=time.time(),
        content_hash=f"hash_{task_id}",
    )


def test_dispatcher_retrieves_approved_tasks(test_env):
    queue, _ = test_env
    dispatcher = ParallelWorkerDispatcher(queue=queue, max_workers=3)

    # 1. Enqueue tasks with various statuses
    for i in range(3):
        t_id = f"tsk_approved_{i}"
        queue.enqueue_task(
            task_id=t_id,
            envelope={"project_id": "alphabrain_dogfood", "title": f"Task {i}"},
            provenance=make_dummy_provenance(t_id),
            initial_status=TriageStatus.APPROVED,
        )

    queue.enqueue_task(
        task_id="tsk_pending",
        envelope={"project_id": "alphabrain_dogfood", "title": "Pending"},
        provenance=make_dummy_provenance("tsk_pending"),
        initial_status=TriageStatus.PENDING_REVIEW,
    )

    queue.enqueue_task(
        task_id="tsk_rejected",
        envelope={"project_id": "alphabrain_dogfood", "title": "Rejected"},
        provenance=make_dummy_provenance("tsk_rejected"),
        initial_status=TriageStatus.REJECTED,
    )

    approved = dispatcher.get_approved_tasks()
    approved_ids = {t["id"] for t in approved}
    assert len(approved) == 3
    assert approved_ids == {"tsk_approved_0", "tsk_approved_1", "tsk_approved_2"}
    assert "tsk_pending" not in approved_ids
    assert "tsk_rejected" not in approved_ids


def test_dispatcher_respects_max_workers_concurrency(test_env):
    queue, _ = test_env
    max_workers = 2

    active_tasks_seen = set()
    peak_concurrency = 0
    concurrency_lock = threading.Lock()
    barrier = threading.Barrier(max_workers)
    release_event = threading.Event()

    def mock_worker_cycle(task_dict):
        nonlocal peak_concurrency
        t_id = task_dict["id"]
        with concurrency_lock:
            active_tasks_seen.add(t_id)
            current_count = len(active_tasks_seen)
            if current_count > peak_concurrency:
                peak_concurrency = current_count

        barrier.wait(timeout=5.0)
        release_event.wait(timeout=5.0)

        with concurrency_lock:
            active_tasks_seen.remove(t_id)

        return PRProposal(
            task_id=t_id,
            project_id="alphabrain_dogfood",
            branch_name=f"alpha/{t_id}",
            base_commit="abc1234",
            head_commit="def5678",
            title="Test PR",
            description="Testing concurrency",
            files_changed=["file.py"],
            diff_stat="1 file changed",
            gates_passed=True,
            evidence=[],
            created_at=time.time(),
            attempt_id="att_1",
            worker_id="wrk_1",
        )

    dispatcher = ParallelWorkerDispatcher(
        queue=queue,
        max_workers=max_workers,
        worker_cycle_fn=mock_worker_cycle,
    )

    tasks = [
        {"id": "tsk_c1", "envelope": {"project_id": "p"}},
        {"id": "tsk_c2", "envelope": {"project_id": "p"}},
        {"id": "tsk_c3", "envelope": {"project_id": "p"}},
    ]

    # Dispatch first two tasks (should succeed)
    d1 = dispatcher.dispatch_task(tasks[0])
    d2 = dispatcher.dispatch_task(tasks[1])
    assert d1 == "tsk_c1"
    assert d2 == "tsk_c2"
    assert dispatcher.active_count() == 2
    assert dispatcher.is_pool_full() is True

    # Dispatching third task should be rejected because pool is full
    d3 = dispatcher.dispatch_task(tasks[2])
    assert d3 is None
    assert dispatcher.active_count() == 2

    # Release workers
    release_event.set()
    time.sleep(0.2)
    dispatcher.reap_completed_tasks()

    assert peak_concurrency == 2
    assert dispatcher.active_count() == 0
    dispatcher.stop(wait=True)


def test_isolated_git_worktree_per_task(test_env):
    queue, tmp_path = test_env
    worktrees_created: list[tuple[str, str]] = []

    class MockWorktreeManager:
        def create_or_resume_worktree(self, repo_path, task_id, base_commit):
            wt_path = tmp_path / "worktrees" / f"alpha_{task_id}"
            wt_path.mkdir(parents=True, exist_ok=True)
            worktrees_created.append((task_id, str(wt_path)))
            return wt_path

        @staticmethod
        def find_disallowed_changes(changed_files, allowed_paths):
            return []

    mock_mgr = MockWorktreeManager()
    executed_worktrees: list[str] = []

    def mock_worker_cycle(task_dict):
        t_id = task_dict["id"]
        wt = mock_mgr.create_or_resume_worktree("/repo", t_id, "base_sha")
        executed_worktrees.append(str(wt))
        return None

    dispatcher = ParallelWorkerDispatcher(
        queue=queue,
        max_workers=3,
        worktree_mgr=mock_mgr,
        worker_cycle_fn=mock_worker_cycle,
    )

    task_a = {"id": "tsk_wt_1", "envelope": {"base_commit": "sha1"}}
    task_b = {"id": "tsk_wt_2", "envelope": {"base_commit": "sha2"}}

    dispatcher.dispatch_task(task_a)
    dispatcher.dispatch_task(task_b)

    time.sleep(0.3)
    dispatcher.reap_completed_tasks()

    assert len(worktrees_created) == 2
    wt_dict = dict(worktrees_created)
    assert wt_dict["tsk_wt_1"] != wt_dict["tsk_wt_2"]
    assert "alpha_tsk_wt_1" in wt_dict["tsk_wt_1"]
    assert "alpha_tsk_wt_2" in wt_dict["tsk_wt_2"]
    dispatcher.stop(wait=True)


def test_execution_timeout_termination_and_queue_handling(test_env):
    queue, _ = test_env
    task_id = "tsk_timeout_test"

    # Enqueue in EXECUTING state so fail_task can transition it properly
    queue.enqueue_task(
        task_id=task_id,
        envelope={"project_id": "alphabrain_dogfood"},
        provenance=make_dummy_provenance(task_id),
        initial_status=TriageStatus.EXECUTING,
    )

    task_started = threading.Event()

    def hanging_worker_cycle(task_dict):
        task_started.set()
        time.sleep(10.0)  # Hang past timeout
        return None

    mock_ci_healing = MagicMock()

    dispatcher = ParallelWorkerDispatcher(
        queue=queue,
        max_workers=2,
        timeout_seconds=0.2,  # 200ms timeout
        worker_cycle_fn=hanging_worker_cycle,
        ci_healing_daemon=mock_ci_healing,
    )

    task_payload = {"id": task_id, "envelope": {}}
    dispatched = dispatcher.dispatch_task(task_payload)
    assert dispatched == task_id
    assert task_started.wait(timeout=2.0) is True

    # Sleep slightly to allow timeout threshold to pass
    time.sleep(0.3)

    timed_out = dispatcher.handle_timeouts()
    assert task_id in timed_out
    assert dispatcher.active_count() == 0

    # Verify task was marked FAILED in TaskTriageQueue
    task_row = queue.get_task(task_id)
    assert task_row is not None
    assert task_row["status"] == TriageStatus.FAILED.value
    assert "timeout" in task_row["result_json"].lower()

    # Verify failed task was routed to CI healing
    mock_ci_healing.process_failed_task.assert_called_once()

    dispatcher.stop(wait=False)


def test_completed_tasks_routed_to_senior_review_and_ci_healing(test_env):
    queue, _ = test_env
    task_id = "tsk_routed_success"

    queue.enqueue_task(
        task_id=task_id,
        envelope={"project_id": "alphabrain_dogfood"},
        provenance=make_dummy_provenance(task_id),
        initial_status=TriageStatus.COMPLETED,
    )

    mock_senior_review = MagicMock()
    mock_senior_review.execute_senior_review.return_value = MagicMock(
        to_dict=lambda: {"approved": True, "verdict": "APPROVE"}
    )

    mock_ci_healing = MagicMock()

    dispatcher = ParallelWorkerDispatcher(
        queue=queue,
        max_workers=2,
        senior_review_engine=mock_senior_review,
        ci_healing_daemon=mock_ci_healing,
    )

    results = dispatcher.route_completed_task(task_id)

    # Verify Senior Review was invoked
    mock_senior_review.execute_senior_review.assert_called_once_with(task_id)
    assert results["senior_review"]["approved"] is True

    # Verify CI Healing Daemon process_completed_task was invoked
    mock_ci_healing.process_completed_task.assert_called_once()
    assert results["ci_healing"]["status"] == "processed"

    dispatcher.stop(wait=True)


def test_failed_tasks_routed_to_ci_healing(test_env):
    queue, _ = test_env
    task_id = "tsk_routed_failed"

    queue.enqueue_task(
        task_id=task_id,
        envelope={"project_id": "alphabrain_dogfood"},
        provenance=make_dummy_provenance(task_id),
        initial_status=TriageStatus.FAILED,
    )

    mock_ci_healing = MagicMock()

    dispatcher = ParallelWorkerDispatcher(
        queue=queue,
        max_workers=2,
        ci_healing_daemon=mock_ci_healing,
    )

    results = dispatcher.route_failed_task(task_id, reason="Gate check failure")

    mock_ci_healing.process_failed_task.assert_called_once()
    assert results["ci_healing"]["status"] == "processed"
    assert results["reason"] == "Gate check failure"

    dispatcher.stop(wait=True)


def test_emergency_stop_halts_parallel_dispatching(test_env):
    queue, _ = test_env
    queue.emergency_stop(reason="Security Incident Test")

    dispatcher = ParallelWorkerDispatcher(queue=queue, max_workers=2)

    # 1. Querying approved tasks yields empty list under emergency stop
    approved = dispatcher.get_approved_tasks()
    assert approved == []

    # 2. Batch dispatch does not lease or dispatch any tasks
    dispatched = dispatcher.dispatch_batch()
    assert dispatched == []
    assert dispatcher.active_count() == 0

    dispatcher.stop(wait=True)


def test_run_once_and_continuous_mode_execution(test_env):
    queue, _ = test_env
    dispatcher = ParallelWorkerDispatcher(queue=queue, max_workers=2, poll_interval=0.01)

    summary = dispatcher.run_once()
    assert summary["active_count"] == 0
    assert summary["available_slots"] == 2
    assert summary["timed_out"] == []
    assert summary["dispatched"] == []

    # Run continuous loop for 2 cycles
    start = time.time()
    dispatcher.run_continuously(interval=0.01, max_cycles=2)
    assert time.time() - start < 2.0
