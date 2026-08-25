import json
import logging
import os
import uuid
from pathlib import Path
from typing import cast

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

from .antigravity_live import AntigravityLiveBridge
from .base import BaseAgentAdapter

logger = logging.getLogger("alpha_worker.antigravity")


class AntigravityAdapter(BaseAgentAdapter):
    """Antigravity IDE & Session Adapter integrating directly with Memory Graph."""

    def __init__(self) -> None:
        super().__init__(AgentType.ANTIGRAVITY)
        self.memory_graph_path: Path = Path(settings.MEMORY_GRAPH_PATH)
        self.worktree_mgr = WorktreeManager()
        self.live_bridge = AntigravityLiveBridge()

    def check_readiness(self) -> tuple[bool, str]:
        return cast(tuple[bool, str], self.live_bridge.check_readiness())

    def setup_session_in_memory_graph(
        self,
        task: TaskEnvelope,
        worktree_path: Path,
    ) -> Path:
        """Creates an isolated conversation session inside Memory Graph."""
        session_id = task.session_id or f"agy_{task.task_id}_{uuid.uuid4().hex[:6]}"
        session_dir = self.memory_graph_path / "brain" / session_id
        logs_dir = session_dir / ".system_generated" / "logs"
        artifacts_dir = session_dir / "artifacts"

        logs_dir.mkdir(parents=True, exist_ok=True)
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Write overview context
        overview_path = logs_dir / "overview.txt"
        overview_content = {
            "task_id": task.task_id,
            "project_id": task.project_id,
            "objective": task.objective,
            "worktree_path": str(worktree_path),
            "allowed_paths": task.allowed_paths,
            "allowed_tools": task.allowed_tools,
        }
        overview_path.write_text(json.dumps(overview_content, indent=2))

        # Create project symlink entry point
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
    ) -> TaskResult:
        attempt_id = f"att_{task.task_id}_{uuid.uuid4().hex[:6]}"

        # 1. Record task provenance locally; this is not execution proof.
        session_dir = self.setup_session_in_memory_graph(task, worktree_path)

        # 2. Execute through the project-dedicated Antigravity chat.
        dispatch = await self.live_bridge.dispatch(task, worktree_path)

        # 3. Run declared acceptance gates after explicit agent completion.
        gate_result = self.run_acceptance_gates(task, worktree_path, attempt_id)
        gate_result.evidence_items.append(
            GateEvidence(
                evidence_id=f"evi_{len(gate_result.evidence_items) + 1}",
                gate_type=GateType.CODE_REVIEW_GRAPH,
                passed=dispatch.completed,
                summary=(
                    "Antigravity completed with required code-review graph calls"
                    if dispatch.completed
                    else f"Antigravity execution did not complete: {dispatch.blocked_reason}"
                ),
                artifacts_created=[str(dispatch.transcript_path)]
                if dispatch.transcript_path
                else [],
                metrics={
                    "conversation_id": dispatch.conversation_id,
                    "tools_used": list(dispatch.tool_names),
                },
            )
        )
        if dispatch.qa_evidence:
            gate_result.evidence_items.append(
                GateEvidence(
                    evidence_id=f"evi_{len(gate_result.evidence_items) + 1}",
                    gate_type=GateType.INDEPENDENT_REVIEW,
                    passed=True,
                    summary="Antigravity supplied validated multi-agent-sdlc QA evidence",
                    metrics={"qa_evidence": dispatch.qa_evidence},
                )
            )
        gate_result.all_passed = gate_result.all_passed and dispatch.completed

        # 3. Inspect changed files & commit
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
        if changed_files and not disallowed_changes:
            result_commit = self.worktree_mgr.commit_changes(
                worktree_path,
                f"alpha(task): {task.objective} [{task.task_id}]",
            )

        status = TaskStatus.COMPLETED if gate_result.all_passed else TaskStatus.RETRYABLE_FAILED

        return TaskResult(
            attempt_id=attempt_id,
            task_id=task.task_id,
            status=status,
            agent=self.agent_type,
            model=f"antigravity-{settings.ANTIGRAVITY_MODEL}",
            base_commit=base_commit,
            result_commit=result_commit or base_commit,
            files_changed=changed_files,
            diff_summary=diff_summary,
            gate_result=gate_result,
            artifacts=[
                str(session_dir / "artifacts"),
                *([str(dispatch.transcript_path)] if dispatch.transcript_path else []),
            ],
            blockers=[dispatch.blocked_reason] if dispatch.blocked_reason else [],
            provenance_notes=[
                f"Task provenance recorded at {session_dir}",
                f"Antigravity project conversation: {dispatch.conversation_id}",
            ],
        )
