import json
from argparse import Namespace
from unittest.mock import MagicMock

from alpha_core.queue.triage_queue import TaskTriageQueue
from alpha_core.triage_cli import cmd_stats


def test_stats_empty_queue(capsys):
    queue = MagicMock(spec=TaskTriageQueue)
    queue.list_tasks.return_value = []

    args = Namespace(json=False)
    ret = cmd_stats(args, queue)

    assert ret == 0
    captured = capsys.readouterr().out
    assert "Total Tasks: 0" in captured
    assert "Queue Wait (seconds):" in captured
    assert "Average: 0.00" in captured


def test_stats_with_tasks_table(capsys):
    queue = MagicMock(spec=TaskTriageQueue)
    tasks = [
        {"id": "task1", "status": "completed"},
        {"id": "task2", "status": "failed"},
        {"id": "task3", "status": "pending_review"},
    ]
    queue.list_tasks.return_value = tasks

    def mock_get_telemetry(task_id):
        if task_id == "task1":
            return {"queue_wait_seconds": 10.0, "execution_duration_seconds": 30.0}
        elif task_id == "task2":
            return {"queue_wait_seconds": 20.0, "execution_duration_seconds": 40.0}
        else:
            return {}

    queue.get_task_telemetry.side_effect = mock_get_telemetry

    args = Namespace(json=False)
    ret = cmd_stats(args, queue)

    assert ret == 0
    captured = capsys.readouterr().out

    assert "Total Tasks: 3" in captured
    assert "completed      : 1" in captured
    assert "failed         : 1" in captured
    assert "pending_review : 1" in captured

    assert "Average: 15.00" in captured
    assert "Average: 35.00" in captured


def test_stats_json_output(capsys):
    queue = MagicMock(spec=TaskTriageQueue)
    tasks = [
        {"id": "task1", "status": "completed"},
    ]
    queue.list_tasks.return_value = tasks
    queue.get_task_telemetry.return_value = {
        "queue_wait_seconds": 5.0,
        "execution_duration_seconds": 15.0,
    }

    args = Namespace(json=True)
    ret = cmd_stats(args, queue)

    assert ret == 0
    captured = capsys.readouterr().out

    data = json.loads(captured)
    assert data["total_tasks"] == 1
    assert data["by_status"]["completed"] == 1
    assert data["queue_wait_seconds"]["average"] == 5.0
    assert data["execution_duration_seconds"]["median"] == 15.0
