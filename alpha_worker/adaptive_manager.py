"""
alpha_worker/adaptive_manager.py
Adaptive Hardware Concurrency Manager & Gemini 3.1 Pro-Powered Pipeline Mechanic.

Features:
1. AdaptiveConcurrencyManager: Dynamic power- (AC vs Battery) and queue-aware worker
   scaling with thermal pressure throttling.
2. PipelineMechanic: Gemini 3.1 Pro-powered diagnosis of stuck or halted workers with
   surgical checkpoint-based resumption to eliminate full restarts on recoverable stalls.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Any

from alpha_core.queue.triage_queue import TaskTriageQueue
from alpha_worker.health import HardwareHealthChecker

logger = logging.getLogger("alphabrain.worker.adaptive_manager")


# =============================================================================
# 1. Adaptive Hardware Concurrency Manager
# =============================================================================


@dataclasses.dataclass(frozen=True)
class ConcurrencyProfile:
    """Configuration limits for dynamic concurrency scaling."""

    ac_max_workers: int = 4
    ac_min_workers: int = 1
    battery_max_workers: int = 2
    battery_min_workers: int = 1
    critical_battery_threshold: int = 20
    queue_scale_step: int = 2  # Tasks per extra worker slot


@dataclasses.dataclass
class ConcurrencyDecision:
    """Result of adaptive concurrency calculation."""

    target_workers: int
    is_ac_power: bool
    battery_percentage: int
    thermal_state: str
    queue_depth: int
    reason: str


class AdaptiveConcurrencyManager:
    """
    Dynamically scales worker concurrency based on:
    1. Power source: AC line power allows full scale; Battery clamps concurrency.
    2. Battery charge: Critical battery (<20%) scales to 0 or 1 (draining).
    3. Thermal pressure / system load: Throttles concurrency under heavy/critical heat.
    4. Queue load: Dynamically expands workers as pending tasks accumulate.
    """

    def __init__(
        self,
        profile: ConcurrencyProfile | None = None,
        health_checker: type[HardwareHealthChecker] | None = None,
    ) -> None:
        self.profile = profile or ConcurrencyProfile()
        self.health_checker = health_checker or HardwareHealthChecker

    def compute_concurrency(
        self,
        queue_depth: int,
        is_ac_power: bool | None = None,
        battery_percentage: int | None = None,
        thermal_state: str | None = None,
    ) -> ConcurrencyDecision:
        """
        Calculates optimal concurrency based on current hardware telemetry and queue depth.
        """
        if is_ac_power is None or battery_percentage is None:
            hw_ac, hw_batt = self.health_checker.get_battery_and_power()
            if is_ac_power is None:
                is_ac_power = hw_ac
            if battery_percentage is None:
                battery_percentage = hw_batt

        if thermal_state is None:
            thermal_state = self.health_checker.check_thermal_and_load()

        queue_depth = max(0, queue_depth)

        # 1. Handle thermal emergency
        if thermal_state == "critical":
            return ConcurrencyDecision(
                target_workers=0,
                is_ac_power=is_ac_power,
                battery_percentage=battery_percentage,
                thermal_state=thermal_state,
                queue_depth=queue_depth,
                reason="Thermal state critical: all worker dispatches paused",
            )

        if thermal_state == "heavy":
            target = 1 if queue_depth > 0 else 0
            return ConcurrencyDecision(
                target_workers=target,
                is_ac_power=is_ac_power,
                battery_percentage=battery_percentage,
                thermal_state=thermal_state,
                queue_depth=queue_depth,
                reason="Thermal pressure heavy: concurrency throttled to 1 worker",
            )

        # 2. Handle Battery mode constraints
        if not is_ac_power:
            if battery_percentage < self.profile.critical_battery_threshold:
                target = 1 if queue_depth > 0 else 0
                return ConcurrencyDecision(
                    target_workers=target,
                    is_ac_power=is_ac_power,
                    battery_percentage=battery_percentage,
                    thermal_state=thermal_state,
                    queue_depth=queue_depth,
                    reason=f"Battery critical ({battery_percentage}% < {self.profile.critical_battery_threshold}%): throttled to minimum",
                )

            # Normal battery operation: bounded by battery_max_workers
            if queue_depth == 0:
                target = self.profile.battery_min_workers
            else:
                additional = queue_depth // self.profile.queue_scale_step
                target = min(
                    self.profile.battery_max_workers,
                    self.profile.battery_min_workers + additional,
                )

            # Moderate thermal throttling on battery
            if thermal_state == "moderate":
                target = max(self.profile.battery_min_workers, target - 1)

            return ConcurrencyDecision(
                target_workers=target,
                is_ac_power=is_ac_power,
                battery_percentage=battery_percentage,
                thermal_state=thermal_state,
                queue_depth=queue_depth,
                reason=f"Battery mode ({battery_percentage}%): scaled between {self.profile.battery_min_workers} and {self.profile.battery_max_workers}",
            )

        # 3. AC Power mode
        if queue_depth == 0:
            target = self.profile.ac_min_workers
            reason = "AC power, idle queue: scaled to minimum worker capacity"
        else:
            additional = queue_depth // self.profile.queue_scale_step
            target = min(
                self.profile.ac_max_workers,
                self.profile.ac_min_workers + additional,
            )
            reason = f"AC power, active queue ({queue_depth} pending): scaled up to {target} workers"

        # Moderate thermal adjustment on AC
        if thermal_state == "moderate":
            target = max(self.profile.ac_min_workers, target - 1)
            reason += " (throttled 1 slot for moderate thermal load)"

        return ConcurrencyDecision(
            target_workers=target,
            is_ac_power=is_ac_power,
            battery_percentage=battery_percentage,
            thermal_state=thermal_state,
            queue_depth=queue_depth,
            reason=reason,
        )


# =============================================================================
# 2. Gemini 3.1 Pro-Powered Pipeline Mechanic
# =============================================================================


class MechanicAction(str, Enum):
    RESUME_CHECKPOINT = "RESUME_CHECKPOINT"  # Recoverable: restore checkpoint and resume
    RETRY_STEP = "RETRY_STEP"  # Recoverable: re-execute stuck step in place
    EXTEND_LEASE = "EXTEND_LEASE"  # Worker is making slow but active progress
    TERMINATE = "TERMINATE"  # Unrecoverable stall: abort and route to CI healing


@dataclasses.dataclass
class MechanicDiagnosis:
    """Structured diagnosis emitted by Pipeline Mechanic."""

    is_recoverable: bool
    action: MechanicAction
    reason: str
    checkpoint_phase: str | None = None
    suggested_fix: str = ""
    raw_response: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class TaskStallSnapshot:
    """Snapshot of a stalled task execution state."""

    task_id: str
    elapsed_seconds: float
    timeout_seconds: float
    process_alive: bool
    last_phase: str = "init"
    worktree_path: Path | str | None = None
    checkpoint_file: Path | str | None = None
    envelope: dict[str, Any] = dataclasses.field(default_factory=dict)
    stdout_tail: str = ""
    stderr_tail: str = ""


class PipelineMechanic:
    """
    Gemini 3.1 Pro-powered Pipeline Mechanic.
    Inspects stuck or stalled worker tasks, diagnoses the cause of the halt, and
    prescribes and executes surgical checkpoints/resumptions without full restarts.
    """

    DEFAULT_MODEL = "gemini-3.1-pro-high"

    def __init__(
        self,
        queue: TaskTriageQueue | None = None,
        model: str = DEFAULT_MODEL,
        agy_bin: Path | None = None,
        llm_invoker: Callable[[str, str], dict[str, Any]] | None = None,
    ) -> None:
        self.queue = queue
        self.model = model
        self.agy_bin = agy_bin or Path(shutil.which("agy") or "/usr/local/bin/agy")
        self.llm_invoker = llm_invoker

    @staticmethod
    def save_checkpoint(
        checkpoint_dir: Path | str,
        task_id: str,
        phase: str,
        state_data: dict[str, Any],
    ) -> Path:
        """Saves task execution checkpoint to preserve progress."""
        cp_dir = Path(checkpoint_dir)
        cp_dir.mkdir(parents=True, exist_ok=True)
        cp_file = cp_dir / f"checkpoint_{task_id}.json"
        payload = {
            "task_id": task_id,
            "phase": phase,
            "timestamp": time.time(),
            "state_data": state_data,
        }
        with open(cp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return cp_file

    @staticmethod
    def load_checkpoint(checkpoint_dir: Path | str, task_id: str) -> dict[str, Any] | None:
        """Loads the most recent checkpoint for a task."""
        cp_file = Path(checkpoint_dir) / f"checkpoint_{task_id}.json"
        if not cp_file.exists():
            return None
        try:
            with open(cp_file, encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else None
        except Exception as e:
            logger.warning("Failed to load checkpoint for %s: %s", task_id, e)
            return None

    def diagnose_stall(self, snapshot: TaskStallSnapshot) -> MechanicDiagnosis:
        """
        Uses Gemini 3.1 Pro to diagnose whether a stalled task can be surgically resumed.
        """
        prompt = self._construct_prompt(snapshot)
        raw_result = self._call_gemini(prompt, snapshot)
        return self._parse_diagnosis(raw_result, snapshot)

    def _construct_prompt(self, snapshot: TaskStallSnapshot) -> str:
        """Generates structured diagnostic prompt for Gemini 3.1 Pro."""
        out_tail = snapshot.stdout_tail[-1500:] if snapshot.stdout_tail else "(data empty)"
        err_tail = snapshot.stderr_tail[-1500:] if snapshot.stderr_tail else "(data empty)"

        return f"""You are the AlphaBrain Gemini 3.1 Pro Pipeline Mechanic.
