"""
Preview supervisor for retained static worktrees.
Manages bounded localhost HTTP readiness checks requiring 200-level non-empty body,
captures and persists PID/port/health metadata, safely reclaims or restarts
proven AlphaBrain-owned preview processes, and refuses to terminate unknown listeners.
"""

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from alpha_core.config import settings

logger = logging.getLogger("alpha_worker.preview")


class PreviewStatus(str, Enum):
    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"


@dataclass
class PreviewMetadata:
    """Structured runtime metadata for a managed preview process."""

    task_id: str
    project_id: str
    worktree_path: Path
    port: int
    pid: int | None = None
    url: str = ""
    status: PreviewStatus = PreviewStatus.STARTING
    started_at: datetime | None = None
    last_health_check_at: datetime | None = None
    health_error: str | None = None
    restart_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "project_id": self.project_id,
            "worktree_path": str(self.worktree_path),
            "port": self.port,
            "pid": self.pid,
            "url": self.url,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "last_health_check_at": (
                self.last_health_check_at.isoformat() if self.last_health_check_at else None
            ),
            "health_error": self.health_error,
            "restart_count": self.restart_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PreviewMetadata":
        started_at = None
        if data.get("started_at"):
            try:
                started_at = datetime.fromisoformat(data["started_at"])
            except Exception:
                pass
        last_check = None
        if data.get("last_health_check_at"):
            try:
                last_check = datetime.fromisoformat(data["last_health_check_at"])
            except Exception:
                pass
        return cls(
            task_id=str(data["task_id"]),
            project_id=str(data["project_id"]),
            worktree_path=Path(data["worktree_path"]),
            port=int(data["port"]),
            pid=int(data["pid"]) if data.get("pid") is not None else None,
            url=str(data.get("url") or f"http://127.0.0.1:{data['port']}/"),
            status=PreviewStatus(data.get("status", PreviewStatus.STARTING.value)),
            started_at=started_at,
            last_health_check_at=last_check,
            health_error=data.get("health_error"),
            restart_count=int(data.get("restart_count", 0)),
        )


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a localhost TCP port is free for binding."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) != 0


