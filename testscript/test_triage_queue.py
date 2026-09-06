"""
testscript/test_triage_queue.py
Unit and concurrency tests for AlphaBrain Phase 9 Task Triage Queue.

Authoritative Reference:
docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md (Section 6)
"""

from __future__ import annotations

import concurrent.futures
import time
from pathlib import Path

import pytest

from alpha_core.queue.triage_queue import (
    EmergencyStopActiveError,
    TaskProvenance,
    TaskTriageQueue,
    TriageStatus,
)


@pytest.fixture
def temp_queue(tmp_path: Path) -> TaskTriageQueue:
    db_file = tmp_path / "test_triage.db"
    lock_file = tmp_path / "emergency_stop.lock"
    return TaskTriageQueue(db_path=db_file, emergency_lock_path=lock_file, busy_timeout_ms=3000)


def create_sample_provenance(
    envelope: dict, seed: str = "meeting-1", content_hash: str | None = None
) -> TaskProvenance:
    if content_hash is None:
        import hashlib
        import json

        canonical_env = json.dumps(envelope, sort_keys=True, separators=(",", ":"), default=str)
        content_hash = hashlib.sha256(canonical_env.encode("utf-8")).hexdigest()
    return TaskProvenance(
        meeting_id=f"room_{seed}",
        speaker_id="founder_ajay",
        utterance_timestamp=1725345600.0,
        transcript_excerpt="We need to build a self-development triage queue for AlphaBrain.",
        extraction_model="gemini-3.1-pro-high",
        extraction_confidence=0.98,
        eva_session_id="eva_sess_001",
        created_at=time.time(),
        content_hash=content_hash,
    )


