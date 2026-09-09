import time

from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue, TriageStatus
from testscript.planning_fixtures import approve_with_plan


def test_telemetry_recording(tmp_path):
    db_path = tmp_path / "test.db"
    lock_path = tmp_path / "lock.file"
    queue = TaskTriageQueue(db_path=db_path, emergency_lock_path=lock_path)

    # 1. Enqueue task
    task_id = "task_test_123"
    provenance = TaskProvenance(
        meeting_id="m1",
        speaker_id="s1",
        utterance_timestamp=100.0,
        transcript_excerpt="do something",
        extraction_model="test",
        extraction_confidence=0.9,
        eva_session_id="session1",
        created_at=time.time(),
        content_hash="7a38bf81f383f69433ad6e900d35b3e2385593f76a7b7ab5d4355b8ba41ee24b",
    )

    queue.enqueue_task(
        task_id=task_id,
        envelope={"foo": "bar"},
        provenance=provenance,
        initial_status=TriageStatus.PENDING_REVIEW,
    )

    # Wait slightly to ensure queue_wait_seconds > 0
    time.sleep(0.01)

    # Approve task
    approve_with_plan(queue, task_id)

    # 2. Lease task (should record task_leased)
    leased = queue.lease_next_approved_task(worker_id="worker_99")
    assert leased is not None
    assert leased["id"] == task_id

    # Wait slightly for execution_duration_seconds > 0
    time.sleep(0.01)

    # 3. Complete task (should record task_completed)
    queue.complete_task(task_id, result={"success": True})

    # 4. Check telemetry
    telemetry = queue.get_task_telemetry(task_id)

    assert telemetry["transition_count"] == 2
    assert telemetry["queue_wait_seconds"] > 0.0
    assert telemetry["execution_duration_seconds"] > 0.0
    assert telemetry["total_lifecycle_seconds"] > 0.0

    # Test failure path too
    task_id_2 = "task_fail_456"
    provenance_2 = TaskProvenance(
        meeting_id="m2",
        speaker_id="s2",
        utterance_timestamp=100.0,
        transcript_excerpt="do something else",
        extraction_model="test",
        extraction_confidence=0.9,
        eva_session_id="session2",
        created_at=time.time(),
        content_hash="c450c726579d41e1daa46158c07c1ed4a81dddc5e8dcb96ad729bca95e0e6fac",
    )

    queue.enqueue_task(
        task_id=task_id_2,
        envelope={"foo": "baz"},
        provenance=provenance_2,
        initial_status=TriageStatus.PENDING_REVIEW,
    )

    assert approve_with_plan(queue, task_id_2)
    leased_2 = queue.lease_next_approved_task(worker_id="worker_100")
    assert leased_2 is not None

    queue.fail_task(task_id_2, error_details="failed", allow_retry=False)

    telemetry_2 = queue.get_task_telemetry(task_id_2)
    assert telemetry_2["transition_count"] == 2
    assert telemetry_2["queue_wait_seconds"] >= 0.0
    assert telemetry_2["execution_duration_seconds"] >= 0.0
    assert telemetry_2["total_lifecycle_seconds"] >= 0.0

    # Ensure worker_id was recorded in audit history
    task_data = queue.get_task(task_id)
    audit_history = task_data["provenance"]["audit_history"]
    leased_entry = next(entry for entry in audit_history if entry["action"] == "task_leased")
    assert leased_entry["worker_id"] == "worker_99"
