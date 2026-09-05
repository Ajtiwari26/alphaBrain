import time

import pytest
from fastapi.testclient import TestClient

from alpha_core.api.app import app
from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue, TriageStatus


@pytest.fixture
def queue(tmp_path):
    q = TaskTriageQueue(db_path=tmp_path / "test.db", emergency_lock_path=tmp_path / "lock")
    return q

@pytest.fixture
def api_client():
    return TestClient(app)

def test_happy_path(queue):
    prov = TaskProvenance("mtg", "spk", 0.0, "exc", "mod", 1.0, "eva", time.time(), "hash")
    task_id = "tsk_1"
    queue.enqueue_task(task_id, {"project_id": "prj_alphabrain_dogfood"}, prov)
    queue.approve_task(task_id)

    # Lease
    task = queue.lease_next_approved_task(worker_id="worker_1")
    assert task is not None
    assert task["id"] == task_id

    # Extract metadata
    lease_meta = task["provenance"]["lease_metadata"]
    worker_id = lease_meta["worker_id"]
    lease_id = lease_meta["lease_id"]
    epoch = lease_meta["fencing_epoch"]
    attempt_id = lease_meta["attempt_id"]

    # Complete
    res = queue.complete_task(
        task_id,
        {"success": True},
        worker_id=worker_id,
        lease_id=lease_id,
        fencing_epoch=epoch,
        attempt_id=attempt_id
    )
    assert res is True

    t = queue.get_task(task_id)
    assert t["status"] == TriageStatus.COMPLETED.value

def test_cross_worker_denial(queue):
    prov = TaskProvenance("mtg", "spk", 0.0, "exc", "mod", 1.0, "eva", time.time(), "hash2")
    task_id = "tsk_2"
    queue.enqueue_task(task_id, {"project_id": "prj_alphabrain_dogfood"}, prov)
    queue.approve_task(task_id)

    task = queue.lease_next_approved_task(worker_id="worker_1")
    lease_meta = task["provenance"]["lease_metadata"]

    # Complete with wrong worker
    res = queue.complete_task(
        task_id,
        {"success": True},
        worker_id="worker_2",
        lease_id=lease_meta["lease_id"],
        fencing_epoch=lease_meta["fencing_epoch"],
        attempt_id=lease_meta["attempt_id"]
    )
    assert res is False

def test_stale_reassignment_race(queue):
    prov = TaskProvenance("mtg", "spk", 0.0, "exc", "mod", 1.0, "eva", time.time(), "hash3")
    task_id = "tsk_3"
    queue.enqueue_task(task_id, {"project_id": "prj_alphabrain_dogfood"}, prov)
    queue.approve_task(task_id)

    task = queue.lease_next_approved_task(worker_id="worker_1")
    lease_meta1 = task["provenance"]["lease_metadata"]

    # Reassign to worker 2
    res = queue.reassign(
        task_id,
        worker_id="worker_1",
        lease_id=lease_meta1["lease_id"],
        fencing_epoch=lease_meta1["fencing_epoch"],
        attempt_id=lease_meta1["attempt_id"],
        new_worker_id="worker_2"
    )
    assert res is True

    # Worker 1 tries to complete
    res1 = queue.complete_task(
        task_id,
        {"success": True},
        worker_id="worker_1",
        lease_id=lease_meta1["lease_id"],
        fencing_epoch=lease_meta1["fencing_epoch"],
        attempt_id=lease_meta1["attempt_id"]
    )
    assert res1 is False

    t = queue.get_task(task_id)
    lease_meta2 = t["provenance"]["lease_metadata"]
    assert lease_meta2["worker_id"] == "worker_2"

    # Worker 2 tries to complete
    res2 = queue.complete_task(
        task_id,
        {"success": True},
        worker_id="worker_2",
        lease_id=lease_meta2["lease_id"],
        fencing_epoch=lease_meta2["fencing_epoch"],
        attempt_id=lease_meta2["attempt_id"]
    )
    assert res2 is True

def test_expired_lease_denial(queue):
    prov = TaskProvenance("mtg", "spk", 0.0, "exc", "mod", 1.0, "eva", time.time(), "hash4")
    task_id = "tsk_4"
    queue.enqueue_task(task_id, {"project_id": "prj_alphabrain_dogfood"}, prov)
    queue.approve_task(task_id)

    queue.lease_next_approved_task(worker_id="worker_1")
    queue.reap_stale_executing_tasks(timeout_seconds=-1)  # Force reap

    t = queue.get_task(task_id)
    assert t["status"] == TriageStatus.FAILED.value
    assert "task_reaped_by_watchdog" in [x["action"] for x in t["provenance"]["audit_history"]]

def test_fail_task_fencing(queue):
    prov = TaskProvenance("mtg", "spk", 0.0, "exc", "mod", 1.0, "eva", time.time(), "hash5")
    task_id = "tsk_5"
    queue.enqueue_task(task_id, {"project_id": "prj_alphabrain_dogfood"}, prov)
    queue.approve_task(task_id)

    task = queue.lease_next_approved_task(worker_id="worker_1")
    lease_meta = task["provenance"]["lease_metadata"]

    # Reassign
    queue.reassign(
        task_id,
        worker_id="worker_1",
        lease_id=lease_meta["lease_id"],
        fencing_epoch=lease_meta["fencing_epoch"],
        attempt_id=lease_meta["attempt_id"],
        new_worker_id="worker_2"
    )

    # Worker 1 fails task - should be denied by CAS
    res = queue.fail_task(
        task_id,
        {"error": "fail"},
        worker_id="worker_1",
        lease_id=lease_meta["lease_id"],
        fencing_epoch=lease_meta["fencing_epoch"],
        attempt_id=lease_meta["attempt_id"]
    )
    assert res is False

