"""
alpha_core/safety/gate.py
Deterministic and semantic safety gate for AlphaBrain Phase 9.

Authoritative Reference:
docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md (Section 6 - P9 Constitution)
Laws:
- Law 1: No Direct Path (Mandatory Intermediary)
- Law 2: Blast Radius Containment (Max 10 files, 500 lines)
- Law 3: Protected Paths (Immutable boundaries)
"""

from __future__ import annotations

import dataclasses
import logging
import re
from typing import Any

from alpha_core.queue.triage_queue import TaskTriageQueue, TriageStatus
from alpha_protocol.task import TaskEnvelope

logger = logging.getLogger("alphabrain.safety.gate")

# Immutable paths that automated tasks must NEVER modify
PROTECTED_PATHS: tuple[str, ...] = (
    ".git",
    "alpha_meet",  # Strictly immutable per Senior Directive
    "alpha_core/eva",  # Eva cannot modify herself
    "alpha_core/safety",  # Safety Gate cannot be bypassed
    "config/secrets",
    ".env",
    ".env.local",
    "Library/LaunchAgents",
    "docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md",
)

# Forbidden execution patterns in gate commands
FORBIDDEN_COMMAND_PATTERNS: tuple[str, ...] = (
    "rm -rf",
    "sudo ",
    "chmod ",
    "chown ",
    "curl ",
    "wget ",
    "nc ",
    "ncat ",
    "bash -i",
    "/dev/tcp",
    "python -c 'import socket",
)

# Known prompt injection and adversarial intent regexes
ADVERSARIAL_REGEXES: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"delete\s+all\s+(files|code|repositories)", re.IGNORECASE),
    re.compile(r"drop\s+database", re.IGNORECASE),
    re.compile(r"drop\s+table", re.IGNORECASE),
    re.compile(r"exfiltrate\s+(keys?|secrets?|tokens?)", re.IGNORECASE),
    re.compile(r"leak\s+(keys?|secrets?|tokens?)", re.IGNORECASE),
)

MAX_ALLOWED_FILES = 10


@dataclasses.dataclass(frozen=True)
class SafetyVerdict:
    passed: bool
    verdict: str  # "PASS" | "REJECT" | "ESCALATE"
    reason: str
    violations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class SafetyGate:
    """
    Deterministic rules engine verifying task envelopes against the P9 Constitution.
    """

    def __init__(
        self,
        protected_paths: tuple[str, ...] = PROTECTED_PATHS,
        max_allowed_files: int = MAX_ALLOWED_FILES,
    ) -> None:
        self.protected_paths = protected_paths
        self.max_allowed_files = max_allowed_files

    def evaluate_envelope(self, envelope: TaskEnvelope | dict[str, Any]) -> SafetyVerdict:
        """
        Runs deterministic Stage 1 safety checks against the TaskEnvelope.
        """
        violations: list[str] = []

        # Convert dict to access fields consistently
        commands: list[str] = []
        if isinstance(envelope, TaskEnvelope):
            objective = envelope.objective
            allowed_paths = envelope.allowed_paths
            acceptance_plan = envelope.acceptance_plan
            if acceptance_plan and hasattr(acceptance_plan, "commands"):
                for cmd_obj in acceptance_plan.commands:
                    cmd_str = f"{getattr(cmd_obj, 'executable', '')} {' '.join(getattr(cmd_obj, 'args', []))}"
                    commands.append(cmd_str)
        else:
            objective = str(envelope.get("objective", ""))
            allowed_paths = envelope.get("allowed_paths", [])
            plan = envelope.get("acceptance_plan", {})
            if isinstance(plan, dict):
                for cmd_obj in plan.get("commands", []):
                    if isinstance(cmd_obj, dict):
                        cmd_str = (
                            f"{cmd_obj.get('executable', '')} {' '.join(cmd_obj.get('args', []))}"
                        )
                        commands.append(cmd_str)
                    elif isinstance(cmd_obj, str):
                        commands.append(cmd_obj)

        # Check 1: Blast Radius (Max files)
        if len(allowed_paths) > self.max_allowed_files:
            violations.append(
                f"Blast radius violation: Task requests {len(allowed_paths)} files, "
                f"exceeding max allowed limit of {self.max_allowed_files}."
            )

        # Check 2: Protected Paths
        for path in allowed_paths:
            clean_path = path.strip().lstrip("/")
            for protected in self.protected_paths:
                if (
                    clean_path == protected
                    or clean_path.startswith(f"{protected}/")
                    or protected in clean_path
                ):
                    violations.append(f"Protected path violation: Path '{path}' is immutable.")
                    break

        # Check 3: Forbidden Command Patterns in Acceptance Gates
        for cmd in commands:
            for pattern in FORBIDDEN_COMMAND_PATTERNS:
                if pattern in cmd:
                    violations.append(
                        f"Forbidden command violation: Command '{cmd}' contains '{pattern}'."
                    )

        # Check 4: Adversarial Intent & Prompt Injection
        for adv_regex in ADVERSARIAL_REGEXES:
            if adv_regex.search(objective):
                violations.append(
                    f"Adversarial pattern violation: Objective matched suspicious pattern '{adv_regex.pattern}'."
                )
                break

        if violations:
            logger.warning("Safety gate REJECTED envelope: %s", violations)
            return SafetyVerdict(
                passed=False,
                verdict="REJECT",
                reason="; ".join(violations),
                violations=violations,
            )

        logger.info("Safety gate PASSED envelope for objective: %s", objective[:60])
        return SafetyVerdict(
            passed=True,
            verdict="PASS",
            reason="Passed all deterministic P9 Constitution checks",
            violations=[],
        )

    def review_task(self, task_id: str, queue: TaskTriageQueue) -> SafetyVerdict:
        """
        Reviews a specific task in the queue and atomically transitions it to APPROVED or REJECTED.
        """
        task = queue.get_task(task_id)
        if not task:
            return SafetyVerdict(
                passed=False,
                verdict="REJECT",
                reason=f"Task {task_id} not found in triage queue",
                violations=["Task not found"],
            )

        envelope = task["envelope"]
        verdict = self.evaluate_envelope(envelope)

        if verdict.passed:
            queue.approve_task(
                task_id=task_id,
                safety_verdict=verdict.verdict,
                safety_reason=verdict.reason,
            )
        else:
            queue.reject_task(
                task_id=task_id,
                reason=verdict.reason,
            )

        return verdict

    def sweep_and_review_pending(
        self,
        queue: TaskTriageQueue,
        max_batch_size: int = 20,
    ) -> list[tuple[str, SafetyVerdict]]:
        """
        Sweeps the queue for PENDING_REVIEW tasks and evaluates each in batch.
        """
        pending_tasks = queue.list_tasks(status=TriageStatus.PENDING_REVIEW, limit=max_batch_size)
        results: list[tuple[str, SafetyVerdict]] = []

        for t in pending_tasks:
            task_id = t["id"]
            verdict = self.review_task(task_id, queue)
            results.append((task_id, verdict))

        return results
