import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from alpha_core.config import settings
from alpha_protocol import (
    AgentType,
    GateEvidence,
    GateResult,
    TaskEnvelope,
    TaskResult,
)


class BaseAgentAdapter(ABC):
    """Abstract interface that all execution adapters must implement."""

    def __init__(self, agent_type: AgentType):
        self.agent_type = agent_type

    @abstractmethod
    def check_readiness(self) -> tuple[bool, str]:
        """Returns (is_ready, reason/details)."""
        pass

    @abstractmethod
    async def execute(
        self,
        task: TaskEnvelope,
        worktree_path: Path,
        base_commit: str,
    ) -> TaskResult:
        """Executes the assigned task in the isolated worktree."""
        pass

    def run_acceptance_gates(
        self,
        task: TaskEnvelope,
        worktree_path: Path,
        attempt_id: str,
    ) -> GateResult:
        """Runs typed allowlisted commands and proves every required gate."""
        evidence_items: list[GateEvidence] = []
        allowed_executables = set(settings.ALLOWED_GATE_EXECUTABLES)

        for command in task.acceptance_plan.commands:
            command_label = " ".join([command.executable, *command.args])
            if command.executable not in allowed_executables:
                evidence_items.append(
                    GateEvidence(
                        evidence_id=f"evi_{len(evidence_items) + 1}",
                        gate_type=command.gate_type,
                        passed=False,
                        summary=f"Executable '{command.executable}' is not allowlisted",
                    )
                )
                continue

            resolved_executable = shutil.which(command.executable)
            if not resolved_executable:
                evidence_items.append(
                    GateEvidence(
                        evidence_id=f"evi_{len(evidence_items) + 1}",
                        gate_type=command.gate_type,
                        passed=False,
                        summary=f"Executable '{command.executable}' was not found",
                    )
                )
                continue

            try:
                res = subprocess.run(
                    [resolved_executable, *command.args],
                    cwd=str(worktree_path),
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=command.timeout_seconds,
                )
                passed = res.returncode == 0

                evidence_items.append(
                    GateEvidence(
                        evidence_id=f"evi_{len(evidence_items) + 1}",
                        gate_type=command.gate_type,
                        passed=passed,
                        summary=f"Command '{command_label}' exited with code {res.returncode}",
                        output_log=res.stdout[-2000:]
                        + ("\nSTDERR:\n" + res.stderr[-1000:] if res.stderr else ""),
                        metrics={"exit_code": res.returncode},
                    )
                )
            except Exception as e:
                evidence_items.append(
                    GateEvidence(
                        evidence_id=f"evi_{len(evidence_items) + 1}",
                        gate_type=command.gate_type,
                        passed=False,
                        summary=f"Command '{command_label}' failed with exception: {e!s}",
                    )
                )

        for required_gate in task.acceptance_plan.required_gates:
            matching_evidence = [item for item in evidence_items if item.gate_type == required_gate]
            if not matching_evidence:
                evidence_items.append(
                    GateEvidence(
                        evidence_id=f"evi_{len(evidence_items) + 1}",
                        gate_type=required_gate,
                        passed=False,
                        summary=f"Required gate '{required_gate.value}' produced no evidence",
                    )
                )

        all_passed = bool(evidence_items) and all(item.passed for item in evidence_items)

        return GateResult(
            task_id=task.task_id,
            attempt_id=attempt_id,
            all_passed=all_passed,
            evidence_items=evidence_items,
        )
