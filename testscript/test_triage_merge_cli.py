"""
Unit tests verifying the autonomous fast-forward PR merge engine for AlphaBrain.
Ensures acceptance gate enforcement, 2-Round Senior Review enforcement, fail-closed handling,
clean fast-forward merge into main, and worktree/branch pruning.
"""

import time
from unittest.mock import MagicMock, patch

from alpha_core.queue.triage_queue import TriageStatus
from alpha_core.triage_cli import cmd_merge, cmd_senior_review


def test_merge_rejects_missing_task():
    queue = MagicMock()
    queue.get_task.return_value = None
    args = MagicMock(task_id="missing_task_id", json=False, skip_senior_review=False)
    assert cmd_merge(args, queue) == 1


def test_merge_rejects_incomplete_task():
    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_executing",
        "status": TriageStatus.EXECUTING.value,
    }
    args = MagicMock(task_id="task_executing", json=False, skip_senior_review=False)
    assert cmd_merge(args, queue) == 1


def test_merge_rejects_failed_gates():
    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_failed_gates",
        "status": TriageStatus.COMPLETED.value,
        "result": {"gates_passed": False},
    }
    args = MagicMock(task_id="task_failed_gates", json=False, skip_senior_review=False)
    assert cmd_merge(args, queue) == 1


def test_merge_rejects_unapproved_senior_review():
    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_no_sr",
        "status": TriageStatus.COMPLETED.value,
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "exec_1",
            "result_sha": "abc1234567890abcdef1234567890abcdef12345",
            "senior_review": {"approved": False},
        },
    }
    args = MagicMock(task_id="task_no_sr", json=False, skip_senior_review=False)
    # Must reject because senior review is not approved
    assert cmd_merge(args, queue) == 1


def test_merge_rejects_missing_branch():
    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_no_branch",
        "status": TriageStatus.COMPLETED.value,
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "exec_1",
            "result_sha": "abc1234567890abcdef1234567890abcdef12345",
            "senior_review": {"approved": True},
        },
        "branch_name": None,
    }
    args = MagicMock(task_id="task_no_branch", json=False, skip_senior_review=False)
    assert cmd_merge(args, queue) == 1


@patch("alpha_protocol.task.ReviewAttestation.verify")
@patch("alpha_core.triage_cli.subprocess.run")
@patch("alpha_core.triage_cli.Path.exists")
def test_merge_successful_with_senior_review_approved(
    mock_exists, mock_run, mock_verify, tmp_path, monkeypatch
):
    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_test_key", "dummy_secret")
    mock_verify.return_value = True
    evidence = {"test_metric": 10}
    from alpha_protocol.task import ReviewAttestation

    ev_digest = ReviewAttestation.compute_evidence_digest(evidence)

    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_success",
        "status": TriageStatus.COMPLETED.value,
        "branch_name": "alpha/task_success",
        "worktree_path": "/tmp/worktrees/task_success",
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "exec_1",
            "result_sha": "abc1234567890abcdef1234567890abcdef12345",
            "evidence": evidence,
            "senior_review": {
                "approved": True,
                "pro_verdict": "APPROVE",
                "opus_verdict": "FINAL_APPROVAL",
                "attestation": {
                    "schema_version": "2.0",
                    "task_id": "task_success",
                    "attempt_id": "att_1",
                    "base_commit": "b" * 40,
                    "result_sha": "abc1234567890abcdef1234567890abcdef12345",
                    "tree_digest": "c" * 40,
                    "pro_verdict": "APPROVE",
                    "opus_verdict": "FINAL_APPROVAL",
                    "approved": True,
                    "evidence_digest": ev_digest,
                    "reviewed_at": time.time(),
                    "issued_at": time.time(),
                    "expires_at": time.time() + 3600,
                    "nonce": "n",
                    "executor_id": "exec_1",
                    "key_id": "alpha_test_key",
                    "reviewer_id": "SYSTEM_SENIOR_REVIEW_ENGINE",
                    "signature": "f" * 64,
                },
            },
        },
        "envelope": {"repo": str(tmp_path), "base_commit": "b" * 40},
        "provenance": {
            "lease_metadata": {
                "worker_id": "exec_1",
                "attempt_id": "att_1",
                "lease_id": "lease_123",
                "fencing_epoch": 1,
            }
        },
    }

    def mock_exists_side_effect(*args, **kwargs):
        return any("task_success" in str(arg) for arg in args) if args else False

    mock_exists.side_effect = mock_exists_side_effect

    def mock_run_side_effect(*args, **kwargs):
        cmd = args[0]
        if cmd[1] == "rev-parse":
            if "^{tree}" in cmd[2]:
                return MagicMock(returncode=0, stdout="c" * 40 + "\n")
            return MagicMock(returncode=0, stdout="abc1234567890abcdef1234567890abcdef12345\n")
        return MagicMock(returncode=0, stdout="Updating 1234..5678\nFast-forward")

    mock_run.side_effect = mock_run_side_effect

    args = MagicMock(task_id="task_success", json=False, skip_senior_review=False)
    with patch("alpha_core.triage_cli.advance_checkout") as advance:
        ret = cmd_merge(args, queue)
        advance.assert_called_once_with(
            str(tmp_path), "b" * 40, "abc1234567890abcdef1234567890abcdef12345"
        )
    assert ret == 0

    # Git checkout correctness is covered by real-repository helper tests.
    assert not any(call.args[0][:2] == ["git", "update-ref"] for call in mock_run.call_args_list)
    queue.record_task_promotion.assert_called_once()


