import argparse
import json
import os
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from alpha_core.queue.triage_queue import TriageStatus
from alpha_core.triage_cli import cmd_merge
from alpha_protocol.task import ReviewAttestation


def run_git(repo_path, *cmd):
    return subprocess.run(
        ["git", *cmd], cwd=repo_path, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def real_git_repo(tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    run_git(repo_path, "init")
    run_git(repo_path, "config", "user.name", "Test User")
    run_git(repo_path, "config", "user.email", "test@example.com")
    run_git(repo_path, "commit", "--allow-empty", "-m", "Initial commit")
    base_commit = run_git(repo_path, "rev-parse", "HEAD")

    run_git(repo_path, "checkout", "-b", "alpha/tsk_123")
    run_git(repo_path, "commit", "--allow-empty", "-m", "Task commit")
    result_sha = run_git(repo_path, "rev-parse", "HEAD")
    tree_digest = run_git(repo_path, "rev-parse", "HEAD^{tree}")

    # Go back to main
    run_git(repo_path, "checkout", "main")

    return repo_path, base_commit, result_sha, tree_digest


def create_valid_attestation(
    task_id,
    result_sha,
    base_commit,
    tree_digest,
    secret="test_promotion_signing_secret_123",
    approved=True,
):
    evidence = {"dummy": "evidence"}
    return ReviewAttestation.create(
        task_id=task_id,
        attempt_id="att_1",
        result_sha=result_sha,
        base_commit=base_commit,
        tree_digest=tree_digest,
        pro_verdict="APPROVE",
        opus_verdict="FINAL_APPROVAL",
        approved=approved,
        reviewed_at=time.time(),
        evidence=evidence,
        secret=secret,
        nonce="nonce",
        executor_id="exec_1",
        key_id="alpha_test_key",
    ).model_dump()


@pytest.fixture
def base_task(real_git_repo):
    repo_path, base_commit, result_sha, tree_digest = real_git_repo
    evidence = {"dummy": "evidence"}
    expected_evidence_digest = ReviewAttestation.compute_evidence_digest(evidence)

    return {
        "id": "tsk_123",
        "status": TriageStatus.COMPLETED.value,
        "branch_name": "alpha/tsk_123",
        "envelope": {
            "repo": str(repo_path),
            "base_commit": base_commit,
        },
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "exec_1",
            "result_sha": result_sha,
            "evidence": evidence,
            "evidence_digest": expected_evidence_digest,
            "senior_review": {
                "approved": True,
                "attestation": create_valid_attestation(
                    "tsk_123", result_sha, base_commit, tree_digest
                ),
            },
        },
        "provenance": {
            "lease_metadata": {
                "worker_id": "exec_1",
                "attempt_id": "att_1",
                "lease_id": "lease_123",
                "fencing_epoch": 1,
            }
        },
    }


def test_successful_promotion_real_git(base_task):
    queue = MagicMock()
    queue.get_task.return_value = base_task
    args = argparse.Namespace(task_id="tsk_123", json=False)

    with patch.dict(
        os.environ, {"ALPHA_SIGNING_SECRET_alpha_test_key": "test_promotion_signing_secret_123"}
    ):
        exit_code = cmd_merge(args, queue)

    assert exit_code == 0
    repo_path = base_task["envelope"]["repo"]
    assert run_git(repo_path, "rev-parse", "main") == base_task["result"]["result_sha"]

    # Branch should be deleted
    with pytest.raises(subprocess.CalledProcessError):
        run_git(repo_path, "rev-parse", "alpha/tsk_123")

    # State should be FINALIZED
    with open(Path(repo_path) / ".alphabrain" / "promotions" / "nonce.json") as f:
        state = json.load(f)
        assert state["state"] == "FINALIZED"


def test_crash_recovery_from_reserved(base_task):
    queue = MagicMock()
    queue.get_task.return_value = base_task
    args = argparse.Namespace(task_id="tsk_123", json=False)
    repo_path = base_task["envelope"]["repo"]

    # 1. Inject crash right after writing RESERVED
    original_write = __import__(
        "alpha_core.triage_cli", fromlist=["_atomic_write_json"]
    )._atomic_write_json

    def crash_after_reserved(filepath, data):
        original_write(filepath, data)
        if data.get("state") == "RESERVED":
            raise RuntimeError("CRASH!")

    with patch.dict(
        os.environ, {"ALPHA_SIGNING_SECRET_alpha_test_key": "test_promotion_signing_secret_123"}
    ):
        with patch("alpha_core.triage_cli._atomic_write_json", side_effect=crash_after_reserved):
            with pytest.raises(RuntimeError, match="CRASH!"):
                cmd_merge(args, queue)

    # Verify we are in RESERVED state and main has not advanced
    with open(Path(repo_path) / ".alphabrain" / "promotions" / "nonce.json") as f:
        state = json.load(f)
        assert state["state"] == "RESERVED"
    assert run_git(repo_path, "rev-parse", "main") == base_task["envelope"]["base_commit"]

    # 2. Recover
    with patch.dict(
        os.environ, {"ALPHA_SIGNING_SECRET_alpha_test_key": "test_promotion_signing_secret_123"}
    ):
        exit_code = cmd_merge(args, queue)

    assert exit_code == 0
    assert run_git(repo_path, "rev-parse", "main") == base_task["result"]["result_sha"]
    with open(Path(repo_path) / ".alphabrain" / "promotions" / "nonce.json") as f:
        state = json.load(f)
        assert state["state"] == "FINALIZED"


def test_crash_recovery_from_applied(base_task):
    queue = MagicMock()
    queue.get_task.return_value = base_task
    args = argparse.Namespace(task_id="tsk_123", json=False)
    repo_path = base_task["envelope"]["repo"]

    # 1. Inject crash right after writing APPLIED
    original_write = __import__(
        "alpha_core.triage_cli", fromlist=["_atomic_write_json"]
    )._atomic_write_json

    def crash_after_applied(filepath, data):
        original_write(filepath, data)
        if data.get("state") == "APPLIED":
            raise SystemExit("CRASH!")

    with patch.dict(
        os.environ, {"ALPHA_SIGNING_SECRET_alpha_test_key": "test_promotion_signing_secret_123"}
    ):
        with patch("alpha_core.triage_cli._atomic_write_json", side_effect=crash_after_applied):
            with pytest.raises(SystemExit, match="CRASH!"):
                cmd_merge(args, queue)

    # Verify we are in APPLIED state and main HAS advanced (because update-ref happened before write APPLIED)
    with open(Path(repo_path) / ".alphabrain" / "promotions" / "nonce.json") as f:
        state = json.load(f)
        assert state["state"] == "APPLIED"
    assert run_git(repo_path, "rev-parse", "main") == base_task["result"]["result_sha"]

    # Recovery must not switch an unrelated/detached checkout silently.
    run_git(repo_path, "checkout", base_task["envelope"]["base_commit"])

    with patch.dict(
        os.environ, {"ALPHA_SIGNING_SECRET_alpha_test_key": "test_promotion_signing_secret_123"}
    ):
        assert cmd_merge(args, queue) == 1
    assert run_git(repo_path, "rev-parse", "HEAD") == base_task["envelope"]["base_commit"]
    run_git(repo_path, "checkout", "main")

    # 2. Recover
    with patch.dict(
        os.environ, {"ALPHA_SIGNING_SECRET_alpha_test_key": "test_promotion_signing_secret_123"}
    ):
        exit_code = cmd_merge(args, queue)

    assert exit_code == 0
    assert run_git(repo_path, "rev-parse", "main") == base_task["result"]["result_sha"]
    # Verify index is clean and correctly on main
    assert run_git(repo_path, "rev-parse", "HEAD") == base_task["result"]["result_sha"]
    with open(Path(repo_path) / ".alphabrain" / "promotions" / "nonce.json") as f:
        state = json.load(f)
        assert state["state"] == "FINALIZED"


def _worker_merge(base_task_json):
    import argparse
    import json
    import os
    from unittest.mock import MagicMock

    from alpha_core.triage_cli import cmd_merge

    os.environ["ALPHA_SIGNING_SECRET_alpha_test_key"] = "test_promotion_signing_secret_123"

    queue = MagicMock()
    queue.get_task.return_value = json.loads(base_task_json)
    args = argparse.Namespace(task_id="tsk_123", json=False)

    try:
        return cmd_merge(args, queue)
    except Exception as e:
        return str(e)


def test_concurrency_safe(base_task):
    import json

    # Run 5 concurrent processes attempting to merge the same task
    base_task_json = json.dumps(base_task)

    results = []
    with ProcessPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_worker_merge, base_task_json) for _ in range(5)]
        for f in as_completed(futures):
            results.append(f.result())

    # One should succeed (exit code 0), and others should either gracefully exit (code 0 via idempotency block)
    # or fail due to lock contention/destination advanced.
    assert all(isinstance(r, int) for r in results), (
        f"Expected all processes to return ints, got: {results}"
    )

    repo_path = base_task["envelope"]["repo"]
    assert run_git(repo_path, "rev-parse", "main") == base_task["result"]["result_sha"]
    with open(Path(repo_path) / ".alphabrain" / "promotions" / "nonce.json") as f:
        state = json.load(f)
        assert state["state"] == "FINALIZED"
