"""Fail-closed admission checks for AlphaBrain self-improvement tasks."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from sqlalchemy.ext.asyncio import AsyncSession

from alpha_core.config import settings
from alpha_core.db.models import TaskRecord
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import AcceptancePlan, AgentType, GateType, RiskClass, TaskEnvelope


@dataclass(frozen=True)
class SelfImprovementRequest:
    """Founder-approved, bounded request to change AlphaBrain itself."""

    source_repo: Path
    allowed_paths: tuple[str, ...]
    founder_identity: str
    requires_approval: bool
    risk_class: RiskClass = RiskClass.LOW
    base_commit: str = "HEAD"


@dataclass(frozen=True)
class SelfImprovementAdmission:
    """Read-only admission result; callers must not execute rejected requests."""

    admitted: bool
    reason: str
    source_repo: Path | None = None
    base_commit: str | None = None


def _git(repo: Path, *args: str) -> tuple[int, str, str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _validate_allowed_paths(paths: tuple[str, ...]) -> str | None:
    if not paths:
        return "Self-improvement task requires at least one allowed path"
    for raw_path in paths:
        if raw_path == ".":
            continue
        path = PurePosixPath(raw_path)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            return f"Unsafe allowed path: {raw_path}"
    return None


def admit_self_improvement(request: SelfImprovementRequest) -> SelfImprovementAdmission:
    """Validate self-task base without mutating source, git state, or worktrees."""

    founder_identity = request.founder_identity.strip()
    if not founder_identity:
        return SelfImprovementAdmission(False, "Founder identity is required")
    if not request.requires_approval:
        return SelfImprovementAdmission(False, "Founder approval is required")
    if request.risk_class is not RiskClass.LOW:
        return SelfImprovementAdmission(False, "Self-improvement tasks must start at low risk")

    allowed_path_error = _validate_allowed_paths(request.allowed_paths)
    if allowed_path_error:
        return SelfImprovementAdmission(False, allowed_path_error)

    repo = request.source_repo.expanduser().resolve()
    roots = tuple(root.expanduser().resolve() for root in settings.ALLOWED_REPO_ROOTS)
    if not any(repo == root or repo.is_relative_to(root) for root in roots):
        return SelfImprovementAdmission(False, "Source repository is outside allowed roots")
    if not repo.is_dir():
        return SelfImprovementAdmission(False, "Source repository does not exist")

    code, inside_worktree, _ = _git(repo, "rev-parse", "--is-inside-work-tree")
    if code != 0 or inside_worktree != "true":
        return SelfImprovementAdmission(False, "Source repository is not a Git worktree")

    code, status, error = _git(repo, "status", "--porcelain")
    if code != 0:
        return SelfImprovementAdmission(False, f"Could not inspect source repository: {error}")
    if status:
        return SelfImprovementAdmission(
            False,
            "Source repository has uncommitted changes; approve a clean base commit or explicit "
            "immutable snapshot workflow",
        )

    code, base_commit, error = _git(
        repo, "rev-parse", "--verify", f"{request.base_commit}^{{commit}}"
    )
    if code != 0:
        return SelfImprovementAdmission(False, f"Could not resolve immutable base commit: {error}")

    return SelfImprovementAdmission(
        True,
        "Self-improvement base admitted; founder-approved task may be created",
        source_repo=repo,
        base_commit=base_commit,
    )


async def create_self_improvement_task(
    session: AsyncSession,
    request: SelfImprovementRequest,
    *,
    project_id: str,
    task_id: str,
    objective: str,
    acceptance_plan: AcceptancePlan,
    detailed_instructions: str | None = None,
) -> TaskRecord:
    """Create, but never execute, one founder-approved self-development task.

    Admission resolves a clean immutable source revision before any durable row
    is written.  The resulting task always waits for the normal execution
    approval, so creating a self-task cannot run AGY or mutate AlphaBrain.
    """

    admission = admit_self_improvement(request)
    if not admission.admitted or not admission.source_repo or not admission.base_commit:
        raise ValueError(f"Self-improvement admission rejected: {admission.reason}")

    if not acceptance_plan.required_gates:
        raise ValueError("Self-development task requires nonempty required_gates")
    if not acceptance_plan.require_independent_review:
        raise ValueError("Self-development task must have require_independent_review=True")

    req_gates = set(acceptance_plan.required_gates)
    if GateType.INDEPENDENT_REVIEW not in req_gates or GateType.CODE_REVIEW_GRAPH not in req_gates:
        raise ValueError("required_gates must include INDEPENDENT_REVIEW and CODE_REVIEW_GRAPH")

    cmd_gates = {cmd.gate_type for cmd in acceptance_plan.commands}
    for gate in req_gates:
        if gate not in {
            GateType.INDEPENDENT_REVIEW,
            GateType.CODE_REVIEW_GRAPH,
        }:
            if gate not in cmd_gates:
                raise ValueError(f"Required gate {gate.value} has no matching GateCommand")

    for cmd in acceptance_plan.commands:
        if cmd.gate_type not in req_gates:
            raise ValueError(
                f"Command gate_type {cmd.gate_type.value} must be declared in required_gates"
            )
        if cmd.gate_type in {GateType.INDEPENDENT_REVIEW, GateType.CODE_REVIEW_GRAPH}:
            raise ValueError(f"Gate type {cmd.gate_type.value} cannot be a shell command gate")
        if cmd.executable not in settings.ALLOWED_GATE_EXECUTABLES:
            raise ValueError(
                f"Command executable '{cmd.executable}' is not in ALLOWED_GATE_EXECUTABLES"
            )

    await TaskEngine.create_project(
        session,
        project_id=project_id,
        name="AlphaBrain self-development",
        repo_path=str(admission.source_repo),
    )
    envelope = TaskEnvelope(
        task_id=task_id,
        project_id=project_id,
        repo=str(admission.source_repo),
        base_commit=admission.base_commit,
        objective=objective,
        detailed_instructions=(
            "SELF-DEVELOPMENT SAFETY CONTRACT:\n"
            "- Work only inside allowed_paths.\n"
            "- Never change source repository directly; use assigned worktree.\n"
            "- No deployment, network side effect, credential change, or merge.\n"
            "- Return declared tests, diff, blockers, and evidence.\n\n"
            f"{detailed_instructions or ''}"
        ).strip(),
        allowed_paths=list(request.allowed_paths),
        preferred_agent=AgentType.ANTIGRAVITY,
        risk_class=RiskClass.LOW,
        requires_approval=True,
        require_packet_binding=True,
        acceptance_plan=acceptance_plan,
    )
    return await TaskEngine.submit_task(session, envelope, project_id=project_id)
