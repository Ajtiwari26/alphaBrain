import argparse
from unittest.mock import MagicMock, patch

import pytest

from alpha_core.queue.triage_queue import TriageStatus
from alpha_core.triage_cli import cmd_merge


@pytest.fixture
def mock_queue():
    queue = MagicMock()
    # Setup mock task
    queue.get_task.return_value = {
        "id": "task_123",
        "status": TriageStatus.COMPLETED.value,
        "branch_name": "task-branch",
        "envelope": {"repo": "/fake/repo", "base_commit": "base_sha"},
        "result": {
            "gates_passed": True,
            "result_sha": "result_sha",
            "attempt_id": "attempt_1",
            "worker_id": "worker_1",
            "evidence": {}
        },
        "provenance": {
            "lease_metadata": {
                "attempt_id": "attempt_1",
                "worker_id": "worker_1"
            }
        }
    }
    return queue

def setup_attestation(mock_ReviewAttestation):
    att_mock = MagicMock()
    att_mock.key_id = "alpha_production_v1"
    att_mock.verify.return_value = True
    att_mock.task_id = "task_123"
    att_mock.result_sha = "result_sha"
    att_mock.base_commit = "base_sha"
    att_mock.approved = True
    att_mock.pro_verdict = "APPROVE"
    att_mock.opus_verdict = "FINAL_APPROVAL"
    att_mock.evidence_digest = "evidence_digest"
    att_mock.attempt_id = "attempt_1"
    att_mock.executor_id = "worker_1"
    att_mock.expires_at = 9999999999.0
    att_mock.issued_at = 0.0
    att_mock.nonce = "nonce_123"
    att_mock.tree_digest = "tree_sha"
    mock_ReviewAttestation.return_value = att_mock
    mock_ReviewAttestation.compute_evidence_digest.return_value = "evidence_digest"
    return att_mock

@patch("alpha_protocol.task.ReviewAttestation")
@patch("alpha_core.triage_cli.subprocess.run")
@patch("alpha_core.triage_cli.os.environ.get")
@patch("alpha_core.triage_cli.Path")
@patch("builtins.open")
@patch("fcntl.flock")
@patch("alpha_core.triage_cli._atomic_write_json")
@patch("alpha_core.triage_cli.json.load")
def test_newer_commit_protection_recovery(
    mock_json_load, mock_atomic_write, mock_flock, mock_open, mock_path, mock_env, mock_run, mock_ReviewAttestation, mock_queue
):
    mock_env.return_value = "fake_secret"
    setup_attestation(mock_ReviewAttestation)

    # Simulate APPLIED state for recovery
    mock_json_load.return_value = {
        "nonce": "nonce_123",
        "task_id": "task_123",
        "result_sha": "result_sha",
        "attempt_id": "attempt_1",
        "base_commit": "base_sha",
        "evidence_digest": "evidence_digest",
        "tree_digest": "tree_sha",
        "state": "APPLIED"
    }

    # First call in APPLIED is `git status --porcelain`
    mock_status_res = MagicMock()
    mock_status_res.stdout = ""  # Clean tree

    # Second call is `git rev-parse main`
    mock_rev_parse_res = MagicMock()
    mock_rev_parse_res.stdout = "newer_sha"  # main has advanced!

    # Third call is `git merge-base --is-ancestor result_sha current_main`
    mock_merge_base_res = MagicMock()
    mock_merge_base_res.returncode = 0  # It is an ancestor, so main has advanced

    # Configure side_effects for subprocess.run
    def run_side_effect(args, **kwargs):
        if "status" in args:
            return mock_status_res
        if "rev-parse" in args and "main" in args:
            return mock_rev_parse_res
        if "merge-base" in args:
            return mock_merge_base_res
        return MagicMock()

    mock_run.side_effect = run_side_effect

    args = argparse.Namespace(task_id="task_123", json=False)

    exit_code = cmd_merge(args, mock_queue)
    assert exit_code == 1  # Should abort due to newer commits

@patch("alpha_protocol.task.ReviewAttestation")
@patch("alpha_core.triage_cli.subprocess.run")
@patch("alpha_core.triage_cli.os.environ.get")
@patch("alpha_core.triage_cli.Path")
@patch("builtins.open")
@patch("fcntl.flock")
@patch("alpha_core.triage_cli._atomic_write_json")
@patch("alpha_core.triage_cli.json.load")
def test_single_unstaged_modification_detected(
    mock_json_load, mock_atomic_write, mock_flock, mock_open, mock_path, mock_env, mock_run, mock_ReviewAttestation, mock_queue
):
    mock_env.return_value = "fake_secret"
    setup_attestation(mock_ReviewAttestation)

    # Simulate APPLIED state
    mock_json_load.return_value = {
        "nonce": "nonce_123",
        "task_id": "task_123",
        "result_sha": "result_sha",
        "attempt_id": "attempt_1",
        "base_commit": "base_sha",
        "evidence_digest": "evidence_digest",
        "tree_digest": "tree_sha",
        "state": "APPLIED"
    }

    # Simulate dirty tree with single unstaged file
    mock_status_res = MagicMock()
    mock_status_res.stdout = " M file.py\n"

    def run_side_effect(args, **kwargs):
        if "status" in args:
            return mock_status_res
        return MagicMock()

    mock_run.side_effect = run_side_effect

    args = argparse.Namespace(task_id="task_123", json=False)

    exit_code = cmd_merge(args, mock_queue)
    assert exit_code == 1  # Should abort due to dirty tree

@patch("alpha_protocol.task.ReviewAttestation")
@patch("alpha_core.triage_cli.subprocess.run")
@patch("alpha_core.triage_cli.os.environ.get")
@patch("alpha_core.triage_cli.Path")
@patch("builtins.open")
@patch("fcntl.flock")
@patch("alpha_core.triage_cli._atomic_write_json")
@patch("alpha_core.triage_cli.json.load")
def test_non_exemption_alphabrain_in_path(
    mock_json_load, mock_atomic_write, mock_flock, mock_open, mock_path, mock_env, mock_run, mock_ReviewAttestation, mock_queue
):
    mock_env.return_value = "fake_secret"
    setup_attestation(mock_ReviewAttestation)

    # Simulate APPLIED state
    mock_json_load.return_value = {
        "nonce": "nonce_123",
        "task_id": "task_123",
        "result_sha": "result_sha",
        "attempt_id": "attempt_1",
        "base_commit": "base_sha",
        "evidence_digest": "evidence_digest",
        "tree_digest": "tree_sha",
        "state": "APPLIED"
    }

    # Simulate dirty tree with a file containing alphabrain but not in .alphabrain/
    mock_status_res = MagicMock()
    mock_status_res.stdout = " M src/my_alphabrain.py\n"

    def run_side_effect(args, **kwargs):
        if "status" in args:
            return mock_status_res
        return MagicMock()

    mock_run.side_effect = run_side_effect

    args = argparse.Namespace(task_id="task_123", json=False)

    exit_code = cmd_merge(args, mock_queue)
    assert exit_code == 1  # Should abort due to dirty tree
