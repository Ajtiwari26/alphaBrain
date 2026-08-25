import shutil
import subprocess
import uuid
from pathlib import Path

from alpha_core.config import settings
from alpha_protocol import (
    AgentType,
    GateEvidence,
    GateType,
    TaskEnvelope,
    TaskResult,
    TaskStatus,
)
from alpha_worker.worktree import WorktreeManager

from .base import BaseAgentAdapter


class ClaudeCLIAdapter(BaseAgentAdapter):
    """Headless Claude Code CLI harness using existing logged-in subscription session."""

    def __init__(self):
        super().__init__(AgentType.CLAUDE_CODE)
        self.worktree_mgr = WorktreeManager()

    def check_readiness(self) -> tuple[bool, str]:
        claude_bin = shutil.which("claude")
        if not claude_bin:
            return False, "claude binary not found in system PATH"
        return True, f"Claude CLI ready at {claude_bin}"

    async def execute(
        self,
        task: TaskEnvelope,
        worktree_path: Path,
        base_commit: str,
    ) -> TaskResult:
        attempt_id = f"att_{task.task_id}_{uuid.uuid4().hex[:6]}"
        is_ready, reason = self.check_readiness()

        if not is_ready:
            return TaskResult(
                attempt_id=attempt_id,
                task_id=task.task_id,
                status=TaskStatus.BLOCKED,
                agent=self.agent_type,
                model="claude-code-cli",
                base_commit=base_commit,
                blockers=[reason],
            )

        prompt = (
            f"OBJECTIVE: {task.objective}\n\n"
            f"ALLOWED PATHS: {', '.join(task.allowed_paths) if task.allowed_paths else 'All repo files'}\n"
            f"INSTRUCTIONS: {task.detailed_instructions or 'Follow project standards and verify all test scripts.'}\n"
            f"ACCEPTANCE CRITERIA: Ensure all declared tests pass in testscript/."
        )

        requested_tools = task.allowed_tools or list(settings.ALLOWED_CLAUDE_TOOLS)
        allowed_tools = [tool for tool in requested_tools if tool in settings.ALLOWED_CLAUDE_TOOLS]
        if not allowed_tools:
            return TaskResult(
                attempt_id=attempt_id,
                task_id=task.task_id,
                status=TaskStatus.BLOCKED,
                agent=self.agent_type,
                model="claude-code-cli",
                base_commit=base_commit,
                blockers=["Task requested no allowed Claude tools"],
            )

        cmd = [
            "claude",
            "-p",
            prompt,
            "--permission-mode",
            "acceptEdits",
            "--tools",
            ",".join(allowed_tools),
            "--output-format",
            "json",
            "--no-session-persistence",
        ]

        try:
            res = subprocess.run(
                cmd,
                cwd=str(worktree_path),
                capture_output=True,
                text=True,
                timeout=900,  # 15 minutes max per attempt
            )
        except subprocess.TimeoutExpired:
            return TaskResult(
                attempt_id=attempt_id,
                task_id=task.task_id,
                status=TaskStatus.RETRYABLE_FAILED,
                agent=self.agent_type,
                model="claude-code-cli",
                base_commit=base_commit,
                blockers=["Claude CLI execution timed out after 15 minutes"],
            )
        except Exception as e:
            return TaskResult(
                attempt_id=attempt_id,
                task_id=task.task_id,
                status=TaskStatus.RETRYABLE_FAILED,
                agent=self.agent_type,
                model="claude-code-cli",
                base_commit=base_commit,
                blockers=[f"Claude CLI execution failed: {e!s}"],
            )

        # Run acceptance gates
        gate_result = self.run_acceptance_gates(task, worktree_path, attempt_id)

        # Gather changed files and commit
        changed_files = self.worktree_mgr.get_changed_files(worktree_path, base_commit)
        diff_summary = self.worktree_mgr.get_diff_summary(worktree_path)
        disallowed_changes = self.worktree_mgr.find_disallowed_changes(
            changed_files,
            task.allowed_paths,
        )
        if disallowed_changes:
            gate_result.evidence_items.append(
                GateEvidence(
                    evidence_id=f"evi_{len(gate_result.evidence_items) + 1}",
                    gate_type=GateType.SECURITY_SCAN,
                    passed=False,
                    summary="Agent changed files outside allowed_paths",
                    artifacts_created=disallowed_changes,
                )
            )
            gate_result.all_passed = False

        result_commit = None
        if changed_files and not disallowed_changes and res.returncode == 0:
            result_commit = self.worktree_mgr.commit_changes(
                worktree_path,
                f"alpha(claude): {task.objective} [{task.task_id}]",
            )

        status = (
            TaskStatus.COMPLETED
            if res.returncode == 0 and gate_result.all_passed
            else TaskStatus.RETRYABLE_FAILED
        )

        return TaskResult(
            attempt_id=attempt_id,
            task_id=task.task_id,
            status=status,
            agent=self.agent_type,
            model="claude-code-cli",
            base_commit=base_commit,
            result_commit=result_commit or base_commit,
            files_changed=changed_files,
            diff_summary=diff_summary,
            gate_result=gate_result,
            blockers=[]
            if res.returncode == 0
            else [f"Claude CLI exited with code {res.returncode}"],
            provenance_notes=[f"CLI exited with code {res.returncode}"],
        )