A worker executing task '{snapshot.task_id}' has halted or exceeded its execution window.
Analyze the snapshot below and prescribe a surgical intervention.

TASK EXECUTION SNAPSHOT:
- Task ID: {snapshot.task_id}
- Elapsed Time: {snapshot.elapsed_seconds:.1f}s (Timeout limit: {snapshot.timeout_seconds:.1f}s)
- Worker Process Alive: {snapshot.process_alive}
- Last Recorded Phase: {snapshot.last_phase}
- Worktree Path: {snapshot.worktree_path}
- Checkpoint Available: {snapshot.checkpoint_file is not None}
- Stdout Tail:
{out_tail}
- Stderr Tail:
{err_tail}

CRITERIA:
1. RECOVERABLE STALL:
   - If worktree has a saved checkpoint, git working files exist, or worker hung on a transient lock/network call/test runner.
   - Action: 'RESUME_CHECKPOINT' or 'RETRY_STEP' or 'EXTEND_LEASE'.
   - Goal: ZERO full restarts on recoverable stall. Preserve worktree changes.
2. UNRECOVERABLE STALL:
   - Fatal unhandled exception, syntax corruption, or irrecoverable OOM with no checkpoint.
   - Action: 'TERMINATE'.

Respond with a single valid JSON object strictly matching this schema:
{{
  "is_recoverable": true,
  "action": "RESUME_CHECKPOINT",
  "reason": "Brief explanation of the diagnostic finding",
  "checkpoint_phase": "{snapshot.last_phase}",
  "suggested_fix": "Surgical action to keep pipeline flowing without full restart"
}}
"""

    def _call_gemini(self, prompt: str, snapshot: TaskStallSnapshot) -> dict[str, Any]:
        """Calls Gemini 3.1 Pro via custom invoker, AGY CLI, or deterministic rule engine."""
        if self.llm_invoker is not None:
            try:
                return self.llm_invoker(self.model, prompt)
            except Exception as e:
                logger.warning("Custom LLM invoker failed: %s; falling back", e)

        if self.agy_bin.exists():
            try:
                with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
                    f.write(prompt)
                    prompt_file = f.name

                cmd = [
                    str(self.agy_bin),
                    "--model",
                    self.model,
                    "--mode",
                    "plan",
                    "--output-format",
                    "json",
                    "--input-format",
                    "text",
                    "--print-timeout",
                    "60s",
                ]
                with open(prompt_file) as pf:
                    res = subprocess.run(
                        cmd,
                        stdin=pf,
                        capture_output=True,
                        text=True,
                        timeout=70,
                        check=False,
                    )
                Path(prompt_file).unlink(missing_ok=True)
                if res.returncode == 0 and res.stdout.strip():
                    parsed = self._extract_json(res.stdout)
                    if parsed:
                        return parsed
            except Exception as e:
                logger.warning("AGY CLI execution failed for mechanic: %s", e)

        return self._deterministic_fallback_diagnosis(snapshot)

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        """Extracts JSON dict from LLM response string."""
        text = text.strip()
        try:
            val = json.loads(text)
            if isinstance(val, dict):
                return val
        except Exception:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                val = json.loads(text[start : end + 1])
                if isinstance(val, dict):
                    return val
            except Exception:
                pass
        return {}

    def _deterministic_fallback_diagnosis(
        self, snapshot: TaskStallSnapshot
    ) -> dict[str, Any]:
        """
        Deterministic diagnostic rules when external Gemini endpoint is unreachable.
        Adheres strictly to the invariant: zero full restarts on recoverable stall.
        """
        has_checkpoint = bool(snapshot.checkpoint_file)
        has_worktree = bool(snapshot.worktree_path)

        stderr_lower = snapshot.stderr_tail.lower()
        if "syntaxerror" in stderr_lower or "fatal: corrupted" in stderr_lower:
            return {
                "is_recoverable": False,
                "action": MechanicAction.TERMINATE.value,
                "reason": "Corrupted state or unrecoverable syntax crash",
                "checkpoint_phase": None,
                "suggested_fix": "Terminate and route to CI healing",
            }

        if has_checkpoint or has_worktree:
            return {
                "is_recoverable": True,
                "action": MechanicAction.RESUME_CHECKPOINT.value,
                "reason": f"Active worktree/checkpoint detected at phase '{snapshot.last_phase}'. Surgical resumption viable.",
                "checkpoint_phase": snapshot.last_phase,
                "suggested_fix": "Preserve worktree artifacts and resume from last phase checkpoint",
            }

        if snapshot.process_alive:
            return {
                "is_recoverable": True,
                "action": MechanicAction.EXTEND_LEASE.value,
                "reason": "Worker process is active; extending execution lease.",
                "checkpoint_phase": snapshot.last_phase,
                "suggested_fix": "Extend task lease for worker completion",
            }

        return {
            "is_recoverable": False,
            "action": MechanicAction.TERMINATE.value,
            "reason": "No valid worktree state or checkpoint to resume from.",
            "checkpoint_phase": None,
            "suggested_fix": "Abort execution and trigger CI healing",
        }

    def _parse_diagnosis(
        self, raw: dict[str, Any], snapshot: TaskStallSnapshot
    ) -> MechanicDiagnosis:
        """Parses model response into a strongly typed MechanicDiagnosis."""
        is_rec = bool(raw.get("is_recoverable", True))
        action_str = str(raw.get("action", MechanicAction.RESUME_CHECKPOINT.value)).upper()
        try:
            action = MechanicAction(action_str)
        except ValueError:
            action = MechanicAction.RESUME_CHECKPOINT if is_rec else MechanicAction.TERMINATE

        reason = str(raw.get("reason", "Stall evaluated by Gemini 3.1 Pro Mechanic"))
        phase = raw.get("checkpoint_phase") or snapshot.last_phase
        suggested_fix = str(raw.get("suggested_fix", ""))

        return MechanicDiagnosis(
            is_recoverable=is_rec,
            action=action,
            reason=reason,
            checkpoint_phase=phase,
            suggested_fix=suggested_fix,
            raw_response=raw,
        )

    def execute_surgical_resumption(
        self,
        snapshot: TaskStallSnapshot,
        diagnosis: MechanicDiagnosis,
        resume_callback: Callable[[str, str, dict[str, Any]], bool] | None = None,
    ) -> bool:
        """
        Executes surgical resumption without full restart:
        1. Preserves worktree state.
        2. Refreshes task lease in queue with updated checkpoint envelope.
        3. Invokes resume_callback or updates triage queue status.
        """
        if not diagnosis.is_recoverable:
            logger.info("Task %s diagnosed unrecoverable. Skipping resumption.", snapshot.task_id)
            return False

        logger.info(
            "Executing surgical resumption for task %s: action=%s, phase=%s",
            snapshot.task_id,
            diagnosis.action.value,
            diagnosis.checkpoint_phase,
        )

        if self.queue is not None:
            try:
                task = self.queue.get_task(snapshot.task_id)
                if task:
                    envelope = dict(task.get("envelope", {}))
                    mechanic_history = list(envelope.get("mechanic_interventions", []))
                    mechanic_history.append(
                        {
                            "timestamp": time.time(),
                            "action": diagnosis.action.value,
                            "phase": diagnosis.checkpoint_phase,
                            "reason": diagnosis.reason,
                            "zero_restart": True,
                        }
                    )
                    envelope["mechanic_interventions"] = mechanic_history
                    envelope["last_checkpoint_phase"] = diagnosis.checkpoint_phase
                    if hasattr(self.queue, "modify_task"):
                        self.queue.modify_task(snapshot.task_id, new_envelope=envelope)
                    elif hasattr(self.queue, "update_task_envelope"):
                        self.queue.update_task_envelope(snapshot.task_id, envelope)
            except Exception as e:
                logger.warning("Failed updating queue envelope during surgical resumption: %s", e)

        if resume_callback is not None:
            try:
                return resume_callback(
                    snapshot.task_id,
                    diagnosis.checkpoint_phase or "init",
                    snapshot.envelope,
                )
            except Exception as cb_err:
                logger.error("Resume callback failed for task %s: %s", snapshot.task_id, cb_err)
                return False

        return True
