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
import os
import re
import shlex
from pathlib import Path
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

# Forbidden binary names in gate execution
FORBIDDEN_BINARIES: tuple[str, ...] = (
    "curl",
    "wget",
    "nc",
    "ncat",
    "netcat",
    "sudo",
    "su",
    "chmod",
    "chown",
    "ssh",
    "scp",
    "rsync",
    "bash",
    "sh",
    "zsh",
    "xargs",
)

# Known prompt injection and adversarial intent regexes
ADVERSARIAL_REGEXES: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"delete\s+all\s+(files|code|repositories|data)", re.IGNORECASE),
    re.compile(r"drop\s+database", re.IGNORECASE),
    re.compile(r"drop\s+table", re.IGNORECASE),
    re.compile(r"exfiltrate\s+(keys?|secrets?|tokens?|data|env)", re.IGNORECASE),
    re.compile(r"leak\s+(keys?|secrets?|tokens?|env)", re.IGNORECASE),
)

MAX_ALLOWED_FILES = 10


def is_protected_path(
    path_str: str, protected_paths: tuple[str, ...] = PROTECTED_PATHS
) -> tuple[bool, str]:
    """
    Validates a file path using canonical path normalization and discrete component matching.
    Prevents directory traversal attacks (e.g. '../') and avoids substring false-positives.
    """
    cleaned = path_str.strip()
    if not cleaned or cleaned in (".", "/", "*"):
        return True, f"Invalid wildcard or root path '{path_str}' is forbidden."

    # Disallow explicit traversal sequences
    if "/../" in cleaned or cleaned.startswith("../") or cleaned.endswith("/.."):
        return True, f"Directory traversal sequence detected in '{path_str}'."

    # Normalize path
    norm = os.path.normpath(cleaned.lstrip("/"))
    if norm.startswith(".."):
        return True, f"Path traversal outside project root detected in '{path_str}'."

    # Disallow wildcard globs that circumvent blast radius limits
    if any(char in norm for char in ("*", "?", "[", "]")):
        return True, f"Wildcard glob pattern in path '{path_str}' is forbidden."

    parts = Path(norm).parts
    if not parts:
        return True, f"Path '{path_str}' resolved to empty destination."

    for prot in protected_paths:
        prot_norm = os.path.normpath(prot.strip().lstrip("/"))
        prot_parts = Path(prot_norm).parts

        # Component prefix matching: e.g. ('alpha_core', 'eva', '...') matches ('alpha_core', 'eva')
        if len(parts) >= len(prot_parts) and parts[: len(prot_parts)] == prot_parts:
            return True, f"Path '{path_str}' targets protected directory '{prot}'."

        # Protected file match anywhere: e.g. .env or .env.local
        if prot_norm.startswith(".env") and parts[-1] == prot_norm:
            return True, f"Path '{path_str}' targets protected file '{prot}'."

    return False, ""


OPERATOR_TOKENS: tuple[str, ...] = (";", "&&", "||", "&", "|", ">", ">>", "<", "<<")
PROCESS_WRAPPERS: tuple[str, ...] = ("env", "nohup", "time", "nice")
RECURSIVE_FLAG_PATTERN: re.Pattern[str] = re.compile(r"^-[a-zA-Z]*[rR][a-zA-Z]*$")


