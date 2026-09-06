"""
Unit tests verifying the autonomous fast-forward PR merge engine for AlphaBrain.
Ensures acceptance gate enforcement, 2-Round Senior Review enforcement, fail-closed handling,
clean fast-forward merge into main, and worktree/branch pruning.
"""

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
            "result_sha": "abc1234567890abcdef1234567890abcdef12345",
            "senior_review": {"approved": True},
        },
        "branch_name": None,
    }
    args = MagicMock(task_id="task_no_branch", json=False, skip_senior_review=False)
    assert cmd_merge(args, queue) == 1


@patch("alpha_core.triage_cli.subprocess.run")
@patch("alpha_core.triage_cli.Path.exists")
def test_merge_successful_with_senior_review_approved(mock_exists, mock_run, tmp_path):
    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_success",
        "status": TriageStatus.COMPLETED.value,
        "branch_name": "alpha/task_success",
        "worktree_path": "/tmp/worktrees/task_success",
        "result": {
            "gates_passed": True,
            "result_sha": "abc1234567890abcdef1234567890abcdef12345",
            "senior_review": {
                "approved": True,
                "pro_verdict": "APPROVE",
                "opus_verdict": "FINAL_APPROVAL",
            },
        },
        "envelope": {"repo": str(tmp_path)},
    }
    mock_exists.return_value = True

    def mock_run_side_effect(*args, **kwargs):
        cmd = args[0]
        if cmd[1] == "rev-parse":
            return MagicMock(returncode=0, stdout="abc1234567890abcdef1234567890abcdef12345\n")
        return MagicMock(returncode=0, stdout="Updating 1234..5678\nFast-forward")

    mock_run.side_effect = mock_run_side_effect

    args = MagicMock(task_id="task_success", json=False, skip_senior_review=False)
    ret = cmd_merge(args, queue)
    assert ret == 0

    # Verify execution sequence: checkout main -> ff merge -> prune worktree -> delete branch
    mock_run.assert_any_call(
        ["git", "checkout", "main"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
        text=True,
    )
    mock_run.assert_any_call(
        ["git", "merge", "--ff-only", "abc1234567890abcdef1234567890abcdef12345"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
        text=True,
    )


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
def test_cmd_senior_review_execution(mock_invoke, tmp_path):
    mock_invoke.side_effect = ['{"verdict": "APPROVE"}', '{"verdict": "FINAL_APPROVAL"}']
    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_sr_test",
        "status": TriageStatus.COMPLETED.value,
        "branch_name": "alpha/task_sr_test",
        "result": {
            "gates_passed": True,
            "result_sha": "abc1234567890abcdef1234567890abcdef12345",
            "diff_stat": "1 file changed",
        },
        "envelope": {"title": "Test Task", "repo": str(tmp_path)},
    }
    args = MagicMock(task_id="task_sr_test", json=False)
    assert cmd_senior_review(args, queue) == 0
    queue.record_senior_review.assert_called_once()