def default_http_checker(url: str, timeout: float = 3.0) -> tuple[int, bytes]:
    """Perform bounded localhost HTTP GET and return (status_code, body_bytes)."""
    req = urllib.request.Request(url, headers={"User-Agent": "AlphaBrain-PreviewSupervisor/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except Exception as exc:
        raise RuntimeError(f"HTTP connection failed to {url}: {exc}") from exc


def default_process_launcher(cmd: list[str], cwd: Path) -> subprocess.Popen[bytes]:
    """Spawn child process in isolated process group."""
    return subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def default_port_owner_finder(port: int) -> int | None:
    """Discover listening PID on localhost port using lsof."""
    try:
        res = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if res.returncode == 0 and res.stdout.strip():
            lines = res.stdout.strip().splitlines()
            for line in lines:
                val = line.strip()
                if val.isdigit():
                    return int(val)
    except Exception:
        pass
    return None


def default_process_inspector(pid: int) -> dict[str, Any] | None:
    """Inspect running process command line and working directory."""
    try:
        ps_res = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=2.0,
        )
        if ps_res.returncode == 0 and ps_res.stdout.strip():
            command = ps_res.stdout.strip()
            cwd = ""
            cwd_res = subprocess.run(
                ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if cwd_res.returncode == 0:
                for line in cwd_res.stdout.splitlines():
                    if line.startswith("n"):
                        cwd = line[1:].strip()
                        break
            return {"pid": pid, "command": command, "cwd": cwd}
    except Exception:
        pass
    return None


class PreviewSupervisor:
    """Supervises static preview processes, performs HTTP readiness checks, and manages lifecycle."""

    def __init__(
        self,
        *,
        state_dir: Path | None = None,
        http_checker: Callable[[str, float], tuple[int, bytes]] | None = None,
        process_launcher: Callable[[list[str], Path], Any] | None = None,
        port_owner_finder: Callable[[int], int | None] | None = None,
        process_inspector: Callable[[int], dict[str, Any] | None] | None = None,
    ) -> None:
        self._state_dir = (
            (state_dir or settings.WORKER_STATE_DIR / "previews").expanduser().resolve()
        )
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._http_checker = http_checker or default_http_checker
        self._process_launcher = process_launcher or default_process_launcher
        self._port_owner_finder = port_owner_finder or default_port_owner_finder
        self._process_inspector = process_inspector or default_process_inspector
        self._managed_processes: dict[int, Any] = {}

    def _state_file_path(self, task_id: str) -> Path:
        return self._state_dir / f"{task_id}.json"

    def load_persisted_metadata(self, task_id: str) -> PreviewMetadata | None:
        path = self._state_file_path(task_id)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return PreviewMetadata.from_dict(data)
        except Exception as exc:
            logger.warning("Could not read preview state file %s: %s", path, exc)
        return None

    def save_persisted_metadata(self, metadata: PreviewMetadata) -> None:
        path = self._state_file_path(metadata.task_id)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(metadata.to_dict(), indent=2) + "\n", encoding="utf-8")
            path.chmod(0o600)
        except Exception as exc:
            logger.warning("Could not save preview state file %s: %s", path, exc)

    def is_process_proven_owned(
        self,
        pid: int,
        target_port: int,
        worktree_path: Path,
        task_id: str,
        project_id: str,
    ) -> bool:
        """
        Verify whether an existing process on target_port is proven AlphaBrain-owned.
        Returns True if:
        1. Persisted task preview record matches task_id, project_id, worktree_path, port, and pid; OR
        2. Process inspection proves it is running Python http.server for target_port and exact worktree.
        """
        persisted = self.load_persisted_metadata(task_id)
        if (
            persisted
            and persisted.pid == pid
            and persisted.port == target_port
            and persisted.project_id == project_id
            and persisted.worktree_path.resolve() == worktree_path.resolve()
        ):
            return True

        info = self._process_inspector(pid)
        if not info:
            return False

        command = info.get("command", "")
        cwd = info.get("cwd", "")
        expected_cwd = str(worktree_path.resolve())

        is_http_server = "http.server" in command and str(target_port) in command
        cwd_matches = cwd and (Path(cwd).resolve() == worktree_path.resolve())

        if is_http_server and (cwd_matches or expected_cwd in command):
            return True

        return False

    def find_available_port(self, start_port: int = 4173, max_attempts: int = 50) -> int:
        """Find an available port starting from start_port."""
        for offset in range(max_attempts):
            candidate = start_port + offset
            if is_port_available(candidate):
                return candidate
        raise RuntimeError(
            f"No available localhost port found in range {start_port}-{start_port + max_attempts}"
        )

    def start_preview(
        self,
        worktree_path: Path,
        *,
        task_id: str,
        project_id: str,
        port: int | None = None,
        timeout_seconds: float = 10.0,
    ) -> PreviewMetadata:
        """
        Starts or reclaims a static HTTP preview server in the given worktree, performs bounded
        readiness polling requiring 200-level non-empty body, and returns metadata.
        Never terminates an unknown port listener.
        """
        worktree = Path(worktree_path).resolve()
        if not worktree.is_dir():
            raise ValueError(f"Worktree path does not exist or is not a directory: {worktree}")

        target_port = port or self.find_available_port()

        # Check if port is already bound
        if not is_port_available(target_port):
            listener_pid = self._port_owner_finder(target_port)
            if listener_pid is None or not self.is_process_proven_owned(
                listener_pid, target_port, worktree, task_id, project_id
            ):
                raise RuntimeError(
                    f"Port {target_port} is already in use by an unknown listener (PID: {listener_pid}); "
                    "refusing to terminate unmanaged process."
                )

            # Process is proven AlphaBrain-owned! Check its current health
            url = f"http://127.0.0.1:{target_port}/"
            try:
                status_code, body = self._http_checker(url, 2.0)
                if 200 <= status_code < 300 and len(body.strip()) > 0:
                    # Reclaim existing healthy instance
                    adopted = PreviewMetadata(
                        task_id=task_id,
                        project_id=project_id,
                        worktree_path=worktree,
                        port=target_port,
                        pid=listener_pid,
                        url=url,
                        status=PreviewStatus.HEALTHY,
                        started_at=datetime.now(UTC),
                        last_health_check_at=datetime.now(UTC),
                        health_error=None,
                    )
                    self.save_persisted_metadata(adopted)
                    logger.info(
                        "Reclaimed existing healthy AlphaBrain preview on port %d (PID %d)",
                        target_port,
                        listener_pid,
                    )
                    return adopted
            except Exception:
                pass

            # Existing owned process is unhealthy -> terminate it cleanly
            logger.info(
                "Terminating unhealthy owned preview process %d on port %d",
                listener_pid,
                target_port,
            )
            self._kill_process_group(listener_pid, port=target_port)
            time.sleep(0.1)

        cmd = [sys.executable, "-m", "http.server", str(target_port), "--bind", "127.0.0.1"]
        process = self._process_launcher(cmd, worktree)
        pid = getattr(process, "pid", None)
        if pid is not None:
            self._managed_processes[pid] = process

        url = f"http://127.0.0.1:{target_port}/"
        metadata = PreviewMetadata(
            task_id=task_id,
            project_id=project_id,
            worktree_path=worktree,
            port=target_port,
            pid=pid,
            url=url,
            status=PreviewStatus.STARTING,
            started_at=datetime.now(UTC),
        )
        self.save_persisted_metadata(metadata)

        deadline = time.time() + timeout_seconds
        readiness_error: str | None = None
        while time.time() < deadline:
            if hasattr(process, "poll") and process.poll() is not None:
                readiness_error = (
                    f"Preview process exited prematurely with code {process.returncode}"
                )
                break

            try:
                status_code, body = self._http_checker(url, 1.5)
                if 200 <= status_code < 300:
                    if len(body.strip()) > 0:
                        metadata.status = PreviewStatus.HEALTHY
                        metadata.last_health_check_at = datetime.now(UTC)
                        metadata.health_error = None
                        self.save_persisted_metadata(metadata)
                        return metadata
                    else:
                        readiness_error = (
                            f"HTTP {status_code} returned empty response body (0 bytes)"
                        )
                else:
                    readiness_error = f"HTTP {status_code} is not a successful 2xx response"
            except Exception as exc:
                readiness_error = str(exc)

            time.sleep(0.1)

        self.terminate_preview(metadata)
        metadata.status = PreviewStatus.UNHEALTHY
        metadata.health_error = readiness_error or "Readiness check timed out"
        self.save_persisted_metadata(metadata)
        raise RuntimeError(
            f"Preview failed readiness check on port {target_port}: {metadata.health_error}"
        )

    def check_health(self, metadata: PreviewMetadata, timeout_seconds: float = 3.0) -> bool:
        """
        Check if managed preview is alive and returning valid 200-level non-empty responses.
        """
        pid = metadata.pid
        process = self._managed_processes.get(pid) if pid else None
        if process and hasattr(process, "poll") and process.poll() is not None:
            metadata.status = PreviewStatus.UNHEALTHY
            metadata.health_error = f"Process {pid} terminated with code {process.returncode}"
            self.save_persisted_metadata(metadata)
            return False

        try:
            status_code, body = self._http_checker(metadata.url, timeout_seconds)
            metadata.last_health_check_at = datetime.now(UTC)
            if 200 <= status_code < 300 and len(body.strip()) > 0:
                metadata.status = PreviewStatus.HEALTHY
                metadata.health_error = None
                self.save_persisted_metadata(metadata)
                return True
            else:
                err = (
                    f"HTTP {status_code} returned empty response body"
                    if 200 <= status_code < 300
                    else f"HTTP status {status_code} is not 2xx"
                )
                metadata.status = PreviewStatus.UNHEALTHY
                metadata.health_error = err
                self.save_persisted_metadata(metadata)
                return False
        except Exception as exc:
            metadata.last_health_check_at = datetime.now(UTC)
            metadata.status = PreviewStatus.UNHEALTHY
            metadata.health_error = str(exc)
            self.save_persisted_metadata(metadata)
            return False

    def restart_unhealthy_preview(
        self,
        metadata: PreviewMetadata,
        *,
        max_restarts: int = 3,
        timeout_seconds: float = 10.0,
    ) -> PreviewMetadata:
        """Terminate failed/unhealthy preview process and launch a fresh managed instance."""
        if metadata.restart_count >= max_restarts:
            raise RuntimeError(
                f"Max restart limit ({max_restarts}) exceeded for preview {metadata.task_id}"
            )

        restarts = metadata.restart_count + 1
        self.terminate_preview(metadata)

        new_meta = self.start_preview(
            metadata.worktree_path,
            task_id=metadata.task_id,
            project_id=metadata.project_id,
            port=metadata.port,
            timeout_seconds=timeout_seconds,
        )
        new_meta.restart_count = restarts
        self.save_persisted_metadata(new_meta)
        return new_meta

    def _kill_process_group(
        self,
        pid: int,
        port: int | None = None,
        timeout_seconds: float = 2.0,
    ) -> None:
        try:
            os.killpg(pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass

        if port is not None:
            deadline = time.time() + timeout_seconds
            while time.time() < deadline:
                if not is_port_available(port):
                    time.sleep(0.05)
                else:
                    break

        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass

    def terminate_preview(self, metadata: PreviewMetadata, timeout_seconds: float = 2.0) -> None:
        """Cleanly terminate the preview process group."""
        pid = metadata.pid
        if not pid:
            metadata.status = PreviewStatus.STOPPED
            self.save_persisted_metadata(metadata)
            return

        self._managed_processes.pop(pid, None)
        self._kill_process_group(pid, port=metadata.port, timeout_seconds=timeout_seconds)
        metadata.status = PreviewStatus.STOPPED
        self.save_persisted_metadata(metadata)
