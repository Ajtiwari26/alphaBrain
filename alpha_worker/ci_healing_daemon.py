import json
import logging
import os
import subprocess
from typing import Any

from alpha_core.healing.circuit_breaker import CircuitBreaker, TripReason
from alpha_core.healing.failure_analyzer import FailureAnalyzer
from alpha_core.healing.repair_synthesizer import RepairEnvelopeSynthesizer
from alpha_core.queue.triage_queue import TaskTriageQueue, TriageStatus

logger = logging.getLogger("alphabrain.worker.healing_daemon")


class CIHealingDaemon:
    def __init__(self, queue: TaskTriageQueue, project_id: str = "prj_phase10"):
        self.queue = queue
        self.project_id = project_id
        self.failure_analyzer = FailureAnalyzer()
        self.circuit_breakers: dict[str, CircuitBreaker] = {}

    def get_circuit_breaker(self, task_id: str) -> CircuitBreaker:
        if task_id not in self.circuit_breakers:
            self.circuit_breakers[task_id] = CircuitBreaker()
        return self.circuit_breakers[task_id]

    def process_completed_task(self, task: dict[str, Any]) -> None:
        task_id = task["task_id"]
        logger.info(f"Processing completed task: {task_id}")

        # 1. Automated Senior Review
        # Using subprocess to run the triage_cli senior-review command, or we could use the Engine directly.
        # Since we have SeniorReviewEngine, let's use subprocess to keep it isolated as CLI is standard.
        env = os.environ.copy()

        try:
            logger.info(f"Running senior review for {task_id}")
            result = subprocess.run(
                ["python", "-m", "alpha_core.triage_cli", "senior-review", task_id, "--json"],
                capture_output=True,
                text=True,
                env=env,
                check=False
            )

            if result.returncode != 0:
                logger.error(f"Senior review failed for {task_id}: {result.stderr}")
                # If senior review fails, it either sets the task back or leaves it. We'll let it be.
                return

            try:
                review_data = json.loads(result.stdout)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse senior review output: {result.stdout}")
                return

            if not review_data.get("approved", False):
                logger.info(f"Task {task_id} not approved by senior review. Repair required.")
                # We could transition to failed, but senior-review CLI should handle it.
                return

            logger.info(f"Task {task_id} approved. Executing auto-merge.")

            # 2. Auto-merge
            merge_result = subprocess.run(
                ["python", "-m", "alpha_core.triage_cli", "merge", task_id, "--json"],
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
        task_id = task["task_id"]
        logger.info(f"Processing failed task: {task_id}")

        # Assuming the worker saves pytest/ruff output somewhere, or we pull from task result.
        # Let's extract from the task's failure evidence.
        # For simplicity, if we don't have the files, we'll use empty strings.
        # The daemon would look at the task's worktree.
        worktree_dir = task.get("payload", {}).get("worktree", "")
        if not worktree_dir or not os.path.exists(worktree_dir):
            logger.warning(f"No valid worktree found for failed task {task_id}")
            return

        # We simulate reading pytest_output.txt and ruff_output.txt from the worktree's evidence dir
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

        # 3. Failure diagnosis via FailureAnalyzer
        analysis = self.failure_analyzer.analyze(pytest_output, ruff_output)
        signature = analysis.get("signature", "unknown")
        logger.info(f"Analyzed failure for {task_id}. Signature: {signature}")

        # 4. Circuit breaker checks
        cb = self.get_circuit_breaker(task_id)
        trip_reason = cb.record_failure(signature)

        if trip_reason == TripReason.ESCALATED_HUMAN_REVIEW:
            logger.warning(f"Circuit breaker tripped for {task_id}. Escalating to human review.")
            self.queue.update_status(task_id, TriageStatus.PENDING_REVIEW)
            return

        # 5. Repair synthesis
        epoch = cb.attempts
        synthesizer = RepairEnvelopeSynthesizer(parent_task_id=task_id, repair_epoch=epoch)
        original_paths = task.get("payload", {}).get("allowed_paths", [])

        repair_envelope = synthesizer.synthesize(
            original_paths=original_paths,
            failures=analysis,
            project_id=self.project_id,
            worktree=worktree_dir
        )

        logger.info(f"Synthesized repair envelope for {task_id}: {repair_envelope}")

        # Create a new repair task or update the existing one.
        # For this daemon, we'll just log it or add it to the queue.
        # We will enqueue a repair task with the synthesized envelope.
        repair_task_id = f"{task_id}_repair_{epoch}"
        self.queue.submit_task(
            task_id=repair_task_id,
            payload={
                "project_id": self.project_id,
                "worktree": worktree_dir,
                "allowed_paths": repair_envelope["allowed_paths"],
                "instruction": repair_envelope["actionable_prompt"],
                "parent_task_id": task_id,
                "repair_epoch": epoch
            }
        )
        logger.info(f"Submitted repair task {repair_task_id} for {task_id}")

        # Mark original as handled (e.g. pending_review or archive it)
        # We'll set it to PENDING_REVIEW to get it out of the failed queue for the daemon
        self.queue.update_status(task_id, TriageStatus.PENDING_REVIEW)

    def run_once(self) -> None:
        if self.queue.is_emergency_stopped():
            logger.warning("Emergency stop is active. Healing daemon suspended.")
            return

        completed_tasks = self.queue.list_tasks(status=TriageStatus.COMPLETED)
        for task in completed_tasks:
            self.process_completed_task(task)

        failed_tasks = self.queue.list_tasks(status=TriageStatus.FAILED)
        for task in failed_tasks:
            self.process_failed_task(task)

