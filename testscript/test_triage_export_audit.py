"""
Tests verifying the alphabrain triage export-audit command.
"""

import json
from unittest.mock import MagicMock

from alpha_core.triage_cli import cmd_export_audit


def test_export_audit_missing_task():
    queue = MagicMock()
    queue.get_task.return_value = None
    args = MagicMock(task_id="missing_task", output=None, json=False)
    assert cmd_export_audit(args, queue) == 1


def test_export_audit_success(tmp_path):
    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_123",
        "status": "completed",
        "created_at": 1000.0,
        "updated_at": 2000.0,
        "provenance": {"meeting_id": "m1", "model": "gemini-3.1-pro"},
        "result": {"gates_passed": True},
    }
    out_file = tmp_path / "audit.json"
    args = MagicMock(task_id="task_123", output=str(out_file), json=False)
    assert cmd_export_audit(args, queue) == 0

    data = json.loads(out_file.read_text())
    assert data["task_id"] == "task_123"
    assert data["provenance"]["model"] == "gemini-3.1-pro"
    assert data["execution_history"]["gates_passed"] is True
