"""Tests for read-only launchd readiness inspector."""

import json
from pathlib import Path

from alpha_worker.launchd_status import LaunchdInspector


def test_absent_plist(tmp_path: Path) -> None:
    def mock_run(cmd: list[str]) -> tuple[int, str, str]:
        return 0, "", ""

    inspector = LaunchdInspector(
        command_runner=mock_run,
        home_dir=tmp_path,
        status_file=None,
    )
    report = inspector.inspect()
    assert not report.plist_installed
    assert not report.plist_valid
    assert not report.loaded
    assert report.recovery_command is not None
    assert "Missing plist. Run:" in report.recovery_command


def test_invalid_plist(tmp_path: Path) -> None:
    plist = tmp_path / "Library" / "LaunchAgents" / "com.deploymate.alphabrain.worker.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.touch()

    def mock_run(cmd: list[str]) -> tuple[int, str, str]:
        if cmd[0] == "plutil":
            return 1, "", "XML error"
        return 0, "", ""

    inspector = LaunchdInspector(
        command_runner=mock_run,
        home_dir=tmp_path,
        status_file=None,
    )
    report = inspector.inspect()
    assert report.plist_installed
    assert not report.plist_valid
    assert report.recovery_command is not None
    assert "Invalid plist. Run:" in report.recovery_command


def test_loaded_healthy_fresh(tmp_path: Path) -> None:
    plist = tmp_path / "Library" / "LaunchAgents" / "com.deploymate.alphabrain.worker.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.touch()

    status_file = tmp_path / "node_status.json"
    status_file.write_text(json.dumps({"status": "online"}))

    def mock_run(cmd: list[str]) -> tuple[int, str, str]:
        if cmd[0] == "plutil":
            return 0, "OK", ""
        if cmd[0] == "launchctl" and cmd[1] == "list":
            return 0, "1234 0 com.deploymate.alphabrain.worker\n", ""
        return 1, "", ""

    def mock_time() -> float:
        return status_file.stat().st_mtime + 10  # 10 seconds fresh

    inspector = LaunchdInspector(
        command_runner=mock_run,
        time_fn=mock_time,
        home_dir=tmp_path,
        status_file=status_file,
    )
    report = inspector.inspect()
    assert report.plist_installed
    assert report.plist_valid
    assert report.loaded
    assert report.running
    assert report.exit_code == 0
    assert report.status_freshness_seconds == 10
    assert report.recovery_command is None


def test_stopped_failed_worker(tmp_path: Path) -> None:
    plist = tmp_path / "Library" / "LaunchAgents" / "com.deploymate.alphabrain.worker.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.touch()

    def mock_run(cmd: list[str]) -> tuple[int, str, str]:
        if cmd[0] == "plutil":
            return 0, "OK", ""
        if cmd[0] == "launchctl" and cmd[1] == "list":
            return 0, "- 78 com.deploymate.alphabrain.worker\n", ""
        return 1, "", ""

    inspector = LaunchdInspector(
        command_runner=mock_run,
        home_dir=tmp_path,
        status_file=None,
    )
    report = inspector.inspect()
    assert report.plist_installed
    assert report.loaded
    assert not report.running
    assert report.exit_code == 78
    assert report.recovery_command is not None
    assert "Service stopped (exit 78). Run:" in report.recovery_command


def test_stale_health(tmp_path: Path) -> None:
    plist = tmp_path / "Library" / "LaunchAgents" / "com.deploymate.alphabrain.worker.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.touch()

    status_file = tmp_path / "node_status.json"
    status_file.write_text(json.dumps({"status": "online"}))

    def mock_run(cmd: list[str]) -> tuple[int, str, str]:
        if cmd[0] == "plutil":
            return 0, "OK", ""
        if cmd[0] == "launchctl" and cmd[1] == "list":
            return 0, "1234 0 com.deploymate.alphabrain.worker\n", ""
        return 1, "", ""

    def mock_time() -> float:
        return status_file.stat().st_mtime + 400  # Stale by 400 seconds

    inspector = LaunchdInspector(
        command_runner=mock_run,
        time_fn=mock_time,
        home_dir=tmp_path,
        status_file=status_file,
    )
    report = inspector.inspect()
    assert report.running
    assert report.status_freshness_seconds == 400
    assert report.recovery_command is not None
    assert "Worker running but stale status. Run:" in report.recovery_command


def test_command_failure(tmp_path: Path) -> None:
    plist = tmp_path / "Library" / "LaunchAgents" / "com.deploymate.alphabrain.worker.plist"
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.touch()

    def mock_run(cmd: list[str]) -> tuple[int, str, str]:
        if cmd[0] == "launchctl" and cmd[1] == "list":
            return 1, "", "launchctl error"
        return 0, "", ""

    inspector = LaunchdInspector(
        command_runner=mock_run,
        home_dir=tmp_path,
        status_file=None,
    )
    report = inspector.inspect()
    assert report.plist_installed
    assert not report.loaded
    assert report.recovery_command is not None
    assert "Service not loaded. Run:" in report.recovery_command