def is_forbidden_command(cmd_str: str) -> tuple[bool, str]:
    """
    Tokenizes and inspects a command string for unauthorized network binaries,
    privilege escalation, shell control chaining, or dangerous destructive operations.
    Uses quote-aware lexing (shlex punctuation_chars=True) to avoid false-positives
    on quoted semicolons, redirect characters, or backticks.
    """
    try:
        lexer = shlex.shlex(cmd_str, posix=True, punctuation_chars=True)
        tokens = list(lexer)
    except Exception as e:
        return True, f"Malformed command failed shell parsing: '{cmd_str}' ({e})"

    if not tokens:
        return False, ""

    # 1. Check for unquoted backtick or $( command substitution in token sequence
    for i, tok in enumerate(tokens):
        if tok == "`":
            return (
                True,
                f"Unquoted backtick command substitution is forbidden in gate command: '{cmd_str}'",
            )
        if tok == "$" and i + 1 < len(tokens) and tokens[i + 1] == "(":
            return (
                True,
                f"Unquoted '$()' command substitution is forbidden in gate command: '{cmd_str}'",
            )

    # 2. Reject unquoted shell control and redirection operators
    for tok in tokens:
        if tok in OPERATOR_TOKENS:
            return True, f"Shell control operator '{tok}' is forbidden in gate command: '{cmd_str}'"

    # 3. Contextual command execution extraction
    expect_command = True
    in_rm_command = False
    active_wrapper: str | None = None

    for tok in tokens:
        if expect_command:
            if active_wrapper == "env":
                # env skips options (starts with -) and variable assignments (contains =)
                if tok.startswith("-") or "=" in tok:
                    continue
            elif active_wrapper in ("time", "nohup", "nice"):
                if tok.startswith("-"):
                    continue
            else:
                if tok.startswith("-"):
                    continue

            base_exe = Path(tok).name.lower()
            if base_exe in FORBIDDEN_BINARIES:
                return True, f"Forbidden binary '{base_exe}' detected in gate command: '{cmd_str}'"

            if base_exe == "rm":
                in_rm_command = True
                expect_command = False
                active_wrapper = None
            elif base_exe in PROCESS_WRAPPERS:
                active_wrapper = base_exe
                expect_command = True
            else:
                in_rm_command = False
                expect_command = False
                active_wrapper = None
        else:
            if in_rm_command:
                if RECURSIVE_FLAG_PATTERN.match(tok) or tok in ("--recursive", "--recursive=true"):
                    return (
                        True,
                        f"Destructive recursive removal flag '{tok}' detected in gate command: '{cmd_str}'",
                    )

    # 4. Check for raw reverse socket patterns
    cmd_lower = cmd_str.lower()
    if "bash -i" in cmd_lower or "/dev/tcp" in cmd_lower or "python -c 'import socket" in cmd_lower:
        return True, f"Reverse shell pattern detected in gate command: '{cmd_str}'"

    return False, ""


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

        # 1. Extract fields defensively with None-safe guards
        commands: list[str] = []
        text_blobs_to_scan: list[str] = []

        if isinstance(envelope, TaskEnvelope):
            objective = envelope.objective or ""
            allowed_paths = envelope.allowed_paths or []
            detailed_instructions = envelope.detailed_instructions or ""
            text_blobs_to_scan.extend([objective, detailed_instructions])

            acceptance_plan = envelope.acceptance_plan
            if acceptance_plan and hasattr(acceptance_plan, "commands"):
                for cmd_obj in acceptance_plan.commands:
                    cmd_tokens = [
                        getattr(cmd_obj, "executable", ""),
                        *getattr(cmd_obj, "args", []),
                    ]
                    commands.append(shlex.join(cmd_tokens).strip())
        else:
            obj_val = envelope.get("objective")
            objective = str(obj_val) if obj_val is not None else ""
            allowed_paths = envelope.get("allowed_paths") or []
            inst_val = envelope.get("detailed_instructions")
            detailed_instructions = str(inst_val) if inst_val is not None else ""
            text_blobs_to_scan.extend([objective, detailed_instructions])

            plan = envelope.get("acceptance_plan") or {}
            if isinstance(plan, dict):
                for cmd_obj in plan.get("commands", []):
                    if isinstance(cmd_obj, dict):
                        cmd_tokens = [
                            cmd_obj.get("executable", ""),
                            *cmd_obj.get("args", []),
                        ]
                        commands.append(shlex.join(cmd_tokens).strip())
                    elif isinstance(cmd_obj, str):
                        commands.append(cmd_obj.strip())

        # Check 1: Blast Radius (Max files)
        if len(allowed_paths) > self.max_allowed_files:
            violations.append(
                f"Blast radius violation: Task requests {len(allowed_paths)} files, "
                f"exceeding max allowed limit of {self.max_allowed_files}."
            )

        # Check 2: Protected Paths & Traversal
        for path in allowed_paths:
            is_blocked, reason = is_protected_path(path, self.protected_paths)
            if is_blocked:
                violations.append(f"Protected path violation: {reason}")

        # Check 3: Forbidden Command Patterns in Acceptance Gates
        for cmd in commands:
            is_forbidden, cmd_reason = is_forbidden_command(cmd)
            if is_forbidden:
                violations.append(cmd_reason)

        # Check 4: Deep Adversarial Intent & Prompt Injection Scan
        for text in text_blobs_to_scan:
            for adv_regex in ADVERSARIAL_REGEXES:
                match = adv_regex.search(text)
                if match:
                    violations.append(
                        f"Adversarial pattern violation: Matched suspicious pattern '{adv_regex.pattern}' "
                        f"in text excerpt: '{match.group(0)}'."
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
