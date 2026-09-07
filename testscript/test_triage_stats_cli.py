import json
from argparse import Namespace
from unittest.mock import MagicMock

from alpha_core.queue.triage_queue import TaskTriageQueue
from alpha_core.triage_cli import cmd_stats


def test_stats_empty_queue(capsys):
    queue = MagicMock(spec=TaskTriageQueue)
    queue.get_stats.return_value = {
        "total_tasks": 0,
        "by_status": {},
        "queue_wait_seconds": {"average": 0.0, "median": 0.0},
        "execution_duration_seconds": {"average": 0.0, "median": 0.0},
    }

    args = Namespace(json=False)
    ret = cmd_stats(args, queue)

    assert ret == 0
    captured = capsys.readouterr().out
    assert "Total Tasks: 0" in captured
    assert "Queue Wait (seconds):" in captured
    assert "Average: 0.00" in captured


def test_stats_with_tasks_table(capsys):
    queue = MagicMock(spec=TaskTriageQueue)
    queue.get_stats.return_value = {
        "total_tasks": 3,
        "by_status": {"completed": 1, "failed": 1, "pending_review": 1},
        "queue_wait_seconds": {"average": 15.0, "median": 15.0},
        "execution_duration_seconds": {"average": 35.0, "median": 35.0},
    }

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
    queue.get_stats.return_value = {
        "total_tasks": 1,
        "by_status": {"completed": 1},
        "queue_wait_seconds": {"average": 5.0, "median": 5.0},
        "execution_duration_seconds": {"average": 15.0, "median": 15.0},
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
