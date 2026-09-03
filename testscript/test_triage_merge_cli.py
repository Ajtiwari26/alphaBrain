"""
Unit tests verifying the autonomous fast-forward PR merge engine for AlphaBrain.
Ensures acceptance gate enforcement, fail-closed handling, clean fast-forward merge into main,
and worktree/branch pruning.
"""

from unittest.mock import MagicMock, patch

from alpha_core.queue.triage_queue import TriageStatus
from alpha_core.triage_cli import cmd_merge


def test_merge_rejects_missing_task():
    queue = MagicMock()
    queue.get_task.return_value = None
    args = MagicMock(task_id="missing_task_id", json=False)
    assert cmd_merge(args, queue) == 1


def test_merge_rejects_incomplete_task():
    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_executing",
        "status": TriageStatus.EXECUTING.value,
    }
    args = MagicMock(task_id="task_executing", json=False)
    assert cmd_merge(args, queue) == 1


def test_merge_rejects_failed_gates():
    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_failed_gates",
        "status": TriageStatus.COMPLETED.value,
        "result": {"gates_passed": False},
    }
    args = MagicMock(task_id="task_failed_gates", json=False)
    assert cmd_merge(args, queue) == 1


def test_merge_rejects_missing_branch():
    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_no_branch",
        "status": TriageStatus.COMPLETED.value,
        "result": {"gates_passed": True},
        "branch_name": None,
    }
    args = MagicMock(task_id="task_no_branch", json=False)
    assert cmd_merge(args, queue) == 1


@patch("alpha_core.triage_cli.subprocess.run")
@patch("alpha_core.triage_cli.Path.exists")
def test_merge_successful_fast_forward_and_prune(mock_exists, mock_run):
    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_success",
        "status": TriageStatus.COMPLETED.value,
        "branch_name": "alpha/task_success",
        "worktree_path": "/tmp/worktrees/task_success",
        "result": {"gates_passed": True},
        "envelope": {"repo": "/repos/alphaBrain"},
    }
    mock_exists.return_value = True
    mock_run.return_value = MagicMock(returncode=0, stdout="Updating 1234..5678\nFast-forward")

    args = MagicMock(task_id="task_success", json=False)
    ret = cmd_merge(args, queue)
    assert ret == 0

    # Verify execution sequence: checkout main -> ff merge -> prune worktree -> delete branch
    mock_run.assert_any_call(
        ["git", "checkout", "main"],
        cwd="/repos/alphaBrain",
        check=True,
        capture_output=True,
        text=True,
    )
    mock_run.assert_any_call(
        ["git", "merge", "--ff-only", "alpha/task_success"],
        cwd="/repos/alphaBrain",
        check=True,
        capture_output=True,
        text=True,
    )
    mock_run.assert_any_call(
        ["git", "worktree", "remove", "--force", "/tmp/worktrees/task_success"],
        cwd="/repos/alphaBrain",
        check=True,
        capture_output=True,
        text=True,
    )
    mock_run.assert_any_call(
        ["git", "branch", "-d", "alpha/task_success"],
        cwd="/repos/alphaBrain",
        check=True,
        capture_output=True,
        text=True,
    )
