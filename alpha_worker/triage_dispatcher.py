"""
alpha_worker/triage_dispatcher.py
Worker Dispatch & PR Generation Pipeline for Phase 9 Autonomous Closed-Loop.

Orchestrates:
1. Leasing APPROVED tasks from TaskTriageQueue (strictly ignoring PENDING_REVIEW).
2. Content hash integrity check before execution.
3. Isolated git worktree branch provisioning.
4. Acceptance gate verification (tests, lint) on the worktree.
5. Git commit creation and Pull Request proposal artifact generation.
6. Updating TaskTriageQueue state to COMPLETED or FAILED.

Authoritative Reference:
docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md (Section 6.5)
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import dataclasses
import hashlib
import json
import logging
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, cast

from alpha_core.config import settings
from alpha_core.queue.triage_queue import TaskTriageQueue
from alpha_protocol import AgentType, GateType, RiskClass, TaskEnvelope
from alpha_worker.adapters.antigravity import AntigravityAdapter
from alpha_worker.adapters.antigravity_live import AntigravityLiveBridge
from alpha_worker.worktree import WorktreeManager

logger = logging.getLogger("alpha_worker.triage_dispatcher")


@dataclasses.dataclass(frozen=True)
class PRProposal:
    """Represents a generated Pull Request proposal resulting from task execution."""

    task_id: str
    project_id: str
    branch_name: str
    base_commit: str
    head_commit: str
    title: str
    description: str
    files_changed: list[str]
    diff_stat: str
    gates_passed: bool
    evidence: list[dict[str, Any]]
    created_at: float
    attempt_id: str
    worker_id: str
    plan_digest: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class TriageTaskDispatcher:
    """
    Worker dispatch controller for polling and executing tasks from TaskTriageQueue.
    """

    def __init__(
        self,
        queue: TaskTriageQueue,
        worktree_mgr: WorktreeManager | None = None,
        default_base_commit: str | None = None,
        live_bridge: AntigravityLiveBridge | None = None,
        adapter: AntigravityAdapter | None = None,
        enable_agent_execution: bool | None = None,
    ) -> None:
        self.queue = queue
        self.worktree_mgr = worktree_mgr or WorktreeManager()
        self.default_base_commit = default_base_commit
        self.live_bridge = live_bridge or AntigravityLiveBridge()
        self.adapter = adapter or AntigravityAdapter()
        if enable_agent_execution is not None:
            self.enable_agent_execution = enable_agent_execution
        else:
            self.enable_agent_execution = (
                settings.ENV != "test"
            ) and settings.ANTIGRAVITY_EXECUTION_ENABLED

    def lease_task(self) -> dict[str, Any] | None:
        """
        Polls and atomically leases the oldest APPROVED task.
        Returns None if no approved tasks exist or emergency stop is active.
        """
        if self.queue.is_emergency_stopped():
            logger.warning("Emergency stop tombstone active. Worker leasing suspended.")
            return None

        leased = self.queue.lease_next_approved_task()
        return cast(dict[str, Any] | None, leased)

    def run_command_in_worktree(
        self,
        worktree_path: Path,
        cmd: list[str],
        timeout_seconds: int = 120,
    ) -> tuple[int, str, str]:
        """
        Executes a shell command safely inside the worktree directory without shell=True.
        """
        exec_cmd = list(cmd)
        if exec_cmd:
            venv_bin = Path(sys.executable).parent / exec_cmd[0]
            if venv_bin.exists():
                exec_cmd[0] = str(venv_bin)
            elif exec_cmd[0] == "python":
                exec_cmd[0] = sys.executable

        try:
            res = subprocess.run(
                exec_cmd,
                cwd=str(worktree_path),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            return res.returncode, res.stdout, res.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"Command timed out after {timeout_seconds} seconds"
        except Exception as e:
            return 1, "", f"Execution error: {e}"

    def run_acceptance_gates(
        self,
        worktree_path: Path,
        envelope: dict[str, Any],
    ) -> tuple[bool, list[dict[str, Any]]]:
        """
        Executes required acceptance plan commands in the worktree.
        Returns (all_passed, evidence_items).
        """
        plan = envelope.get("acceptance_plan", {})
        commands = plan.get("commands", [])
        required_gates = plan.get("required_gates", [])

        if not commands and required_gates:
            logger.error("No commands provided but required_gates exist.")
            return False, []

        all_passed = True
        evidence: list[dict[str, Any]] = []
        executed_gates = set()

        for c in commands:
            exe = c.get("executable")
            if not exe:
                continue
            args = c.get("args", [])
            full_cmd = [exe, *args]

            gate_type = c.get("gate_type")
            if not gate_type:
                logger.error("Gate missing explicit gate_type in command definition: %s", c)
                return False, evidence

            executed_gates.add(gate_type)

            returncode, stdout, stderr = self.run_command_in_worktree(worktree_path, full_cmd)
            passed = returncode == 0
            if not passed:
                all_passed = False

            evidence.append(
                {
                    "gate_type": gate_type,
                    "command": " ".join(full_cmd),
                    "passed": passed,
                    "returncode": returncode,
                    "stdout_snippet": stdout[:5000],
                    "stderr_snippet": stderr[:5000],
                    "timestamp": time.time(),
                }
            )

        for rg in required_gates:
            if rg not in executed_gates:
                logger.error("Required gate %s was not executed.", rg)
                return False, evidence

        return all_passed, evidence

    def get_git_diff_and_changed_files(
        self, worktree_path: Path, base_commit: str
    ) -> tuple[list[str], str]:
        """Inspects git diff relative to base_commit inside the worktree, including uncommitted changes."""
        # 1. Changed files (committed on branch relative to base)
        ret, out, _ = self.run_command_in_worktree(
            worktree_path, ["git", "diff", "--name-only", f"{base_commit}..HEAD"]
        )
        changed_files: list[str] = []
        if ret == 0 and out.strip():
            for line in out.strip().splitlines():
                changed_files.append(line.strip('"'))

        # Also include uncommitted changes in the worktree
        ret2, out2, _ = self.run_command_in_worktree(
            worktree_path, ["git", "status", "--porcelain", "-uall"]
        )
        if ret2 == 0 and out2.strip():
            for line in out2.strip().splitlines():
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2:
                    f = parts[1].strip('"')
                    if f not in changed_files:
                        changed_files.append(f)

        # 2. Diff stat
        _, stat_out, _ = self.run_command_in_worktree(
            worktree_path, ["git", "diff", "--stat", f"{base_commit}..HEAD"]
        )
        _, uncommitted_stat, _ = self.run_command_in_worktree(
            worktree_path, ["git", "diff", "--stat"]
        )

        full_stat = stat_out.strip()
        if uncommitted_stat.strip():
            full_stat += "\n" + uncommitted_stat.strip()

        return changed_files, full_stat

    def create_git_commit(
        self,
        worktree_path: Path,
        commit_message: str,
        author_name: str = "AlphaBrain Autonomous Worker",
        author_email: str = "worker@alphabrain.ai",
    ) -> str | None:
        """
        Stages all modified/added files and creates a git commit inside the worktree.
        Returns the new commit SHA on success, or None on failure.
        """
        # git add -A
        ret, _, err = self.run_command_in_worktree(worktree_path, ["git", "add", "-A"])
        if ret != 0:
            logger.error(f"git add failed: {err}")
            return None

        # Check if anything is staged
        ret, out, _ = self.run_command_in_worktree(
            worktree_path, ["git", "diff", "--cached", "--name-only"]
        )
        if ret == 0 and not out.strip():
            # No changes to commit
            logger.info("No modifications staged in worktree.")
            # Return current HEAD
            ret_head, head_out, _ = self.run_command_in_worktree(
                worktree_path, ["git", "rev-parse", "HEAD"]
            )
            return head_out.strip() if ret_head == 0 else None

        commit_cmd = [
            "git",
            "-c",
            f"user.name={author_name}",
            "-c",
            f"user.email={author_email}",
            "commit",
            "-m",
            commit_message,
        ]
        ret, _, err = self.run_command_in_worktree(worktree_path, commit_cmd)
        if ret != 0:
            logger.error(f"git commit failed: {err}")
            return None

        ret, out, _ = self.run_command_in_worktree(worktree_path, ["git", "rev-parse", "HEAD"])
        return out.strip() if ret == 0 else None

    def validate_acceptance_plan(self, plan: dict[str, Any]) -> str | None:
        """
        Validates the acceptance plan prior to execution.
        Returns an error string if validation fails, or None if valid.
        """
        if not plan:
            return None

        if not isinstance(plan, dict):
            return "Invalid acceptance plan format: must be a dictionary."

        commands = plan.get("commands", [])
        required_gates = plan.get("required_gates", [])

        if required_gates and not commands:
            return "Ambiguous empty plan: required_gates present but commands is empty."

        gate_types_seen = set()
        recognized_gates = {g.value for g in GateType}

        if not isinstance(commands, list):
            return "Invalid commands format: must be a list."

        for c in commands:
            if not isinstance(c, dict):
                return "Invalid command definition format: must be a dictionary."

            gate_type = c.get("gate_type")
            if not gate_type or gate_type not in recognized_gates:
                return f"Unknown or missing gate type: {gate_type}"

            if gate_type in gate_types_seen:
                return f"Duplicate command definition for gate_type: {gate_type}"
            gate_types_seen.add(gate_type)

            exe = c.get("executable")
            if not exe or not str(exe).strip():
                return f"Command missing executable for gate_type: {gate_type}"

        return None

    def execute_task(self, leased_task: dict[str, Any]) -> PRProposal | None:
        """
        Executes a single leased task through the full isolation and PR generation lifecycle.
        """
        task_id = leased_task["id"]
        envelope = leased_task["envelope"]
        provenance = leased_task.get("provenance", {})
        project_id = envelope.get("project_id", "default_proj")
        repo_path = envelope.get("repo", ".")
        base_commit = envelope.get("base_commit", self.default_base_commit)
        if not base_commit or base_commit == "HEAD":
            raise ValueError(
                f"Task '{task_id}' rejected: mutable HEAD or missing base_commit. Must provide a resolved SHA."
            )

        # 1.5 Validate acceptance plan (Pre-Execution Typed Gate Validation)
        validation_error = self.validate_acceptance_plan(envelope.get("acceptance_plan", {}))
        if validation_error:
            logger.error(f"Task {task_id} validation failed: {validation_error}")
            self.queue.fail_task(
                task_id, error_details={"error": validation_error}, allow_retry=False
            )
            return None

        # 1. Verify content_hash integrity
        env_json = json.dumps(envelope, sort_keys=True, separators=(",", ":"), default=str)
        computed_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
        stored_hash = leased_task.get("content_hash")
        legacy_hash = hashlib.sha256(json.dumps(envelope, default=str).encode("utf-8")).hexdigest()
        if stored_hash and computed_hash != stored_hash and legacy_hash != stored_hash:
            from alpha_core.eva.queue_producer import EvaQueueProducer

            eva_hash = EvaQueueProducer.compute_content_hash(
                title=envelope.get("title") or envelope.get("objective") or "",
                acceptance_criteria=envelope.get("acceptance_criteria") or [],
                allowed_paths=envelope.get("allowed_paths") or [],
            )
            if eva_hash != stored_hash:
                err_msg = f"Security Violation: Content hash mismatch on task {task_id}! (stored: {stored_hash}, computed: {computed_hash})"
                logger.critical(err_msg)
                self.queue.fail_task(task_id, error_details={"error": err_msg}, allow_retry=False)
                return None

        # 1.5. Validate complete authoritative lease tuple before provisioning worktree or launching agents
        lease_meta = (leased_task.get("provenance") or {}).get("lease_metadata") or {}
        attempt_id = leased_task.get("attempt_id") or lease_meta.get("attempt_id")
        worker_id = leased_task.get("worker_id") or lease_meta.get("worker_id")
        lease_id = leased_task.get("lease_id") or lease_meta.get("lease_id")
        fencing_epoch = leased_task.get("fencing_epoch")
        if fencing_epoch is None:
            fencing_epoch = lease_meta.get("fencing_epoch")

        if (
            not attempt_id
            or attempt_id in ("att_unknown", "None", "")
            or not worker_id
            or worker_id in ("worker_unknown", "None", "")
            or not lease_id
            or lease_id in ("lease_unknown", "None", "")
            or fencing_epoch is None
            or fencing_epoch in ("None", "")
        ):
            err_msg = (
                f"Task {task_id} missing complete authoritative lease tuple: "
                f"worker_id={worker_id}, attempt_id={attempt_id}, lease_id={lease_id}, fencing_epoch={fencing_epoch}"
            )
            logger.critical(err_msg)
            self.queue.fail_task(task_id, error_details={"error": err_msg}, allow_retry=False)
            return None

        # 2. Provision isolated worktree
        branch_name = f"alpha/{task_id}"
        worktree_path_obj: Path | None = None
        try:
            worktree_path_obj = self.worktree_mgr.create_or_resume_worktree(
                repo_path=repo_path,
                task_id=task_id,
                base_commit=base_commit,
            )
        except Exception as e:
            err_msg = f"Failed to provision worktree: {e}"
            logger.error(err_msg)
            self.queue.fail_task(task_id, error_details={"error": err_msg})
            return None

        worktree_path = worktree_path_obj

        try:
            # 2.5. Launch the local AGY coding agent inside the worktree if enabled
            if self.enable_agent_execution:
                ready, reason = self.live_bridge.check_readiness()
                if not ready:
                    err_msg = f"AGY execution enabled but bridge not ready: {reason}"
                    logger.warning(err_msg)
                    self.queue.fail_task(
                        task_id, error_details={"error": err_msg}, allow_retry=True
                    )
                    return None

                logger.info("Launching local AGY coding agent inside worktree: %s", worktree_path)
                try:
                    task_env = self._build_task_envelope(leased_task, worktree_path)
                    session_dir = self.adapter.setup_session_in_memory_graph(
                        task_env, worktree_path
                    )
                    dispatch_res = self._run_async_dispatch(
                        task_env, worktree_path, attempt_id, session_dir
                    )
                    logger.info(
                        "AGY agent completed turn for %s. Completed: %s, changed files: %s",
                        task_id,
                        getattr(dispatch_res, "completed", False),
                        getattr(dispatch_res, "changed_files", []),
                    )
                    if not getattr(dispatch_res, "completed", False):
                        err_msg = (
                            getattr(dispatch_res, "error_msg", None)
                            or getattr(dispatch_res, "blocked_reason", None)
                            or f"AGY dispatcher returned completed=False for task {task_id}"
                        )
                        self.queue.fail_task(
                            task_id, error_details={"error": err_msg}, allow_retry=True
                        )
                        return None
                except Exception as agy_err:
                    logger.error("AGY coding agent error on task %s: %s", task_id, agy_err)
                    self.queue.fail_task(
                        task_id,
                        error_details={"error": f"Agent error: {agy_err}"},
                        allow_retry=True,
                    )
                    return None

            # 3. Check for worktree modifications and diff
            changed_files, diff_stat = self.get_git_diff_and_changed_files(
                worktree_path, base_commit
            )

            allowed_paths = envelope.get("allowed_paths", [])
            if changed_files:
                violations = WorktreeManager.find_disallowed_changes(changed_files, allowed_paths)
                if violations:
                    err_msg = (
                        f"Security Violation: Modified files outside allowed_paths: {violations}"
                    )
                    logger.error(err_msg)
                    self.queue.fail_task(
                        task_id, error_details={"error": err_msg}, allow_retry=False
                    )
                    return None

            # 4. Run acceptance gates
            gates_passed, evidence = self.run_acceptance_gates(worktree_path, envelope)

            if not gates_passed:
                err_msg = "Acceptance gates failed during task execution"
                self.queue.fail_task(
                    task_id,
                    error_details={"error": err_msg, "evidence": evidence},
                )
                return None

            # R1 (P0): Fail-Closed Law Enforcement — zero modified files with passing gates MUST fail task
            if not changed_files:
                err_msg = (
                    f"Fail-Closed Violation: Task {task_id} produced zero file modifications. "
                    "No work product detected — failing task."
                )
                logger.error(err_msg)
                self.queue.fail_task(
                    task_id,
                    error_details={"error": err_msg, "diff_stat": diff_stat},
                    allow_retry=True,
                )
                return None

            # 5. Create Git Commit on worktree
            title = envelope.get("objective") or envelope.get("title") or f"Execute task {task_id}"
            commit_msg = f"feat({project_id}): {title}\n\nTask-ID: {task_id}\nProvenance: {provenance.get('meeting_id', 'eva')}"
            head_commit = self.create_git_commit(worktree_path, commit_msg)
            if not head_commit:
                err_msg = "Failed to create commit in worktree."
                logger.error(err_msg)
                self.queue.fail_task(task_id, error_details={"error": err_msg}, allow_retry=False)
                return None

            # 5.5 Post-Commit Final Diff Audit & Budget Enforcement
            _ret, out, _ = self.run_command_in_worktree(
                worktree_path, ["git", "diff", "--name-only", f"{base_commit}..{head_commit}"]
            )
            final_changed_files = [
                line.strip('"') for line in out.strip().splitlines() if line.strip()
            ]

            if final_changed_files:
                violations = WorktreeManager.find_disallowed_changes(
                    final_changed_files, allowed_paths
                )
                if violations:
                    err_msg = f"Security Violation: Post-commit diff contains files outside allowed_paths: {violations}"
                    logger.error(err_msg)
                    self.queue.fail_task(
                        task_id, error_details={"error": err_msg}, allow_retry=False
                    )
                    return None

            _ret, diff_tree_out, _ = self.run_command_in_worktree(
                worktree_path,
                ["git", "diff-tree", "-r", "--diff-filter=ACMR", base_commit, head_commit],
            )
            for line in diff_tree_out.strip().splitlines():
                parts = line.split()
                if len(parts) >= 2 and (parts[1] == "120000" or parts[1] == "160000"):
                    err_msg = (
                        "Security Violation: Symlink or submodule added/modified in final commit."
                    )
                    logger.error(err_msg)
                    self.queue.fail_task(
                        task_id, error_details={"error": err_msg}, allow_retry=False
                    )
                    return None

            _ret, status_out, _ = self.run_command_in_worktree(
                worktree_path, ["git", "status", "--porcelain"]
            )
            if status_out.strip():
                err_msg = "Dirty uncommitted residue left behind after commit."
                logger.error(err_msg)
                self.queue.fail_task(task_id, error_details={"error": err_msg}, allow_retry=False)
                return None

            max_changed_files = envelope.get("max_changed_files")
            if isinstance(max_changed_files, int) and len(final_changed_files) > max_changed_files:
                err_msg = f"Budget Error: Changed files count ({len(final_changed_files)}) exceeds max_changed_files ({max_changed_files})."
                logger.error(err_msg)
                self.queue.fail_task(task_id, error_details={"error": err_msg}, allow_retry=False)
                return None

            max_diff_lines = envelope.get("max_diff_lines")
            if isinstance(max_diff_lines, int):
                _ret, diff_stat_out, _ = self.run_command_in_worktree(
                    worktree_path, ["git", "diff", "--shortstat", f"{base_commit}..{head_commit}"]
                )
                lines_changed = 0
                match_ins = re.search(r"(\d+)\s+insertion", diff_stat_out)
                match_del = re.search(r"(\d+)\s+deletion", diff_stat_out)
                if match_ins:
                    lines_changed += int(match_ins.group(1))
                if match_del:
                    lines_changed += int(match_del.group(1))

                if lines_changed > max_diff_lines:
                    err_msg = f"Budget Error: Diff lines count ({lines_changed}) exceeds max_diff_lines ({max_diff_lines})."
                    logger.error(err_msg)
                    self.queue.fail_task(
                        task_id, error_details={"error": err_msg}, allow_retry=False
                    )
                    return None

            plan_digest = None
            blueprint_json = leased_task.get("plan_blueprint_json")
            if blueprint_json:
                plan_digest = hashlib.sha256(blueprint_json.encode("utf-8")).hexdigest()

            # 6. Generate PR Proposal Artifact
            pr_proposal = PRProposal(
                task_id=task_id,
                project_id=project_id,
                branch_name=branch_name,
                base_commit=base_commit,
                head_commit=head_commit,
                title=f"Autonomous Delivery: {title}",
                description=envelope.get("detailed_instructions")
                or envelope.get("description")
                or title,
                files_changed=final_changed_files,
                diff_stat=diff_stat,
                gates_passed=gates_passed,
                evidence=evidence,
                created_at=time.time(),
                attempt_id=attempt_id,
                worker_id=worker_id,
                plan_digest=plan_digest,
            )

            # 7. Complete task in queue with lease ownership verification
            if (
                not worker_id
                or worker_id in ("worker_unknown", "None", "")
                or not attempt_id
                or attempt_id in ("att_unknown", "None", "")
                or not lease_id
                or lease_id in ("lease_unknown", "None", "")
                or fencing_epoch is None
                or fencing_epoch in ("None", "")
            ):
                err_msg = (
                    f"Dispatcher cannot complete task {task_id}: incomplete authoritative lease tuple "
                    f"(worker_id={worker_id}, attempt_id={attempt_id}, lease_id={lease_id}, fencing_epoch={fencing_epoch})"
                )
                logger.critical(err_msg)
                self.queue.fail_task(task_id, error_details={"error": err_msg}, allow_retry=False)
                return None

            success = self.queue.complete_task(
                task_id=task_id,
                result=pr_proposal.to_dict(),
                worktree_path=str(worktree_path),
                branch_name=branch_name,
                worker_id=worker_id,
                lease_id=lease_id,
                fencing_epoch=int(fencing_epoch),
                attempt_id=attempt_id,
            )
            if not success:
                logger.error(
                    f"Failed to mark task {task_id} as COMPLETED in queue (lease ownership validation failed)"
                )
                return None

            return pr_proposal

        except Exception as e:
            logger.exception(f"Unexpected error executing task {task_id}: {e}")
            self.queue.fail_task(task_id, error_details={"error": str(e)})
            return None

    def execute_next_cycle(self) -> PRProposal | None:
        """
        Performs one complete worker cycle: poll/lease task, execute, collect evidence, generate PR.
        Returns the PRProposal if a task was processed, or None if queue is empty or idle.
        """
        leased = self.lease_task()
        if not leased:
            return None
        return self.execute_task(leased)

    def _build_task_envelope(
        self, leased_task: dict[str, Any], worktree_path: Path
    ) -> TaskEnvelope:
        env_dict = dict(leased_task["envelope"])
        task_id = leased_task["id"]
        env_dict.setdefault("task_id", task_id)
        env_dict.setdefault("project_id", "alphabrain_triage")
        env_dict.setdefault("repo", str(worktree_path))
        env_dict.setdefault("base_commit", self.default_base_commit)

        env_dict.setdefault("preferred_agent", AgentType.ANTIGRAVITY)
        env_dict.setdefault("risk_class", RiskClass.LOW)

        evidence_list = leased_task.get("result", {}).get("evidence", [])
        failed_gates = [e for e in evidence_list if not e.get("passed", True)]
        if failed_gates:
            repair_block = "\n\n## 🚨 PREVIOUS ATTEMPT GATE FAILURES (REPAIR DIRECTIVES)\n"
            for fg in failed_gates:
                cmd = fg.get("command", "Unknown")
                ret = fg.get("returncode", 1)
                stdout = fg.get("stdout_snippet", "").strip()
                stderr = fg.get("stderr_snippet", "").strip()
                repair_block += f"### Failed Gate: {cmd} (Exit {ret})\n"
                if stdout:
                    repair_block += f"**Stdout:**\n```\n{stdout}\n```\n"
                if stderr:
                    repair_block += f"**Stderr:**\n```\n{stderr}\n```\n"

            old_inst = env_dict.get("detailed_instructions") or ""
            env_dict["detailed_instructions"] = old_inst + repair_block

        blueprint_json = leased_task.get("plan_blueprint_json")
        if blueprint_json:
            try:
                blueprint = json.loads(blueprint_json)
                plan_md = blueprint.get("plan_markdown")
                if plan_md:
                    old_inst = env_dict.get("detailed_instructions") or ""
                    env_dict["detailed_instructions"] = (
                        f"## 📋 SENIOR ENGINEERING PLAN\n\n{plan_md}\n\n---\n{old_inst}"
                    )
            except Exception:
                pass

        acc_plan = env_dict.get("acceptance_plan")
        if isinstance(acc_plan, dict):
            cmds = acc_plan.get("commands", [])
            formatted_cmds = []
            for cmd in cmds:
                if isinstance(cmd, dict):
                    c = dict(cmd)
                    # Removed auto unit_test default to enforce explicit gate types
                    pass
                    formatted_cmds.append(c)
                elif isinstance(cmd, str):
                    parts = cmd.split()
                    formatted_cmds.append(
                        {
                            "gate_type": GateType.UNIT_TEST.value,
                            "executable": parts[0] if parts else "pytest",
                            "args": parts[1:] if len(parts) > 1 else [],
                        }
                    )
            acc_plan["commands"] = formatted_cmds
        else:
            env_dict["acceptance_plan"] = {
                "commands": [{"gate_type": "unit_test", "executable": "pytest", "args": ["-q"]}],
                "required_gates": ["unit_test"],
            }
        return TaskEnvelope.model_validate(env_dict)  # type: ignore

    def _run_async_dispatch(  # type: ignore
        self,
        task: TaskEnvelope,
        worktree_path: Path,
        attempt_id: str,
        session_dir: Path | None = None,
    ) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(
                    asyncio.run,
                    self.live_bridge.dispatch(task, worktree_path, attempt_id, session_dir),
                ).result()
        else:
            return asyncio.run(
                self.live_bridge.dispatch(task, worktree_path, attempt_id, session_dir)
            )
