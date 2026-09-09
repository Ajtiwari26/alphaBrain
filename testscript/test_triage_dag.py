import json
import time
from argparse import Namespace
from pathlib import Path

import pytest

from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue
from testscript.planning_fixtures import approve_with_plan


def make_dummy_envelope(task_id: str, depends_on: list[str] | None = None):
    deps = [{"task_id": d, "required_status": "completed"} for d in (depends_on or [])]
    return {
        "protocol_version": "1",
        "task_id": task_id,
        "project_id": "test_proj",
        "repo": ".",
        "base_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "objective": "Test",
        "allowed_paths": ["."],
        "dependencies": deps,
    }


def make_dummy_provenance(task_id: str, depends_on: list[str] | None = None):
    content = f"{task_id}_{','.join(depends_on or [])}"
    return TaskProvenance(
        meeting_id="m1",
        speaker_id="s1",
        utterance_timestamp=time.time(),
        transcript_excerpt="test",
        extraction_model="test",
        extraction_confidence=1.0,
        eva_session_id="e1",
        created_at=time.time(),
        content_hash=f"hash-{content}",
    )


@pytest.fixture
def queue(tmp_path: Path):
    db_path = tmp_path / "queue.db"
    lock_path = tmp_path / "emergency.lock"
    q = TaskTriageQueue(db_path=db_path, emergency_lock_path=lock_path)
    return q


def test_enqueue_cycle_detection(queue: TaskTriageQueue):
    queue.enqueue_task(
        "task_1",
        make_dummy_envelope("task_1", depends_on=["task_2"]),
        make_dummy_provenance("task_1", depends_on=["task_2"]),
    )
    with pytest.raises(ValueError, match="Circular dependency detected"):
        queue.enqueue_task(
            "task_2",
            make_dummy_envelope("task_2", depends_on=["task_1"]),
            make_dummy_provenance("task_2", depends_on=["task_1"]),
        )


def test_modify_cycle_detection(queue: TaskTriageQueue):
    queue.enqueue_task("task_1", make_dummy_envelope("task_1"), make_dummy_provenance("task_1"))
    queue.enqueue_task(
        "task_2",
        make_dummy_envelope("task_2", depends_on=["task_1"]),
        make_dummy_provenance("task_2", depends_on=["task_1"]),
    )
    env1 = make_dummy_envelope("task_1", depends_on=["task_2"])
    with pytest.raises(ValueError, match="Circular dependency detected"):
        queue.modify_task("task_1", new_envelope=env1)


def test_dag_leasing_blocked(queue: TaskTriageQueue):
    queue.enqueue_task(
        "task_1",
        make_dummy_envelope("task_1", depends_on=["task_2"]),
        make_dummy_provenance("task_1", depends_on=["task_2"]),
    )
    queue.enqueue_task("task_2", make_dummy_envelope("task_2"), make_dummy_provenance("task_2"))
    approve_with_plan(queue, "task_1")
    approve_with_plan(queue, "task_2")
    task = queue.lease_next_approved_task()
    assert task is not None
    assert task["id"] == "task_2"
    assert queue.lease_next_approved_task() is None
    queue.complete_task("task_2", {"result": "ok", "senior_review": {"approved": True}})
    task = queue.lease_next_approved_task()
    assert task is not None
    assert task["id"] == "task_1"


def test_cli_dag(queue: TaskTriageQueue):
    queue.enqueue_task("task_1", make_dummy_envelope("task_1"), make_dummy_provenance("task_1"))
    queue.enqueue_task(
        "task_2",
        make_dummy_envelope("task_2", depends_on=["task_1"]),
        make_dummy_provenance("task_2", depends_on=["task_1"]),
    )
    from alpha_core.triage_cli import cmd_dag

    args = Namespace(json=True)
    import io
    import sys

    out = io.StringIO()
    sys.stdout = out
    try:
        cmd_dag(args, queue)
    finally:
        sys.stdout = sys.__stdout__
    output = json.loads(out.getvalue())
    assert "task_1" in output["tasks"]
    assert "task_2" in output["tasks"]
    assert "task_2" in output["graph"]["task_1"]
