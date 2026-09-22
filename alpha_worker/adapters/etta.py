"""ETTA v0.2.0 autonomous coding worker adapter."""

from __future__ import annotations

import json
import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from alpha_core.config import settings
from alpha_core.security import redact_dict, worker_kill_switch
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
from .etta_live import EttaLiveBridge

logger = logging.getLogger("alpha_worker.etta")


class EttaAdapter(BaseAgentAdapter):
    """ETTA v0.2.0 Autonomous Coding Worker Adapter."""

    def __init__(self, live_bridge: EttaLiveBridge | None = None) -> None:
        super().__init__(AgentType.ETTA)
        self.live_bridge = live_bridge or EttaLiveBridge()
        self.worktree_mgr = WorktreeManager()
        self.memory_graph_path = Path(settings.MEMORY_GRAPH_PATH)

    def check_readiness(self) -> tuple[bool, str]:
        """Check if ETTA worker is ready to execute."""
        return self.live_bridge.check_readiness()

    def setup_session_in_memory_graph(
        self,
        task: TaskEnvelope,
        worktree_path: Path,
    ) -> Path:
        """Creates an isolated conversation session inside Memory Graph."""
        session_id = task.session_id or f"etta_{task.task_id}_{uuid.uuid4().hex[:6]}"
        session_dir = self.memory_graph_path / "brain" / session_id
        logs_dir = session_dir / ".system_generated" / "logs"
        artifacts_dir = session_dir / "artifacts"

        logs_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        overview_path = logs_dir / "overview.txt"
        overview_content = {
            "task_id": task.task_id,
            "project_id": task.project_id,
            "objective": task.objective,
            "worktree_path": str(worktree_path),
            "allowed_paths": task.allowed_paths,
            "allowed_tools": task.allowed_tools,
            "agent_type": self.agent_type.value,
        }
        overview_path.write_text(json.dumps(redact_dict(overview_content), indent=2))

        project_link_dir = self.memory_graph_path / "by_project" / task.project_id
        project_link_dir.mkdir(parents=True, exist_ok=True)
        link_target = project_link_dir / session_id
        if not link_target.exists():
            try:
                os.symlink(session_dir, link_target)
            except OSError as exc:
                logger.warning("Could not create Memory Graph project link: %s", exc)

        return session_dir

    async def execute(
        self,
        task: TaskEnvelope,
        worktree_path: Path,
        base_commit: str,
        emit_checkpoint: (
            Callable[[str, str, str, str, dict[str, Any]], Awaitable[None]] | None
        ) = None,
    ) -> TaskResult:
        """Executes the assigned task in the isolated worktree."""
        attempt_id = f"att_{task.task_id}_{uuid.uuid4().hex[:6]}"
        if emit_checkpoint:
            await emit_checkpoint(attempt_id, "worktree_validated", "none", "", {})

        if not worker_kill_switch.can_execute(task.project_id):
            logger.warning("Execution halted by kill switch for project %s", task.project_id)
            return TaskResult(
                attempt_id=attempt_id,
                task_id=task.task_id,
                status=TaskStatus.BLOCKED,
                agent=self.agent_type,
                model=getattr(settings, "ETTA_MODEL", "gemini-3.8-flash-high"),
                base_commit=base_commit,
                result_commit=base_commit,
                files_changed=[],
                diff_summary="",
                blockers=[f"Worker kill switch active for project {task.project_id}"],
            )

        is_ready, reason = self.check_readiness()
        if not is_ready:
            logger.warning("ETTA adapter not ready: %s", reason)
            return TaskResult(
                attempt_id=attempt_id,
                task_id=task.task_id,
                status=TaskStatus.BLOCKED,
                agent=self.agent_type,
                model=getattr(settings, "ETTA_MODEL", "gemini-3.8-flash-high"),
                base_commit=base_commit,
                result_commit=base_commit,
                files_changed=[],
                diff_summary="",
                blockers=[reason],
            )

        session_dir = self.setup_session_in_memory_graph(task, worktree_path)
        if emit_checkpoint:
            await emit_checkpoint(
                attempt_id,
                "conversation_bound",
                "none",
                "",
                {"session_dir": str(session_dir)},
            )

        try:
            if emit_checkpoint:
                await emit_checkpoint(attempt_id, "implementation_started", "started", "", {})
            dispatch = await self.live_bridge.dispatch(task, worktree_path, attempt_id, session_dir)
        except Exception as exc:
            logger.error("ETTA bridge dispatch failed: %s", exc)
            return TaskResult(
                attempt_id=attempt_id,
                task_id=task.task_id,
                status=TaskStatus.RETRYABLE_FAILED,
                agent=self.agent_type,
                model=getattr(settings, "ETTA_MODEL", "gemini-3.8-flash-high"),
                base_commit=base_commit,
                result_commit=base_commit,
                files_changed=[],
                diff_summary="",
                blockers=[f"Dispatch failed ({type(exc).__name__}): {exc!s}"],
            )

        if emit_checkpoint:
            await emit_checkpoint(
                attempt_id,
                "process_exited",
                "prepared",
                "",
                {"exit_code": dispatch.exit_code},
            )

        additional_evidence: list[GateEvidence] = [
            GateEvidence(
                evidence_id="evi_placeholder_etta",
                gate_type=GateType.INDEPENDENT_REVIEW,
                passed=dispatch.completed,
                summary=(
                    "ETTA autonomous execution completed successfully"
                    if dispatch.completed
                    else f"ETTA execution did not complete: {dispatch.blocked_reason}"
                ),
                artifacts_created=[str(dispatch.transcript_path)]
                if dispatch.transcript_path
                else [],
                metrics={
                    "tools_used": list(dispatch.tool_names),
                    "tokens_used": dispatch.tokens_used,
                    "cost": dispatch.cost,
                },
            )
        ]

        if emit_checkpoint:
            await emit_checkpoint(attempt_id, "gates_started", "prepared", "", {})
        gate_result = self.run_acceptance_gates(
            task, worktree_path, attempt_id, additional_evidence
        )
        gate_result.all_passed = gate_result.all_passed and dispatch.completed
        if emit_checkpoint:
            await emit_checkpoint(
                attempt_id,
                "gates_completed",
                "prepared",
                "",
                {"all_passed": gate_result.all_passed},
            )

        uncommitted_files = self.worktree_mgr.get_uncommitted_files(worktree_path)
        disallowed_uncommitted = (
            self.worktree_mgr.find_disallowed_changes(
                uncommitted_files,
                task.allowed_paths,
            )
            if uncommitted_files
            else []
        )

        commit_sha = base_commit
        if uncommitted_files and not disallowed_uncommitted:
            commit_result = self.worktree_mgr.commit_changes(
                worktree_path,
                f"feat({task.project_id}): {task.objective}\n\nTask-ID: {task.task_id}\nAgent: ETTA",
                allowed_paths=task.allowed_paths,
            )
            if commit_result:
                commit_sha = commit_result

        status = (
            TaskStatus.VERIFIED
            if (dispatch.completed and gate_result.all_passed and not disallowed_uncommitted)
            else TaskStatus.RETRYABLE_FAILED
        )

        return TaskResult(
            attempt_id=attempt_id,
            task_id=task.task_id,
            status=status,
            agent=self.agent_type,
            model=getattr(settings, "ETTA_MODEL", "gemini-3.8-flash-high"),
            base_commit=base_commit,
            result_commit=commit_sha,
            files_changed=uncommitted_files or list(dispatch.changed_files),
            diff_summary=dispatch.diff_summary,
            gate_result=gate_result,
            artifacts=list(dispatch.artifacts),
            blockers=[dispatch.blocked_reason] if dispatch.blocked_reason else [],
        )
