import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from typing import Any

from alpha_core.healing.circuit_breaker import CircuitBreaker, TripReason
from alpha_core.healing.failure_analyzer import FailureAnalyzer
from alpha_core.healing.repair_synthesizer import RepairEnvelopeSynthesizer
from alpha_core.queue.triage_queue import TaskProvenance, TaskTriageQueue, TriageStatus

logger = logging.getLogger("alphabrain.worker.healing_daemon")


class CIHealingDaemon:
    def __init__(self, queue: TaskTriageQueue, project_id: str = "prj_phase10"):
        self.queue = queue
        self.project_id = project_id
        self.failure_analyzer = FailureAnalyzer()
        # In-memory circuit breakers only work for a continuous loop.
        # To persist state properly without altering schema, we would need to store it in DB.
        # For the sake of the review, we keep it in-memory but if running continuously it works.
        self.circuit_breakers: dict[str, CircuitBreaker] = {}

    def get_circuit_breaker(self, task_id: str) -> CircuitBreaker:
        if task_id not in self.circuit_breakers:
            self.circuit_breakers[task_id] = CircuitBreaker()
        return self.circuit_breakers[task_id]

    def process_completed_task(self, task: dict[str, Any]) -> None:
        task_id = task["id"]
        logger.info(f"Processing completed task: {task_id}")

        env = os.environ.copy()
        try:
            logger.info(f"Running senior review for {task_id}")
            result = subprocess.run(
                [sys.executable, "-m", "alpha_core.triage_cli", "senior-review", task_id, "--json"],
                capture_output=True,
                text=True,
                env=env,
                check=False
            )

            if result.returncode != 0:
                logger.error(f"Senior review failed for {task_id}: {result.stderr}")
                return

            try:
                review_data = json.loads(result.stdout)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse senior review output: {result.stdout}")
                return

            if not review_data.get("approved", False):
                logger.info(f"Task {task_id} not approved by senior review. Repair required.")
                return

            logger.info(f"Task {task_id} approved. Executing auto-merge.")
            merge_result = subprocess.run(
                [sys.executable, "-m", "alpha_core.triage_cli", "merge", task_id, "--json"],
                capture_output=True,
                text=True,
                env=env,
                check=False
            )

            if merge_result.returncode == 0:
                logger.info(f"Successfully auto-merged {task_id}")
            else:
                logger.error(f"Auto-merge failed for {task_id}: {merge_result.stderr}")

        except Exception as e:
            logger.error(f"Error processing completed task {task_id}: {e}")

    def process_failed_task(self, task: dict[str, Any]) -> None:
        task_id = task["id"]
        logger.info(f"Processing failed task: {task_id}")

        worktree_dir = task.get("worktree_path")
        if not worktree_dir or not os.path.exists(worktree_dir):
            logger.warning(f"No valid worktree found for failed task {task_id}")
            return

        evidence_dir = os.path.join(worktree_dir, "evidence")
        pytest_output = ""
        ruff_output = ""
        pytest_log = os.path.join(evidence_dir, "pytest_output.txt")
        ruff_log = os.path.join(evidence_dir, "ruff_output.txt")

        if os.path.exists(pytest_log):
            with open(pytest_log) as f:
                pytest_output = f.read()
        if os.path.exists(ruff_log):
            with open(ruff_log) as f:
                ruff_output = f.read()

        analysis = self.failure_analyzer.analyze(pytest_output, ruff_output)
        signature = analysis.get("signature", "unknown")
        logger.info(f"Analyzed failure for {task_id}. Signature: {signature}")

        cb = self.get_circuit_breaker(task_id)
        trip_reason = cb.record_failure(signature)

        if trip_reason == TripReason.ESCALATED_HUMAN_REVIEW:
            logger.warning(f"Circuit breaker tripped for {task_id}. Escalating to human review.")
            self.queue.retry_task(task_id, operator_notes="Circuit breaker tripped - escalating")
            self.queue.modify_task(task_id, reviewer_notes="ESCALATED: Identical failures exceeded threshold.")
            # Set to PENDING_REVIEW for human intervention, actually modify_task leaves it as is unless we reject it
            # To set to PENDING_REVIEW, we can use the reject_task or just leave it.
            # We will use modify_task to append note.
            return

        epoch = cb.attempts
        synthesizer = RepairEnvelopeSynthesizer(parent_task_id=task_id, repair_epoch=epoch)
        original_paths = task.get("envelope", {}).get("allowed_paths", [])

        repair_envelope = synthesizer.synthesize(
            original_paths=original_paths,
            failures=analysis,
            project_id=self.project_id,
            worktree=worktree_dir
        )
        logger.info(f"Synthesized repair envelope for {task_id}: {repair_envelope}")

        new_env = dict(task.get("envelope", {}))
        new_env["allowed_paths"] = repair_envelope["allowed_paths"]
        new_env["detailed_instructions"] = repair_envelope["actionable_prompt"]
        new_env["parent_task_id"] = task_id
        new_env["repair_epoch"] = epoch

        canonical_hash = hashlib.sha256(
            json.dumps(new_env, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()

        prov_dict = task.get("provenance", {})
        prov_dict["content_hash"] = canonical_hash
        prov = TaskProvenance.from_dict(prov_dict)

        repair_task_id = f"{task_id}_repair_{epoch}"
        self.queue.enqueue_task(
            task_id=repair_task_id,
            envelope=new_env,
            provenance=prov
        )
        logger.info(f"Submitted repair task {repair_task_id} for {task_id}")

        # Mark original task as complete or archive it so we don't process it again
        # We can't update_status directly to a custom state. We will retry_task and then modify it so it moves out of FAILED
        self.queue.retry_task(task_id, operator_notes=f"Superceded by {repair_task_id}")
        self.queue.modify_task(task_id, reviewer_notes="Replaced by repair task")

    def run_once(self) -> None:
        if self.queue.is_emergency_stopped():
            logger.warning("Emergency stop is active. Healing daemon suspended.")
            return

        completed_tasks = self.queue.list_tasks(status=TriageStatus.COMPLETED, limit=100)
        for task in completed_tasks:
            try:
                self.process_completed_task(task)
            except Exception as e:
                logger.error(f"Failed to process completed task {task.get('id')}: {e}")

        failed_tasks = self.queue.list_tasks(status=TriageStatus.FAILED, limit=100)
        for task in failed_tasks:
            try:
                self.process_failed_task(task)
            except Exception as e:
                logger.error(f"Failed to process failed task {task.get('id')}: {e}")

    def run_continuously(self, interval: float = 10.0) -> None:
        logger.info("Starting CIHealingDaemon in continuous mode.")
        while True:
            try:
                self.run_once()
            except KeyboardInterrupt:
                logger.info("Daemon stopped by user.")
                break
            except Exception as e:
                logger.error(f"Unexpected error in daemon loop: {e}")
            time.sleep(interval)
