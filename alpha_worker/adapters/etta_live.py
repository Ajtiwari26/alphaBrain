"""ETTA CLI live bridge for executing autonomous coding tasks in AlphaBrain."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alpha_core.config import settings
from alpha_protocol import TaskEnvelope

logger = logging.getLogger("alpha_worker.etta_live")


@dataclass(frozen=True)
class EttaDispatch:
    """Structured result from an ETTA CLI task execution."""

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
    status: str = "succeeded"
    changed_files: tuple[str, ...] = ()
    diff_summary: str = ""
    artifacts: tuple[str, ...] = ()
    tokens_used: int = 0
    cost: float = 0.0


class EttaLiveBridge:
    """Subprocess and session bridge for ETTA autonomous coding agent."""

    def __init__(
        self,
        bin_path: Path | str | None = None,
        model: str | None = None,
        effort: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.bin_path = Path(bin_path) if bin_path else settings.ETTA_BIN
        self.model: str = str(model or getattr(settings, "ETTA_MODEL", "gemini-3.8-flash-high"))
        self.effort: str = str(effort or getattr(settings, "ETTA_EFFORT", "auto"))
        self.timeout_seconds: int = int(
            timeout_seconds
            if timeout_seconds is not None
            else getattr(settings, "ETTA_TASK_TIMEOUT_SECONDS", 1200)
        )

    def resolve_bin(self) -> Path | None:
        """Resolves the executable path to etta."""
        if self.bin_path.exists() and os.access(self.bin_path, os.X_OK):
            return self.bin_path
        which_path = shutil.which(str(self.bin_path))
        if which_path:
            return Path(which_path)
        if self.bin_path == settings.ETTA_BIN:
            fallback = shutil.which("etta")
            if fallback:
                return Path(fallback)
        return None

    def check_readiness(self) -> tuple[bool, str]:
        """Checks if ETTA CLI is installed, executable, and ready."""
        bin_path = self.resolve_bin()
        if not bin_path:
            return False, f"ETTA binary not found at '{self.bin_path}' or in PATH"
        try:
            res = subprocess.run(
                [str(bin_path), "--headless", "--output-format", "json", "--status"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if res.returncode == 0:
                return True, f"ETTA ready at {bin_path}"
            return True, f"ETTA binary present at {bin_path} (status exited {res.returncode})"
        except Exception as e:
            return False, f"ETTA readiness check error: {e}"

    async def dispatch(
        self,
        task: TaskEnvelope,
        worktree_path: Path,
        attempt_id: str,
        session_dir: Path | None = None,
    ) -> EttaDispatch:
        """Executes task inside the worktree using ETTA CLI in headless mode."""
        bin_path = self.resolve_bin()
        if not bin_path:
            return EttaDispatch(
                conversation_id=attempt_id,
                completed=False,
                blocked_reason=f"ETTA binary not found at '{self.bin_path}'",
                tool_names=(),
                final_message="",
                transcript_path=None,
                status="failed",
            )

        prompt_lines = [f"Goal: {task.objective}"]
        if task.detailed_instructions:
            prompt_lines.append(f"\nInstructions:\n{task.detailed_instructions}")
        if task.allowed_paths:
            prompt_lines.append(f"\nAllowed paths: {', '.join(task.allowed_paths)}")
        goal = "\n".join(prompt_lines)

        cmd = [
            str(bin_path),
            "--headless",
            "--output-format",
            "json",
            "--workspace",
            str(worktree_path),
            "--goal",
            goal,
            "--model",
            self.model,
            "--effort",
            self.effort,
        ]

        logger.info("Executing ETTA command: %s", " ".join(cmd[:6]))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(worktree_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=float(self.timeout_seconds),
                )
            except TimeoutError:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
                return EttaDispatch(
                    conversation_id=attempt_id,
                    completed=False,
                    blocked_reason=f"ETTA timed out after {self.timeout_seconds} seconds",
                    tool_names=(),
                    final_message="",
                    transcript_path=None,
                    status="timed_out",
                )

            stdout_str = stdout_bytes.decode("utf-8", errors="replace")
            stderr_str = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = proc.returncode if proc.returncode is not None else 0

            # Parse JSON output if present
            parsed: dict[str, Any] = {}
            for line in reversed(stdout_str.splitlines()):
                line_s = line.strip()
                if line_s.startswith("{") and line_s.endswith("}"):
                    try:
                        parsed = json.loads(line_s)
                        break
                    except Exception:
                        pass
            if not parsed and stdout_str.strip().startswith("{"):
                try:
                    parsed = json.loads(stdout_str.strip())
                except Exception:
                    pass

            transcript_path: Path | None = None
            if session_dir:
                logs_dir = session_dir / ".system_generated" / "logs"
                logs_dir.mkdir(parents=True, exist_ok=True)
                transcript_path = logs_dir / "etta_transcript.json"
                transcript_path.write_text(stdout_str or stderr_str, encoding="utf-8")

            completed = (exit_code == 0) and not parsed.get("error")
            blocked_reason = None
            if not completed:
                blocked_reason = (
                    parsed.get("error")
                    or (stderr_str.strip() if stderr_str else None)
                    or f"ETTA exited with status {exit_code}"
                )

            return EttaDispatch(
                conversation_id=attempt_id,
                completed=completed,
                blocked_reason=blocked_reason,
                tool_names=("edit_file", "view_file", "run_command"),
                final_message=stdout_str[-500:] if stdout_str else "",
                transcript_path=transcript_path,
                pid=proc.pid,
                exit_code=exit_code,
                model=self.model,
                status="succeeded" if completed else "failed",
                tokens_used=int(parsed.get("tokens_used", 0)),
                cost=float(parsed.get("cost", 0.0)),
            )

        except Exception as exc:
            logger.exception("ETTA dispatch error: %s", exc)
            return EttaDispatch(
                conversation_id=attempt_id,
                completed=False,
                blocked_reason=f"ETTA dispatch failed: {exc}",
                tool_names=(),
                final_message="",
                transcript_path=None,
                status="failed",
            )
