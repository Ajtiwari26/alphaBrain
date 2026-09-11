"""
alpha_worker/daemon_supervisor.py
macOS launchd persistent supervisor for CI/CD Self-Healing Daemon and ParallelWorkerDispatcher.

Provides continuous background supervision with:
- Subprocess and in-process thread supervision
- Auto-restart and crash recovery with exponential backoff
- Crash loop detection and threshold enforcement
- Health status inspection and atomic 0600 status persistence
- Graceful signal handling (SIGTERM, SIGINT) and child process reaping
- Launchd inspection and recovery guidance for com.alphabrain.healing
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

from alpha_core.config import settings

logger = logging.getLogger("alphabrain.worker.daemon_supervisor")


class SupervisorState(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    CRASH_LOOP = "crash_loop"
    STOPPING = "stopping"
    STOPPED = "stopped"


class ServiceState(str, Enum):
    INITIALIZING = "initializing"
    RUNNING = "running"
    CRASHED = "crashed"
    RESTARTING = "restarting"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclasses.dataclass
class ServiceConfig:
    """Configuration for a supervised daemon service."""

    name: str
    target: Callable[..., Any] | None = None
    args: tuple[Any, ...] = ()
    kwargs: dict[str, Any] = dataclasses.field(default_factory=dict)
    command: list[str] | None = None
    cwd: str | Path | None = None
    env: dict[str, str] | None = None
    max_restarts: int = 5
    restart_window_seconds: float = 300.0
    backoff_base_seconds: float = 1.0
    backoff_max_seconds: float = 30.0
    crash_reset_window_seconds: float = 60.0
    health_check: Callable[[], bool] | None = None
    on_crash: Callable[[str, str | None], None] | None = None
    on_restart: Callable[[str, int], None] | None = None
    stop_signal: int = signal.SIGTERM


@dataclasses.dataclass
class ServiceRuntime:
    """Runtime tracking state for a supervised service."""

    config: ServiceConfig
    state: ServiceState = ServiceState.INITIALIZING
    thread: threading.Thread | None = None
    process: subprocess.Popen[Any] | None = None
    pid: int | None = None
    stop_event: threading.Event = dataclasses.field(default_factory=threading.Event)
    restart_count: int = 0
    consecutive_crashes: int = 0
    crash_timestamps: list[float] = dataclasses.field(default_factory=list)
    last_started_at: float | None = None
    last_crashed_at: float | None = None
    last_error: str | None = None
    next_restart_at: float = 0.0
    should_stop: bool = False

    @property
    def uptime_seconds(self) -> float:
        if self.state == ServiceState.RUNNING and self.last_started_at is not None:
            return max(0.0, time.time() - self.last_started_at)
        return 0.0


@dataclasses.dataclass
class ServiceHealthReport:
    name: str
    state: str
    pid: int | None = None
    restart_count: int = 0
    consecutive_crashes: int = 0
    last_started_at: float | None = None
    last_crashed_at: float | None = None
    last_error: str | None = None
    uptime_seconds: float = 0.0
    healthy: bool = True
    extra: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass
class SupervisorHealthReport:
    supervisor_state: str
    pid: int
    uptime_seconds: float
    started_at: float
    services: dict[str, ServiceHealthReport]
    healthy: bool
    hardware_health: dict[str, Any] = dataclasses.field(default_factory=dict)
    updated_at: float = dataclasses.field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        out = {
            "supervisor_state": self.supervisor_state,
            "pid": self.pid,
            "uptime_seconds": self.uptime_seconds,
            "started_at": self.started_at,
            "healthy": self.healthy,
            "services": {k: v.to_dict() for k, v in self.services.items()},
            "hardware_health": self.hardware_health,
            "updated_at": self.updated_at,
        }
        return out

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class DaemonSupervisor:
    """
    Supervises background daemons for AlphaBrain (CIHealingDaemon, ParallelWorkerDispatcher).
    Manages process/thread lifecycles, exponential backoff auto-restart, crash loop mitigation,
    and atomic health status reporting.
    """

    def __init__(
        self,
        services: list[ServiceConfig] | None = None,
        state_dir: Path | None = None,
        status_file: Path | None = None,
        poll_interval: float = 1.0,
    ) -> None:
        self.poll_interval = poll_interval
        self._state_dir = (state_dir or settings.WORKER_STATE_DIR).expanduser().resolve()
        self._state_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self._state_dir, 0o700)
        except OSError:
            pass

        self._status_file = status_file or (self._state_dir / "supervisor_status.json")
        self._lock = threading.RLock()
        self._services: dict[str, ServiceRuntime] = {}
        self._state: SupervisorState = SupervisorState.STARTING
        self._started_at: float = time.time()
        self._shutdown: bool = False
        self._signals_registered: bool = False

        if services:
            for s in services:
                self.register_service(s)

    @property
    def state(self) -> SupervisorState:
        with self._lock:
            return self._state

    @property
    def status_file(self) -> Path:
        return self._status_file

    @property
    def uptime_seconds(self) -> float:
        return max(0.0, time.time() - self._started_at)

    def register_service(self, config: ServiceConfig) -> None:
        with self._lock:
            if config.name in self._services:
                raise ValueError(f"Service '{config.name}' is already registered.")
            self._services[config.name] = ServiceRuntime(config=config)
            logger.info("Registered service '%s' for supervision", config.name)

    def _spawn_service(self, runtime: ServiceRuntime) -> None:
        runtime.should_stop = False
        runtime.stop_event.clear()
        cfg = runtime.config

        if cfg.command:
            # Spawn as external subprocess
            env = os.environ.copy()
            if cfg.env:
                env.update(cfg.env)
            cwd = str(cfg.cwd) if cfg.cwd else None
            logger.info("Spawning subprocess service '%s': %s", cfg.name, cfg.command)
            # Inherit parent stdout/stderr to avoid 64KB OS pipe buffer exhaustion deadlock.
            # Under launchd, child logs stream directly to StandardOutPath and StandardErrorPath.
            proc = subprocess.Popen(
                cfg.command,
                cwd=cwd,
                env=env,
            )
            runtime.process = proc
            runtime.pid = proc.pid
            runtime.thread = None
        elif cfg.target:
            # Spawn as thread running target callable
            def _runner() -> None:
                try:
                    logger.info("Starting thread service '%s'", cfg.name)
                    # Support target callables that accept stop_event or kwargs
                    import inspect
                    sig = inspect.signature(cfg.target)
                    kwargs = dict(cfg.kwargs)
                    if "stop_event" in sig.parameters and "stop_event" not in kwargs:
                        kwargs["stop_event"] = runtime.stop_event
                    cfg.target(*cfg.args, **kwargs)
                    logger.info("Thread service '%s' finished cleanly", cfg.name)
                except Exception as exc:
                    logger.error("Exception in service '%s': %s", cfg.name, exc, exc_info=True)
                    runtime.last_error = str(exc)

            th = threading.Thread(target=_runner, name=f"svc_{cfg.name}", daemon=True)
            runtime.thread = th
            runtime.process = None
            runtime.pid = os.getpid()
            th.start()
        else:
            raise ValueError(f"Service '{cfg.name}' has neither command nor target specified.")

        runtime.last_started_at = time.time()
        runtime.state = ServiceState.RUNNING
        logger.info("Service '%s' transitioned to RUNNING (pid=%s)", cfg.name, runtime.pid)

    def start_service(self, name: str) -> bool:
        with self._lock:
            runtime = self._services.get(name)
            if not runtime:
                logger.error("Cannot start unknown service '%s'", name)
                return False
            if runtime.state == ServiceState.RUNNING:
                return True
            try:
                self._spawn_service(runtime)
                return True
            except Exception as e:
                logger.error("Failed to start service '%s': %s", name, e)
                runtime.state = ServiceState.FAILED
                runtime.last_error = str(e)
                return False

    def stop_service(self, name: str, timeout: float = 5.0) -> bool:
        with self._lock:
            runtime = self._services.get(name)
            if not runtime:
                return False
            runtime.should_stop = True
            runtime.stop_event.set()

        # Stop subprocess if applicable
        if runtime.process:
            try:
                if runtime.process.poll() is None:
                    runtime.process.terminate()
                    runtime.process.wait(timeout=timeout)
            except Exception:
                try:
                    if runtime.process.poll() is None:
                        runtime.process.kill()
                        runtime.process.wait(timeout=1.0)
                except Exception:
                    pass

        # Wait for thread if applicable
        if runtime.thread and runtime.thread.is_alive():
            runtime.thread.join(timeout=timeout)

        with self._lock:
            runtime.state = ServiceState.STOPPED
            runtime.pid = None
            logger.info("Service '%s' stopped", name)
            return True

    def restart_service(self, name: str, reason: str = "manual_restart") -> bool:
        with self._lock:
            runtime = self._services.get(name)
            if not runtime:
                return False
            logger.info("Restarting service '%s' (reason: %s)", name, reason)
            self.stop_service(name, timeout=2.0)
            runtime.restart_count += 1
            if runtime.config.on_restart:
                try:
                    runtime.config.on_restart(name, runtime.restart_count)
                except Exception as e:
                    logger.warning("on_restart hook error for '%s': %s", name, e)
            return self.start_service(name)

    def start(self) -> None:
        """Starts all registered services and sets supervisor state to RUNNING."""
        with self._lock:
            self.register_signals()
            self._started_at = time.time()
            self._state = SupervisorState.RUNNING
            for name in list(self._services.keys()):
                self.start_service(name)
            self.write_status_file()
            logger.info("DaemonSupervisor started with %d services", len(self._services))

    def register_signals(self) -> None:
        """Registers SIGINT and SIGTERM handlers if running on the main thread."""
        if self._signals_registered:
            return
        if threading.current_thread() is not threading.main_thread():
            return

        def _handler(signum: int, _frame: Any) -> None:
            sig_name = signal.Signals(signum).name
            logger.info("DaemonSupervisor received %s. Initiating graceful shutdown.", sig_name)
            self.stop()

        try:
            signal.signal(signal.SIGINT, _handler)
            signal.signal(signal.SIGTERM, _handler)
            self._signals_registered = True
        except (ValueError, OSError) as e:
            logger.warning("Failed to register signal handlers: %s", e)

    def _handle_service_crash(self, runtime: ServiceRuntime, error_msg: str | None) -> None:
        now = time.time()
        runtime.state = ServiceState.CRASHED
        runtime.last_crashed_at = now
        runtime.last_error = error_msg
        runtime.consecutive_crashes += 1
        runtime.restart_count += 1
        runtime.crash_timestamps.append(now)

        # Retain only crashes within the sliding restart window
        window = runtime.config.restart_window_seconds
        runtime.crash_timestamps = [t for t in runtime.crash_timestamps if (now - t) <= window]

        logger.warning(
            "Service '%s' crashed (consecutive: %d, in window: %d, error: %s)",
            runtime.config.name,
            runtime.consecutive_crashes,
            len(runtime.crash_timestamps),
            error_msg,
        )

        if runtime.config.on_crash:
            try:
                runtime.config.on_crash(runtime.config.name, error_msg)
            except Exception as e:
                logger.warning("on_crash hook failed for '%s': %s", runtime.config.name, e)

        # Check if crash loop threshold is exceeded
        if len(runtime.crash_timestamps) > runtime.config.max_restarts:
            runtime.state = ServiceState.FAILED
            logger.error(
                "Service '%s' exceeded max_restarts (%d in %.1fs). Marking FAILED.",
                runtime.config.name,
                runtime.config.max_restarts,
                window,
            )
            return

        # Calculate exponential backoff
        exp = max(0, runtime.consecutive_crashes - 1)
        backoff = min(
            runtime.config.backoff_max_seconds,
            runtime.config.backoff_base_seconds * (2**exp),
        )
        runtime.next_restart_at = now + backoff
        runtime.state = ServiceState.RESTARTING
        logger.info(
            "Service '%s' scheduled for auto-restart in %.1fs (at %.1f)",
            runtime.config.name,
            backoff,
            runtime.next_restart_at,
        )

    def supervise_cycle(self) -> dict[str, Any]:
        """
        Executes a single pass of supervision:
        - Detects crashed services (process exit or thread death)
        - Applies crash loop detection and exponential backoff auto-restart
        - Resets consecutive crash count for stable services
        - Updates supervisor state and persists atomic health status
        """
        now = time.time()
        with self._lock:
            for name, runtime in self._services.items():
                # 1. Check active RUNNING services
                if runtime.state == ServiceState.RUNNING:
                    is_dead = False
                    err: str | None = None

                    if runtime.process is not None:
                        exit_code = runtime.process.poll()
                        if exit_code is not None:
                            is_dead = True
                            err = f"Process exited with code {exit_code}"
                    elif runtime.thread is not None:
                        if not runtime.thread.is_alive():
                            is_dead = True
                            err = runtime.last_error or "Thread terminated unexpectedly"

                    if is_dead and not runtime.should_stop:
                        self._handle_service_crash(runtime, err)
                    elif not is_dead:
                        # Service is alive. Check stability window to reset consecutive crash count
                        if (
                            runtime.last_started_at is not None
                            and (now - runtime.last_started_at)
                            >= runtime.config.crash_reset_window_seconds
                        ):
                            if runtime.consecutive_crashes > 0:
                                logger.info(
                                    "Service '%s' has run stably for %.1fs. Resetting crash count.",
                                    name,
                                    now - runtime.last_started_at,
                                )
                                runtime.consecutive_crashes = 0

                        # Run custom health check if defined
                        if runtime.config.health_check:
                            try:
                                is_healthy = runtime.config.health_check()
                                if not is_healthy:
                                    logger.warning("Custom health check failed for '%s'", name)
                            except Exception as chk_err:
                                logger.warning("Health check raised for '%s': %s", name, chk_err)

                # 2. Check RESTARTING services ready for auto-restart
                elif runtime.state == ServiceState.RESTARTING:
                    if now >= runtime.next_restart_at and not runtime.should_stop:
                        logger.info("Executing auto-restart for service '%s'", name)
                        try:
                            self._spawn_service(runtime)
                            if runtime.config.on_restart:
                                runtime.config.on_restart(name, runtime.restart_count)
                        except Exception as start_err:
                            logger.error("Auto-restart failed for '%s': %s", name, start_err)
                            self._handle_service_crash(runtime, str(start_err))

            # 3. Evaluate overall supervisor state
            states = [r.state for r in self._services.values()]
            if self._shutdown:
                self._state = SupervisorState.STOPPING
            elif any(s == ServiceState.FAILED for s in states):
                self._state = SupervisorState.CRASH_LOOP
            elif any(s in (ServiceState.CRASHED, ServiceState.RESTARTING) for s in states):
                self._state = SupervisorState.DEGRADED
            elif all(s == ServiceState.RUNNING for s in states) and states:
                self._state = SupervisorState.RUNNING
            elif all(s == ServiceState.STOPPED for s in states) and states:
                self._state = SupervisorState.STOPPED
            else:
                self._state = SupervisorState.RUNNING

            report = self.inspect_health()
            self.write_status_file()
            return report.to_dict()

    def run_loop(
        self, poll_interval: float | None = None, max_cycles: int | None = None
    ) -> None:
        """Supervision loop running continuously until stopped or max_cycles reached."""
        sleep_sec = poll_interval if poll_interval is not None else self.poll_interval
        logger.info("Starting DaemonSupervisor run loop (poll_interval=%.1fs)", sleep_sec)
        cycle = 0

        while not self._shutdown:
            try:
                self.supervise_cycle()
            except Exception as e:
                logger.error("Error during supervision cycle: %s", e, exc_info=True)

            cycle += 1
            if max_cycles is not None and cycle >= max_cycles:
                logger.info("Reached maximum requested supervisor cycles (%d). Stopping.", max_cycles)
                break

            if not self._shutdown:
                time.sleep(sleep_sec)

        self.stop()
        logger.info("DaemonSupervisor run loop exited.")

    def stop(self, timeout: float = 5.0) -> None:
        """Gracefully stops all supervised services and records STOPPED state."""
        with self._lock:
            self._shutdown = True
            self._state = SupervisorState.STOPPING
            logger.info("Stopping all supervised services...")
            for name in list(self._services.keys()):
                try:
                    self.stop_service(name, timeout=timeout)
                except Exception as e:
                    logger.error("Error stopping service '%s': %s", name, e)

            self._state = SupervisorState.STOPPED
            self.write_status_file()
            logger.info("All supervised services stopped. Supervisor state: STOPPED.")

    def inspect_health(self) -> SupervisorHealthReport:
        """Inspects and returns a complete, typed health report of the supervisor and services."""
        with self._lock:
            service_reports: dict[str, ServiceHealthReport] = {}
            for name, runtime in self._services.items():
                service_reports[name] = ServiceHealthReport(
                    name=name,
                    state=runtime.state.value,
                    pid=runtime.pid,
                    restart_count=runtime.restart_count,
                    consecutive_crashes=runtime.consecutive_crashes,
                    last_started_at=runtime.last_started_at,
                    last_crashed_at=runtime.last_crashed_at,
                    last_error=runtime.last_error,
                    uptime_seconds=runtime.uptime_seconds,
                    healthy=runtime.state == ServiceState.RUNNING,
                )

            # Retrieve host/hardware metrics safely
            hw_metrics: dict[str, Any] = {}
            try:
                from alpha_worker.health import HardwareHealthChecker

                health_status, metrics = HardwareHealthChecker.evaluate_worker_health()
                hw_metrics = {
                    "health_status": getattr(health_status, "value", str(health_status)),
                    **metrics,
                }
            except Exception:
                hw_metrics = {"status": "unavailable"}

            all_healthy = (
                self._state == SupervisorState.RUNNING
                and all(r.healthy for r in service_reports.values())
                if service_reports
                else True
            )

            return SupervisorHealthReport(
                supervisor_state=self._state.value,
                pid=os.getpid(),
                uptime_seconds=self.uptime_seconds,
                started_at=self._started_at,
                services=service_reports,
                healthy=all_healthy,
                hardware_health=hw_metrics,
                updated_at=time.time(),
            )

    def write_status_file(self) -> None:
        """Atomically writes current health report to status_file with 0600 permissions."""
        try:
            report = self.inspect_health()
            temporary = self._status_file.with_suffix(".tmp")
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w") as out:
                out.write(report.to_json(indent=2) + "\n")
                out.flush()
                os.fsync(out.fileno())
            os.replace(temporary, self._status_file)
        except Exception as e:
            logger.error("Failed to write supervisor status file: %s", e)

    @staticmethod
    def read_status_file(path: Path) -> dict[str, Any] | None:
        """Safely reads and parses the JSON supervisor status file."""
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    @classmethod
    def create_healing_supervisor(
        cls,
        queue: Any | None = None,
        project_id: str = "alphabrain_dogfood",
        max_workers: int = 4,
        state_dir: Path | None = None,
        status_file: Path | None = None,
        poll_interval: float = 1.0,
        execution_mode: str = "thread",
        auto_approve_repairs: bool = True,
    ) -> DaemonSupervisor:
        """
        Factory creating a DaemonSupervisor configured for AlphaBrain's
        CIHealingDaemon and ParallelWorkerDispatcher.
        """
        from alpha_core.queue.triage_queue import TaskTriageQueue
        from alpha_worker.ci_healing_daemon import CIHealingDaemon
        from alpha_worker.parallel_dispatcher import ParallelWorkerDispatcher

        q = queue or TaskTriageQueue()

        if execution_mode == "subprocess":
            healing_cmd = [
                sys.executable,
                "-m",
                "alpha_worker",
                "healing-daemon",
                "--project-id",
                project_id,
            ]
            dispatcher_cmd = [
                sys.executable,
                "-m",
                "alpha_worker",
                "dispatcher",
                "--project-id",
                project_id,
                "--max-workers",
                str(max_workers),
            ]
            services = [
                ServiceConfig(name="ci_healing", command=healing_cmd, max_restarts=5),
                ServiceConfig(name="parallel_dispatcher", command=dispatcher_cmd, max_restarts=5),
            ]
        else:
            # Threaded in-process runners
            healing_daemon = CIHealingDaemon(
                queue=q,
                project_id=project_id,
                auto_approve_repairs=auto_approve_repairs,
            )
            dispatcher = ParallelWorkerDispatcher(
                queue=q,
                project_id=project_id,
                max_workers=max_workers,
                ci_healing_daemon=healing_daemon,
                auto_approve_repairs=auto_approve_repairs,
            )

            def _run_healing(stop_event: threading.Event) -> None:
                while not stop_event.is_set():
                    healing_daemon.run_once()
                    stop_event.wait(timeout=2.0)

            def _run_dispatcher(stop_event: threading.Event) -> None:
                while not stop_event.is_set():
                    dispatcher.run_once()
                    stop_event.wait(timeout=1.0)

            services = [
                ServiceConfig(
                    name="ci_healing",
                    target=_run_healing,
                    max_restarts=5,
                    backoff_base_seconds=1.0,
                ),
                ServiceConfig(
                    name="parallel_dispatcher",
                    target=_run_dispatcher,
                    max_restarts=5,
                    backoff_base_seconds=1.0,
                ),
            ]

        return cls(
            services=services,
            state_dir=state_dir,
            status_file=status_file,
            poll_interval=poll_interval,
        )


class HealingLaunchdInspector:
    """Read-only inspector for com.alphabrain.healing launchd service."""

    LABEL = "com.alphabrain.healing"

    def __init__(
        self,
        command_runner: Callable[[list[str]], tuple[int, str, str]] | None = None,
        time_fn: Callable[[], float] = time.time,
        home_dir: Path | None = None,
        status_file: Path | None = None,
    ) -> None:
        if command_runner is None:

            def _default_runner(cmd: list[str]) -> tuple[int, str, str]:
                res = subprocess.run(cmd, capture_output=True, text=True, check=False)
                return res.returncode, res.stdout, res.stderr

            self._run_cmd = _default_runner
        else:
            self._run_cmd = command_runner

        self._time = time_fn
        self._home = home_dir or Path.home()
        self._plist_path = self._home / "Library" / "LaunchAgents" / f"{self.LABEL}.plist"
        self._status_file = status_file or (settings.WORKER_STATE_DIR / "supervisor_status.json")
        self._recovery_cmd = "./ops/launchd/install_healing_daemon.sh $(pwd)"

    def inspect(self) -> dict[str, Any]:
        """Inspects the installation and running status of com.alphabrain.healing."""
        import plistlib

        report: dict[str, Any] = {
            "service_label": self.LABEL,
            "plist_installed": self._plist_path.exists(),
            "plist_valid": False,
            "loaded": False,
            "running": False,
            "pid": None,
            "exit_code": None,
            "status_freshness_seconds": None,
            "recovery_command": None,
        }

        if report["plist_installed"]:
            code, _, _ = self._run_cmd(["plutil", "-lint", str(self._plist_path)])
            if code == 0:
                report["plist_valid"] = True
                try:
                    with open(self._plist_path, "rb") as f:
                        data = plistlib.load(f)
                    if data.get("UserName") == "root":
                        report["plist_valid"] = False
                    if "RootDirectory" in data:
                        report["plist_valid"] = False
                    if not data.get("KeepAlive"):
                        report["plist_valid"] = False
                    if data.get("ThrottleInterval", 0) < 10:
                        report["plist_valid"] = False
                    if data.get("ProcessType") != "Background":
                        report["plist_valid"] = False
                except Exception:
                    report["plist_valid"] = False

        # Query launchctl list
        code, stdout, _ = self._run_cmd(["launchctl", "list"])
        if code == 0:
            for line in stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 3 and parts[2] == self.LABEL:
                    report["loaded"] = True
                    pid_str = parts[0]
                    status_str = parts[1]
                    if pid_str.isdigit():
                        report["running"] = True
                        report["pid"] = int(pid_str)
                    else:
                        report["running"] = False
                    if status_str.isdigit() or (
                        status_str.startswith("-") and status_str[1:].isdigit()
                    ):
                        report["exit_code"] = int(status_str)
                    break

        if self._status_file and self._status_file.exists():
            try:
                mtime = self._status_file.stat().st_mtime
                report["status_freshness_seconds"] = max(0.0, self._time() - mtime)
            except OSError:
                pass

        # Formulate recovery command if needed
        if not report["plist_installed"]:
            report["recovery_command"] = f"Missing plist. Run: {self._recovery_cmd}"
        elif not report["plist_valid"]:
            report["recovery_command"] = f"Invalid plist. Run: {self._recovery_cmd}"
        elif not report["loaded"]:
            report["recovery_command"] = f"Service not loaded. Run: {self._recovery_cmd}"
        elif not report["running"]:
            report["recovery_command"] = (
                f"Service stopped (exit {report['exit_code']}). Run: {self._recovery_cmd}"
            )
        elif (
            report["status_freshness_seconds"] is not None
            and report["status_freshness_seconds"] > 300
        ):
            report["recovery_command"] = f"Supervisor running but stale status. Run: {self._recovery_cmd}"

        return report
