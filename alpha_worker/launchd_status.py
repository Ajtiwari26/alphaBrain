"""Typed read-only per-user launchd inspector and recovery report."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LaunchdInspectorReport:
    plist_installed: bool = False
    plist_valid: bool = False
    loaded: bool = False
    running: bool = False
    exit_code: int | None = None
    status_freshness_seconds: float | None = None
    recovery_command: str | None = None


class LaunchdInspector:
    """Read-only inspector for launchd service."""

    LABEL = "com.deploymate.alphabrain.worker"

    def __init__(
        self,
        command_runner: Callable[[list[str]], tuple[int, str, str]],
        time_fn: Callable[[], float] = time.time,
        home_dir: Path | None = None,
        status_file: Path | None = None,
    ):
        self._run_cmd = command_runner
        self._time = time_fn
        self._home = home_dir or Path.home()
        self._plist_path = self._home / "Library" / "LaunchAgents" / f"{self.LABEL}.plist"
        self._status_file = status_file
        self._recovery_cmd = "./ops/launchd/install_worker.sh $(pwd)"

    def inspect(self) -> LaunchdInspectorReport:
        report = LaunchdInspectorReport()

        report.plist_installed = self._plist_path.exists()

        if report.plist_installed:
            code, _, _ = self._run_cmd(["plutil", "-lint", str(self._plist_path)])
            if code == 0:
                report.plist_valid = True
                try:
                    import plistlib
                    with open(self._plist_path, "rb") as f:
                        plist_data = plistlib.load(f)

                    if plist_data.get("UserName") == "root":
                        report.plist_valid = False
                    if "RootDirectory" in plist_data:
                        report.plist_valid = False
                    if not plist_data.get("KeepAlive"):
                        report.plist_valid = False
                    if plist_data.get("ThrottleInterval", 0) < 10:
                        report.plist_valid = False
                    if plist_data.get("ProcessType") != "Background":
                        report.plist_valid = False
                except Exception:
                    report.plist_valid = False
            else:
                report.plist_valid = False

        # Use launchctl list to check loaded/running/exit_code
        code, stdout, _ = self._run_cmd(["launchctl", "list"])
        if code == 0:
            for line in stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 3 and parts[2] == self.LABEL:
                    report.loaded = True
                    pid_str = parts[0]
                    status_str = parts[1]

                    if pid_str.isdigit():
                        report.running = True
                    else:
                        report.running = False

                    if status_str.isdigit() or (
                        status_str.startswith("-") and status_str[1:].isdigit()
                    ):
                        report.exit_code = int(status_str)
                    break

        if self._status_file and self._status_file.exists():
            try:
                mtime = self._status_file.stat().st_mtime
                report.status_freshness_seconds = max(0.0, self._time() - mtime)
            except OSError:
                pass

        if not report.plist_installed:
            report.recovery_command = f"Missing plist. Run: {self._recovery_cmd}"
        elif not report.plist_valid:
            report.recovery_command = f"Invalid plist. Run: {self._recovery_cmd}"
        elif not report.loaded:
            report.recovery_command = f"Service not loaded. Run: {self._recovery_cmd}"
        elif not report.running:
            report.recovery_command = (
                f"Service stopped (exit {report.exit_code}). Run: {self._recovery_cmd}"
            )
        elif report.status_freshness_seconds is not None and report.status_freshness_seconds > 300:
            report.recovery_command = f"Worker running but stale status. Run: {self._recovery_cmd}"
        else:
            report.recovery_command = None

        return report
