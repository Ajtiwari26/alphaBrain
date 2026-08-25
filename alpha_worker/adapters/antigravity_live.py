"""Safe bridge to a running Antigravity IDE conversation.

This module creates one conversation per Alpha Brain project through the same
local ``agentapi`` route used by Unifold. It never opens the Antigravity UI,
searches for, or reuses arbitrary Antigravity conversations. The project
mapping lives in local Memory Graph only as orchestration state; Antigravity's
transcript remains execution record.
"""

import asyncio
import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from alpha_core.config import settings
from alpha_protocol import TaskEnvelope

CONVERSATION_ID_PATTERN = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
COMPLETION_TOKEN = "ALPHA_BRAIN_TASK_DONE"
BLOCKED_TOKEN = "ALPHA_BRAIN_TASK_BLOCKED"
QA_EVIDENCE_TOKEN = "ALPHA_BRAIN_QA_EVIDENCE:"
SDLC_SKILL_NAME = "multi-agent-sdlc"
REQUIRED_REVIEW_TOOLS = frozenset({"build_or_update_graph_tool", "get_review_context_tool"})


@dataclass(frozen=True)
class AntigravityDispatch:
    """Outcome from a single task message sent to Antigravity."""

    conversation_id: str
    completed: bool
    blocked_reason: str | None
    tool_names: tuple[str, ...]
    final_message: str
    transcript_path: Path | None
    qa_evidence: dict[str, Any] | None = None


