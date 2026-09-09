"""Official AGY CLI bridge for one isolated Alpha Brain project conversation."""

import asyncio
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, cast

from alpha_core.config import settings
from alpha_protocol import (
    ExecutionStage,
    RoutingDecisionStatus,
    RoutingRequest,
    TaskEnvelope,
)
from alpha_worker.agy_credentials import (
    CredentialLockTimeoutError,
    IdentityMismatchError,
    SwitchCommandError,
    acquire_credential_lease,
)
from alpha_worker.routing import call_model_router, report_model_outcome

CONVERSATION_ID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
COMPLETION_TOKEN = "ALPHA_BRAIN_TASK_DONE"
BLOCKED_TOKEN = "ALPHA_BRAIN_TASK_BLOCKED"
QA_EVIDENCE_TOKEN = "ALPHA_BRAIN_QA_EVIDENCE:"
SDLC_SKILL_NAME = "multi-agent-sdlc"
REQUIRED_REVIEW_TOOLS = frozenset({"build_or_update_graph_tool", "get_review_context_tool"})


class AGYAttemptStatus(str, Enum):
    """Typed status of a single AGY execution attempt."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    RATE_LIMITED = "rate_limited"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class AntigravityAttemptOutcome:
    """Typed execution outcome structure for one AGY attempt."""

    conversation_id: str
    model: str
    pid: int | None = None
    exit_code: int = 0
    status: AGYAttemptStatus = AGYAttemptStatus.FAILED
    changed_files: tuple[str, ...] = ()
    diff_summary: str = ""
    artifacts: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    gate_evidence: dict[str, Any] | None = None
    tool_names: tuple[str, ...] = ()
    final_message: str = ""
    transcript_path: Path | None = None
    qa_evidence: dict[str, Any] | None = None
    blocked_reason: str | None = None

    @property
    def completed(self) -> bool:
        return self.status == AGYAttemptStatus.SUCCEEDED


@dataclass(frozen=True)
class AntigravityDispatch:
    """Structured terminal result from one official AGY CLI task execution."""

    conversation_id: str
    completed: bool
    blocked_reason: str | None
    tool_names: tuple[str, ...]
    final_message: str
    transcript_path: Path | None
    qa_evidence: dict[str, Any] | None = None
    pid: int | None = None
    exit_code: int = 0
    model: str = ""
    status: AGYAttemptStatus = AGYAttemptStatus.FAILED
    changed_files: tuple[str, ...] = ()
    diff_summary: str = ""
    artifacts: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    gate_evidence: dict[str, Any] | None = None
    events: tuple[dict[str, Any], ...] = ()


@asynccontextmanager
async def _optional_credential_lease(account_id: str):
    if settings.MODEL_ROUTING_ENABLED:
        async with acquire_credential_lease(account_id) as lease:
            yield lease
    else:
        yield None


def evaluate_agy_execution_outcome(
    *,
    conversation_id: str = "",
    model: str = "",
    pid: int | None = None,
    exit_code: int = 0,
    raw_status: AGYAttemptStatus | str | None = None,
    events: Sequence[Mapping[str, Any]] | Sequence[Any] = (),
    stderr: str = "",
    response_text: str = "",
    expected_qa_gates: tuple[str, ...] = (),
    expected_project_id: str = "",
    require_qa_audit: bool = False,
    forbid_external_dependencies: bool = False,
    changed_files: tuple[str, ...] = (),
    diff_summary: str = "",
    artifacts: tuple[str, ...] = (),
    transcript_path: Path | None = None,
) -> AntigravityAttemptOutcome:
    """
    Pure deterministic helper evaluating an AGY execution turn.
    Refuses success when exit code is nonzero, timeout/cancel/rate-limit occurs,
    tool calls are missing, or required QA evidence is missing/invalid.
    """
    # 1. Explicit cancellation or timeout status overrides
    if raw_status is not None:
        status_enum = AGYAttemptStatus(raw_status) if isinstance(raw_status, str) else raw_status
        if status_enum in {
            AGYAttemptStatus.CANCELLED,
            AGYAttemptStatus.TIMED_OUT,
            AGYAttemptStatus.RATE_LIMITED,
            AGYAttemptStatus.BLOCKED,
        }:
            reason = stderr or f"AGY execution flagged as {status_enum.value}"
            return AntigravityAttemptOutcome(
                conversation_id=conversation_id,
                model=model,
                pid=pid,
                exit_code=exit_code,
                status=status_enum,
                changed_files=changed_files,
                diff_summary=diff_summary,
                artifacts=artifacts,
                blockers=(reason,),
                tool_names=(),
                final_message=response_text,
                transcript_path=transcript_path,
                blocked_reason=reason,
            )

    # 2. Non-zero exit code check
    if exit_code != 0:
        status = AGYAttemptStatus.TIMED_OUT if exit_code == -1 else AGYAttemptStatus.FAILED
        error = stderr or f"AGY CLI process exited with non-zero exit code {exit_code}"
        return AntigravityAttemptOutcome(
            conversation_id=conversation_id,
            model=model,
            pid=pid,
            exit_code=exit_code,
            status=status,
            changed_files=changed_files,
            diff_summary=diff_summary,
            artifacts=artifacts,
            blockers=(error,),
            tool_names=(),
            final_message=response_text,
            transcript_path=transcript_path,
            blocked_reason=error,
        )

    # 3. Rate-limit and quota detection
    lower_stderr = stderr.lower()
    lower_resp = response_text.lower()
    if (
        "rate limit" in lower_stderr
        or "rate_limit" in lower_stderr
        or "429" in lower_stderr
        or "quota exceeded" in lower_stderr
        or "resource_exhausted" in lower_stderr
        or "rate limit" in lower_resp
        or "resource_exhausted" in lower_resp
    ):
        return AntigravityAttemptOutcome(
            conversation_id=conversation_id,
            model=model,
            pid=pid,
            exit_code=exit_code,
            status=AGYAttemptStatus.RATE_LIMITED,
            changed_files=changed_files,
            diff_summary=diff_summary,
            artifacts=artifacts,
            blockers=("Rate limit or API quota exceeded",),
            tool_names=(),
            final_message=response_text,
            transcript_path=transcript_path,
            blocked_reason="Rate limit or API quota exceeded",
        )

    # 4. Event processing
    tool_names_set: set[str] = set()
    policy_violations: list[str] = []
    parsed_conversation_id = conversation_id
    response = response_text
    result_event: dict[str, Any] | None = None
    full_response = ""

    for event in events:
        if event.get("event") == "init":
            parsed_conversation_id = str(event.get("conversation_id") or parsed_conversation_id)
        if event.get("event") == "step_update":
            step = event.get("step_update")
            if isinstance(step, dict) and step.get("step_type") == "agent_response":
                full_response += str(step.get("text_delta", ""))
            if isinstance(step, dict) and step.get("step_type") == "tool":
                name = step.get("tool_name")
                info = step.get("tool_info")
                if not isinstance(name, str) and isinstance(info, dict):
                    name = info.get("name")

                if isinstance(name, str):
                    tool_names_set.add(name)
                if isinstance(info, dict):
                    parameters = info.get("parameters")
                    if isinstance(parameters, dict):
                        server = parameters.get("ServerName")
                        tool = parameters.get("ToolName")
                        if isinstance(server, str) and isinstance(tool, str):
                            tool_names_set.add(f"{server}/{tool}")

                # Check for browser tool usage
                is_browser_tool = isinstance(name, str) and (
                    "chrome-devtools" in name.lower() or "browser" in name.lower()
                )
                if isinstance(info, dict):
                    parameters = info.get("parameters")
                    if isinstance(parameters, dict):
                        server = str(parameters.get("ServerName") or "")
                        if "chrome-devtools" in server.lower() or "browser" in server.lower():
                            is_browser_tool = True
                if is_browser_tool:
                    policy_violations.append("Forbidden browser tool usage detected")

                if name == "run_command" and isinstance(info, dict):
                    parameters = info.get("parameters")
                    if isinstance(parameters, dict):
                        cmdline = str(parameters.get("CommandLine", "")).lower()
                        for pattern in [
                            "npm install",
                            "npm ci",
                            "npx playwright install",
                            "curl",
                            "wget",
                        ]:
                            if pattern in cmdline:
                                policy_violations.append(
                                    f"Forbidden command execution detected: {pattern}"
                                )
        if event.get("event") == "result" and isinstance(event.get("result"), dict):
            result_event = event["result"]
            parsed_conversation_id = str(
                result_event.get("conversation_id") or parsed_conversation_id
            )
            response = str(result_event.get("response") or response)

    tools_tuple = tuple(sorted(tool_names_set))

    # 4b. Command policy check
    if forbid_external_dependencies and policy_violations:
        error_msg = policy_violations[0]
        return AntigravityAttemptOutcome(
            conversation_id=parsed_conversation_id,
            model=model,
            pid=pid,
            exit_code=exit_code,
            status=AGYAttemptStatus.BLOCKED,
            changed_files=changed_files,
            diff_summary=diff_summary,
            artifacts=artifacts,
            blockers=(error_msg,),
            tool_names=tools_tuple,
            final_message=response,
            transcript_path=transcript_path,
            blocked_reason=error_msg,
        )

    # 5. Result event status check
    if not result_event or result_event.get("status") != "SUCCESS":
        error_msg = str((result_event or {}).get("error") or stderr or "AGY CLI execution failed")
        return AntigravityAttemptOutcome(
            conversation_id=parsed_conversation_id,
            model=model,
            pid=pid,
            exit_code=exit_code,
            status=AGYAttemptStatus.FAILED,
            changed_files=changed_files,
            diff_summary=diff_summary,
            artifacts=artifacts,
            blockers=(error_msg,),
            tool_names=tools_tuple,
            final_message=response,
            transcript_path=transcript_path,
            blocked_reason=error_msg,
        )

    # 6 & 7. Terminal protocol token check
    # Parse final result assistant response by lines.
    final_marker = None
    blocked_msg = ""

    lines = [line.strip() for line in response.splitlines() if line.strip()]

    def is_valid_marker(line: str) -> tuple[str | None, str]:
        if line == COMPLETION_TOKEN:
            return COMPLETION_TOKEN, ""
        elif line.startswith(BLOCKED_TOKEN):
            remainder = line[len(BLOCKED_TOKEN) :].strip()
            if not remainder or remainder.startswith(":"):
                return BLOCKED_TOKEN, remainder.lstrip(": ")
        return None, ""

    valid_markers = []
    for i, line in enumerate(lines):
        marker, msg = is_valid_marker(line)
        if marker:
            valid_markers.append((i, marker, msg))

    if len(valid_markers) == 1:
        marker_idx, marker, msg = valid_markers[0]
        if marker_idx == len(lines) - 1:
            final_marker = marker
            blocked_msg = msg

    if final_marker == BLOCKED_TOKEN:
        blocked_msg = blocked_msg or "Blocked without reason"
        return AntigravityAttemptOutcome(
            conversation_id=parsed_conversation_id,
            model=model,
            pid=pid,
            exit_code=exit_code,
            status=AGYAttemptStatus.BLOCKED,
            changed_files=changed_files,
            diff_summary=diff_summary,
            artifacts=artifacts,
            blockers=(blocked_msg,),
            tool_names=tools_tuple,
            final_message=response,
            transcript_path=transcript_path,
            blocked_reason=blocked_msg,
        )

    if final_marker != COMPLETION_TOKEN:
        error_msg = f"AGY response omitted terminal {COMPLETION_TOKEN} or {BLOCKED_TOKEN}"
        return AntigravityAttemptOutcome(
            conversation_id=parsed_conversation_id,
            model=model,
            pid=pid,
            exit_code=exit_code,
            status=AGYAttemptStatus.FAILED,
            changed_files=changed_files,
            diff_summary=diff_summary,
            artifacts=artifacts,
            blockers=(error_msg,),
            tool_names=tools_tuple,
            final_message=response,
            transcript_path=transcript_path,
            blocked_reason=error_msg,
        )

    # 8. Required code review tools check
    missing_tools = {
        required
        for required in REQUIRED_REVIEW_TOOLS
        if not any(required in name for name in tool_names_set)
    }
    if missing_tools:
        error_msg = "Required code-review graph calls missing: " + ", ".join(sorted(missing_tools))
        return AntigravityAttemptOutcome(
            conversation_id=parsed_conversation_id,
            model=model,
            pid=pid,
            exit_code=exit_code,
            status=AGYAttemptStatus.FAILED,
            changed_files=changed_files,
            diff_summary=diff_summary,
            artifacts=artifacts,
            blockers=(error_msg,),
            tool_names=tools_tuple,
            final_message=response,
            transcript_path=transcript_path,
            blocked_reason=error_msg,
        )

    # 9. QA Evidence validation
    qa_evidence, evidence_error = AntigravityLiveBridge._parse_qa_evidence(
        response + "\n" + full_response,
        expected_qa_gates,
        expected_project_id,
        require_qa_audit=require_qa_audit,
    )
    if evidence_error is not None:
        return AntigravityAttemptOutcome(
            conversation_id=parsed_conversation_id,
            model=model,
            pid=pid,
            exit_code=exit_code,
            status=AGYAttemptStatus.FAILED,
            changed_files=changed_files,
            diff_summary=diff_summary,
            artifacts=artifacts,
            blockers=(evidence_error,),
            tool_names=tools_tuple,
            final_message=response,
            transcript_path=transcript_path,
            qa_evidence=qa_evidence,
            gate_evidence=qa_evidence,
            blocked_reason=evidence_error,
        )

    # 10. All checks passed -> SUCCEEDED
    return AntigravityAttemptOutcome(
        conversation_id=parsed_conversation_id,
        model=model,
        pid=pid,
        exit_code=0,
        status=AGYAttemptStatus.SUCCEEDED,
        changed_files=changed_files,
        diff_summary=diff_summary,
        artifacts=artifacts,
        blockers=(),
        gate_evidence=qa_evidence,
        tool_names=tools_tuple,
        final_message=response,
        transcript_path=transcript_path,
        qa_evidence=qa_evidence,
        blocked_reason=None,
    )


class AntigravityLiveBridge:
    @staticmethod
    def _resolve_executable(exe: str) -> str:
        from pathlib import Path

        bin_dir = Path(sys.executable).parent
        resolved = bin_dir / exe
        if resolved.exists():
            return str(resolved)
        return exe

    """Runs project-scoped tasks through AGY CLI; never IDE/private database scraping."""

    def __init__(self) -> None:
        self.agy_bin = settings.ANTIGRAVITY_CLI_BIN
        self.session_store_dir = settings.MEMORY_GRAPH_PATH / "antigravity_sessions"

    def check_readiness(self) -> tuple[bool, str]:
        if not settings.ANTIGRAVITY_EXECUTION_ENABLED:
            return False, "Antigravity execution is disabled by configuration"
        if not self.agy_bin.is_file() or not self.agy_bin.stat().st_mode & 0o111:
            return False, f"Official AGY CLI not found or not executable at {self.agy_bin}"
        if not settings.ANTIGRAVITY_SDLC_SKILL_PATH.is_file():
            return False, (
                f"Required Antigravity SDLC skill not found at "
                f"{settings.ANTIGRAVITY_SDLC_SKILL_PATH}"
            )
        return True, "Official AGY CLI and Alpha Brain SDLC skill are available"

    async def dispatch(
        self,
        task: TaskEnvelope,
        worktree_path: Path,
        attempt_id: str,
        session_dir: Path | None = None,
    ) -> AntigravityDispatch:
        """Create/resume only task project conversation, then parse AGY event evidence."""

        ready, reason = self.check_readiness()
        if not ready:
            raise RuntimeError(reason)

        forbid_deps = (
            "dependency-free" in (task.objective or "").lower()
            or "no external dependency acquisition" in (task.objective or "").lower()
            or "dependency-free" in (task.detailed_instructions or "").lower()
            or "no external dependency acquisition" in (task.detailed_instructions or "").lower()
        )

        max_attempts = settings.MAX_ELIGIBLE_ATTEMPTS if settings.MODEL_ROUTING_ENABLED else 1
        attempts_made = 0

        while attempts_made < max_attempts:
            attempts_made += 1

            req = RoutingRequest(
                project_id=task.project_id,
                task_id=task.task_id,
                attempt_id=attempt_id,
                stage=ExecutionStage.IMPLEMENT,
                risk_class=task.risk_class.value,
                complexity_class="medium",
            )
            decision = call_model_router(req)

            if decision.status == RoutingDecisionStatus.BLOCKED:
                return AntigravityDispatch(
                    conversation_id="",
                    completed=False,
                    blocked_reason="Router blocked execution: "
                    + ", ".join(decision.rationale_codes),
                    tool_names=(),
                    final_message="",
                    transcript_path=None,
                )
            if decision.status == RoutingDecisionStatus.RATE_LIMITED:
                return AntigravityDispatch(
                    conversation_id="",
                    completed=False,
                    blocked_reason="Router rate limited globally",
                    tool_names=(),
                    final_message="",
                    transcript_path=None,
                )

            account_id = decision.account_id or "legacy_default"
            model = decision.model or settings.ANTIGRAVITY_MODEL
            effort = decision.effort or settings.ANTIGRAVITY_EFFORT

            try:
                async with _optional_credential_lease(account_id) as _lease:
                    conversation_id, is_new_project = self._get_project_conversation(task)
                    raw = await self._run_agy(
                        prompt=self._build_task_prompt(task, worktree_path, is_new_project),
                        worktree_path=worktree_path,
                        conversation_id=conversation_id,
                        is_new_project=is_new_project,
                        timeout_seconds=min(
                            task.lease_timeout_seconds, settings.ANTIGRAVITY_TASK_TIMEOUT_SECONDS
                        ),
                        log_path=self._turn_log_path(session_dir, "implementation"),
                        model=model,
                        effort=effort,
                    )

                    if self._is_rate_limited(raw):
                        report_model_outcome(account_id, model, "rate_limit")
                        if attempts_made >= max_attempts:
                            return AntigravityDispatch(
                                conversation_id=conversation_id or "",
                                completed=False,
                                blocked_reason="exhausted eligible accounts via 429",
                                tool_names=(),
                                final_message="",
                                transcript_path=None,
                            )
                        continue

                    report_model_outcome(account_id, model, "success")

                    dispatch_res = self._parse_agy_result(
                        raw,
                        expected_qa_gates=tuple(
                            gate.value
                            for gate in task.acceptance_plan.required_gates
                            if gate.value not in {"independent_review", "code_review_graph"}
                        ),
                        expected_project_id=task.project_id,
                        forbid_external_dependencies=forbid_deps,
                    )
                    if not dispatch_res.conversation_id:
                        raise RuntimeError("AGY result did not include a conversation ID")
                    dispatch_res = replace(
                        dispatch_res,
                        transcript_path=self._turn_log_path(session_dir, "implementation"),
                    )
                    if is_new_project:
                        self._write_record(
                            self._project_store_path(task.task_id),
                            {
                                "project_id": task.task_id,
                                "repo_path": str(Path(task.repo).expanduser().resolve()),
                                "conversation_id": dispatch_res.conversation_id,
                                "created_at": datetime.now(UTC).isoformat(),
                                "updated_at": datetime.now(UTC).isoformat(),
                                "source": "official_agy_cli_new_project",
                            },
                        )
                    if self._needs_compliance_repair(dispatch_res):
                        repair_raw = await self._run_agy(
                            prompt=self._build_compliance_repair_prompt(
                                task, worktree_path, dispatch_res
                            ),
                            worktree_path=worktree_path,
                            conversation_id=dispatch_res.conversation_id,
                            is_new_project=False,
                            timeout_seconds=min(
                                task.lease_timeout_seconds,
                                settings.ANTIGRAVITY_TASK_TIMEOUT_SECONDS,
                            ),
                            log_path=self._turn_log_path(session_dir, "compliance-repair"),
                            model=model,
                            effort=effort,
                        )
                        if self._is_rate_limited(repair_raw):
                            report_model_outcome(account_id, model, "rate_limit")
                            if attempts_made >= max_attempts:
                                return AntigravityDispatch(
                                    conversation_id=dispatch_res.conversation_id,
                                    completed=False,
                                    blocked_reason="exhausted eligible accounts via 429",
                                    tool_names=(),
                                    final_message="",
                                    transcript_path=None,
                                )
                            continue

                        dispatch_res = self._parse_agy_result(
                            self._combine_turn_evidence(raw, repair_raw),
                            expected_qa_gates=tuple(
                                gate.value
                                for gate in task.acceptance_plan.required_gates
                                if gate.value not in {"independent_review", "code_review_graph"}
                            ),
                            expected_project_id=task.project_id,
                            forbid_external_dependencies=forbid_deps,
                        )
                        dispatch_res = replace(
                            dispatch_res,
                            transcript_path=self._turn_log_path(session_dir, "compliance-repair"),
                        )
                    if dispatch_res.completed:
                        audit_raw = await self._run_agy(
                            prompt=self._build_qa_audit_prompt(task, worktree_path),
                            worktree_path=worktree_path,
                            conversation_id=dispatch_res.conversation_id,
                            is_new_project=False,
                            timeout_seconds=min(
                                task.lease_timeout_seconds,
                                settings.ANTIGRAVITY_TASK_TIMEOUT_SECONDS,
                            ),
                            log_path=self._turn_log_path(session_dir, "qa-audit"),
                            model=model,
                            effort=effort,
                        )
                        if self._is_rate_limited(audit_raw):
                            report_model_outcome(account_id, model, "rate_limit")
                            if attempts_made >= max_attempts:
                                return AntigravityDispatch(
                                    conversation_id=dispatch_res.conversation_id,
                                    completed=False,
                                    blocked_reason="exhausted eligible accounts via 429",
                                    tool_names=(),
                                    final_message="",
                                    transcript_path=None,
                                )
                            continue

                        dispatch_res = self._parse_agy_result(
                            audit_raw,
                            expected_qa_gates=tuple(
                                gate.value
                                for gate in task.acceptance_plan.required_gates
                                if gate.value not in {"independent_review", "code_review_graph"}
                            ),
                            expected_project_id=task.project_id,
                            require_qa_audit=True,
                            forbid_external_dependencies=forbid_deps,
                        )
                        dispatch_res = replace(
                            dispatch_res,
                            transcript_path=self._turn_log_path(session_dir, "qa-audit"),
                        )

                    return dispatch_res

            except CredentialLockTimeoutError:
                return AntigravityDispatch(
                    conversation_id="",
                    completed=False,
                    blocked_reason="credential_lock_timeout",
                    tool_names=(),
                    final_message="",
                    transcript_path=None,
                )
            except SwitchCommandError:
                report_model_outcome(account_id, model, "auth_failed")
                return AntigravityDispatch(
                    conversation_id="",
                    completed=False,
                    blocked_reason="auth_failed",
                    tool_names=(),
                    final_message="",
                    transcript_path=None,
                )
            except IdentityMismatchError:
                report_model_outcome(account_id, model, "auth_failed")
                return AntigravityDispatch(
                    conversation_id="",
                    completed=False,
                    blocked_reason="auth_failed",
                    tool_names=(),
                    final_message="",
                    transcript_path=None,
                )

        return AntigravityDispatch(
            conversation_id="",
            completed=False,
            blocked_reason="exhausted eligible accounts",
            tool_names=(),
            final_message="",
            transcript_path=None,
        )

    @staticmethod
    def _needs_compliance_repair(dispatch: AntigravityDispatch) -> bool:
        """Retry one bounded turn only when AGY completed work but omitted required proof."""
        return bool(
            dispatch.conversation_id
            and COMPLETION_TOKEN in dispatch.final_message
            and dispatch.blocked_reason
            and dispatch.blocked_reason.startswith("Required code-review graph calls missing:")
        )

    @staticmethod
    def _combine_turn_evidence(
        implementation_raw: dict[str, Any], repair_raw: dict[str, Any]
    ) -> dict[str, Any]:
        """Keep proof from bounded same-task repair turns; final result stays repair turn."""
        return {
            **repair_raw,
            "events": [
                *implementation_raw.get("events", []),
                *repair_raw.get("events", []),
            ],
        }

    def _project_store_path(self, task_id: str) -> Path:
        return cast(Path, self.session_store_dir / f"{task_id}.json")

    def _get_project_conversation(self, task: TaskEnvelope) -> tuple[str | None, bool]:
        """Return only stored conversation bound to exact task and repository."""
        repo_path = str(Path(task.repo).expanduser().resolve())
        record = self._load_record(self._project_store_path(task.task_id))
        if record and record.get("repo_path") == repo_path:
            conversation_id = record.get("conversation_id")
            if isinstance(conversation_id, str) and CONVERSATION_ID_PATTERN.fullmatch(
                conversation_id
            ):
                return conversation_id, False
        if task.session_id:
            if not CONVERSATION_ID_PATTERN.fullmatch(task.session_id):
                raise RuntimeError("Configured Antigravity project conversation ID is invalid")
            self._write_record(
                self._project_store_path(task.task_id),
                {
                    "project_id": task.task_id,
                    "repo_path": repo_path,
                    "conversation_id": task.session_id,
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "source": "pre_registered_official_agy_conversation",
                },
            )
            return task.session_id, False
        configured_conversation = settings.ALPHA_BRAIN_ANTIGRAVITY_CONVERSATION_ID
        if configured_conversation and Path(repo_path) == settings.WORKSPACE_ROOT.resolve():
            if not CONVERSATION_ID_PATTERN.fullmatch(configured_conversation):
                raise RuntimeError("Configured AlphaBrain Antigravity conversation ID is invalid")
            self._write_record(
                self._project_store_path(task.task_id),
                {
                    "project_id": task.task_id,
                    "repo_path": repo_path,
                    "conversation_id": configured_conversation,
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "source": "configured_alphabrain_conversation",
                },
            )
            return configured_conversation, False
        return None, True

    async def _run_agy(
        self,
        *,
        prompt: str,
        worktree_path: Path,
        conversation_id: str | None,
        is_new_project: bool,
        timeout_seconds: int,
        log_path: Path | None = None,
        model: str | None = None,
        effort: str | None = None,
    ) -> dict[str, Any]:
        """Run one headless AGY turn with structured stdout events."""
        args = [
            str(self.agy_bin),
            "--output-format",
            "stream-json",
            "--print-timeout",
            f"{max(60, timeout_seconds)}s",
            "--mode",
            "accept-edits",
            "--model",
            model or settings.ANTIGRAVITY_MODEL,
        ]
        if "claude" not in (model or "").lower():
            args.extend(["--effort", effort or settings.ANTIGRAVITY_EFFORT])
        args.extend(["--print", prompt])

        # Inject the programmatic safety hook instead of the dangerous flag
        hooks_dir = worktree_path / ".agents"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hooks_file = hooks_dir / "hooks.json"

        hook_script = Path(__file__).parent / "safety_hook.py"

        hooks_config = {
            "worktree-safety-gate": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"ALPHA_WORKTREE_PATH='{worktree_path!s}' '{sys.executable}' '{hook_script!s}'",
                                "timeout": 5,
                            }
                        ],
                    }
                ]
            }
        }
        hooks_file.write_text(json.dumps(hooks_config))
        if is_new_project:
            args.insert(1, "--new-project")
        else:
            assert conversation_id is not None
            args[1:1] = ["--conversation", conversation_id]

        args.append("--dangerously-skip-permissions")
        # Do not use asyncio subprocess pipes here. AGY may spawn descendants
        # which inherit pipe descriptors; then communicate()/wait() can hang
        # after AGY itself has exited. File-backed logs plus poll() give this
        # supervisor a bounded, observable lifecycle.
        with tempfile.TemporaryDirectory(prefix="alpha-agy-") as log_dir:
            stdout_path = Path(log_dir) / "stdout.ndjson"
            stderr_path = Path(log_dir) / "stderr.log"
            with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
                print("DEBUG AGY ARGS:", args, file=sys.stderr)
                process = subprocess.Popen(
                    args,
                    cwd=str(worktree_path),
                    stdout=stdout_file,
                    stderr=stderr_file,
                    start_new_session=True,
                )
                deadline = asyncio.get_running_loop().time() + max(90, timeout_seconds + 30)
                try:
                    while process.poll() is None:
                        if asyncio.get_running_loop().time() >= deadline:
                            self._terminate_process_group(process.pid)
                            await asyncio.sleep(2)
                            if process.poll() is None:
                                self._kill_process_group(process.pid)
                            return {
                                "returncode": -1,
                                "events": [],
                                "stderr": "AGY CLI timed out",
                            }
                        await asyncio.sleep(0.5)
                except asyncio.CancelledError:
                    self._terminate_process_group(process.pid)
                    await asyncio.sleep(0.2)
                    if process.poll() is None:
                        self._kill_process_group(process.pid)
                    raise

                # Background descendants are never valid post-turn work.
                self._terminate_process_group(process.pid)

            stdout = stdout_path.read_bytes()
            stderr = stderr_path.read_bytes()

            with open("/tmp/agy_real_crash.log", "ab") as f:
                f.write(b"--- AGY STDERR ---\n")
                f.write(stderr)
                f.write(b"\n")

        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(
                json.dumps(
                    {
                        "recorded_at": datetime.now(UTC).isoformat(),
                        "returncode": process.returncode,
                        "stdout": stdout.decode("utf-8", errors="replace"),
                        "stderr": stderr.decode("utf-8", errors="replace"),
                    },
                    indent=2,
                )
            )
            log_path.chmod(0o600)

        events: list[dict[str, Any]] = []
        for line in stdout.decode("utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
        return {
            "returncode": process.returncode,
            "events": events,
            "stderr": stderr.decode("utf-8", errors="replace")[-4000:],
        }

    @staticmethod
    def _turn_log_path(session_dir: Path | None, turn: str) -> Path | None:
        if not session_dir:
            return None
        return session_dir / ".system_generated" / "logs" / f"agy-{turn}.json"

    @staticmethod
    def _terminate_process_group(pid: int | None) -> None:
        """End AGY's isolated process group without touching other work."""
        if not pid:
            return
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            return

    @staticmethod
    def _kill_process_group(pid: int | None) -> None:
        """Force-stop a timed-out AGY process group after graceful shutdown."""
        if not pid:
            return
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            return

    @staticmethod
    def _is_rate_limited(raw: dict[str, Any]) -> bool:
        if raw.get("returncode") == 429:
            return True
        raw_output = (
            raw.get("stdout", "").decode("utf-8", errors="replace")
            if isinstance(raw.get("stdout"), bytes)
            else str(raw.get("stdout", ""))
        )
        raw_err = raw.get("stderr", "")

        with open("/tmp/agy_crash.log", "a") as f:
            f.write(f"--- RUN ---\nSTDOUT:\n{raw_output}\nSTDERR:\n{raw_err}\n")

        response_text = ""
        for event in raw.get("events", []):
            if event.get("event") == "result":
                res = event.get("result", {})
                if res.get("status") == "SUCCESS":
                    response_text = res.get("response", "")
        lower_stderr = raw_err.lower()
        lower_resp = response_text.lower()
        return (
            "rate limit" in lower_stderr
            or "rate_limit" in lower_stderr
            or "429" in lower_stderr
            or "quota exceeded" in lower_stderr
            or "resource_exhausted" in lower_stderr
            or "rate limit" in lower_resp
            or "resource_exhausted" in lower_resp
        )

    @classmethod
    def _parse_agy_result(
        cls,
        raw: dict[str, Any],
        *,
        expected_qa_gates: tuple[str, ...],
        expected_project_id: str,
        require_qa_audit: bool = False,
        forbid_external_dependencies: bool = False,
    ) -> AntigravityDispatch:
        """Reject quiet, malformed, or unproven AGY completion."""
        outcome = evaluate_agy_execution_outcome(
            exit_code=raw.get("returncode", 0),
            events=raw.get("events", []),
            stderr=raw.get("stderr", ""),
            expected_qa_gates=expected_qa_gates,
            expected_project_id=expected_project_id,
            require_qa_audit=require_qa_audit,
            forbid_external_dependencies=forbid_external_dependencies,
        )
        return AntigravityDispatch(
            conversation_id=outcome.conversation_id,
            completed=outcome.completed,
            blocked_reason=outcome.blocked_reason,
            tool_names=outcome.tool_names,
            final_message=outcome.final_message,
            transcript_path=outcome.transcript_path,
            qa_evidence=outcome.qa_evidence,
            pid=outcome.pid,
            exit_code=outcome.exit_code,
            model=outcome.model,
            status=outcome.status,
            changed_files=outcome.changed_files,
            diff_summary=outcome.diff_summary,
            artifacts=outcome.artifacts,
            blockers=outcome.blockers,
            gate_evidence=outcome.gate_evidence,
            events=tuple(raw.get("events", [])),
        )

    def _build_task_prompt(
        self, task: TaskEnvelope, worktree_path: Path, is_new_project: bool
    ) -> str:
        forbid_deps = (
            "dependency-free" in (task.objective or "").lower()
            or "no external dependency acquisition" in (task.objective or "").lower()
            or "dependency-free" in (task.detailed_instructions or "").lower()
            or "no external dependency acquisition" in (task.detailed_instructions or "").lower()
        )
        dependency_rule = (
            "\n- NO package managers or external network commands allowed. This is a strict dependency-free execution."
            if forbid_deps
            else ""
        )

        if task.acceptance_plan.browser_smoke_url:
            browser_rule = "Browser smoke is declared. You must gather browser/E2E + keyboard + responsive evidence using browser capabilities."
        else:
            browser_rule = "Browser smoke is NOT independently declared. Do NOT trigger browser-driver/download/install attempts. You may attach existing local evidence but no network acquisition."

        project_note = (
            "New dedicated project conversation."
            if is_new_project
            else "Existing dedicated project conversation."
        )
        required_gates_json = json.dumps(
            [
                gate.value
                for gate in task.acceptance_plan.required_gates
                if gate.value not in {"independent_review", "code_review_graph"}
            ]
        )
        declared_commands = (
            "\n".join(
                f"- {command.gate_type.value}: {' '.join([self._resolve_executable(command.executable), *command.args])}"
                for command in task.acceptance_plan.commands
            )
            or "- No executable gates declared"
        )

        return f"""AlphaBrain Junior Execution Contract (Version 1)
{project_note}

1. IMMUTABLE INPUTS (Scope strict boundary):
Task ID: {task.task_id}
Project ID: {task.project_id}
Worktree: {worktree_path}
Base commit: [Provided by Git]
Allowed paths: {", ".join(task.allowed_paths)}
Allowed tools: {", ".join(task.allowed_tools) or "Antigravity built-in tools only"}
Risk class: {task.risk_class.value}
Accepted gate commands:
{declared_commands}

Objective: {task.objective}
Detailed instructions: {task.detailed_instructions or "None"}

2. PHASE 0 (Orientation):
Validate scope. Output max five-line plan.

3. PRE-EDIT GRAPH CHECKS:
Call `code-review-graph` MCP tools: `build_or_update_graph_tool` then `get_review_context_tool`. Respect tool schema.

4. BOUNDED IMPLEMENTATION:
Implement ONLY in allowed paths.

5. EXACT DECLARED COMMANDS:
Run exact declared acceptance commands. Capture exit code and output. NEVER substitute a different command.
{browser_rule}

6. POST-EDIT GRAPH CHECKS:
Call review graph tools again. Fix material findings.

7. QA MANIFEST:
Emit a single-line JSON manifest before termination exactly matching this format (no extra colons or newlines):
{QA_EVIDENCE_TOKEN}{{"contract_version": 1, "skill": "{SDLC_SKILL_NAME}", "testscript_root": "testscript", "project_id": "{task.project_id}", "task_id": "{task.task_id}", "executed_commands": [{{"command": "...", "exit_code": 0, "summary": "..."}}], "required_gates": {required_gates_json}, "passed_gates": [], "review_calls": 2, "security_review": {{"executed": true}}, "artifacts": [], "blockers": []}}

8. TERMINAL PROTOCOL:
- SUCCESS: ONLY after every gate passes (exit code 0), emit exactly {COMPLETION_TOKEN} on its own line. If resuming an existing conversation where gates have already passed, you MUST still emit {QA_EVIDENCE_TOKEN}<json> and {COMPLETION_TOKEN} on their own lines in this response.
- FAILURE: On blocked or failing gate, emit exactly {BLOCKED_TOKEN}: <exact reason>. NEVER emit {COMPLETION_TOKEN}.

9. EXPLICIT ANTI-PATTERNS (Will cause immediate contract termination):
- No claiming tests pass without actual captured command output.
- No silent permission denial (fail loudly if denied).
- No self-approval, no deployments, no remote push commands.
- No production side effects (mutations outside local test bounds).
- No roadmap changes or broader refactoring beyond task objective.{dependency_rule}
- No invented fallback models or identity shifting.

10. TOOL CALL CONSTRAINTS (CRITICAL):
- When calling tools, NEVER wrap arguments in double quotes. Pass them as raw strings.
- All integer parameters in tool calls MUST be passed as JSON integers, NEVER as strings.

11. CONCURRENCY CONSTRAINT (CRITICAL):
- NEVER call multiple run_command tools concurrently. You MUST wait for the result of the first command before calling another command.

12. RETRY RULE:
The supervisor controls retries. The junior never reruns uncontrolled loops internally. Fail immediately upon unrecoverable state so the supervisor can send a narrow repair task with persisted evidence.
"""

    def _build_qa_audit_prompt(self, task: TaskEnvelope, worktree_path: Path) -> str:

        if task.acceptance_plan.browser_smoke_url:
            browser_rule = "For user-facing work, start local preview and exercise primary flows with\nreal browser clicks, keyboard input, validation errors, responsive layouts, and visual inspection."
        else:
            browser_rule = "Browser smoke is NOT independently declared. Do NOT attempt browser server, browser tool, driver/install/download, curl/wget, or network acquisition. Audit only allowed local source/tests and exact declared gates."

        required_gates = ", ".join(
            gate.value
            for gate in task.acceptance_plan.required_gates
            if gate.value not in {"independent_review", "code_review_graph"}
        )
        declared_commands = (
            "\n".join(
                f"- {command.gate_type.value}: {' '.join([self._resolve_executable(command.executable), *command.args])}"
                for command in task.acceptance_plan.commands
            )
            or "- No executable gates declared"
        )

        allowed_paths_str = ", ".join(task.allowed_paths)
        if ".gitignore" in task.allowed_paths:
            hygiene_rule = "Since .gitignore is explicitly in allowed paths, you may add or repair .gitignore and remove generated files from Git tracking."
        else:
            hygiene_rule = "Inspect source-control hygiene. If generated artifacts, dependencies, or caches require an undeclared path (e.g. .gitignore), do NOT modify it. Report it as an external blocker instead."

        return f"""You are now Alpha Brain's mandatory QA auditor and repair owner.

Project: {task.project_id}
Workspace: {worktree_path}
Original objective: {task.objective}
Allowed paths: {allowed_paths_str}
Required gates: {required_gates}
Declared commands (must run exactly):
{declared_commands}

Do not trust prior completion claims. Read the multi-agent-sdlc skill and independently audit
current implementation. {browser_rule}
Run relevant unit, build, security, accessibility, and regression checks.

You may edit ONLY the paths listed in 'Allowed paths'.
Do not add, remove, rename, stage, or modify any file outside allowed paths.

If any defect, missing test, weak evidence, malformed error state, or QA failure exists: diagnose
root cause. If the defect requires editing ANY file outside allowed paths, do NOT modify it. Report it as a genuine external blocker and emit {BLOCKED_TOKEN} with the reason.
Otherwise, repair it yourself in this same conversation, strictly within allowed paths, then rerun all affected checks. Repeat until
passing or genuine external blocker. Never stop merely to report a fix for another agent.

{hygiene_rule} Preserve package manifests, lockfiles, source, testscript/, docs, and evidence.
You MUST unconditionally call code-review-graph build_or_update_graph_tool and get_review_context_tool in this turn before finishing, even if you made no changes.
Do not deploy, push, access unrelated projects, or use dangerous permission bypasses.

Before success emit one {QA_EVIDENCE_TOKEN} JSON line matching SDLC schema plus:
  "qa_audit": {{"executed": true, "result": "passed", "defects_found": <integer>,
                "defects_fixed": <integer>, "browser_evidence": ["relative/path"]}}
Only then end exactly {COMPLETION_TOKEN}. If genuine blocker remains, end
{BLOCKED_TOKEN}: <specific reason>.
"""

    def _build_compliance_repair_prompt(
        self, task: TaskEnvelope, worktree_path: Path, dispatch: AntigravityDispatch
    ) -> str:
        return f"""Alpha Brain rejected previous completion due to missing execution proof.

Project: {task.project_id}
Workspace: {worktree_path}
Exact blocker: {dispatch.blocked_reason}

Do not start another project. First use code-review-graph `get_review_context_tool` now, inspect
its findings, and repair any material issue yourself. Preserve verified work unless a finding
requires a change. Rerun every declared gate, then emit updated {QA_EVIDENCE_TOKEN}<JSON> and
{COMPLETION_TOKEN}. Do not report completion without executing missing tool.
"""

    @staticmethod
    def _load_record(path: Path) -> dict[str, Any] | None:
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _write_record(path: Path, record: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2) + "\n")

    @staticmethod
    def _parse_qa_evidence(
        content: str,
        expected_qa_gates: tuple[str, ...],
        expected_project_id: str,
        *,
        require_qa_audit: bool = False,
        forbid_external_dependencies: bool = False,
    ) -> tuple[dict[str, Any] | None, str | None]:
        evidence_line = next(
            (
                line.strip()
                for line in reversed(content.splitlines())
                if line.strip().startswith(QA_EVIDENCE_TOKEN)
            ),
            None,
        )
        if evidence_line is None:
            return None, f"Missing {QA_EVIDENCE_TOKEN} manifest"
        try:
            evidence = json.loads(evidence_line[len(QA_EVIDENCE_TOKEN) :].strip())
        except json.JSONDecodeError as exc:
            return None, f"Invalid {QA_EVIDENCE_TOKEN} JSON: {exc.msg}"
        if not isinstance(evidence, dict):
            return None, "QA evidence manifest must be a JSON object"
        if evidence.get("skill") != SDLC_SKILL_NAME:
            return None, f"QA evidence must identify skill '{SDLC_SKILL_NAME}'"
        if evidence.get("project_id") != expected_project_id:
            return None, "QA evidence project_id does not match dispatched task"
        if evidence.get("testscript_root") != "testscript":
            return None, "QA evidence must use testscript as test harness root"
        passed_gates = evidence.get("passed_gates")
        if not isinstance(passed_gates, list) or not all(
            isinstance(gate, str) for gate in passed_gates
        ):
            return None, "QA evidence passed_gates must be a list of gate names"
        missing_gates = sorted(
            set(expected_qa_gates) - set(passed_gates) - {"independent_review", "code_review_graph"}
        )
        if missing_gates:
            return None, "QA evidence missing required gates: " + ", ".join(missing_gates)
        security_review = evidence.get("security_review")
        security_passed = isinstance(security_review, dict) and (
            security_review.get("executed") is True
            or str(security_review.get("status", "")).lower() == "passed"
        )
        if not security_passed:
            return None, "QA evidence missing executed security review"
        if "browser_smoke" in expected_qa_gates:
            browser_e2e = evidence.get("browser_e2e")
            browser_summary = evidence.get("browser_e2e_tests")
            browser_summary_passed = (
                isinstance(browser_summary, dict)
                and isinstance(browser_summary.get("total"), int)
                and browser_summary["total"] > 0
                and browser_summary.get("passed") == browser_summary["total"]
            )
            if not browser_summary_passed and (
                not isinstance(browser_e2e, dict)
                or browser_e2e.get("executed") is not True
                or browser_e2e.get("result") != "passed"
            ):
                return None, "QA evidence missing passed browser E2E proof"
        if require_qa_audit:
            qa_audit = evidence.get("qa_audit")
            if (
                not isinstance(qa_audit, dict)
                or qa_audit.get("executed") is not True
                or qa_audit.get("result") != "passed"
            ):
                return None, "QA evidence missing passed independent audit"
        return evidence, None