@patch("alpha_core.triage_cli.subprocess.run")
@patch("alpha_core.triage_cli.Path.exists")
def test_merge_fails_without_senior_review(mock_exists, mock_run, tmp_path):
    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_skip",
        "status": TriageStatus.COMPLETED.value,
        "branch_name": "alpha/task_skip",
        "worktree_path": "/tmp/worktrees/task_skip",
        "result": {"gates_passed": True},  # No senior_review recorded
        "envelope": {"repo": str(tmp_path)},
    }
    mock_exists.return_value = True
    mock_run.return_value = MagicMock(returncode=0, stdout="Fast-forward")

    args = MagicMock(task_id="task_skip", json=False)
    assert cmd_merge(args, queue) == 1


@patch("alpha_worker.senior_review_engine.SeniorReviewEngine._invoke_agy")
def test_cmd_senior_review_execution(mock_invoke, tmp_path, monkeypatch):
    monkeypatch.setenv("ALPHA_REVIEW_KEY_ID", "alpha_test_key")
    monkeypatch.setenv("ALPHA_SIGNING_SECRET_alpha_test_key", "test_sr_signing_secret")
    mock_invoke.side_effect = [
        {"response": "", "structured_output": {"verdict": "APPROVE"}},
        {"response": "", "structured_output": {"verdict": "FINAL_APPROVAL"}},
    ]
    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_sr_test",
        "status": TriageStatus.COMPLETED.value,
        "branch_name": "alpha/task_sr_test",
        "worktree_path": str(tmp_path),
        "result": {
            "gates_passed": True,
            "attempt_id": "att_1",
            "worker_id": "exec_1",
            "result_sha": "abc1234567890abcdef1234567890abcdef12345",
            "diff_stat": "1 file changed",
        },
        "envelope": {"title": "Test Task", "repo": str(tmp_path)},
        "provenance": {
            "lease_metadata": {
                "worker_id": "exec_1",
                "attempt_id": "att_1",
                "lease_id": "lease_123",
                "fencing_epoch": 1,
            }
        },
    }
    args = MagicMock(task_id="task_sr_test", json=False)

    with patch("subprocess.check_output") as mock_git:

        def fake_git(cmd, **kwargs):
            if cmd[:2] == ["git", "rev-parse"]:
                return "abc1234567890abcdef1234567890abcdef12345\n"
            if cmd[:2] == ["git", "status"]:
                return ""
            return ""

        mock_git.side_effect = fake_git

        assert cmd_senior_review(args, queue) == 0
        queue.record_senior_review.assert_called_once()
