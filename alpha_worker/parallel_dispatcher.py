"""
alpha_worker/parallel_dispatcher.py
Parallel Worker Dispatcher Daemon for AlphaBrain.

Orchestrates concurrent worker execution:
1. Queries TaskTriageQueue for approved tasks.
2. Maintains a concurrency pool bounded by max_workers.
3. Dispatches tasks simultaneously into isolated git worktrees via worker-cycle.
4. Enforces execution timeouts, terminating runaway workers and recording failure.
5. Routes completed tasks to Senior Review and CI Healing daemons.
"""

from __future__ import annotations

import argparse
import dataclasses
import inspect
import logging
import multiprocessing
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from alpha_core.queue.triage_queue import TaskTriageQueue, TriageStatus
from alpha_worker.adaptive_manager import (
    AdaptiveConcurrencyManager,
    MechanicAction,
    PipelineMechanic,
    TaskStallSnapshot,
)
from alpha_worker.ci_healing_daemon import CIHealingDaemon
from alpha_worker.senior_review_engine import SeniorReviewEngine
from alpha_worker.triage_dispatcher import PRProposal, TriageTaskDispatcher
from alpha_worker.worktree import WorktreeManager

logger = logging.getLogger("alphabrain.worker.parallel_dispatcher")


class ProcessHandle:
    """Wrapper around multiprocessing.Process providing a subprocess.Popen-compatible interface."""

    def __init__(self, process: multiprocessing.Process) -> None:
        self._proc = process

    @property
    def pid(self) -> int | None:
        return self._proc.pid

    def poll(self) -> int | None:
        if self._proc.is_alive():
            return None
        return self._proc.exitcode

    def terminate(self) -> None:
        self._proc.terminate()

    def kill(self) -> None:
        self._proc.kill()

    def wait(self, timeout: float | None = None) -> int | None:
        self._proc.join(timeout=timeout)
        return self.poll()


@dataclasses.dataclass
class ActiveTaskExecution:
    """Tracks state and metadata for an actively running worker task."""

    task_id: str
    started_at: float | None
    worker_id: str
    process: subprocess.Popen[Any] | ProcessHandle | None = None
    result_queue: Any | None = None
    worktree_path: Path | str | None = None
    envelope: dict[str, Any] = dataclasses.field(default_factory=dict)
    cancelled: bool = False
    future: Any | None = None

    @property
    def elapsed_seconds(self) -> float:
        if self.started_at is None:
            return 0.0
        return max(0.0, time.time() - self.started_at)


def _worker_process_target(
    worker_fn: Callable[..., Any],
    leased_task: dict[str, Any],
    worker_id: str,
    result_queue: Any,
) -> None:
    """Entrypoint executing inside an isolated worker child process."""
    try:
        sig = inspect.signature(worker_fn)
        if len(sig.parameters) >= 2:
            res = worker_fn(leased_task, worker_id)
        else:
            res = worker_fn(leased_task)

        res_data: Any
        if hasattr(res, "to_dict"):
            res_data = res.to_dict()
        elif isinstance(res, (dict, list, str, int, float, bool, type(None))):
            res_data = res
        else:
            res_data = str(res)

        result_queue.put({"success": True, "result": res_data, "error": None})
    except Exception as e:
        logger.exception("Worker execution error on task %s: %s", leased_task.get("id"), e)
        result_queue.put({"success": False, "result": None, "error": str(e)})


