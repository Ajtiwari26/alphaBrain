import argparse
import fcntl
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from alpha_core.queue.triage_queue import TriageStatus
from alpha_core.triage_cli import cmd_merge
from alpha_protocol.task import ReviewAttestation


def create_valid_attestation(
    task_id,
    result_sha,
    base_commit,
    secret="test_promotion_signing_secret_123",
    approved=True,
    pro_verdict="APPROVE",
    opus_verdict="FINAL_APPROVAL",
    evidence=None,
):
    import time
    if evidence is None:
        evidence = {"dummy": "evidence"}
    return ReviewAttestation.create(
        task_id=task_id,
        attempt_id="att_1",
        result_sha=result_sha,
        base_commit=base_commit,
        tree_digest="c" * 40,
        pro_verdict=pro_verdict,
        opus_verdict=opus_verdict,
        approved=approved,
        reviewed_at=time.time(),
        evidence=evidence,
        secret=secret,
        nonce="nonce",
        executor_id="exec",
        key_id="key1",
    ).model_dump()


@pytest.fixture
def mock_queue():
    queue = MagicMock()
    return queue


@pytest.fixture
def base_task(tmp_path):
    repo_path = str(tmp_path / "repo")
    os.makedirs(repo_path, exist_ok=True)
    evidence = {"dummy": "evidence"}
    return {
        "id": "tsk_123",
        "status": TriageStatus.COMPLETED.value,
        "branch_name": "alpha/tsk_123",
        "envelope": {
            "repo": repo_path,
            "base_commit": "a" * 40,
        },
        "result": {
            "gates_passed": True,
            "result_sha": "b" * 40,
            "evidence": evidence,
            "senior_review": {
                "approved": True,
                "attestation": create_valid_attestation(
                    task_id="tsk_123",
                    result_sha="b" * 40,
                    base_commit="a" * 40,
                    evidence=evidence,
                ),
            },
        },
    }


def test_successful_promotion_merging_exact_sha(mock_queue, base_task):
    mock_queue.get_task.return_value = base_task
    args = argparse.Namespace(task_id="tsk_123", json=False)

    with (
        patch.dict(os.environ, {"ALPHA_SIGNING_SECRET": "test_promotion_signing_secret_123"}),
        patch("subprocess.run") as mock_run,
    ):
        # mock git rev-parse branch_name to return result_sha
        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "rev-parse"]:
                m = MagicMock()
                m.stdout = ("c" * 40 if "^{tree}" in cmd[2] else "b" * 40) + "\n"
                return m
            m = MagicMock()
            m.stdout = ""
            return m

        mock_run.side_effect = side_effect

        exit_code = cmd_merge(args, mock_queue)

        assert exit_code == 0

        # Verify git merge --ff-only result_sha was called
        merge_called = False
        for call in mock_run.call_args_list:
            if call[0][0] == ["git", "merge", "--ff-only", "b" * 40]:
                merge_called = True
        assert merge_called, "Exact result_sha should be merged"


def test_promotion_rejected_invalid_forged_attestation(mock_queue, base_task):
    # Forge the attestation signature
    base_task["result"]["senior_review"]["attestation"]["signature"] = "f" * 64
    mock_queue.get_task.return_value = base_task
    args = argparse.Namespace(task_id="tsk_123", json=False)

    with patch.dict(os.environ, {"ALPHA_SIGNING_SECRET": "test_promotion_signing_secret_123"}):
        exit_code = cmd_merge(args, mock_queue)
    assert exit_code == 1


def test_promotion_rejected_result_sha_mismatch(mock_queue, base_task):
    # Attestation result_sha differs from result["result_sha"]
    base_task["result"]["senior_review"]["attestation"] = create_valid_attestation(
        task_id="tsk_123",
        result_sha="c" * 40,  # Mismatch!
        base_commit="a" * 40,
    )
    mock_queue.get_task.return_value = base_task
    args = argparse.Namespace(task_id="tsk_123", json=False)

    with patch.dict(os.environ, {"ALPHA_SIGNING_SECRET": "test_promotion_signing_secret_123"}):
        exit_code = cmd_merge(args, mock_queue)
    assert exit_code == 1


def test_promotion_rejected_branch_tip_mismatch(mock_queue, base_task):
    mock_queue.get_task.return_value = base_task
    args = argparse.Namespace(task_id="tsk_123", json=False)

    with (
        patch.dict(os.environ, {"ALPHA_SIGNING_SECRET": "test_promotion_signing_secret_123"}),
        patch("subprocess.run") as mock_run,
    ):

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "rev-parse"]:
                m = MagicMock()
                m.stdout = "c" * 40 + "\n"  # Branch tip does not match expected result_sha
                return m
            m = MagicMock()
            m.stdout = ""
            return m

        mock_run.side_effect = side_effect

        exit_code = cmd_merge(args, mock_queue)
        assert exit_code == 1


def test_cross_process_promotion_lock(mock_queue, base_task):
    mock_queue.get_task.return_value = base_task
    args = argparse.Namespace(task_id="tsk_123", json=False)

    repo_path = base_task["envelope"]["repo"]
    lock_file_path = Path(repo_path) / ".alphabrain" / "promotion.lock"
    lock_file_path.parent.mkdir(parents=True, exist_ok=True)

    with (
        patch.dict(os.environ, {"ALPHA_SIGNING_SECRET": "test_promotion_signing_secret_123"}),
        patch("subprocess.run") as mock_run,
    ):

        def side_effect(cmd, **kwargs):
            if cmd[:2] == ["git", "rev-parse"]:
                m = MagicMock()
                m.stdout = ("c" * 40 if "^{tree}" in cmd[2] else "b" * 40) + "\n"
                return m
            m = MagicMock()
            m.stdout = ""
            return m

        mock_run.side_effect = side_effect

        # Hold the lock exclusively
        with open(lock_file_path, "w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)

            # While holding the lock, try to run cmd_merge
            exit_code = cmd_merge(args, mock_queue)
            assert exit_code == 1

            # Release lock
            fcntl.flock(lock_file, fcntl.LOCK_UN)
