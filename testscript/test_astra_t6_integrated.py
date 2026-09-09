import argparse
import fcntl
import hashlib
import json
import sqlite3
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue, TriageStatus
from alpha_core.triage_cli import cmd_approve, cmd_merge, cmd_retry
from alpha_protocol.task import ReviewAttestation
from alpha_worker.triage_dispatcher import TriageTaskDispatcher
from alpha_worker.worktree import WorktreeManager
from testscript.planning_fixtures import approve_with_plan, attach_test_plan


def get_head_sha(repo_path):
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_path).decode().strip()


@pytest.fixture
def e2e_setup(tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)

    test_file = repo_path / "allowed.py"
    test_file.write_text("def dummy(): pass\n")

    subprocess.run(["git", "add", "allowed.py"], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=True)

    base_commit = get_head_sha(repo_path)

    db_path = tmp_path / "queue.db"
    lock_path = tmp_path / "emergency.lock"
    queue = TaskTriageQueue(str(db_path), str(lock_path))

    from alpha_worker.worktree import settings

    settings.ALLOWED_REPO_ROOTS = (*settings.ALLOWED_REPO_ROOTS, tmp_path)

    return repo_path, base_commit, queue


def create_valid_attestation(
    task_id,
    result_sha,
    base_commit,
    secret="alphabrain_senior_review_key",
    approved=True,
    pro_verdict="APPROVE",
    opus_verdict="FINAL_APPROVAL",
    evidence=None,
    attempt_id="att_1",
    executor_id="exec_1",
):
    import time

    if evidence is None:
        evidence = {"dummy": "evidence"}
    return ReviewAttestation.create(
        task_id=task_id,
        attempt_id=attempt_id,
        result_sha=result_sha,
        base_commit=base_commit,
        tree_digest="c" * 40,
        pro_verdict=pro_verdict,
        opus_verdict=opus_verdict,
        approved=approved,
        reviewed_at=time.time(),
        issued_at=time.time(),
        expires_at=time.time() + 3600,
        evidence=evidence,
        secret=secret,
        nonce="nonce",
        executor_id=executor_id,
        key_id="alpha_test_key",
    ).model_dump()