class ParallelWorkerDispatcher:
    """
    Parallel Worker Dispatcher Daemon managing a concurrent pool of up to max_workers.
    Queries TaskTriageQueue for approved tasks, executes them concurrently in isolated
    git worktrees, enforces execution timeouts, and routes completions to Senior Review and CI Healing.
    """

    def __init__(
        self,
        queue: TaskTriageQueue,
        max_workers: int = 4,
        worktree_mgr: WorktreeManager | None = None,
        timeout_seconds: float = 300.0,
        poll_interval: float = 1.0,
        project_id: str | None = None,
        senior_review_engine: SeniorReviewEngine | None = None,
        ci_healing_daemon: CIHealingDaemon | None = None,
        worker_cycle_fn: Callable[[dict[str, Any]], Any] | None = None,
        enable_agent_execution: bool = False,
        execution_mode: str = "process",
        auto_approve_repairs: bool = False,
        adaptive_manager: AdaptiveConcurrencyManager | None = None,
        enable_adaptive_concurrency: bool = False,
        pipeline_mechanic: PipelineMechanic | None = None,
        enable_pipeline_mechanic: bool = False,
    ) -> None:
        if max_workers < 1:
            raise ValueError(f"max_workers must be at least 1, got {max_workers}")

        self.queue = queue
        self.max_workers = max_workers
        self.worktree_mgr = worktree_mgr or WorktreeManager()
        self.timeout_seconds = timeout_seconds
        self.poll_interval = poll_interval
        self.project_id = project_id
        self.senior_review_engine = senior_review_engine
        self.ci_healing_daemon = ci_healing_daemon
        self.worker_cycle_fn = worker_cycle_fn
        self.enable_agent_execution = enable_agent_execution
        self.execution_mode = execution_mode
        self.auto_approve_repairs = auto_approve_repairs

        self.adaptive_manager = adaptive_manager
        self.enable_adaptive_concurrency = enable_adaptive_concurrency or (adaptive_manager is not None)
        self.pipeline_mechanic = pipeline_mechanic
        self.enable_pipeline_mechanic = enable_pipeline_mechanic or (pipeline_mechanic is not None)

        try:
            self._mp_context = multiprocessing.get_context("fork")
        except ValueError:
            self._mp_context = multiprocessing.get_context()

        self._lock = threading.Lock()
        self._active_tasks: dict[str, ActiveTaskExecution] = {}
        self._shutdown = False

    def _get_healing_daemon(self) -> CIHealingDaemon:
        if self.ci_healing_daemon is not None:
            return self.ci_healing_daemon
        return CIHealingDaemon(
            queue=self.queue,
            project_id=self.project_id or "alphabrain_dogfood",
            auto_approve_repairs=self.auto_approve_repairs,
        )

    # -------------------------------------------------------------------------
    # Pool State and Capacity
    # -------------------------------------------------------------------------
    @property
    def active_tasks(self) -> dict[str, ActiveTaskExecution]:
        with self._lock:
            return dict(self._active_tasks)

    def active_count(self) -> int:
        with self._lock:
            return len(self._active_tasks)

    def get_effective_max_workers(self, queue_depth: int | None = None) -> int:
        """Computes current maximum worker capacity considering adaptive hardware limits."""
        if not self.enable_adaptive_concurrency or self.adaptive_manager is None:
            return self.max_workers

        if queue_depth is None:
            try:
                tasks = self.queue.list_tasks(
                    status=TriageStatus.APPROVED, limit=50, project_id=self.project_id
                )
                queue_depth = len(tasks)
            except Exception:
                queue_depth = 0

        decision = self.adaptive_manager.compute_concurrency(queue_depth=queue_depth)
        return min(self.max_workers, decision.target_workers)

    def available_slots(self) -> int:
        with self._lock:
            effective_limit = self.get_effective_max_workers()
            return max(0, effective_limit - len(self._active_tasks))

    def is_pool_full(self) -> bool:
        return self.available_slots() == 0

    # -------------------------------------------------------------------------
    # Task Retrieval & Queue Querying
    # -------------------------------------------------------------------------
    def get_approved_tasks(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        Queries TaskTriageQueue for approved tasks eligible for worker execution.
        """
        if self.queue.is_emergency_stopped():
            logger.warning("Emergency stop active; approved task retrieval suspended.")
            return []

        try:
            return self.queue.list_tasks(
                status=TriageStatus.APPROVED,
                limit=limit,
                project_id=self.project_id,
            )
        except Exception as e:
            logger.error("Failed to query approved tasks from queue: %s", e)
            return []

    # -------------------------------------------------------------------------
    # Worker-Cycle Task Execution
    # -------------------------------------------------------------------------
    def execute_single_worker_cycle(
        self, leased_task: dict[str, Any], worker_id: str = ""
    ) -> PRProposal | None:
        """
        Executes a single leased task through worker-cycle inside an isolated git worktree.
        """
        task_id = leased_task["id"]
        logger.info("Executing worker cycle for task %s on worker %s", task_id, worker_id)

        if self.worker_cycle_fn is not None:
            sig = inspect.signature(self.worker_cycle_fn)
            if len(sig.parameters) >= 2:
                return self.worker_cycle_fn(leased_task, worker_id)
            return self.worker_cycle_fn(leased_task)

        dispatcher = TriageTaskDispatcher(
            queue=self.queue,
            worktree_mgr=self.worktree_mgr,
            enable_agent_execution=self.enable_agent_execution,
        )
        return dispatcher.execute_task(leased_task)

    def _spawn_worker_process(
        self, leased_task: dict[str, Any], worker_id: str
    ) -> tuple[subprocess.Popen[Any] | ProcessHandle, Any | None, float]:
        """Spawns an isolated worker child process and returns (proc_handle, result_queue, started_at)."""
        task_id = leased_task["id"]
        proc_handle: subprocess.Popen[Any] | ProcessHandle
        result_queue: Any | None
        if self.execution_mode == "subprocess":
            cmd = [
                sys.executable,
                "-m",
                "alpha_worker.parallel_dispatcher",
                "worker-cycle",
                "--task-id",
                task_id,
                "--db-path",
                str(self.queue.db_path),
            ]
            proc_handle = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            started_at = time.time()
            result_queue = None
        else:
            result_queue = self._mp_context.Queue()
            worker_fn = self.worker_cycle_fn or self.execute_single_worker_cycle

            proc = self._mp_context.Process(
                target=_worker_process_target,
                args=(worker_fn, leased_task, worker_id, result_queue),
            )
            proc.start()
            started_at = time.time()
            proc_handle = ProcessHandle(proc)
        return proc_handle, result_queue, started_at

    def dispatch_task(self, leased_task: dict[str, Any]) -> str | None:
        """
        Submits a leased task to the concurrent worker pool in an isolated OS process.
        Returns task_id on success, or None if pool is full or dispatch was rejected.
        """
        task_id = leased_task["id"]
        with self._lock:
            effective_max = self.get_effective_max_workers()
            if len(self._active_tasks) >= effective_max:
                logger.warning(
                    "Concurrency limit (%d) reached. Cannot dispatch task %s.",
                    effective_max,
                    task_id,
                )
                return None

            if task_id in self._active_tasks:
                logger.warning("Task %s is already running in worker pool.", task_id)
                return None

            worker_id = f"wrk_parallel_{task_id}_{int(time.time() * 1000)}"
            proc_handle, result_queue, started_at = self._spawn_worker_process(leased_task, worker_id)

            execution = ActiveTaskExecution(
                task_id=task_id,
                started_at=started_at,
                worker_id=worker_id,
                process=proc_handle,
                result_queue=result_queue,
                envelope=leased_task.get("envelope", {}),
            )
            self._active_tasks[task_id] = execution

        logger.info(
            "Dispatched task %s to concurrent worker pool (active: %d/%d, pid: %s)",
            task_id,
            self.active_count(),
            self.max_workers,
            proc_handle.pid,
        )
        return task_id

    def lease_and_dispatch_next(self) -> str | None:
        """
        Atomically leases the next approved task from TaskTriageQueue and dispatches it.
        Returns task_id on success, or None if no approved tasks or pool is full.
        """
        if self.queue.is_emergency_stopped():
            return None

        if self.is_pool_full():
            return None

        worker_tag = f"wrk_pool_{int(time.time() * 1000)}"
        leased = self.queue.lease_next_approved_task(worker_id=worker_tag)
        if not leased:
            return None

        dispatched_id = self.dispatch_task(leased)
        if not dispatched_id:
            # Revert or handle un-dispatched leased task
            logger.error("Failed to dispatch leased task %s to pool. Marking failed for retry.", leased["id"])
            try:
                self.queue.fail_task(leased["id"], error_details="Worker pool dispatch saturation", allow_retry=True)
            except Exception:
                pass
            return None

        return dispatched_id

    # -------------------------------------------------------------------------
    # Timeout Enforcement
    # -------------------------------------------------------------------------
    def handle_timeouts(self) -> list[str]:
        """
        Checks all active tasks against timeout_seconds.
        If pipeline mechanic is enabled, diagnoses stalls before termination and
        prescribes surgical resumption for recoverable stalls without full restarts.
        Terminates unrecoverable runaway executions forcefully with OS signals (SIGTERM, then SIGKILL),
        marks tasks failed in TaskTriageQueue, and routes them to CI healing.
        Returns the list of timed-out task IDs.
        """
        now = time.time()
        stalled_tasks: list[ActiveTaskExecution] = []

        with self._lock:
            for _task_id, execution in list(self._active_tasks.items()):
                if execution.started_at is not None and (now - execution.started_at) > self.timeout_seconds:
                    stalled_tasks.append(execution)

        timed_out_ids: list[str] = []
        for execution in stalled_tasks:
            task_id = execution.task_id

            # If pipeline mechanic is enabled, evaluate for surgical resumption
            if self.enable_pipeline_mechanic and self.pipeline_mechanic is not None:
                proc_alive = False
                if execution.process and execution.process.poll() is None:
                    proc_alive = True

                worktree_path = execution.worktree_path
                if not worktree_path and self.worktree_mgr:
                    try:
                        wt = self.worktree_mgr.get_worktree_path(task_id)
                        if wt.exists():
                            worktree_path = wt
                    except Exception:
                        pass

                snapshot = TaskStallSnapshot(
                    task_id=task_id,
                    elapsed_seconds=execution.elapsed_seconds,
                    timeout_seconds=self.timeout_seconds,
                    process_alive=proc_alive,
                    last_phase=execution.envelope.get("phase", "running"),
                    worktree_path=worktree_path,
                    envelope=dict(execution.envelope),
                )
                diagnosis = self.pipeline_mechanic.diagnose_stall(snapshot)

                # Re-acquire lock to guard against race conditions if task completed naturally during diagnosis
                with self._lock:
                    if task_id not in self._active_tasks:
                        logger.info("Task %s was removed or completed during diagnosis; aborting resumption.", task_id)
                        continue
                    if execution.process and execution.process.poll() is not None:
                        logger.info("Task %s completed naturally during diagnosis; aborting resumption.", task_id)
                        continue

                if diagnosis.is_recoverable:
                    logger.info(
                        "Task %s stall diagnosed as recoverable by Pipeline Mechanic: action=%s, phase=%s",
                        task_id,
                        diagnosis.action.value,
                        diagnosis.checkpoint_phase,
                    )
                    # For EXTEND_LEASE: worker process is making progress
                    if diagnosis.action == MechanicAction.EXTEND_LEASE and proc_alive:
                        with self._lock:
                            execution.started_at = time.time()
                        logger.info("Extended lease for active worker on task %s", task_id)
                        continue

                    # For RESUME_CHECKPOINT / RETRY_STEP: terminate stuck child process cleanly
                    if execution.process and execution.process.poll() is None:
                        try:
                            execution.process.terminate()
                            execution.process.wait(timeout=1.0)
                        except Exception:
                            pass

                    # Prepare task payload with checkpoint envelope for surgical resumption
                    task_row = self.queue.get_task(task_id) or {"id": task_id}
                    resumed_envelope = dict(task_row.get("envelope", {}) or execution.envelope)
                    resumed_envelope["last_checkpoint_phase"] = diagnosis.checkpoint_phase
                    resumed_envelope["surgically_resumed"] = True
                    task_dict = dict(task_row)
                    task_dict["envelope"] = resumed_envelope

                    resumed = self.pipeline_mechanic.execute_surgical_resumption(
                        snapshot,
                        diagnosis,
                    )
                    if resumed:
                        new_worker_id = f"wrk_resumed_{task_id}_{int(time.time() * 1000)}"
                        new_proc, new_rq, new_started = self._spawn_worker_process(task_dict, new_worker_id)
                        with self._lock:
                            execution.process = new_proc
                            execution.result_queue = new_rq
                            execution.started_at = new_started
                            execution.worker_id = new_worker_id
                            execution.envelope = resumed_envelope
                            execution.cancelled = False
                        logger.info(
                            "Task %s surgically resumed with active worker process (pid: %s, phase: %s). Zero full restarts.",
                            task_id,
                            new_proc.pid,
                            diagnosis.checkpoint_phase,
                        )
                        continue

            # Unrecoverable stall or no mechanic: terminate and fail
            with self._lock:
                if task_id in self._active_tasks:
                    execution.cancelled = True
                    del self._active_tasks[task_id]

            logger.error(
                "Task %s exceeded timeout limit of %.1fs (elapsed: %.1fs). Terminating.",
                task_id,
                self.timeout_seconds,
                execution.elapsed_seconds,
            )

            # Cancel future if present
            if execution.future and hasattr(execution.future, "cancel") and not execution.future.done():
                execution.future.cancel()

            # Forcibly terminate runaway process
            if execution.process:
                try:
                    if execution.process.poll() is None:
                        execution.process.terminate()
                        execution.process.wait(timeout=2.0)
                except Exception as term_err:
                    logger.warning("Error terminating process for task %s: %s", task_id, term_err)

                try:
                    if execution.process.poll() is None:
                        execution.process.kill()
                        execution.process.wait(timeout=1.0)
                except Exception as kill_err:
                    logger.warning("Error killing process for task %s: %s", task_id, kill_err)

            # Fail the task in the queue
            timeout_msg = f"Task execution exceeded timeout limit of {self.timeout_seconds}s"
            try:
                self.queue.fail_task(
                    task_id=task_id,
                    error_details={"error": timeout_msg, "timeout": True},
                    allow_retry=False,
                )
            except Exception as e:
                logger.error("Failed to mark timed out task %s failed in queue: %s", task_id, e)

            # Route to CI Healing
            try:
                self.route_failed_task(task_id, reason=timeout_msg)
            except Exception as e:
                logger.error("Failed to route timed out task %s to CI healing: %s", task_id, e)

            timed_out_ids.append(task_id)

        return timed_out_ids

    # -------------------------------------------------------------------------
    # Task Completion & Routing (Senior Review & CI Healing)
    # -------------------------------------------------------------------------
    def route_completed_task(self, task_or_id: str | dict[str, Any]) -> dict[str, Any]:
        """
        Routes a successfully completed task to Senior Review and CI Healing.
        """
        task_id = task_or_id if isinstance(task_or_id, str) else task_or_id["id"]
        task_dict = (
            task_or_id
            if isinstance(task_or_id, dict)
            else self.queue.get_task(task_id) or {"id": task_id}
        )

        results: dict[str, Any] = {
            "task_id": task_id,
            "senior_review": None,
            "ci_healing": None,
        }

        # 1. Route to Senior Review
        engine = self.senior_review_engine or SeniorReviewEngine(queue=self.queue)
        try:
            logger.info("Routing completed task %s to Senior Review Engine", task_id)
            verdict = engine.execute_senior_review(task_id)
            results["senior_review"] = verdict.to_dict() if hasattr(verdict, "to_dict") else verdict
        except Exception as e:
            logger.warning("Senior review execution for completed task %s: %s", task_id, e)
            results["senior_review"] = {"error": str(e), "approved": False}

        # 2. Route to CI Healing
        healing_daemon = self._get_healing_daemon()
        try:
            logger.info("Routing completed task %s to CI Healing Daemon", task_id)
            healing_daemon.process_completed_task(task_dict)
            results["ci_healing"] = {"status": "processed"}
        except Exception as e:
            logger.warning("CI healing processing for completed task %s: %s", task_id, e)
            results["ci_healing"] = {"error": str(e)}

        return results

    def route_failed_task(
        self, task_or_id: str | dict[str, Any], reason: str | None = None
    ) -> dict[str, Any]:
        """
        Routes a failed task to CI Healing for failure analysis and repair synthesis.
        """
        task_id = task_or_id if isinstance(task_or_id, str) else task_or_id["id"]
        task_dict = (
            dict(task_or_id)
            if isinstance(task_or_id, dict)
            else self.queue.get_task(task_id) or {"id": task_id}
        )

        # Ensure worktree_path is present if resolvable from worktree_mgr
        if not task_dict.get("worktree_path") and self.worktree_mgr:
            try:
                wt = self.worktree_mgr.get_worktree_path(task_id)
                if wt.exists():
                    task_dict["worktree_path"] = str(wt)
            except Exception:
                pass

        results: dict[str, Any] = {
            "task_id": task_id,
            "ci_healing": None,
            "reason": reason,
        }

        healing_daemon = self._get_healing_daemon()
        try:
            logger.info("Routing failed task %s to CI Healing Daemon", task_id)
            healing_res = healing_daemon.process_failed_task(task_dict)
            ci_status: dict[str, Any] = {"status": "processed"}
            if isinstance(healing_res, dict):
                ci_status["result"] = healing_res
            results["ci_healing"] = ci_status
        except Exception as e:
            logger.warning("CI healing processing for failed task %s: %s", task_id, e)
            results["ci_healing"] = {"error": str(e)}

        return results

    def process_pending_heals(self) -> list[dict[str, Any]]:
        """
        Queries TaskTriageQueue for FAILED tasks and processes them through CI healing.
        Returns list of healing results.
        """
        if self.queue.is_emergency_stopped():
            return []

        results: list[dict[str, Any]] = []
        try:
            failed_tasks = self.queue.list_tasks(
                status=TriageStatus.FAILED, limit=50, project_id=self.project_id
            )
            for task in failed_tasks:
                try:
                    route_res = self.route_failed_task(task)
                    res = route_res.get("ci_healing", {}).get("result") or route_res
                    results.append({"task_id": task.get("id"), "result": res})
                except Exception as e:
                    logger.error("Failed healing processing for task %s: %s", task.get("id"), e)
        except Exception as e:
            logger.error("Failed querying failed tasks for healing: %s", e)
        return results

    # -------------------------------------------------------------------------
    # Execution Lifecycle (Reaping & Dispatch Cycle)
    # -------------------------------------------------------------------------
    def reap_completed_tasks(self) -> dict[str, list[str]]:
        """
        Inspects running worker processes, harvests finished executions, and routes them.
        """
        completed_ids: list[str] = []
        failed_ids: list[str] = []
        finished_tasks: list[tuple[str, ActiveTaskExecution, Any, str | None]] = []

        with self._lock:
            for task_id, execution in list(self._active_tasks.items()):
                is_done = False
                if execution.process and execution.process.poll() is not None:
                    is_done = True
                elif execution.future and execution.future.done():
                    is_done = True

                if is_done:
                    res: Any = None
                    err: str | None = None

                    if execution.result_queue is not None:
                        try:
                            if not execution.result_queue.empty():
                                msg = execution.result_queue.get_nowait()
                                if msg.get("success"):
                                    res = msg.get("result")
                                else:
                                    err = msg.get("error")
                        except Exception as q_err:
                            logger.warning(
                                "Error reading result queue for task %s: %s",
                                task_id,
                                q_err,
                            )

                    if execution.process:
                        exit_code = execution.process.poll()
                        if exit_code not in (0, None) and not err:
                            err = f"Worker process exited with code {exit_code}"

                    if execution.future and execution.future.done() and not err and not res:
                        try:
                            res = execution.future.result()
                        except Exception as f_err:
                            err = str(f_err)

                    finished_tasks.append((task_id, execution, res, err))
                    del self._active_tasks[task_id]

        for task_id, execution, _res, err in finished_tasks:
            if execution.process:
                try:
                    execution.process.wait(timeout=0.5)
                except Exception:
                    pass

            if err:
                logger.error("Task %s completed with error: %s", task_id, err)
                try:
                    self.queue.fail_task(
                        task_id=task_id,
                        error_details={"error": err},
                        allow_retry=False,
                    )
                except Exception:
                    pass
                failed_ids.append(task_id)
                self.route_failed_task(task_id, reason=err)
            else:
                task_row = self.queue.get_task(task_id)
                status = task_row.get("status") if task_row else None
                if status == TriageStatus.FAILED.value:
                    logger.warning("Task %s status is FAILED. Routing to CI healing.", task_id)
                    failed_ids.append(task_id)
                    self.route_failed_task(task_row or task_id)
                else:
                    logger.info("Task %s completed successfully. Routing.", task_id)
                    completed_ids.append(task_id)
                    self.route_completed_task(task_row or task_id)

        return {"completed": completed_ids, "failed": failed_ids}

    def dispatch_batch(self) -> list[str]:
        """
        Dispatches as many approved tasks as available concurrency slots permit.
        Returns list of newly dispatched task IDs.
        """
        if self.queue.is_emergency_stopped():
            logger.warning("Emergency stop is active. No tasks dispatched.")
            return []

        # 1. Harvest completed/failed tasks
        self.reap_completed_tasks()

        # 2. Check and enforce timeouts
        self.handle_timeouts()

        # 3. Fill available concurrency slots
        dispatched: list[str] = []
        slots = self.available_slots()
        while slots > 0:
            task_id = self.lease_and_dispatch_next()
            if not task_id:
                break
            dispatched.append(task_id)
            slots = self.available_slots()

        return dispatched

    def run_once(self) -> dict[str, Any]:
        """
        Executes a single cycle of timeout checks, reaping, and dispatching.
        Returns summary dictionary.
        """
        timed_out = self.handle_timeouts()
        reaped = self.reap_completed_tasks()
        dispatched = self.dispatch_batch()

        return {
            "active_count": self.active_count(),
            "available_slots": self.available_slots(),
            "timed_out": timed_out,
            "reaped_completed": reaped["completed"],
            "reaped_failed": reaped["failed"],
            "dispatched": dispatched,
        }

    def run_continuously(self, interval: float | None = None, max_cycles: int | None = None) -> None:
        """
        Runs the ParallelWorkerDispatcher daemon loop until stopped or max_cycles reached.
        """
        sleep_sec = interval if interval is not None else self.poll_interval
        logger.info("Starting ParallelWorkerDispatcher continuous daemon (max_workers=%d)", self.max_workers)

        def handle_signal(signum: int, frame: Any) -> None:
            logger.info("Signal %d received. Gracefully stopping daemon...", signum)
            self._shutdown = True

        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

        cycle_count = 0
        while not self._shutdown:
            try:
                self.run_once()
            except Exception as e:
                logger.error("Error in daemon cycle: %s", e)

            cycle_count += 1
            if max_cycles is not None and cycle_count >= max_cycles:
                logger.info("Reached maximum requested cycles (%d). Stopping.", max_cycles)
                break

            if not self._shutdown:
                time.sleep(sleep_sec)

        self.stop()
        logger.info("ParallelWorkerDispatcher daemon stopped.")

    def stop(self, wait: bool = True) -> None:
        """
        Stops the daemon and terminates all running worker processes.
        """
        self._shutdown = True
        with self._lock:
            active = list(self._active_tasks.values())
            self._active_tasks.clear()

        for execution in active:
            if execution.future and hasattr(execution.future, "cancel") and not execution.future.done():
                execution.future.cancel()

            if execution.process and execution.process.poll() is None:
                try:
                    execution.process.terminate()
                    if wait:
                        execution.process.wait(timeout=2.0)
                except Exception:
                    pass

                try:
                    if execution.process.poll() is None:
                        execution.process.kill()
                        if wait:
                            execution.process.wait(timeout=1.0)
                except Exception:
                    pass


def main() -> int:
    """CLI entrypoint for running parallel dispatcher or worker cycles."""
    parser = argparse.ArgumentParser(description="AlphaBrain Parallel Worker Dispatcher")
    subparsers = parser.add_subparsers(dest="command")

    p_worker = subparsers.add_parser("worker-cycle", help="Execute single worker cycle")
    p_worker.add_argument("--task-id", required=True, help="Task ID to execute")
    p_worker.add_argument("--db-path", required=True, help="SQLite database path")
    p_worker.add_argument("--emergency-lock", help="Emergency lock file path")

    args = parser.parse_args()
    if args.command == "worker-cycle":
        queue = TaskTriageQueue(db_path=args.db_path, emergency_lock_path=args.emergency_lock)
        task = queue.get_task(args.task_id)
        if not task:
            print(f"Task {args.task_id} not found", file=sys.stderr)
            return 1
        dispatcher = TriageTaskDispatcher(queue=queue)
        proposal = dispatcher.execute_task(task)
        if proposal and proposal.gates_passed:
            return 0
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
