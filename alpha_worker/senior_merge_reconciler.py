"""
alpha_worker/senior_merge_reconciler.py
Autonomous Senior Merge & Fast-Forward Reconciliation Engine.

Consumes SeniorReviewVerdict from senior_review_engine, validates git ancestry,
performs ff-only merge, runs post-merge gate, and transitions queue state.
"""
from __future__ import annotations

import enum
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from alpha_core.queue.triage_queue import TaskTriageQueue
from alpha_worker.senior_review_engine import SeniorReviewVerdict

logger = logging.getLogger("alphabrain.worker.senior_merge_reconciler")


class MergeState(str, enum.Enum):
    """State machine for the merge reconciliation lifecycle."""
    PENDING = "pending"               # Verdict received, not yet processed
    VALIDATING_ANCESTRY = "validating_ancestry"  # Checking base commit ancestry
    ANCESTRY_VALID = "ancestry_valid"  # Base commit is ancestor of main
    MERGING = "merging"               # git merge --ff-only in progress
    MERGE_COMPLETE = "merge_complete"  # Merge succeeded
    RUNNING_GATE = "running_gate"     # Post-merge acceptance gate running
    GATE_PASSED = "gate_passed"       # Post-merge gate passed
    GATE_FAILED = "gate_failed"       # Post-merge gate failed → rollback
    ROLLING_BACK = "rolling_back"     # Rolling back failed merge
    ROLLED_BACK = "rolled_back"       # Rollback complete
    COMPLETED = "completed"           # Queue state updated, done
    FAILED = "failed"                 # Unrecoverable failure


class MergeError(Exception):
    """Base exception for merge reconciliation errors."""
    pass


class AncestryViolationError(MergeError):
    """Raised when the task branch is not a descendant of main."""
    def __init__(self, task_branch: str, main_head: str):
        self.task_branch = task_branch
        self.main_head = main_head
        super().__init__(
            f"Ancestry violation: main HEAD {main_head} is not an ancestor of "
            f"task branch {task_branch}. Cannot fast-forward."
        )


class FastForwardError(MergeError):
    """Raised when git merge --ff-only fails."""
    def __init__(self, task_branch: str, stderr: str):
        self.task_branch = task_branch
        self.stderr = stderr
        super().__init__(f"Fast-forward merge failed for {task_branch}: {stderr}")


class PostMergeGateError(MergeError):
    """Raised when the post-merge acceptance gate fails."""
    def __init__(self, gate_command: str, exit_code: int, output: str):
        self.gate_command = gate_command
        self.exit_code = exit_code
        self.output = output
        super().__init__(
            f"Post-merge gate '{gate_command}' failed with exit code {exit_code}"
        )


class RollbackError(MergeError):
    """Raised when rollback after failed gate also fails."""
    def __init__(self, original_error: str, rollback_error: str):
        self.original_error = original_error
        self.rollback_error = rollback_error
        super().__init__(
            f"CRITICAL: Rollback failed. Original: {original_error}. "
            f"Rollback: {rollback_error}"
        )


@dataclass
class MergeReceipt:
    """Immutable receipt of a completed merge reconciliation."""
    task_id: str
    state: MergeState
    pre_merge_main_head: str
    post_merge_main_head: str | None
    task_branch_head: str
    verdict_approved: bool
    merge_timestamp: float
    gate_command: str | None
    gate_exit_code: int | None
    gate_output: str | None
    rollback_performed: bool = False
    error_message: str | None = None
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "state": self.state.value,
            "pre_merge_main_head": self.pre_merge_main_head,
            "post_merge_main_head": self.post_merge_main_head,
            "task_branch_head": self.task_branch_head,
            "verdict_approved": self.verdict_approved,
            "merge_timestamp": self.merge_timestamp,
            "gate_command": self.gate_command,
            "gate_exit_code": self.gate_exit_code,
            "gate_output": self.gate_output,
            "rollback_performed": self.rollback_performed,
            "error_message": self.error_message,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class MergeReconcilerConfig:
    """Configuration for the merge reconciler."""
    repo_path: Path = field(default_factory=lambda: Path.cwd())
    main_branch: str = "main"
    post_merge_gate_command: str | None = "ruff check ."
    gate_timeout_seconds: float = 120.0
    dry_run: bool = False