def make_task_provenance(task_id, envelope):
    canonical_hash = hashlib.sha256(
        json.dumps(envelope, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    return TaskProvenance(
        meeting_id="m1",
        speaker_id="s1",
        utterance_timestamp=1.0,
        transcript_excerpt="test",
        extraction_model="test",
        extraction_confidence=1.0,
        eva_session_id="e1",
        created_at=1.0,
        content_hash=canonical_hash,
    )


def test_full_happy_path_lifecycle(e2e_setup, monkeypatch):
    repo_path, base_commit, queue = e2e_setup
    task_id = "tsk_happy_1"

    envelope = {
        "protocol_version": "1",
        "task_id": task_id,
        "project_id": "test_proj",
        "repo": str(repo_path),
        "base_commit": base_commit,
        "objective": "Test",
        "allowed_paths": ["allowed.py"],
        "acceptance_plan": {
            "required_gates": ["unit_test"],
            "commands": [{"gate_type": "unit_test", "executable": "echo", "args": ["passed"]}],
        },
    }
    queue.enqueue_task(task_id, envelope, make_task_provenance(task_id, envelope))

    args = argparse.Namespace(task_id=task_id, force=True, notes=None, json=False)
    attach_test_plan(queue, task_id)
    assert cmd_approve(args, queue) == 0

    class DummyBridge:
        def check_readiness(self):
            return True, ""

        async def dispatch(self, task, worktree_path, attempt_id, session_dir):
            import subprocess

            (Path(worktree_path) / "allowed.py").write_text("def dummy():\n    print('hello')\n")
            subprocess.run(["git", "add", "allowed.py"], cwd=worktree_path, check=True)
            subprocess.run(["git", "commit", "-m", "worker changes"], cwd=worktree_path, check=True)

            class Res:
                def __init__(self):
                    self.completed = True
                    self.changed_files = ["allowed.py"]

            return Res()

    wm = WorktreeManager()
    dispatcher = TriageTaskDispatcher(
        queue=queue,
        worktree_mgr=wm,
        default_base_commit=base_commit,
        live_bridge=DummyBridge(),
        enable_agent_execution=True,
    )

    proposal = dispatcher.execute_next_cycle()
    assert proposal is not None
    assert proposal.task_id == task_id
    assert proposal.gates_passed is True

    result_sha = proposal.head_commit
    task_data = queue.get_task(task_id)
    res = task_data["result"]
    res["result_sha"] = result_sha
    evidence = res.get("evidence", {})
    attestation = create_valid_attestation(
        task_id,
        result_sha,
        base_commit,
        evidence=evidence,
        attempt_id=res.get("attempt_id", "att_1"),
        executor_id=res.get("worker_id", "exec_1"),
    )
    res["senior_review"] = {"approved": True, "attestation": attestation}
    with sqlite3.connect(queue.db_path) as conn:
        conn.execute(
            "UPDATE task_triage_queue SET result_json = ? WHERE id = ?", (json.dumps(res), task_id)
        )

    args = argparse.Namespace(task_id=task_id, json=False)
    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_test_key", "alphabrain_senior_review_key")

    with patch("subprocess.run") as mock_run:

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "rev-parse"]:
                m = MagicMock()
                if "^{tree}" in cmd[2]:
                    m.stdout = "c" * 40 + "\n"
                else:
                    m.stdout = result_sha + "\n"
                return m
            elif cmd[:2] == ["git", "merge"]:
                m = MagicMock()
                m.stdout = ""
                m.returncode = 0
                return m
            elif cmd[:2] == ["git", "worktree"] and cmd[2] == "remove":
                m = MagicMock()
                m.stdout = ""
                m.returncode = 0
                return m
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        mock_run.side_effect = side_effect

        with patch("alpha_core.triage_cli.advance_checkout") as advance:
            assert cmd_merge(args, queue) == 0
            advance.assert_called_once_with(str(repo_path), base_commit, result_sha)
        assert not any(
            call.args[0][:2] == ["git", "update-ref"] for call in mock_run.call_args_list
        )
        assert queue.get_task(task_id)["result"]["promotion"]["result_sha"] == result_sha


def test_stale_fencing_rejection(e2e_setup):
    repo_path, base_commit, queue = e2e_setup
    task_id = "tsk_fence_1"

    envelope = {
        "protocol_version": "1",
        "task_id": task_id,
        "repo": str(repo_path),
        "base_commit": base_commit,
        "allowed_paths": ["allowed.py"],
    }
    queue.enqueue_task(task_id, envelope, make_task_provenance(task_id, envelope))
    approve_with_plan(queue, task_id)

    task1 = queue.lease_next_approved_task()
    assert task1 is not None
    fencing_epoch1 = task1["fencing_epoch"]
    lease_id1 = task1["lease_id"]
    worker_id1 = task1["worker_id"]
    attempt_id1 = task1["attempt_id"]

    success = queue.release_lease(
        task_id, worker_id1, lease_id1, fencing_epoch1, attempt_id=attempt_id1
    )
    assert success is True

    task2 = queue.lease_next_approved_task()
    assert task2 is not None
    fencing_epoch2 = task2["fencing_epoch"]
    assert fencing_epoch1 != fencing_epoch2

    assert (
        queue.complete_task(
            task_id,
            {"test": "data"},
            str(repo_path),
            "branch",
            worker_id=worker_id1,
            lease_id=lease_id1,
            fencing_epoch=fencing_epoch1,
            attempt_id=attempt_id1,
        )
        is False
    )


def test_review_forgery_rejection(e2e_setup, monkeypatch):
    repo_path, base_commit, queue = e2e_setup
    task_id = "tsk_forge_1"

    envelope = {
        "protocol_version": "1",
        "task_id": task_id,
        "repo": str(repo_path),
        "base_commit": base_commit,
    }
    queue.enqueue_task(task_id, envelope, make_task_provenance(task_id, envelope))

    with sqlite3.connect(queue.db_path) as conn:
        conn.execute(
            "UPDATE task_triage_queue SET status = ? WHERE id = ?",
            (TriageStatus.COMPLETED.value, task_id),
        )

    attestation = create_valid_attestation(task_id, "b" * 40, base_commit)
    attestation["signature"] = "forged_signature"

    res = {
        "gates_passed": True,
        "attempt_id": "att_1",
        "worker_id": "exec_1",
        "result_sha": "b" * 40,
        "senior_review": {"approved": True, "attestation": attestation},
    }
    with sqlite3.connect(queue.db_path) as conn:
        conn.execute(
            "UPDATE task_triage_queue SET result_json = ? WHERE id = ?", (json.dumps(res), task_id)
        )

    args = argparse.Namespace(task_id=task_id, json=False)
    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_test_key", "alphabrain_senior_review_key")
    assert cmd_merge(args, queue) == 1


def test_dag_dependency_block(e2e_setup):
    repo_path, _, queue = e2e_setup

    parent_id = "parent_1"
    child_id = "child_1"

    queue.enqueue_task(
        parent_id, {"task_id": parent_id}, make_task_provenance(parent_id, {"task_id": parent_id})
    )
    queue.enqueue_task(
        child_id,
        {
            "task_id": child_id,
            "dependencies": [{"task_id": parent_id, "required_status": "completed"}],
        },
        make_task_provenance(
            child_id,
            {
                "task_id": child_id,
                "dependencies": [{"task_id": parent_id, "required_status": "completed"}],
            },
        ),
    )

    approve_with_plan(queue, parent_id)
    approve_with_plan(queue, child_id)

    t1 = queue.lease_next_approved_task()
    assert t1["id"] == parent_id

    queue.complete_task(
        parent_id,
        {"gates_passed": True},
        str(repo_path),
        "branch",
        worker_id=t1["worker_id"],
        lease_id=t1["lease_id"],
        fencing_epoch=t1["fencing_epoch"],
    )

    assert queue.lease_next_approved_task() is None

    task_data = queue.get_task(parent_id)
    res = task_data["result"]
    res["senior_review"] = {"approved": True}
    with sqlite3.connect(queue.db_path) as conn:
        conn.execute(
            "UPDATE task_triage_queue SET result_json = ? WHERE id = ?",
            (json.dumps(res), parent_id),
        )

    t2 = queue.lease_next_approved_task()
    assert t2["id"] == child_id


def test_cumulative_retry_exhaustion(e2e_setup):
    _, _, queue = e2e_setup
    task_id = "tsk_retry_1"

    envelope = {
        "protocol_version": "1",
        "task_id": task_id,
        "max_cumulative_retries": 1,
    }
    queue.enqueue_task(task_id, envelope, make_task_provenance(task_id, envelope))

    with sqlite3.connect(queue.db_path) as conn:
        conn.execute(
            "UPDATE task_triage_queue SET status = ?, cumulative_retries = 1 WHERE id = ?",
            (TriageStatus.FAILED.value, task_id),
        )

    args = argparse.Namespace(task_id=task_id, force=True, json=False, notes=None)
    assert cmd_retry(args, queue) == 1

    t = queue.get_task(task_id)
    assert t["status"] == TriageStatus.FAILED.value


def test_cross_process_promotion_lock(e2e_setup, monkeypatch):
    repo_path, base_commit, queue = e2e_setup
    task_id = "tsk_lock_1"

    envelope = {
        "protocol_version": "1",
        "task_id": task_id,
        "repo": str(repo_path),
        "base_commit": base_commit,
    }
    queue.enqueue_task(task_id, envelope, make_task_provenance(task_id, envelope))

    with sqlite3.connect(queue.db_path) as conn:
        conn.execute(
            "UPDATE task_triage_queue SET status = ? WHERE id = ?",
            (TriageStatus.COMPLETED.value, task_id),
        )

    attestation = create_valid_attestation(task_id, "b" * 40, base_commit)
    res = {
        "gates_passed": True,
        "attempt_id": "att_1",
        "worker_id": "exec_1",
        "result_sha": "b" * 40,
        "senior_review": {"approved": True, "attestation": attestation},
    }
    with sqlite3.connect(queue.db_path) as conn:
        conn.execute(
            "UPDATE task_triage_queue SET result_json = ? WHERE id = ?", (json.dumps(res), task_id)
        )

    args = argparse.Namespace(task_id=task_id, json=False)
    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_test_key", "alphabrain_senior_review_key")

    lock_file_path = repo_path / ".alphabrain" / "promotion.lock"
    lock_file_path.parent.mkdir(parents=True, exist_ok=True)

    with patch("subprocess.run") as mock_run:

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "rev-parse"]:
                m = MagicMock()
                if "^{tree}" in cmd[2]:
                    m.stdout = "c" * 40 + "\n"
                else:
                    m.stdout = "b" * 40 + "\n"
                return m
            m = MagicMock()
            m.stdout = ""
            return m

        mock_run.side_effect = side_effect

        with open(lock_file_path, "w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)

            assert cmd_merge(args, queue) == 1

            fcntl.flock(lock_file, fcntl.LOCK_UN)
