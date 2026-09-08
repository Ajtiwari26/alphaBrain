import json
import os
import signal
from unittest.mock import MagicMock, create_autospec, patch

import pytest

from alpha_core.healing.circuit_breaker import TripReason
from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue, TriageStatus
from alpha_worker.ci_healing_daemon import CIHealingDaemon


@pytest.fixture
def mock_queue():
    queue = create_autospec(TaskTriageQueue, instance=True)
    queue.is_emergency_stopped.return_value = False
    queue.list_tasks.return_value = []
    return queue


def test_daemon_handles_completed_task(mock_queue):
    mock_queue.list_tasks.side_effect = [
        [{"id": "task_1"}],  # completed tasks
        [],  # failed tasks
    ]
    daemon = CIHealingDaemon(mock_queue)

    with patch("alpha_worker.ci_healing_daemon.subprocess.run") as mock_run:
        # First call: senior review
        # Second call: merge
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps({"approved": True})),
            MagicMock(returncode=0),
        ]

        daemon.run_once()

        assert mock_run.call_count == 2
        calls = mock_run.call_args_list
        assert "senior-review" in calls[0][0][0]
        assert "merge" in calls[1][0][0]
        assert "task_1" in daemon.processed_tasks


def test_daemon_handles_completed_task_not_approved(mock_queue):
    mock_queue.list_tasks.side_effect = [[{"id": "task_1"}], []]
    daemon = CIHealingDaemon(mock_queue)

    with patch("alpha_worker.ci_healing_daemon.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps({"approved": False}))

        daemon.run_once()

        assert mock_run.call_count == 1
        assert "task_1" in daemon.processed_tasks


def test_daemon_handles_failed_task(mock_queue, tmp_path):
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "pytest_output.txt").write_text("FAILED test_foo.py::test_bar")

    mock_queue.list_tasks.side_effect = [
        [],  # no completed
        [
            {
                "id": "task_2",
                "worktree_path": str(tmp_path),
                "envelope": {"allowed_paths": ["src"]},
                "provenance": {
                    "meeting_id": "m1",
                    "speaker_id": "s1",
                    "utterance_timestamp": 1.0,
                    "transcript_excerpt": "test",
                    "extraction_model": "test",
                    "extraction_confidence": 0.9,
                    "eva_session_id": "e1",
                    "created_at": 1.0,
                    "content_hash": "dummy",
                },
            }
        ],
    ]

    daemon = CIHealingDaemon(mock_queue)

    with patch.object(daemon.failure_analyzer, "analyze") as mock_analyze:
        mock_analyze.return_value = {
            "signature": "sig123",
            "pytest_failures": [{"file": "test_foo.py"}],
        }

        daemon.run_once()

        mock_queue.enqueue_task.assert_called_once()
        submitted_args = mock_queue.enqueue_task.call_args[1]
        assert submitted_args["task_id"] == "task_2_repair_1"
        assert "detailed_instructions" in submitted_args["envelope"]
        assert submitted_args["envelope"]["parent_task_id"] == "task_2"
        assert isinstance(submitted_args["provenance"], TaskProvenance)
        assert submitted_args["initial_status"] == TriageStatus.PENDING_REVIEW

        mock_queue.retry_task.assert_called_once_with(
            "task_2", operator_notes="Superseded by task_2_repair_1"
        )
        mock_queue.reject_task.assert_called_once_with(
            "task_2", reason="Superseded by task_2_repair_1"
        )
        assert "task_2" in daemon.processed_tasks


def test_daemon_circuit_breaker_trips(mock_queue, tmp_path):
    mock_queue.list_tasks.side_effect = [[], [{"id": "task_3", "worktree_path": str(tmp_path)}]]

    daemon = CIHealingDaemon(mock_queue)
    cb = daemon.get_circuit_breaker("task_3")

    with patch.object(cb, "record_failure", return_value=TripReason.ESCALATED_HUMAN_REVIEW):
        daemon.run_once()

        mock_queue.enqueue_task.assert_not_called()
        mock_queue.retry_task.assert_called_once_with(
            "task_3", operator_notes="Circuit breaker tripped - escalating"
        )
        mock_queue.reject_task.assert_called_once_with(
            "task_3",
            reason="ESCALATED: Identical failures exceeded threshold. Needs human intervention.",
        )
        assert "task_3" in daemon.processed_tasks


