"""
Tests verifying the alphabrain triage export-audit command.
Ensures cryptographic provenance export, secret scrubbing, schema versioning,
deterministic sorting, and graceful error handling.
"""

import json
from unittest.mock import MagicMock, patch

from alpha_core.triage_cli import cmd_export_audit


def test_export_audit_missing_task():
    queue = MagicMock()
    queue.get_task.return_value = None
    args = MagicMock(task_id="missing_task", output=None)
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
    args = MagicMock(task_id="task_123", output=str(out_file))
    assert cmd_export_audit(args, queue) == 0

    data = json.loads(out_file.read_text())
    assert data["task_id"] == "task_123"
    assert data["schema_version"] == "1.0"
    assert "exported_at" in data
    assert data["provenance"]["model"] == "gemini-3.1-pro"
    assert data["execution_history"]["gates_passed"] is True


def test_export_audit_redacts_secrets(tmp_path):
    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_secret",
        "status": "completed",
        "provenance": {
            "api_key": "AIzaSyFakeKey12345",
            "token": "secret_token_abcdef",
            "meeting_id": "m_secret",
        },
        "result": {
            "password": "super_secret_db_pass",
            "bearer_token": "Bearer eyJhbGciOi...",
            "normal_field": "safe_value",
        },
    }
    out_file = tmp_path / "scrubbed_audit.json"
    args = MagicMock(task_id="task_secret", output=str(out_file))
    assert cmd_export_audit(args, queue) == 0

    data = json.loads(out_file.read_text())
    # Secrets must be redacted
    assert data["provenance"]["api_key"] == "[REDACTED]"
    assert data["provenance"]["token"] == "[REDACTED]"
    assert data["provenance"]["meeting_id"] == "m_secret"
    assert data["execution_history"]["password"] == "[REDACTED]"
    assert data["execution_history"]["bearer_token"] == "[REDACTED]"
    assert data["execution_history"]["normal_field"] == "safe_value"


def test_export_audit_file_io_error():
    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_io_err",
        "status": "completed",
    }
    args = MagicMock(task_id="task_io_err", output="/non_existent_dir_12345/sub/audit.json")
    assert cmd_export_audit(args, queue) == 1


def test_export_audit_deterministic_key_order(tmp_path):
    queue = MagicMock()
    queue.get_task.return_value = {
        "id": "task_determ",
        "status": "completed",
        "provenance": {"b": 2, "a": 1, "c": 3},
        "result": {"z": 26, "y": 25, "x": 24},
    }
    file1 = tmp_path / "audit1.json"
    file2 = tmp_path / "audit2.json"

    args1 = MagicMock(task_id="task_determ", output=str(file1))
    args2 = MagicMock(task_id="task_determ", output=str(file2))

    assert cmd_export_audit(args1, queue) == 0
    # Overwrite exported_at for deterministic comparison
    data1 = json.loads(file1.read_text())

    with patch("alpha_core.triage_cli.datetime") as mock_dt:
        mock_dt.datetime.now.return_value.isoformat.return_value = data1["exported_at"]
        mock_dt.timezone.utc = "UTC"
        assert cmd_export_audit(args2, queue) == 0

    assert file1.read_text() == file2.read_text()
