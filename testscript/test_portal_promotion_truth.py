"""Real queue lifecycle: approval is review; verified promotion is completion."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue, TriageStatus
from testscript.planning_fixtures import approve_with_plan


def test_real_portal_javascript_filters_task_events():
    subprocess.run(
        ["node", str(Path(__file__).with_name("portal_event_isolation.cjs"))],
        check=True,
        timeout=10,
    )


@pytest.fixture
def completed_queue(tmp_path):
    queue = TaskTriageQueue(tmp_path / "queue.db", tmp_path / "stop")
    provenance = TaskProvenance("meeting", "speaker", 0, "test", "test", 1, "session", 0, "")
    queue.enqueue_task("task", {"project_id": "project"}, provenance, TriageStatus.PENDING_REVIEW)
    assert approve_with_plan(queue, "task")
    leased = queue.lease_next_approved_task("worker")
    assert leased is not None
    meta = leased["provenance"]["lease_metadata"]
    assert queue.complete_task(
        "task",
        {"result_sha": "a" * 40, "gates_passed": True},
        worker_id="worker",
        lease_id=meta["lease_id"],
        fencing_epoch=meta["fencing_epoch"],
        attempt_id=meta["attempt_id"],
    )
    return queue


def test_review_never_emits_completed(completed_queue):
    queue = completed_queue
    assert queue.record_senior_review("task", "APPROVE", "FINAL_APPROVAL", True)
    events = queue.get_project_events("project")
    assert events[-1]["event_type"] == "senior_review_approved"
    assert events[-1]["state"] == "review"
    assert not any(e["state"] == "completed" for e in events)


def test_promotion_event_is_idempotent_across_restart(completed_queue):
    queue = completed_queue
    queue.record_task_promotion("task", "a" * 40)
    restarted = TaskTriageQueue(queue.db_path, queue.emergency_lock_path)
    restarted.record_task_promotion("task", "a" * 40)
    events = restarted.get_project_events("project")
    promoted = [e for e in events if e["event_type"] == "task_promoted"]
    assert len(promoted) == 1
    assert promoted[0]["state"] == "completed"
    assert restarted.get_task("task")["result"]["promotion"]["result_sha"] == "a" * 40


def test_wrong_result_has_no_completion_event(completed_queue):
    with pytest.raises(ValueError):
        completed_queue.record_task_promotion("task", "b" * 40)
    assert not any(e["state"] == "completed" for e in completed_queue.get_project_events("project"))


def test_event_storage_failure_propagates(completed_queue):
    with patch.object(
        completed_queue, "_execute_write_with_retry", side_effect=RuntimeError("offline")
    ):
        with pytest.raises(RuntimeError, match="offline"):
            completed_queue.record_task_promotion("task", "a" * 40)
    assert "promotion" not in completed_queue.get_task("task")["result"]