class AntigravityLiveBridge:
    """Dispatches bounded worktree tasks through Antigravity's local agentapi."""

    def __init__(self) -> None:
        self.agentapi_bin = settings.ANTIGRAVITY_AGENTAPI_BIN
        self.oauth_token_file = settings.ANTIGRAVITY_OAUTH_TOKEN_FILE
        self.brain_dirs = settings.ANTIGRAVITY_BRAIN_DIRS
        self.hub_conversation_dir = Path.home() / ".gemini" / "antigravity" / "conversations"
        self.session_store_dir = settings.MEMORY_GRAPH_PATH / "antigravity_sessions"

    def check_readiness(self) -> tuple[bool, str]:
        if not settings.ANTIGRAVITY_EXECUTION_ENABLED:
            return False, "Antigravity execution is disabled by configuration"
        if not self.agentapi_bin.is_file():
            return False, f"Antigravity agentapi not found at {self.agentapi_bin}"
        if not self.oauth_token_file.is_file():
            return False, "Antigravity OAuth session is not available"
        if not settings.ANTIGRAVITY_SDLC_SKILL_PATH.is_file():
            return (
                False,
                f"Required Antigravity SDLC skill not found at {settings.ANTIGRAVITY_SDLC_SKILL_PATH}",
            )
        return True, "Antigravity agentapi and authenticated IDE session are available"

    async def dispatch(self, task: TaskEnvelope, worktree_path: Path) -> AntigravityDispatch:
        """Send task to its project conversation and wait for explicit completion."""
        ready, reason = self.check_readiness()
        if not ready:
            raise RuntimeError(reason)

        conversation_id, is_new = await self._get_or_create_project_conversation(
            task, worktree_path
        )
        prompt = self._build_task_prompt(task, worktree_path, is_new)

        if is_new:
            success, output = await self._run_agentapi(
                "new-conversation",
                f"--model={settings.ANTIGRAVITY_MODEL}",
                f"--title=Alpha Brain {task.project_id}",
                prompt,
            )
            conversation_id = self._extract_conversation_id(output)
            if not success or not conversation_id:
                raise RuntimeError(
                    "Antigravity could not create isolated project conversation internally: "
                    + output
                )
            self._write_record(
                self._project_store_path(task.project_id),
                {
                    "project_id": task.project_id,
                    "repo_path": str(Path(task.repo).expanduser().resolve()),
                    "conversation_id": conversation_id,
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "source": "internal_agentapi_new_conversation",
                },
            )
            # new-conversation already contains first task message. Start at zero
            # so a fast agent response cannot be missed.
            before = 0
        else:
            assert conversation_id is not None
            before = self._conversation_cursor(conversation_id)
            success, output = await self._run_agentapi("send-message", conversation_id, prompt)
            if not success:
                raise RuntimeError(f"Antigravity send-message failed: {output}")

        assert conversation_id is not None
        expected_qa_gates = tuple(gate.value for gate in task.acceptance_plan.required_gates)
        return await self._wait_for_completion(
            conversation_id=conversation_id,
            after_line=before,
            timeout_seconds=min(
                task.lease_timeout_seconds, settings.ANTIGRAVITY_TASK_TIMEOUT_SECONDS
            ),
            expected_qa_gates=expected_qa_gates,
            expected_project_id=task.project_id,
        )

    async def _get_or_create_project_conversation(
        self,
        task: TaskEnvelope,
        worktree_path: Path,
    ) -> tuple[str | None, bool]:
        """Return only this project's conversation, or mark first internal creation."""
        store_path = self._project_store_path(task.project_id)
        repo_path = str(Path(task.repo).expanduser().resolve())
        record = self._load_record(store_path)
        if record and record.get("repo_path") == repo_path:
            conversation_id = record.get("conversation_id")
            if isinstance(conversation_id, str) and CONVERSATION_ID_PATTERN.fullmatch(
                conversation_id
            ):
                return conversation_id, False

        # A supplied ID remains supported for migration, but normal operation
        # creates this project's chat internally via agentapi in ``dispatch``.
        if task.session_id:
            if not CONVERSATION_ID_PATTERN.fullmatch(task.session_id):
                raise RuntimeError("Configured Antigravity project conversation ID is invalid")
            self._write_record(
                store_path,
                {
                    "project_id": task.project_id,
                    "repo_path": repo_path,
                    "conversation_id": task.session_id,
                    "created_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "source": "pre_registered_conversation",
                },
            )
            return task.session_id, False

        # Auto-discovery never crosses project boundaries. A 2.0 conversation
        # must be bound to this exact Alpha Brain or client repository.
        repo_root = Path(repo_path)
        if repo_root == settings.WORKSPACE_ROOT.resolve() or repo_root.is_relative_to(
            settings.CLIENT_PROJECTS_ROOT.resolve()
        ):
            hub_conversation_id = await self._discover_hub_project_conversation(repo_root)
            if hub_conversation_id:
                self._write_record(
                    store_path,
                    {
                        "project_id": task.project_id,
                        "repo_path": repo_path,
                        "conversation_id": hub_conversation_id,
                        "created_at": datetime.now(UTC).isoformat(),
                        "updated_at": datetime.now(UTC).isoformat(),
                        "source": "antigravity_2_project_discovery",
                    },
                )
                return hub_conversation_id, False

        return None, True

    def _build_task_prompt(
        self,
        task: TaskEnvelope,
        worktree_path: Path,
        is_new_project: bool,
    ) -> str:
        project_note = (
            "This is a new, project-dedicated conversation. Keep all later tasks for this "
            "same project in this conversation; do not mix other projects here."
            if is_new_project
            else "This is the existing dedicated conversation for this project."
        )
        detail = task.detailed_instructions or "No additional instructions."
        allowed_paths = ", ".join(task.allowed_paths)
        allowed_tools = ", ".join(task.allowed_tools) or "Antigravity built-in tools only"
        required_gates = ", ".join(gate.value for gate in task.acceptance_plan.required_gates)
        return f"""You are Alpha Brain's Antigravity builder for project {task.project_id}.

{project_note}

Workspace: {worktree_path}
Task ID: {task.task_id}
Objective: {task.objective}
Detailed instructions:
{detail}

Safety boundaries:
- Work only inside {worktree_path}.
- Modify only these paths: {allowed_paths}.
- Do not access unrelated repositories, credentials, or external services.
- Do not deploy, publish, push, or create pull requests.
- Allowed tools: {allowed_tools}.

Mandatory Alpha Brain SDLC skill:
1. Activate and read custom skill `{SDLC_SKILL_NAME}` from
   `{settings.ANTIGRAVITY_SDLC_SKILL_PATH}` before planning or editing.
2. Follow its Phases 0 through 8: intake, requirements, architecture/threat model,
   UX/accessibility, implementation, QA, fix loop, security, and founder handoff.
3. All test harnesses created or changed must live under `testscript/`. Do not use
   `testscripts/` or an ad-hoc test folder.
4. Required Alpha Brain acceptance gates for this task: {required_gates}.
5. For user-facing changes, run real local browser E2E, visual, keyboard, and
   responsive checks. Parser/unit checks alone cannot prove UI completion.
6. Before edits call code-review-graph `build_or_update_graph_tool` for {worktree_path},
   then `get_review_context_tool` for affected flows. Repeat both after edits and fix
   material findings.
7. Never claim a gate passed without command/output or artifact evidence.

Completion protocol:
- Before completion, emit one valid, single-line JSON manifest prefixed exactly
  `{QA_EVIDENCE_TOKEN}`. Use schema defined in `{SDLC_SKILL_NAME}`.
- Its `skill` must equal `{SDLC_SKILL_NAME}`, `project_id` must equal `{task.project_id}`,
  `testscript_root` must equal `testscript`, and `passed_gates` must include every
  required gate above.
- `security_review.executed` must be true for code changes. For a required browser_smoke
  gate, `browser_e2e.executed` must be true and result must be `passed`.
- Only after manifest and all checks finish, end final response with exactly
  `{COMPLETION_TOKEN}` on its own line.
- If blocked, end with `{BLOCKED_TOKEN}: <specific reason>` and do not emit completion token.
"""

    async def _run_agentapi(self, *args: str) -> tuple[bool, str]:
        env = await self._resolve_agentapi_env()
        try:
            process = await asyncio.create_subprocess_exec(
                str(self.agentapi_bin),
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        except TimeoutError:
            return False, "agentapi timed out after 30 seconds"
        output = (stdout or b"").decode("utf-8", errors="replace").strip()
        error = (stderr or b"").decode("utf-8", errors="replace").strip()
        return process.returncode == 0, output or error

    async def _resolve_agentapi_env(self) -> dict[str, str]:
        """Locate Alpha Brain's workspace agentapi endpoint without shell interpolation."""
        env = dict(os.environ)
        if env.get("ANTIGRAVITY_LS_ADDRESS") and env.get("ANTIGRAVITY_CSRF_TOKEN"):
            return env

        process = await asyncio.create_subprocess_exec(
            "ps",
            "aux",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        expected_workspace_id = "file_" + str(settings.WORKSPACE_ROOT).lstrip("/").replace("/", "_")
        lines = [
            line
            for line in stdout.decode("utf-8", errors="replace").splitlines()
            if "language_server" in line
        ]
        # IDE server owns project environment. Prefer current Alpha Brain
        # workspace, then another workspace server, then generic server only
        # when no workspace server exists.
        ranked_lines = sorted(
            lines,
            key=lambda line: (
                0
                if "/Applications/Antigravity.app/" in line and "--subclient_type hub" in line
                else 1
                if f"--workspace_id {expected_workspace_id}" in line
                else 2
                if "--workspace_id" in line
                else 3
            ),
        )
        for line in ranked_lines:
            if "language_server" not in line:
                continue
            pid_match = re.match(r"\S+\s+(\d+)", line)
            csrf_match = re.search(r"--csrf_token\s+([a-f0-9-]+)", line)
            if not pid_match or not csrf_match:
                continue
            for port in await self._listening_ports(pid_match.group(1)):
                candidate = dict(env)
                candidate["ANTIGRAVITY_LS_ADDRESS"] = f"127.0.0.1:{port}"
                candidate["ANTIGRAVITY_CSRF_TOKEN"] = csrf_match.group(1)
                if await self._probe_agentapi(candidate):
                    return candidate
        raise RuntimeError("Could not locate Antigravity agentapi language-server endpoint")

    async def _discover_hub_project_conversation(self, workspace_root: Path) -> str | None:
        """Find only a 2.0 conversation explicitly bound to this repository."""
        expected_workspace = str(workspace_root.resolve())
        workspace_marker = expected_workspace.encode()
        for database in sorted(
            self.hub_conversation_dir.glob("*.db"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        ):
            if not CONVERSATION_ID_PATTERN.fullmatch(database.stem):
                continue
            try:
                if workspace_marker not in database.read_bytes():
                    continue
            except OSError:
                continue
            success, response = await self._run_agentapi("get-conversation-metadata", database.stem)
            if success and expected_workspace in response:
                return database.stem
        return None

    async def _probe_agentapi(self, env: dict[str, str]) -> bool:
        process = await asyncio.create_subprocess_exec(
            str(self.agentapi_bin),
            "get-conversation-metadata",
            "00000000-0000-0000-0000-000000000000",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=5)
        except TimeoutError:
            return False
        output = (stdout + stderr).decode("utf-8", errors="replace").lower()
        return "connection error" not in output and "is not set" not in output

    async def _listening_ports(self, pid: str) -> list[int]:
        process = await asyncio.create_subprocess_exec(
            "lsof",
            "-nP",
            "-iTCP",
            "-sTCP:LISTEN",
            "-a",
            "-p",
            pid,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        return [
            int(match.group(1))
            for match in re.finditer(
                r":(\d+)\s+\(LISTEN\)", stdout.decode("utf-8", errors="replace")
            )
        ]

    async def _wait_for_completion(
        self,
        conversation_id: str,
        after_line: int,
        timeout_seconds: int,
        expected_qa_gates: tuple[str, ...] = (),
        expected_project_id: str | None = None,
    ) -> AntigravityDispatch:
        """Require explicit completion and both code-review graph tool calls."""
        deadline = asyncio.get_running_loop().time() + max(60, timeout_seconds)
        cursor = after_line
        tool_names: set[str] = set()
        final_message = ""
        while asyncio.get_running_loop().time() < deadline:
            hub_path = self._get_hub_database_path(conversation_id)
            if hub_path:
                result = self._read_hub_completion(
                    conversation_id,
                    hub_path,
                    cursor,
                    expected_qa_gates,
                    expected_project_id,
                )
                if result:
                    return result
                await asyncio.sleep(2)
                continue
            transcript_path = self._get_transcript_path(conversation_id)
            steps = self._read_steps(transcript_path, cursor)
            if steps:
                cursor += len(steps)
                for step in steps:
                    final_message = step.get("content", final_message) or final_message
                    for call in step.get("tool_calls", []):
                        name = call.get("name")
                        if isinstance(name, str):
                            tool_names.add(name)
                    content = step.get("content", "")
                    # The task prompt itself contains both sentinels. Only a
                    # model response may complete or block an execution.
                    if step.get("source") != "MODEL":
                        continue
                    if BLOCKED_TOKEN in content:
                        return AntigravityDispatch(
                            conversation_id,
                            False,
                            content.partition(BLOCKED_TOKEN)[2].lstrip(": "),
                            tuple(sorted(tool_names)),
                            final_message,
                            transcript_path,
                        )
                    if COMPLETION_TOKEN in content:
                        missing = {
                            required
                            for required in REQUIRED_REVIEW_TOOLS
                            if not any(required in tool_name for tool_name in tool_names)
                        }
                        if missing:
                            return AntigravityDispatch(
                                conversation_id,
                                False,
                                "Required code-review graph calls missing: "
                                + ", ".join(sorted(missing)),
                                tuple(sorted(tool_names)),
                                final_message,
                                transcript_path,
                            )
                        qa_evidence, evidence_error = self._parse_qa_evidence(
                            content, expected_qa_gates, expected_project_id
                        )
                        if evidence_error:
                            return AntigravityDispatch(
                                conversation_id,
                                False,
                                evidence_error,
                                tuple(sorted(tool_names)),
                                final_message,
                                transcript_path,
                            )
                        return AntigravityDispatch(
                            conversation_id,
                            True,
                            None,
                            tuple(sorted(tool_names)),
                            final_message,
                            transcript_path,
                            qa_evidence,
                        )
            await asyncio.sleep(2)
        return AntigravityDispatch(
            conversation_id,
            False,
            f"Antigravity did not emit {COMPLETION_TOKEN} before timeout",
            tuple(sorted(tool_names)),
            final_message,
            self._get_transcript_path(conversation_id),
        )

    def _read_hub_completion(
        self,
        conversation_id: str,
        database: Path,
        after_index: int,
        expected_qa_gates: tuple[str, ...] = (),
        expected_project_id: str | None = None,
    ) -> AntigravityDispatch | None:
        """Read new 2.0 SQLite events; completion token must come from model event type 23."""
        try:
            connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
            rows = connection.execute(
                "SELECT idx, step_type, step_payload FROM steps WHERE idx >= ? ORDER BY idx",
                (after_index,),
            ).fetchall()
            connection.close()
        except sqlite3.Error:
            return None
        tool_names: set[str] = set()
        for _, step_type, payload in rows:
            content = bytes(payload or b"").decode("utf-8", errors="replace")
            if step_type == 15:
                for tool in REQUIRED_REVIEW_TOOLS:
                    if tool in content:
                        tool_names.add(tool)
            if step_type != 23:
                continue
            if BLOCKED_TOKEN in content:
                return AntigravityDispatch(
                    conversation_id,
                    False,
                    content.partition(BLOCKED_TOKEN)[2].lstrip(": "),
                    tuple(sorted(tool_names)),
                    "",
                    database,
                )
            if COMPLETION_TOKEN in content:
                missing = REQUIRED_REVIEW_TOOLS - tool_names
                qa_evidence, evidence_error = self._parse_qa_evidence(
                    content, expected_qa_gates, expected_project_id
                )
                return AntigravityDispatch(
                    conversation_id,
                    not missing and evidence_error is None,
                    (
                        "Required code-review graph calls missing: " + ", ".join(sorted(missing))
                        if missing
                        else evidence_error
                    ),
                    tuple(sorted(tool_names)),
                    "",
                    database,
                    qa_evidence,
                )
        return None

    @staticmethod
    def _parse_qa_evidence(
        content: str,
        expected_qa_gates: tuple[str, ...],
        expected_project_id: str | None = None,
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Validate required machine-readable QA proof from model completion."""
        evidence_line = next(
            (
                line.strip()
                for line in reversed(content.splitlines())
                if line.strip().startswith(QA_EVIDENCE_TOKEN)
            ),
            None,
        )
        if evidence_line is None:
            if not expected_qa_gates:
                return {}, None
            return None, f"Missing {QA_EVIDENCE_TOKEN} manifest"

        try:
            evidence = json.loads(evidence_line[len(QA_EVIDENCE_TOKEN) :].strip())
        except json.JSONDecodeError as exc:
            return None, f"Invalid {QA_EVIDENCE_TOKEN} JSON: {exc.msg}"
        if not isinstance(evidence, dict):
            return None, "QA evidence manifest must be a JSON object"
        if evidence.get("skill") != SDLC_SKILL_NAME:
            return None, f"QA evidence must identify skill '{SDLC_SKILL_NAME}'"
        if expected_project_id and evidence.get("project_id") != expected_project_id:
            return None, "QA evidence project_id does not match dispatched task"
        if evidence.get("testscript_root") != "testscript":
            return None, "QA evidence must use testscript as test harness root"

        passed_gates = evidence.get("passed_gates")
        if not isinstance(passed_gates, list) or not all(
            isinstance(gate, str) for gate in passed_gates
        ):
            return None, "QA evidence passed_gates must be a list of gate names"
        missing_gates = sorted(set(expected_qa_gates) - set(passed_gates))
        if missing_gates:
            return None, "QA evidence missing required gates: " + ", ".join(missing_gates)

        security_review = evidence.get("security_review")
        if not isinstance(security_review, dict) or security_review.get("executed") is not True:
            return None, "QA evidence missing executed security review"
        if "browser_smoke" in expected_qa_gates:
            browser_e2e = evidence.get("browser_e2e")
            if (
                not isinstance(browser_e2e, dict)
                or browser_e2e.get("executed") is not True
                or browser_e2e.get("result") != "passed"
            ):
                return None, "QA evidence missing passed browser E2E proof"
        return evidence, None

    def _project_store_path(self, project_id: str) -> Path:
        return cast(Path, self.session_store_dir / f"{project_id}.json")

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
    def _extract_conversation_id(output: str) -> str | None:
        match = CONVERSATION_ID_PATTERN.search(output)
        return match.group(0) if match else None

    def _get_transcript_path(self, conversation_id: str) -> Path | None:
        for brain_dir in self.brain_dirs:
            path = brain_dir / conversation_id / ".system_generated" / "logs" / "transcript.jsonl"
            if path.is_file():
                return cast(Path, path)
        return None

    def _transcript_line_count(self, conversation_id: str) -> int:
        path = self._get_transcript_path(conversation_id)
        if not path:
            return 0
        return len(path.read_text().splitlines())

    def _get_hub_database_path(self, conversation_id: str) -> Path | None:
        path = self.hub_conversation_dir / f"{conversation_id}.db"
        return path if path.is_file() else None

    def _conversation_cursor(self, conversation_id: str) -> int:
        hub_path = self._get_hub_database_path(conversation_id)
        if hub_path:
            try:
                connection = sqlite3.connect(f"file:{hub_path}?mode=ro", uri=True)
                latest = connection.execute("SELECT COALESCE(MAX(idx), -1) FROM steps").fetchone()[
                    0
                ]
                connection.close()
                return int(latest) + 1
            except sqlite3.Error:
                return 0
        return self._transcript_line_count(conversation_id)

    @staticmethod
    def _read_steps(path: Path | None, start: int) -> list[dict[str, Any]]:
        if not path:
            return []
        steps: list[dict[str, Any]] = []
        for line in path.read_text().splitlines()[start:]:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                steps.append(payload)
        return steps