def test_emergency_stop_aborts(mock_queue):
    mock_queue.is_emergency_stopped.return_value = True
    daemon = CIHealingDaemon(mock_queue)
    daemon.run_once()
    mock_queue.list_tasks.assert_not_called()


def test_no_worktree_silent_abort(mock_queue):
    mock_queue.list_tasks.side_effect = [[], [{"id": "task_no_worktree", "worktree_path": ""}]]
    daemon = CIHealingDaemon(mock_queue)
    daemon.run_once()
    mock_queue.enqueue_task.assert_not_called()
    assert "task_no_worktree" in daemon.processed_tasks


def test_senior_review_non_zero_exit(mock_queue):
    mock_queue.list_tasks.side_effect = [[{"id": "task_1"}], []]
    daemon = CIHealingDaemon(mock_queue)
    with patch("alpha_worker.ci_healing_daemon.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        daemon.run_once()
        assert mock_run.call_count == 1
        assert "task_1" in daemon.processed_tasks


def test_auto_merge_failure(mock_queue):
    mock_queue.list_tasks.side_effect = [[{"id": "task_1"}], []]
    daemon = CIHealingDaemon(mock_queue)
    with patch("alpha_worker.ci_healing_daemon.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=json.dumps({"approved": True})),
            MagicMock(returncode=1, stderr="merge conflict"),
        ]
        daemon.run_once()
        assert mock_run.call_count == 2
        assert "task_1" in daemon.processed_tasks


def test_json_decode_error(mock_queue):
    mock_queue.list_tasks.side_effect = [[{"id": "task_1"}], []]
    daemon = CIHealingDaemon(mock_queue)
    with patch("alpha_worker.ci_healing_daemon.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="not json")
        daemon.run_once()
        assert mock_run.call_count == 1
        assert "task_1" in daemon.processed_tasks


def test_multiple_tasks_error_isolation(mock_queue):
    mock_queue.list_tasks.side_effect = [[{"id": "task_1"}, {"id": "task_2"}], []]
    daemon = CIHealingDaemon(mock_queue)

    with patch.object(daemon, "process_completed_task") as mock_process:
        mock_process.side_effect = [Exception("task 1 failed"), None]
        daemon.run_once()
        assert mock_process.call_count == 2


def test_idempotency_guard(mock_queue):
    mock_queue.list_tasks.side_effect = [[{"id": "task_1"}], []]
    daemon = CIHealingDaemon(mock_queue)
    daemon.processed_tasks.add("task_1")

    with patch("alpha_worker.ci_healing_daemon.subprocess.run") as mock_run:
        daemon.run_once()
        mock_run.assert_not_called()


def test_run_continuously_interrupt(mock_queue):
    daemon = CIHealingDaemon(mock_queue)

    with patch.object(daemon, "run_once") as mock_run:

        def raise_interrupt(*args, **kwargs):
            os.kill(os.getpid(), signal.SIGTERM)

        mock_run.side_effect = raise_interrupt

        # It should exit gracefully
        daemon.run_continuously(interval=0.01)

        assert mock_run.call_count == 1
        assert daemon._shutdown is True


def test_synthesizer_return_contract_validation(mock_queue, tmp_path):
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "pytest_output.txt").write_text("FAILED test_foo.py::test_bar")

    mock_queue.list_tasks.side_effect = [
        [],
        [
            {
                "id": "task_2",
                "worktree_path": str(tmp_path),
                "envelope": {"allowed_paths": ["src"]},
            }
        ],
    ]

    daemon = CIHealingDaemon(mock_queue)

    with patch.object(daemon.failure_analyzer, "analyze") as mock_analyze:
        mock_analyze.return_value = {"signature": "sig123", "pytest_failures": []}
        with patch(
            "alpha_worker.ci_healing_daemon.RepairEnvelopeSynthesizer.synthesize"
        ) as mock_synth:
            mock_synth.return_value = {"bad_key": "val"}  # Invalid return
            daemon.run_once()
            mock_queue.enqueue_task.assert_not_called()
            assert "task_2" in daemon.processed_tasks
