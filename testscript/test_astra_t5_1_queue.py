import hashlib
import json
import time

import pytest

from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue, TriageStatus


@pytest.fixture
def queue(tmp_path):
    db_path = tmp_path / "test_queue.db"
    return TaskTriageQueue(db_path=db_path)


def get_canonical_hash(envelope: dict) -> str:
    return hashlib.sha256(
        json.dumps(envelope, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def make_provenance(envelope: dict) -> TaskProvenance:
    return TaskProvenance(
        meeting_id="m1",
        speaker_id=None,
        utterance_timestamp=time.time(),
        transcript_excerpt="test",
        extraction_model="test",
        extraction_confidence=1.0,
        eva_session_id="e1",
        created_at=time.time(),
        content_hash=get_canonical_hash(envelope),
    )


def test_symbolic_ref_rejection(queue):
    for ref in ["main", "HEAD", "HEAD~1", "tags/v1.0"]:
        envelope = {"base_commit": ref}
        prov = make_provenance(envelope)
        with pytest.raises(
            ValueError,
            match="Task base_commit must be a fully resolved 40-character hexadecimal SHA",
        ):
            queue.enqueue_task("task1", envelope, prov)


def test_partial_hash_rejection(queue):
    envelope = {"base_commit": "abc1234567"}  # 10 chars
    prov = make_provenance(envelope)
    with pytest.raises(
        ValueError, match="Task base_commit must be a fully resolved 40-character hexadecimal SHA"
    ):
        queue.enqueue_task("task2", envelope, prov)


def test_valid_40_char_sha_approval(queue):
    valid_sha = "a" * 40
    envelope = {"base_commit": valid_sha}
    prov = make_provenance(envelope)
    # enqueue successfully
    queue.enqueue_task("task3", envelope, prov)
    # verify it can be approved
    assert queue.approve_task("task3") is True


def test_content_hash_mismatch(queue):
    envelope = {"test": "val"}
    make_provenance(envelope)
    # Corrupt the hash
    corrupt_prov = TaskProvenance(
        meeting_id="m1",
        speaker_id=None,
        utterance_timestamp=time.time(),
        transcript_excerpt="test",
        extraction_model="test",
        extraction_confidence=1.0,
        eva_session_id="e1",
        created_at=time.time(),
        content_hash="c39e33693a0596c508a83796a3505284a18c8d7dda4e6bc51bbbc7dc726a279f",
    )
    with pytest.raises(ValueError, match="Content hash mismatch"):
        queue.enqueue_task("task4", envelope, corrupt_prov)


def test_cumulative_repair_budget(queue):
    valid_sha = "a" * 40
    envelope = {"max_cumulative_retries": 2, "base_commit": valid_sha}
    prov = make_provenance(envelope)
    queue.enqueue_task("task5", envelope, prov)
    queue.approve_task("task5")

    # Lease
    task = queue.lease_next_approved_task("worker1")
    assert task is not None
    assert task["id"] == "task5"

    # Fail it once (retries=1, cumulative=1). It should allow retry.
    res = queue.fail_task(
        "task5",
        "error1",
        allow_retry=True,
        max_retries=2,
        worker_id="worker1",
        lease_id=task["lease_id"],
        fencing_epoch=task["fencing_epoch"],
        attempt_id=task["attempt_id"],
    )
    assert res is True
    t5 = queue.get_task("task5")
    assert t5["status"] == TriageStatus.APPROVED.value
    assert t5["retry_count"] == 1

    # Lease again
    task = queue.lease_next_approved_task("worker1")

    # Fail again (retries=2, cumulative=2). max_retries=1 means it terminally fails on second failure.
    res = queue.fail_task(
        "task5",
        "error2",
        allow_retry=True,
        max_retries=1,
        worker_id="worker1",
        lease_id=task["lease_id"],
        fencing_epoch=task["fencing_epoch"],
        attempt_id=task["attempt_id"],
    )
    t5 = queue.get_task("task5")
    assert t5["status"] == TriageStatus.FAILED.value
    assert t5.get("cumulative_retries", 2) == 2

    # Manual retry #1: This should reset retry_count but preserve cumulative.
    assert queue.retry_task("task5") is False  # Should fail because cumulative >= 2

    t5 = queue.get_task("task5")
    assert t5["status"] == TriageStatus.FAILED.value
    assert "Cumulative lifetime repair budget exhausted" in json.dumps(t5["result"])


def test_parent_dag_senior_review_check(queue):
    valid_sha = "b" * 40
    env_parent = {"job": "parent", "base_commit": valid_sha}
    queue.enqueue_task("parent_t", env_parent, make_provenance(env_parent))
    queue.approve_task("parent_t")

    env_child = {
        "job": "child",
        "base_commit": valid_sha,
        "dependencies": [{"task_id": "parent_t"}],
    }
    queue.enqueue_task("child_t", env_child, make_provenance(env_child))
    queue.approve_task("child_t")

    # Parent is not completed, child cannot lease
    parent_task = queue.lease_next_approved_task("worker1")
    assert parent_task["id"] == "parent_t"
    assert queue.lease_next_approved_task("worker1") is None

    # Complete parent
    queue.complete_task(
        "parent_t",
        {"out": "val"},
        worker_id="worker1",
        lease_id=parent_task["lease_id"],
        fencing_epoch=parent_task["fencing_epoch"],
        attempt_id=parent_task["attempt_id"],
    )

    # Parent completed but no senior review
    assert queue.lease_next_approved_task("worker1") is None

    # Add rejected senior review
    queue.record_senior_review("parent_t", "FAIL", "FAIL", approved=False)
    assert queue.lease_next_approved_task("worker1") is None

    # Add approved senior review
    queue.record_senior_review("parent_t", "PASS", "PASS", approved=True)
    child = queue.lease_next_approved_task("worker1")
    assert child is not None
    assert child["id"] == "child_t"
