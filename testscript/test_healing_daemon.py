import json
from unittest.mock import MagicMock, patch

import pytest

from alpha_core.healing.circuit_breaker import TripReason
from alpha_core.queue.triage_queue import TriageStatus
from alpha_worker.ci_healing_daemon import CIHealingDaemon


@pytest.fixture
def mock_queue():
    queue = MagicMock()
    queue.is_emergency_stopped.return_value = False
    queue.list_tasks.return_value = []
    return queue


def test_daemon_handles_completed_task(mock_queue):
    mock_queue.list_tasks.side_effect = [
        [{"task_id": "task_1"}],  # completed tasks
        []  # failed tasks
    ]
    daemon = CIHealingDaemon(mock_queue)

    with patch("subprocess.run") as mock_run:
        # First call: senior review
        # Second call: merge
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps({"approved": True})),
            MagicMock(returncode=0)
        ]

        daemon.run_once()

        assert mock_run.call_count == 2
        calls = mock_run.call_args_list
        assert "senior-review" in calls[0][0][0]
        assert "merge" in calls[1][0][0]


def test_daemon_handles_completed_task_not_approved(mock_queue):
    mock_queue.list_tasks.side_effect = [
        [{"task_id": "task_1"}],
        []
    ]
    daemon = CIHealingDaemon(mock_queue)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps({"approved": False}))

        daemon.run_once()

        # Only senior review was called
        assert mock_run.call_count == 1


def test_daemon_handles_failed_task(mock_queue, tmp_path):
    # Setup dummy evidence in tmp_path
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "pytest_output.txt").write_text("FAILED test_foo.py::test_bar")

    mock_queue.list_tasks.side_effect = [
        [],  # no completed
        [{"task_id": "task_2", "payload": {"worktree": str(tmp_path), "allowed_paths": ["src"]}}]
    ]

    daemon = CIHealingDaemon(mock_queue)

    with patch.object(daemon.failure_analyzer, "analyze") as mock_analyze:
        mock_analyze.return_value = {"signature": "sig123", "pytest_failures": [{"file": "test_foo.py"}]}

        daemon.run_once()

        # Should submit repair task and update status
        mock_queue.submit_task.assert_called_once()
        submitted_args = mock_queue.submit_task.call_args[1]
        assert submitted_args["task_id"] == "task_2_repair_1"
        assert "instruction" in submitted_args["payload"]
        assert submitted_args["payload"]["parent_task_id"] == "task_2"

        mock_queue.update_status.assert_called_once_with("task_2", TriageStatus.PENDING_REVIEW)


def test_daemon_circuit_breaker_trips(mock_queue, tmp_path):
    mock_queue.list_tasks.side_effect = [
        [],
        [{"task_id": "task_3", "payload": {"worktree": str(tmp_path)}}]
    ]

    daemon = CIHealingDaemon(mock_queue)
    cb = daemon.get_circuit_breaker("task_3")

    with patch.object(cb, "record_failure", return_value=TripReason.ESCALATED_HUMAN_REVIEW):
        daemon.run_once()

        # Escalates to PENDING_REVIEW and does not submit repair task
        mock_queue.submit_task.assert_not_called()
        mock_queue.update_status.assert_called_once_with("task_3", TriageStatus.PENDING_REVIEW)