def test_enqueue_and_provenance_roundtrip(temp_queue: TaskTriageQueue) -> None:
    task_id = "tsk_test_001"
    envelope = {"objective": "Build queue", "repo": ".", "allowed_paths": ["alpha_core/queue/"]}
    prov = create_sample_provenance(envelope)

    enqueued_id = temp_queue.enqueue_task(task_id, envelope, prov)
    assert enqueued_id == task_id

    task = temp_queue.get_task(task_id)
    assert task is not None
    assert task["id"] == task_id
    assert task["status"] == TriageStatus.PENDING_REVIEW.value
    assert task["envelope"]["objective"] == "Build queue"
    assert task["provenance"]["speaker_id"] == "founder_ajay"
    import hashlib
    import json

    expected_hash = hashlib.sha256(
        json.dumps(envelope, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    assert task["provenance"]["content_hash"] == expected_hash


def test_strict_worker_blindness_to_unvetted_tasks(temp_queue: TaskTriageQueue) -> None:
    """P9 Critical Law: Workers NEVER see or lease pending_review tasks."""
    task_id = "tsk_unvetted"
    envelope = {"objective": "Unchecked task"}
    prov = create_sample_provenance(envelope, seed="unvetted")

    temp_queue.enqueue_task(task_id, envelope, prov)

    # Worker attempts to lease next task
    leased = temp_queue.lease_next_approved_task()
    assert leased is None, "Worker must NOT be able to lease unvetted task"


def test_approval_and_atomic_lease(temp_queue: TaskTriageQueue) -> None:
    task_id = "tsk_to_approve"
    envelope = {"objective": "Approved task"}
    prov = create_sample_provenance(envelope, seed="appr")

    temp_queue.enqueue_task(task_id, envelope, prov)

    # Approve task
    ok = temp_queue.approve_task(task_id, safety_verdict="PASS", safety_reason="Passed 5 Laws")
    assert ok is True

    # Check status
    task = temp_queue.get_task(task_id)
    assert task is not None
    assert task["status"] == TriageStatus.APPROVED.value

    # Worker leases task
    leased = temp_queue.lease_next_approved_task()
    assert leased is not None
    assert leased["id"] == task_id
    assert leased["status"] == TriageStatus.EXECUTING.value

    # Second worker attempts to lease — queue is empty
    second_lease = temp_queue.lease_next_approved_task()
    assert second_lease is None, "Task was already leased; second worker should get None"


def test_task_rejection(temp_queue: TaskTriageQueue) -> None:
    task_id = "tsk_to_reject"
    envelope = {"objective": "Dangerous prompt injection"}
    prov = create_sample_provenance(envelope, seed="bad")

    temp_queue.enqueue_task(task_id, envelope, prov)
    ok = temp_queue.reject_task(task_id, reason="Touches protected path")
    assert ok is True

    task = temp_queue.get_task(task_id)
    assert task is not None
    assert task["status"] == TriageStatus.REJECTED.value

    # Worker lease returns None
    assert temp_queue.lease_next_approved_task() is None


def test_retry_and_circuit_breaker(temp_queue: TaskTriageQueue) -> None:
    task_id = "tsk_flaky"
    envelope = {"objective": "Flaky test execution"}
    prov = create_sample_provenance(envelope, seed="flaky")

    temp_queue.enqueue_task(task_id, envelope, prov)
    temp_queue.approve_task(task_id)

    # First execution attempt
    leased = temp_queue.lease_next_approved_task()
    assert leased is not None

    # First failure -> should re-queue as APPROVED (retry 1/2)
    temp_queue.fail_task(
        task_id, error_details={"error": "AssertionError"}, allow_retry=True, max_retries=2
    )
    task_after_fail1 = temp_queue.get_task(task_id)
    assert task_after_fail1 is not None
    assert task_after_fail1["status"] == TriageStatus.APPROVED.value
    assert task_after_fail1["retry_count"] == 1

    # Second execution attempt
    leased2 = temp_queue.lease_next_approved_task()
    assert leased2 is not None
    assert leased2["id"] == task_id

    # Second failure -> should re-queue as APPROVED (retry 2/2)
    temp_queue.fail_task(
        task_id, error_details={"error": "AssertionError 2"}, allow_retry=True, max_retries=2
    )
    task_after_fail2 = temp_queue.get_task(task_id)
    assert task_after_fail2 is not None
    assert task_after_fail2["status"] == TriageStatus.APPROVED.value
    assert task_after_fail2["retry_count"] == 2

    # Third execution attempt
    leased3 = temp_queue.lease_next_approved_task()
    assert leased3 is not None

    # Third failure -> max_retries reached -> status becomes FAILED
    temp_queue.fail_task(
        task_id, error_details={"error": "Permanent failure"}, allow_retry=True, max_retries=2
    )
    task_after_fail3 = temp_queue.get_task(task_id)
    assert task_after_fail3 is not None
    assert task_after_fail3["status"] == TriageStatus.FAILED.value


def test_completion_lifecycle(temp_queue: TaskTriageQueue) -> None:
    task_id = "tsk_success"
    envelope = {"objective": "Working feature"}
    prov = create_sample_provenance(envelope, seed="success")

    temp_queue.enqueue_task(task_id, envelope, prov)
    temp_queue.approve_task(task_id)
    temp_queue.lease_next_approved_task()

    result_payload = {"pr_url": "https://github.com/org/repo/pull/1", "gates_passed": True}
    ok = temp_queue.complete_task(
        task_id,
        result=result_payload,
        worktree_path="/tmp/worktree/tsk_success",
        branch_name="feature/alpha-gen-tsk_success",
    )
    assert ok is True

    task = temp_queue.get_task(task_id)
    assert task is not None
    assert task["status"] == TriageStatus.COMPLETED.value
    assert task["worktree_path"] == "/tmp/worktree/tsk_success"
    assert task["branch_name"] == "feature/alpha-gen-tsk_success"
    assert task["result"]["pr_url"] == "https://github.com/org/repo/pull/1"


def test_content_hash_deduplication(temp_queue: TaskTriageQueue) -> None:
    task_id1 = "tsk_orig"
    task_id2 = "tsk_duplicate"
    envelope = {"objective": "Duplicated spec"}
    prov1 = create_sample_provenance(envelope, seed="meeting1")
    prov2 = create_sample_provenance(envelope, seed="meeting2")

    res1 = temp_queue.enqueue_task(task_id1, envelope, prov1)
    assert res1 == task_id1

    # Second enqueue with identical content_hash returns the first ID
    res2 = temp_queue.enqueue_task(task_id2, envelope, prov2)
    assert res2 == task_id1

    # Queue contains only 1 entry
    tasks = temp_queue.list_tasks()
    assert len(tasks) == 1


def test_emergency_stop_tombstone(temp_queue: TaskTriageQueue) -> None:
    # 1. Normal state: not stopped
    assert temp_queue.is_emergency_stopped() is False

    # 2. Write tombstone file
    temp_queue.emergency_lock_path.write_text("EMERGENCY STOP")
    assert temp_queue.is_emergency_stopped() is True

    # 3. Writes must be rejected
    with pytest.raises(EmergencyStopActiveError):
        temp_queue.enqueue_task(
            "tsk_blocked",
            {"obj": "blocked"},
            create_sample_provenance({"obj": "blocked"}, seed="blocked"),
        )

    # 4. Worker leasing must return None
    assert temp_queue.lease_next_approved_task() is None

    # 5. Remove tombstone -> operations resume cleanly
    temp_queue.emergency_lock_path.unlink()
    assert temp_queue.is_emergency_stopped() is False

    enqueued = temp_queue.enqueue_task(
        "tsk_resumed",
        {"obj": "resumed"},
        create_sample_provenance({"obj": "resumed"}, seed="resumed"),
    )
    assert enqueued == "tsk_resumed"


def test_concurrent_multi_thread_writes(temp_queue: TaskTriageQueue) -> None:
    """Proves that multiple concurrent writers operate cleanly under WAL mode with backoff."""
    task_count = 20

    def worker_write(idx: int) -> str:
        tid = f"tsk_concurrent_{idx}"
        prov = create_sample_provenance({"idx": idx}, seed=f"thread_{idx}")
        return temp_queue.enqueue_task(tid, {"idx": idx}, prov)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(worker_write, i) for i in range(task_count)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == task_count
    all_tasks = temp_queue.list_tasks(limit=100)
    assert len(all_tasks) == task_count
