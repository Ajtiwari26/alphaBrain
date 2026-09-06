import time

import pytest
from fastapi.testclient import TestClient

from alpha_core.api.app import app, get_triage_queue, require_api_principal
from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue, TriageStatus
from alpha_core.security import AuthPrincipal


@pytest.fixture
def queue(tmp_path):
    q = TaskTriageQueue(db_path=tmp_path / "test.db", emergency_lock_path=tmp_path / "lock")
    return q


@pytest.fixture
def api_client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_overrides():
    yield
    app.dependency_overrides.clear()


@pytest.mark.xfail(reason="R2-R6 gap pending")
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
        attempt_id=attempt_id,
    )
    assert res is True

    t = queue.get_task(task_id)
    assert t["status"] == TriageStatus.COMPLETED.value


@pytest.mark.xfail(reason="R2-R6 gap pending")
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
        attempt_id=lease_meta["attempt_id"],
    )
    assert res is False


@pytest.mark.xfail(reason="R2-R6 gap pending")
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
        new_worker_id="worker_2",
    )
    assert res is True

    # Worker 1 tries to complete
    res1 = queue.complete_task(
        task_id,
        {"success": True},
        worker_id="worker_1",
        lease_id=lease_meta1["lease_id"],
        fencing_epoch=lease_meta1["fencing_epoch"],
        attempt_id=lease_meta1["attempt_id"],
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
        attempt_id=lease_meta2["attempt_id"],
    )
    assert res2 is True


@pytest.mark.xfail(reason="R2-R6 gap pending")
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


@pytest.mark.xfail(reason="R2-R6 gap pending")
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
        new_worker_id="worker_2",
    )

    # Worker 1 fails task - should be denied by CAS
    res = queue.fail_task(
        task_id,
        {"error": "fail"},
        worker_id="worker_1",
        lease_id=lease_meta["lease_id"],
        fencing_epoch=lease_meta["fencing_epoch"],
        attempt_id=lease_meta["attempt_id"],
    )
    assert res is False


def test_release_lease_happy_path(queue):
    prov = TaskProvenance("mtg", "spk", 0.0, "exc", "mod", 1.0, "eva", time.time(), "hash_rel_1")
    task_id = "tsk_rel_1"
    queue.enqueue_task(task_id, {"project_id": "prj_alphabrain_dogfood"}, prov)
    queue.approve_task(task_id)

    task = queue.lease_next_approved_task(worker_id="worker_1")
    assert task is not None
    assert task["status"] == TriageStatus.EXECUTING.value

    lease_meta = task["provenance"]["lease_metadata"]
    released = queue.release_lease(
        task_id=task_id,
        worker_id="worker_1",
        lease_id=lease_meta["lease_id"],
        fencing_epoch=lease_meta["fencing_epoch"],
        attempt_id=lease_meta["attempt_id"],
    )
    assert released is True

    t = queue.get_task(task_id)
    assert t["status"] == TriageStatus.APPROVED.value
    assert t["started_at"] is None
    assert t["retry_count"] == 0  # Crucial: retries are NOT incremented
    assert "lease_metadata" not in t["provenance"]  # Evicted cleanly

    # Can be leased again cleanly
    task2 = queue.lease_next_approved_task(worker_id="worker_2")
    assert task2 is not None
    assert task2["id"] == task_id
    assert task2["worker_id"] == "worker_2"


def test_release_lease_stale_fencing_denial(queue):
    prov = TaskProvenance("mtg", "spk", 0.0, "exc", "mod", 1.0, "eva", time.time(), "hash_rel_2")
    task_id = "tsk_rel_2"
    queue.enqueue_task(task_id, {"project_id": "prj_alphabrain_dogfood"}, prov)
    queue.approve_task(task_id)

    task = queue.lease_next_approved_task(worker_id="worker_1")
    lease_meta = task["provenance"]["lease_metadata"]

    # Wrong worker
    res = queue.release_lease(
        task_id=task_id,
        worker_id="rogue_worker",
        lease_id=lease_meta["lease_id"],
        fencing_epoch=lease_meta["fencing_epoch"],
        attempt_id=lease_meta["attempt_id"],
    )
    assert res is False

    # Stale epoch
    res = queue.release_lease(
        task_id=task_id,
        worker_id="worker_1",
        lease_id=lease_meta["lease_id"],
        fencing_epoch=lease_meta["fencing_epoch"] - 1000,
        attempt_id=lease_meta["attempt_id"],
    )
    assert res is False

    # Still executing
    t = queue.get_task(task_id)
    assert t["status"] == TriageStatus.EXECUTING.value


