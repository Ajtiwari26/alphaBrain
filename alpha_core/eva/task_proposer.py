"""
alpha_core/eva/task_proposer.py
Transforms extracted meeting specifications into Alpha Protocol task envelopes.

Authoritative Reference:
docs/architecture/SENIOR_DIRECTIVE_AND_SYSTEM_DESIGN.md (Section 4.2)
"""

import hashlib
import re
import shlex
import subprocess
import time
import uuid
from pathlib import Path

from alpha_core.eva.spec_extractor import ExtractedSpecification
from alpha_protocol.enums import AgentType, GateType, RiskClass
from alpha_protocol.gates import AcceptancePlan, GateCommand
from alpha_protocol.task import TaskEnvelope


def verify_and_resolve_repo_commit(
    repo_path: str | Path,
    base_commit: str | None = None,
    timeout_seconds: float = 5.0,
) -> str:
    """
    Verifies that the target repository exists and resolves/verifies the git base_commit.
    - If base_commit is omitted (None, empty, or 'HEAD'), resolves current HEAD commit via git.
    - If base_commit is supplied, verifies it is a valid 40-char hex SHA AND that it
      exists in the target repository history (git rev-parse --verify {commit}^{commit}).
    - Strict bounded timeout to prevent hanging.
    - Fails closed with descriptive ValueError.
    """
    path = Path(repo_path).resolve()
    if not path.is_dir():
        raise ValueError(
            f"Target repository path '{repo_path}' does not exist or is not a directory"
        ) from None

    if not base_commit or str(base_commit).strip() in ("", "HEAD"):
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=True,
            )
            resolved = res.stdout.strip()
        except subprocess.TimeoutExpired:
            raise ValueError(
                f"Timeout resolving HEAD commit from repository '{repo_path}'"
            ) from None
        except subprocess.CalledProcessError as e:
            err = e.stderr.strip() if e.stderr else str(e)
            raise ValueError(
                f"Failed to resolve HEAD commit from repository '{repo_path}': {err}"
            ) from None
        except Exception as e:
            raise ValueError(
                f"Failed to resolve HEAD commit from repository '{repo_path}': {e}"
            ) from None

        if not bool(re.match(r"^[0-9a-fA-F]{40}$", resolved)):
            raise ValueError(
                f"Resolved HEAD '{resolved}' in '{repo_path}' is not a valid 40-character hexadecimal SHA"
            )
        return resolved

    commit_str = str(base_commit).strip()
    # Base commit supplied: validate format first
    if not bool(re.match(r"^[0-9a-fA-F]{40}$", commit_str)):
        raise ValueError(
            f"Invalid base_commit format '{base_commit}': must be a 40-character hexadecimal SHA"
        )

    # Verify commit exists in the repository
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--verify", f"{commit_str}^{{commit}}"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=True,
        )
        verified = res.stdout.strip()
    except subprocess.TimeoutExpired:
        raise ValueError(
            f"Timeout verifying commit '{base_commit}' in repository '{repo_path}'"
        ) from None
    except subprocess.CalledProcessError as e:
        err = e.stderr.strip() if e.stderr else "Commit not found"
        raise ValueError(
            f"Commit '{base_commit}' does not exist in repository '{repo_path}': {err}"
        ) from None
    except Exception as e:
        raise ValueError(
            f"Failed to verify commit '{base_commit}' in repository '{repo_path}': {e}"
        ) from None

    if verified.lower() != commit_str.lower():
        raise ValueError(
            f"Verified commit '{verified}' does not match expected '{base_commit}'"
        ) from None

    return verified


class EvaTaskProposer:
    """Creates structured TaskEnvelopes from Eva's extracted specifications."""

    def __init__(self, default_repo: str = ".", default_branch: str = "main") -> None:
        self.default_repo = default_repo
        self.default_branch = default_branch

    def build_task_envelope(
        self,
        spec: ExtractedSpecification,
        project_id: str,
        repo: str | None = None,
        base_commit: str | None = None,
        risk_class: RiskClass = RiskClass.LOW,
    ) -> TaskEnvelope:
        """Constructs an Alpha Protocol TaskEnvelope ready for submission to the Control Plane."""
        if not spec.is_actionable:
            raise ValueError("Cannot propose a task from a non-actionable specification.") from None

        target_repo = repo or self.default_repo
        resolved_commit = verify_and_resolve_repo_commit(target_repo, base_commit)
        base_commit = resolved_commit

        unique_seed = f"{project_id}:{spec.title}:{time.time()}:{uuid.uuid4().hex[:8]}"
        task_hash = hashlib.sha256(unique_seed.encode()).hexdigest()[:12]
        task_id = f"tsk_eva_{task_hash}"

        # Construct instructions
        req_lines = "\n".join(f"- {r}" for r in spec.requirements)
        crit_lines = "\n".join(f"- {c}" for c in spec.acceptance_criteria)
        detailed_instructions = (
            f"## Summary\n{spec.summary}\n\n"
            f"## Requirements\n{req_lines}\n\n"
            f"## Acceptance Criteria\n{crit_lines}\n"
        )

        # Construct acceptance gates
        if project_id == "etta":
            commands = [
                GateCommand(
                    gate_type=GateType.UNIT_TEST,
                    executable="cargo",
                    args=["test", "-p", "etta-cli"],
                ),
            ]
        else:
            commands = [
                GateCommand(
                    gate_type=GateType.UNIT_TEST,
                    executable="pytest",
                    args=["-q"],
                ),
                GateCommand(
                    gate_type=GateType.LINT,
                    executable="ruff",
                    args=["check", "."],
                ),
            ]
        if spec.required_gates:
            for g in spec.required_gates:
                if isinstance(g, str) and g not in ("unit_test", "lint", "typecheck"):
                    try:
                        lexer = shlex.shlex(g.strip(), posix=False, punctuation_chars=True)
                        parts = list(lexer)
                    except Exception:
                        parts = g.strip().split()
                    if parts:
                        idx = 0
                        while idx < len(parts) and re.match(
                            r"^[a-zA-Z_][a-zA-Z0-9_]*=.*$", parts[idx]
                        ):
                            idx += 1
                        if idx < len(parts):
                            raw_candidate = parts[idx].split("/")[-1]
                            if re.match(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$", raw_candidate):
                                exec_name = raw_candidate
                                cmd_args = parts[idx + 1 :]
                            else:
                                exec_name = "sh"
                                cmd_args = parts
                            commands.append(
                                GateCommand(
                                    gate_type=GateType.UNIT_TEST,
                                    executable=exec_name,
                                    args=cmd_args,
                                )
                            )

        acceptance_plan = AcceptancePlan(
            required_gates=[GateType.UNIT_TEST, GateType.LINT],
            commands=commands,
            pass_threshold=1.0,
        )

        allowed_paths = (
            list(spec.allowed_paths) if spec.allowed_paths else ["alpha_core", "testscript"]
        )

        return TaskEnvelope(
            task_id=task_id,
            project_id=project_id,
            objective=spec.title,
            detailed_instructions=detailed_instructions,
            repo=target_repo,
            base_commit=base_commit,
            allowed_paths=allowed_paths,
            allowed_tools=["edit_file", "view_file", "run_command"],
            risk_class=risk_class,
            acceptance_plan=acceptance_plan,
            preferred_agent=AgentType.ANTIGRAVITY,
            lease_timeout_seconds=600,
            requires_approval=True,  # Mandatory human/founder review before execution!
        )