class SeniorMergeReconciler:
    """Autonomous reconciler that takes an approved SeniorReviewVerdict,
    validates base commit ancestry, fast-forwards the task branch into main,
    runs post-merge acceptance gate, and marks TaskTriageQueue state.

    State Machine:
        PENDING → VALIDATING_ANCESTRY → ANCESTRY_VALID → MERGING →
        MERGE_COMPLETE → RUNNING_GATE → GATE_PASSED → COMPLETED
                                                    ↓
                                              GATE_FAILED → ROLLING_BACK → ROLLED_BACK → FAILED
    """

    def __init__(self, config: MergeReconcilerConfig | None = None):
        self.config = config or MergeReconcilerConfig()
        self._state = MergeState.PENDING
        self._pre_merge_head: str | None = None

    @property
    def state(self) -> MergeState:
        return self._state

    def reconcile(
        self,
        verdict: SeniorReviewVerdict,
        task_branch: str,
        queue: TaskTriageQueue | None = None,
    ) -> MergeReceipt:
        """Execute the full merge reconciliation pipeline.

        Args:
            verdict: The approved SeniorReviewVerdict.
            task_branch: The git branch name containing the task's changes.
            queue: Optional TaskTriageQueue to update status on completion.

        Returns:
            MergeReceipt with full audit trail.

        Raises:
            MergeError: If verdict is not approved.
            AncestryViolationError: If ancestry check fails.
            FastForwardError: If ff-only merge fails.
            RollbackError: If rollback after gate failure also fails.
        """
        start_time = time.time()
        self._state = MergeState.PENDING

        self._validate_verdict(verdict)

        self._pre_merge_head = self._get_head(self.config.main_branch)
        task_branch_head = self._get_head(task_branch)

        gate_exit_code: int | None = None
        gate_output: str | None = None
        post_merge_head: str | None = None
        rollback_performed = False
        error_message: str | None = None

        try:
            self._validate_ancestry(task_branch)

            if not self.config.dry_run:
                post_merge_head = self._fast_forward_merge(task_branch)

                gate_exit_code, gate_output = self._run_post_merge_gate()
                if gate_exit_code != 0:
                    self._state = MergeState.GATE_FAILED
                    self._rollback(self._pre_merge_head)
                    rollback_performed = True
                    self._state = MergeState.FAILED
                    error_message = f"Gate failed with code {gate_exit_code}: {gate_output}"
                    post_merge_head = self._get_head(self.config.main_branch)
                else:
                    self._state = MergeState.GATE_PASSED
                    if queue:
                        self._update_queue_status(queue, verdict.task_id, "completed")
                    self._state = MergeState.COMPLETED
            else:
                # Dry run skips merge, but updates state
                self._state = MergeState.COMPLETED
        except Exception as e:
            error_message = str(e)
            if self._state == MergeState.MERGE_COMPLETE or self._state == MergeState.RUNNING_GATE:
                if not rollback_performed:
                     try:
                         self._rollback(self._pre_merge_head)
                         rollback_performed = True
                         self._state = MergeState.FAILED
                         post_merge_head = self._get_head(self.config.main_branch)
                     except Exception as re:
                         # Ensure we log the rollback failure and re-raise if it was unexpected
                         if not isinstance(re, RollbackError):
                             raise RollbackError(str(e), str(re)) from re
                         raise
            if isinstance(e, (AncestryViolationError, FastForwardError, MergeError)):
                raise
            raise MergeError(f"Unexpected error during reconcile: {e}") from e

        return MergeReceipt(
            task_id=verdict.task_id,
            state=self._state,
            pre_merge_main_head=self._pre_merge_head,
            post_merge_main_head=post_merge_head,
            task_branch_head=task_branch_head,
            verdict_approved=verdict.approved,
            merge_timestamp=time.time(),
            gate_command=self.config.post_merge_gate_command if not self.config.dry_run else None,
            gate_exit_code=gate_exit_code,
            gate_output=gate_output,
            rollback_performed=rollback_performed,
            error_message=error_message,
            duration_seconds=time.time() - start_time,
        )

    def _validate_verdict(self, verdict: SeniorReviewVerdict) -> None:
        """Ensure verdict.approved is True. Raise MergeError if not."""
        if not verdict.approved:
            raise MergeError(f"Verdict for task {verdict.task_id} is not approved.")

    def _get_head(self, branch: str) -> str:
        """Get the HEAD commit SHA of a branch."""
        try:
            result = self._git(self.config.repo_path, ["rev-parse", branch])
            if result.returncode != 0:
                raise MergeError(f"Failed to get HEAD for branch {branch}: {result.stderr}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired as e:
            raise MergeError(f"Timeout getting HEAD for branch {branch}") from e

    def _validate_ancestry(self, task_branch: str) -> None:
        """Validate that main HEAD is an ancestor of the task branch HEAD.
        Uses: git merge-base --is-ancestor <main_head> <task_branch_head>
        """
        self._state = MergeState.VALIDATING_ANCESTRY
        task_head = self._get_head(task_branch)
        main_head = self._pre_merge_head
        if main_head is None:
            raise MergeError("main HEAD not resolved.")

        try:
            result = self._git(
                self.config.repo_path,
                ["merge-base", "--is-ancestor", main_head, task_head],
            )
            if result.returncode != 0:
                raise AncestryViolationError(task_branch, main_head)
            self._state = MergeState.ANCESTRY_VALID
        except subprocess.TimeoutExpired as e:
            raise MergeError(f"Timeout checking ancestry for {task_branch}") from e

    def _fast_forward_merge(self, task_branch: str) -> str:
        """Perform git merge --ff-only <task_branch> on main.
        Returns the new HEAD commit SHA after merge.
        """
        try:
            # Checkout main
            checkout_result = self._git(self.config.repo_path, ["checkout", self.config.main_branch])
            if checkout_result.returncode != 0:
                raise MergeError(f"Failed to checkout {self.config.main_branch}: {checkout_result.stderr}")

            self._state = MergeState.MERGING
            # Merge
            merge_result = self._git(self.config.repo_path, ["merge", "--ff-only", task_branch])
            if merge_result.returncode != 0:
                raise FastForwardError(task_branch, merge_result.stderr)

            self._state = MergeState.MERGE_COMPLETE
            return self._get_head(self.config.main_branch)
        except subprocess.TimeoutExpired as e:
            raise MergeError(f"Timeout performing fast-forward merge for {task_branch}") from e

    def _run_post_merge_gate(self) -> tuple[int, str]:
        """Run the configured post-merge gate command.
        Returns (exit_code, combined_output).
        """
        if self.config.post_merge_gate_command is None:
            return 0, "gate skipped"

        self._state = MergeState.RUNNING_GATE
        try:
            # We use subprocess directly here to support shell execution if needed
            # But the requirement says to run via subprocess.
            # Usually gate commands are better run with shell=True if they are complex strings.
            result = subprocess.run(
                self.config.post_merge_gate_command,
                cwd=self.config.repo_path,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.config.gate_timeout_seconds
            )
            output = result.stdout + result.stderr
            return result.returncode, output.strip()
        except subprocess.TimeoutExpired as e:
             # Timeout is a failure
             raise MergeError(f"Post-merge gate command timed out after {self.config.gate_timeout_seconds} seconds") from e
        except Exception as e:
            return 1, str(e)

    def _rollback(self, pre_merge_head: str) -> None:
        """Reset main to pre_merge_head via git reset --hard."""
        self._state = MergeState.ROLLING_BACK
        try:
            result = self._git(self.config.repo_path, ["reset", "--hard", pre_merge_head])
            if result.returncode != 0:
                raise RollbackError("Post merge gate failed", result.stderr)
            self._state = MergeState.ROLLED_BACK
        except subprocess.TimeoutExpired as e:
            raise RollbackError("Post merge gate failed", "git reset --hard timed out") from e

    def _update_queue_status(
        self,
        queue: TaskTriageQueue,
        task_id: str,
        status: str,
    ) -> None:
        """Update the task's status in the triage queue."""
        try:
            if hasattr(queue, 'complete_task'):
                queue.complete_task(task_id)
            else:
                logger.warning(f"Queue object has no complete_task method for {task_id}")
        except Exception as e:
            logger.warning(f"Failed to update queue status for {task_id}: {e}")

    @staticmethod
    def _git(repo: Path, args: list[str], timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
        """Execute a git command in the given repo directory."""
        return subprocess.run(
            ["git", *args],
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout
        )
