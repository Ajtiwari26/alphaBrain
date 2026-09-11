import hashlib
import json
import logging
import os
import signal
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
    def __init__(
        self,
        queue: TaskTriageQueue,
        project_id: str = "prj_phase10",
        auto_approve_repairs: bool = False,
        repair_initial_status: TriageStatus | None = None,
    ):
        self.queue = queue
        self.project_id = project_id
        self.auto_approve_repairs = auto_approve_repairs
        self.repair_initial_status = repair_initial_status
        self.failure_analyzer = FailureAnalyzer()
        self._shutdown = False
        self._init_db()

    def _init_db(self) -> None:
        def _create(conn):
            conn.execute(
                "CREATE TABLE IF NOT EXISTS daemon_processed_tasks (task_id TEXT PRIMARY KEY, processed_at REAL NOT NULL);"
            )

        try:
            self.queue._execute_write_with_retry(_create, allow_during_emergency=True)
        except Exception as e:
            logger.warning(f"Failed to initialize daemon_processed_tasks: {e}")

    def is_task_processed(self, task_id: str) -> bool:
        from contextlib import closing

        try:
            with closing(self.queue._get_connection()) as conn:
                cursor = conn.execute(
                    "SELECT 1 FROM daemon_processed_tasks WHERE task_id = ?;", (task_id,)
                )
                return cursor.fetchone() is not None
        except Exception:
            return False

    def mark_task_processed(self, task_id: str) -> None:
        import time

        def _insert(conn):
            conn.execute(
                "INSERT OR IGNORE INTO daemon_processed_tasks (task_id, processed_at) VALUES (?, ?);",
                (task_id, time.time()),
            )

        try:
            self.queue._execute_write_with_retry(_insert, allow_during_emergency=True)
        except Exception as e:
            logger.warning(f"Failed to mark task processed {task_id}: {e}")

    def process_completed_task(self, task: dict[str, Any]) -> None:
        task_id = task["id"]
        if self.is_task_processed(task_id):
            return

        logger.info(f"Processing completed task: {task_id}")

        env = os.environ.copy()
        try:
            logger.info(f"Running senior review for {task_id}")
            result = subprocess.run(
                [sys.executable, "-m", "alpha_core.triage_cli", "senior-review", task_id, "--json"],
                capture_output=True,
                text=True,
                env=env,
                check=False,
                timeout=300,
            )

            if result.returncode != 0:
                logger.error(f"Senior review failed for {task_id}: {result.stderr}")
                # Do NOT add to processed_tasks so it remains eligible for retry
                return

            try:
                review_data = json.loads(result.stdout)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse senior review output: {result.stdout}")
                # Do NOT add to processed_tasks so it remains eligible for retry
                return

            if not review_data.get("approved", False):
                logger.info(f"Task {task_id} not approved by senior review. Repair required.")
                # Do NOT add to processed_tasks so repair cycles can continue
                return

            logger.info(f"Task {task_id} approved. Executing auto-merge.")
            merge_result = subprocess.run(
                [sys.executable, "-m", "alpha_core.triage_cli", "merge", task_id, "--json"],
                capture_output=True,
                text=True,
                env=env,
                check=False,
                timeout=300,
            )

            if merge_result.returncode == 0:
                logger.info(f"Successfully auto-merged {task_id}")
                root_id = task_id.split("_repair_")[0]
                CircuitBreaker.execute_transactionally(
                    self.queue, root_id, lambda cb: cb.record_success()
                )
                self.mark_task_processed(task_id)
            else:
                logger.error(f"Auto-merge failed for {task_id}: {merge_result.stderr}")
                # Do NOT add to processed_tasks so merge can be retried

        except Exception as e:
            logger.error(f"Error processing completed task {task_id}: {e}")

    def process_failed_task(self, task: dict[str, Any]) -> dict[str, Any]:
        task_id = task["id"]
        if self.is_task_processed(task_id):
            return {"status": "already_processed", "task_id": task_id}

        logger.info(f"Processing failed task: {task_id}")

        worktree_dir = task.get("worktree_path")
        if not worktree_dir or not os.path.exists(worktree_dir):
            logger.warning(f"No valid worktree found for failed task {task_id}")
            self.queue.reject_task(task_id, reason="No valid worktree found")
            return {"status": "rejected", "task_id": task_id, "reason": "No valid worktree found"}

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

        # Fallback: check task payload for evidence / error details
        if not pytest_output and not ruff_output:
            result_data = task.get("result") or task.get("error_details") or {}
            if isinstance(result_data, dict):
                evidence = result_data.get("evidence", [])
                if isinstance(evidence, list):
                    for ev in evidence:
                        if isinstance(ev, dict):
                            gate = ev.get("gate_type", "")
                            snippet = (ev.get("stdout_snippet") or "") + "\n" + (ev.get("stderr_snippet") or "")
                            if gate in ("unit_test", "pytest"):
                                pytest_output = snippet
                            elif gate in ("lint", "ruff"):
                                ruff_output = snippet
                if not pytest_output and not ruff_output and "error" in result_data:
                    pytest_output = str(result_data["error"])

        analysis = self.failure_analyzer.analyze(pytest_output, ruff_output)
        signature = analysis.get("signature", "unknown")
        logger.info(f"Analyzed failure for {task_id}. Signature: {signature}")

        root_id = task_id.split("_repair_")[0]
        trip_reason, cb = CircuitBreaker.execute_transactionally(
            self.queue, root_id, lambda _cb: _cb.record_failure(signature)
        )

        if trip_reason == TripReason.ESCALATED_HUMAN_REVIEW:
            logger.warning(f"Circuit breaker tripped for {task_id}. Escalating to human review.")
            self.queue.reject_task(
                task_id,
                reason="ESCALATED: Identical failures exceeded threshold. Needs human intervention.",
            )
            return {
                "status": "circuit_breaker_tripped",
                "task_id": task_id,
                "root_id": root_id,
                "signature": signature,
                "trip_reason": trip_reason.value if hasattr(trip_reason, "value") else str(trip_reason),
                "attempts": cb.attempts if cb else 0,
            }

        epoch = cb.attempts
        synthesizer = RepairEnvelopeSynthesizer(parent_task_id=task_id, repair_epoch=epoch)
        original_paths = task.get("envelope", {}).get("allowed_paths", [])

        repair_envelope = synthesizer.synthesize(
            original_paths=original_paths,
            failures=analysis,
            project_id=self.project_id,
            worktree=worktree_dir,
        )

        # S2: Validate synthesizer return
        if not all(k in repair_envelope for k in ("allowed_paths", "actionable_prompt")):
            logger.error("Synthesizer returned invalid envelope shape")
            self.queue.reject_task(task_id, reason="Synthesizer returned invalid envelope shape")
            return {
                "status": "rejected",
                "task_id": task_id,
                "reason": "Synthesizer returned invalid envelope shape",
            }

        logger.info(f"Synthesized repair envelope for {task_id}: {repair_envelope}")

        new_env = dict(task.get("envelope", {}))
        new_env["allowed_paths"] = repair_envelope["allowed_paths"]
        new_env["detailed_instructions"] = repair_envelope["actionable_prompt"]
        new_env["parent_task_id"] = task_id
        new_env["repair_epoch"] = epoch

        canonical_hash = hashlib.sha256(
            json.dumps(new_env, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()

        prov_raw = task.get("provenance") or {}
        if isinstance(prov_raw, TaskProvenance):
            prov_dict = prov_raw.to_dict()
        elif isinstance(prov_raw, dict):
            prov_dict = dict(prov_raw)
        else:
            prov_dict = {}

        prov_dict["content_hash"] = canonical_hash
        prov_dict.setdefault("meeting_id", "ci_healing")
        prov_dict.setdefault("speaker_id", "ci_healing_daemon")
        prov_dict.setdefault("utterance_timestamp", time.time())
        prov_dict.setdefault("transcript_excerpt", f"Automated repair for {task_id}")
        prov_dict.setdefault("extraction_model", "CIHealingDaemon")
        prov_dict.setdefault("extraction_confidence", 1.0)
        prov_dict.setdefault("eva_session_id", f"healing_{task_id}")
        prov_dict.setdefault("created_at", time.time())

        valid_prov_fields = {
            "meeting_id",
            "speaker_id",
            "utterance_timestamp",
            "transcript_excerpt",
            "extraction_model",
            "extraction_confidence",
            "eva_session_id",
            "created_at",
            "content_hash",
        }
        filtered_prov = {k: v for k, v in prov_dict.items() if k in valid_prov_fields}
        prov = TaskProvenance.from_dict(filtered_prov)

        repair_task_id = f"{task_id}_repair_{epoch}"

        initial_status = (
            self.repair_initial_status
            if self.repair_initial_status is not None
            else (TriageStatus.APPROVED if self.auto_approve_repairs else TriageStatus.PENDING_REVIEW)
        )

        # S1: Explicit initial_status
        self.queue.enqueue_task(
            task_id=repair_task_id,
            envelope=new_env,
            provenance=prov,
            initial_status=initial_status,
        )
        logger.info(f"Submitted repair task {repair_task_id} for {task_id}")

        # Supersede the old task safely to prevent re-execution
        self.queue.reject_task(task_id, reason=f"Superseded by {repair_task_id}")

        return {
            "status": "repair_enqueued",
            "task_id": task_id,
            "repair_task_id": repair_task_id,
            "epoch": epoch,
            "signature": signature,
            "initial_status": initial_status.value,
        }

    def run_once(self) -> None:
        if self.queue.is_emergency_stopped():
            logger.warning("Emergency stop is active. Healing daemon suspended.")
            return

        completed_tasks = self.queue.list_tasks(
            status=TriageStatus.COMPLETED, limit=100, project_id=self.project_id
        )
        for task in completed_tasks:
            try:
                self.process_completed_task(task)
            except Exception as e:
                logger.error(f"Failed to process completed task {task.get('id')}: {e}")

        failed_tasks = self.queue.list_tasks(
            status=TriageStatus.FAILED, limit=100, project_id=self.project_id
        )
        for task in failed_tasks:
            try:
                self.process_failed_task(task)
            except Exception as e:
                logger.error(f"Failed to process failed task {task.get('id')}: {e}")

    def run_continuously(self, interval: float = 10.0) -> None:
        logger.info("Starting CIHealingDaemon in continuous mode.")

        def handle_sigterm(signum, frame):
            logger.info("Received signal, shutting down daemon...")
            self._shutdown = True

        signal.signal(signal.SIGTERM, handle_sigterm)
        signal.signal(signal.SIGINT, handle_sigterm)

        while not self._shutdown:
            try:
                self.run_once()
            except Exception as e:
                logger.error(f"Unexpected error in daemon loop: {e}")

            if not self._shutdown:
                time.sleep(interval)

        logger.info("Daemon stopped gracefully.")
