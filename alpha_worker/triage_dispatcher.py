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
import subprocess
import sys
import time
import uuid
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
        default_base_commit: str = "HEAD",
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
        if not commands:
            # If no custom commands, default to basic pytest verification
            commands = [{"executable": "pytest", "args": ["-q"]}]

        all_passed = True
        evidence: list[dict[str, Any]] = []

        for c in commands:
            exe = c.get("executable", "pytest")
            args = c.get("args", [])
            full_cmd = [exe, *args]

            # Determine gate type
            gate_type = GateType.UNIT_TEST.value
            if "ruff" in exe or "lint" in exe or "flake8" in exe:
                gate_type = GateType.LINT.value
            elif "mypy" in exe or "type" in exe:
                gate_type = GateType.TYPE_CHECK.value

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
                    "stdout_snippet": stdout[:1000],
                    "stderr_snippet": stderr[:1000],
                    "timestamp": time.time(),
                }
            )

        return all_passed, evidence

    def get_git_diff_and_changed_files(self, worktree_path: Path) -> tuple[list[str], str]:
        """Inspects git status and diff inside the worktree."""
        # 1. Changed files
        ret, out, _ = self.run_command_in_worktree(
            worktree_path, ["git", "status", "--porcelain", "-uall"]
        )
        changed_files: list[str] = []
        if ret == 0 and out.strip():
            for line in out.strip().splitlines():
                parts = line.strip().split(maxsplit=1)
                if len(parts) == 2:
                    changed_files.append(parts[1].strip('"'))

        # 2. Diff stat
        _, stat_out, _ = self.run_command_in_worktree(worktree_path, ["git", "diff", "--stat"])
        return changed_files, stat_out.strip()

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

        # 1. Verify content_hash integrity
        env_json = json.dumps(envelope, default=str)
        computed_hash = hashlib.sha256(env_json.encode("utf-8")).hexdigest()
        stored_hash = leased_task.get("content_hash")
        if stored_hash and computed_hash != stored_hash:
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
                if ready:
                    logger.info(
                        "Launching local AGY coding agent inside worktree: %s", worktree_path
                    )
                    try:
                        task_env = self._build_task_envelope(leased_task, worktree_path)
                        attempt_id = f"att_{task_id}_{uuid.uuid4().hex[:6]}"
                        session_dir = self.adapter.setup_session_in_memory_graph(
                            task_env, worktree_path
                        )
                        dispatch_res = self._run_async_dispatch(
                            task_env, worktree_path, attempt_id, session_dir
                        )
                        logger.info(
                            "AGY agent completed turn for %s. Completed: %s, changed files: %s",
                            task_id,
                            dispatch_res.completed,
                            dispatch_res.changed_files,
                        )
                    except Exception as agy_err:
                        logger.error("AGY coding agent error on task %s: %s", task_id, agy_err)
                else:
                    logger.warning("AGY execution enabled but bridge not ready: %s", reason)

            # 3. Check for worktree modifications and diff
            changed_files, diff_stat = self.get_git_diff_and_changed_files(worktree_path)
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

            # 5. Create Git Commit on worktree
            title = envelope.get("objective") or envelope.get("title") or f"Execute task {task_id}"
            commit_msg = f"feat({project_id}): {title}\n\nTask-ID: {task_id}\nProvenance: {provenance.get('meeting_id', 'eva')}"
            head_commit = self.create_git_commit(worktree_path, commit_msg)
            if not head_commit:
                head_commit = base_commit

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
                files_changed=changed_files,
                diff_stat=diff_stat,
                gates_passed=gates_passed,
                evidence=evidence,
                created_at=time.time(),
            )

            # 7. Complete task in queue
            success = self.queue.complete_task(
                task_id=task_id,
                result=pr_proposal.to_dict(),
                worktree_path=str(worktree_path),
                branch_name=branch_name,
            )
            if not success:
                logger.error(f"Failed to mark task {task_id} as COMPLETED in queue")

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

        acc_plan = env_dict.get("acceptance_plan")
        if isinstance(acc_plan, dict):
            cmds = acc_plan.get("commands", [])
            formatted_cmds = []
            for cmd in cmds:
                if isinstance(cmd, dict):
                    c = dict(cmd)
                    c.setdefault("gate_type", GateType.UNIT_TEST.value)
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
        return TaskEnvelope.model_validate(env_dict)

    def _run_async_dispatch(
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