def test_api_result_fencing_tamper_matrix(queue, api_client):
    app.dependency_overrides[get_triage_queue] = lambda: queue
    app.dependency_overrides[require_api_principal] = lambda: AuthPrincipal(
        subject="worker_1", role="worker"
    )

    prov = TaskProvenance("mtg", "spk", 0.0, "exc", "mod", 1.0, "eva", time.time(), "hash_api_1")
    task_id = "tsk_api_1"
    queue.enqueue_task(task_id, {"project_id": "prj_alphabrain_dogfood"}, prov)
    queue.approve_task(task_id)

    task = queue.lease_next_approved_task(worker_id="worker_1")
    lease_meta = task["provenance"]["lease_metadata"]

    # 1. Tampered worker_id -> 403
    r = api_client.post(
        f"/api/triage/tasks/{task_id}/result",
        json={
            "status": "completed",
            "result": {"ok": True},
            "worker_id": "spoofed_worker",
            "lease_id": lease_meta["lease_id"],
            "fencing_epoch": lease_meta["fencing_epoch"],
            "attempt_id": lease_meta["attempt_id"],
        },
    )
    assert r.status_code == 403
    assert "Lease fencing violation" in r.json()["detail"]

    # 2. Tampered lease_id -> 403
    r = api_client.post(
        f"/api/triage/tasks/{task_id}/result",
        json={
            "status": "completed",
            "result": {"ok": True},
            "worker_id": "worker_1",
            "lease_id": "invalid_lease_uuid",
            "fencing_epoch": lease_meta["fencing_epoch"],
            "attempt_id": lease_meta["attempt_id"],
        },
    )
    assert r.status_code == 403
    assert "Lease fencing violation" in r.json()["detail"]

    # 3. Stale fencing_epoch -> 403
    r = api_client.post(
        f"/api/triage/tasks/{task_id}/result",
        json={
            "status": "completed",
            "result": {"ok": True},
            "worker_id": "worker_1",
            "lease_id": lease_meta["lease_id"],
            "fencing_epoch": lease_meta["fencing_epoch"] - 1,
            "attempt_id": lease_meta["attempt_id"],
        },
    )
    assert r.status_code == 403
    assert "Lease fencing violation" in r.json()["detail"]

    # 4. Tampered attempt_id -> 403
    r = api_client.post(
        f"/api/triage/tasks/{task_id}/result",
        json={
            "status": "completed",
            "result": {"ok": True},
            "worker_id": "worker_1",
            "lease_id": lease_meta["lease_id"],
            "fencing_epoch": lease_meta["fencing_epoch"],
            "attempt_id": "invalid_attempt_uuid",
        },
    )
    assert r.status_code == 403
    assert "Lease fencing violation" in r.json()["detail"]

    # 5. Valid submission -> 200
    r = api_client.post(
        f"/api/triage/tasks/{task_id}/result",
        json={
            "status": "completed",
            "result": {"ok": True},
            "worker_id": "worker_1",
            "lease_id": lease_meta["lease_id"],
            "fencing_epoch": lease_meta["fencing_epoch"],
            "attempt_id": lease_meta["attempt_id"],
        },
    )
    assert r.status_code == 200
    assert r.json()["state"] == "completed"

    # 6. Subsequent submission when not executing -> 409 Conflict
    r = api_client.post(
        f"/api/triage/tasks/{task_id}/result",
        json={
            "status": "completed",
            "result": {"ok": True},
            "worker_id": "worker_1",
            "lease_id": lease_meta["lease_id"],
            "fencing_epoch": lease_meta["fencing_epoch"],
            "attempt_id": lease_meta["attempt_id"],
        },
    )
    assert r.status_code == 409
    assert "Task not executing" in r.json()["detail"]


def test_api_lease_tenant_access_denial_compensating_tx(queue, api_client):
    app.dependency_overrides[get_triage_queue] = lambda: queue
    # Worker with unauthorized project access
    app.dependency_overrides[require_api_principal] = lambda: AuthPrincipal(
        subject="unauthorized_worker",
        role="worker",
        project_ids=("other_tenant",),
    )

    prov = TaskProvenance(
        "mtg", "spk", 0.0, "exc", "mod", 1.0, "eva", time.time(), "hash_api_tenant"
    )
    task_id = "tsk_api_tenant"
    queue.enqueue_task(task_id, {"project_id": "prj_alphabrain_dogfood"}, prov)
    queue.approve_task(task_id)

    # Poll lease 5 times; all must return 403 and release lease without burning retries
    for _ in range(5):
        r = api_client.post("/api/triage/tasks/lease", json={})
        assert r.status_code == 403
        assert "Unauthorized tenant access" in r.json()["detail"]

    t = queue.get_task(task_id)
    assert t["status"] == TriageStatus.APPROVED.value
    assert t["retry_count"] == 0  # Never burned into FAILED!
    assert "lease_metadata" not in t["provenance"]  # Stale metadata evicted
