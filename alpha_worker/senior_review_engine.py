"""
AlphaBrain Senior Review Engine
==============================
Executes mandatory 2-Round Senior Engineering Review and Debate between
Gemini 3.1 Pro High and Claude Opus 4.6 Thinking prior to autonomous PR merge.

Review Workflow:
  1. Round 1 Step 1 (Gemini 3.1 Pro High):
     Audits git diff, test evidence, blast radius, and Invariant compliance.
  2. Round 1 Step 2 (Claude Opus 4.6 Thinking):
     Supreme Lead Architect debates Pro's findings, verifies system design,
     and evaluates architecture invariants.
  3. Consensus & Certification:
     When both models approve, stamps cryptographic senior approval into
     TaskTriageQueue. Task is certified for fast-forward merge into main.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alpha_core.queue.triage_queue import TaskTriageQueue, TriageStatus
from alpha_protocol.task import ReviewAttestation

logger = logging.getLogger("alphabrain.worker.senior_review")


@dataclass
class SeniorReviewVerdict:
    task_id: str
    approved: bool
    pro_verdict: str
    opus_verdict: str
    pro_review_text: str
    opus_review_text: str
    reviewed_at: float
    attestation: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "approved": self.approved,
            "pro_verdict": self.pro_verdict,
            "opus_verdict": self.opus_verdict,
            "pro_review_text": self.pro_review_text,
            "opus_review_text": self.opus_review_text,
            "reviewed_at": self.reviewed_at,
            "attestation": self.attestation,
        }


class SeniorReviewEngine:
    def __init__(
        self,
        queue: TaskTriageQueue,
        agy_bin: Path | None = None,
        signing_secret: str | bytes | None = None,
    ) -> None:
        import os

        self.queue = queue
        self.agy_bin = agy_bin or (Path.home() / ".local" / "bin" / "agy")
        self.signing_secret = signing_secret or os.environ.get(
            "ALPHA_SIGNING_SECRET", "alphabrain_senior_review_key"
        )

    def run_command(self, cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return res.returncode, res.stdout, res.stderr
        except Exception as e:
            return 1, "", str(e)

    def get_task_diff(self, task: dict[str, Any]) -> str:
        branch_name = task.get("branch_name")
        repo_path = task.get("envelope", {}).get("repo", ".")
        if branch_name:
            try:
                # Ensure branch is up-to-date with main before diffing
                subprocess.run(
                    ["git", "merge-base", "--is-ancestor", "main", branch_name],
                    cwd=repo_path,
                    capture_output=True,
                )
                stat_res = subprocess.run(
                    ["git", "diff", "--stat", f"main..{branch_name}"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                res = subprocess.run(
                    ["git", "diff", f"main..{branch_name}"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if res.returncode == 0 and res.stdout.strip():
                    stat_str = stat_res.stdout.strip() if stat_res.returncode == 0 else ""
                    diff_str = res.stdout.strip()
                    full_content_str = ""

                    # Also append full file contents of modified files
                    files_res = subprocess.run(
                        ["git", "diff", "--name-only", f"main..{branch_name}"],
                        cwd=repo_path,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if files_res.returncode == 0:
                        for f in files_res.stdout.strip().splitlines():
                            f = f.strip()
                            if f:
                                try:
                                    # Use git show to get the file content at the branch_name
                                    content_res = subprocess.run(
                                        ["git", "show", f"{branch_name}:{f}"],
                                        cwd=repo_path,
                                        capture_output=True,
                                        text=True,
                                        timeout=10,
                                    )
                                    if content_res.returncode == 0:
                                        full_content_str += f"\n\n=== FULL FILE CONTENT: {f} ===\n```\n{content_res.stdout}\n```\n"
                                except Exception:
                                    pass

                    return f"=== Diff Stat ===\n{stat_str}\n\n=== Git Diff ===\n{diff_str}\n{full_content_str}"
            except Exception:
                pass
        result = task.get("result") or {}
        return str(result.get("diff_stat", "No diff available"))

    def _invoke_agy(
        self,
        model: str,
        prompt: str,
        cwd: str | None = None,
        timeout_seconds: int = 300,
        effort: str | None = None,
    ) -> str:
        """Invokes AGY non-interactively with structured prompt."""
        if not self.agy_bin.exists():
            raise RuntimeError(f"AGY executable not found at {self.agy_bin}")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(prompt)
            prompt_file = f.name

        try:
            cmd = [
                str(self.agy_bin),
                "--model",
                model,
                "--disable-slash-commands",
                "--dangerously-skip-permissions",
                "--print-timeout",
                f"{timeout_seconds}s",
            ]
            if "claude" not in model.lower() and effort:
                cmd.extend(["--effort", effort])
            cmd.extend(["--print", prompt])

            res = subprocess.run(
                cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout_seconds + 30
            )
            if res.returncode != 0:
                logger.warning("AGY %s returned non-zero %d: %s", model, res.returncode, res.stderr)
                raise RuntimeError(
                    f"AGY invocation failed with code {res.returncode}: {res.stderr}"
                )
            return res.stdout or res.stderr
        finally:
            Path(prompt_file).unlink(missing_ok=True)

    def parse_verdict_line(self, output: str, valid_enums: list[str], default_verdict: str) -> str:
        """
        Parses a strict one-line JSON verdict from the response lines.
        Inspects only the absolute last non-empty line.
        """
        if not output:
            return default_verdict

        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if not lines:
            return default_verdict

        try:
            import json

            def reject_duplicates(ordered_pairs):
                d = {}
                for k, v in ordered_pairs:
                    if k in d:
                        raise ValueError(f"Duplicate key: {k}")
                    d[k] = v
                return d

            last_line = lines[-1]
            try:
                parsed = json.loads(last_line, object_pairs_hook=reject_duplicates)
                if not isinstance(parsed, dict) or len(parsed) != 1 or "verdict" not in parsed:
                    return default_verdict
                val = parsed["verdict"]
                if isinstance(val, str) and val in valid_enums:
                    return val
            except Exception:
                return default_verdict

            return default_verdict
        except Exception:
            return default_verdict

    def execute_senior_review(self, task_id: str) -> SeniorReviewVerdict:
        task = self.queue.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found in triage queue.")

        if task["status"] != TriageStatus.COMPLETED.value:
            raise ValueError(f"Task '{task_id}' is not completed. Current status: {task['status']}")

        result = task.get("result") or {}
        if not result.get("gates_passed", False):
            raise ValueError(f"Acceptance gates failed or not run for task '{task_id}'.")

        diff_content = self.get_task_diff(task)
        title = task.get("envelope", {}).get("title", "Autonomous Task")
        description = task.get("envelope", {}).get("detailed_instructions", "")

        # --- Round 1 Step 1: Gemini 3.1 Pro High ---
        logger.info("Executing Senior Review Round 1 (Gemini 3.1 Pro High) for %s...", task_id)
        pro_prompt = f"""You are Gemini 3.1 Pro High (gemini-3.1-pro-high), conducting Round 1 Senior Engineering Code Review for task {task_id}.
Title: {title}
Description: {description}

Git Diff:
```diff
{diff_content}
```

Review Instructions:
1. Verify correct implementation of the objective.
2. Check security, boundary validation, and zero secret leakage.
3. Check test coverage and acceptance criteria.
4. Render your verdict explicitly by outputting a strict one-line JSON verdict on the absolute last line of your response. Format: {{"verdict": "APPROVE"}} or {{"verdict": "REPAIR_REQUIRED"}}. Do not output any other JSON.
"""
        pro_out = self._invoke_agy(
            "gemini-3.1-pro-high",
            pro_prompt,
            cwd=task.get("worktree_path"),
            timeout_seconds=240,
            effort="high",
        )
        pro_verdict = self.parse_verdict_line(
            pro_out, ["APPROVE", "REPAIR_REQUIRED"], "REPAIR_REQUIRED"
        )
        pro_approved = pro_verdict == "APPROVE"

        # --- Round 1 Step 2: Claude Opus 4.6 Thinking ---
        logger.info("Executing Senior Review Round 2 (Claude Opus 4.6 Thinking) for %s...", task_id)
        opus_prompt = f"""You are Claude Opus 4.6 Thinking, Supreme Lead Architect for AlphaBrain.
You are conducting Round 2 Step 2 of the Senior Engineering Review and Debate for task {task_id}.
Title: {title}

Git Diff:
```diff
{diff_content}
```

Gemini 3.1 Pro High Round 1 Finding:
{pro_out[:10000]}

Instructions:
1. Debate Gemini Pro's findings.
2. Verify overall system design and AlphaBrain Invariant compliance.
3. CRITICAL: Do NOT invoke external tools or inspect files on disk. The repository on disk is at base_commit; all pending changes are provided in the 'Git Diff' above. Base your architectural evaluation strictly on the provided Git Diff and Round 1 debate context.
4. Render your authoritative final ruling explicitly by outputting a strict one-line JSON verdict on the absolute last line. Format: {{"verdict": "FINAL_APPROVAL"}} or {{"verdict": "REJECT"}}. Do not output any other JSON.
"""
        opus_out = self._invoke_agy(
            "claude-opus-4-6-thinking",
            opus_prompt,
            cwd=task.get("worktree_path"),
            timeout_seconds=500,
        )
        opus_verdict = self.parse_verdict_line(opus_out, ["FINAL_APPROVAL", "REJECT"], "REJECT")
        opus_approved = opus_verdict == "FINAL_APPROVAL"

        unanimous = pro_approved and opus_approved

        # Extract fields for attestation
        base_commit = task.get("envelope", {}).get("base_commit") or ("0" * 40)
        result_sha = (
            task.get("result", {}).get("result_sha")
            or task.get("result", {}).get("head_commit")
            or task.get("result", {}).get("result_commit")
            or ("0" * 40)
        )
        evidence = task.get("result", {}).get("gate_result", {})

        att = ReviewAttestation.create(
            task_id=task_id,
            result_sha=result_sha,
            base_commit=base_commit,
            pro_verdict=pro_verdict,
            opus_verdict=opus_verdict,
            approved=unanimous,
            reviewed_at=time.time(),
            evidence=evidence,
            secret=self.signing_secret,
        )

        verdict = SeniorReviewVerdict(
            task_id=task_id,
            approved=unanimous,
            pro_verdict=pro_verdict,
            opus_verdict=opus_verdict,
            pro_review_text=pro_out,
            opus_review_text=opus_out,
            reviewed_at=att.reviewed_at,
            attestation=att.model_dump(),
        )

        # Record in queue
        self.queue.record_senior_review(
            task_id=task_id,
            pro_verdict=pro_verdict,
            opus_verdict=opus_verdict,
            approved=unanimous,
            review_details=verdict.to_dict(),
        )

        # If repairs required, automatically transition back to APPROVED with senior directives
        if not unanimous:
            repair_packet = (
                f"### Gemini 3.1 Pro High Findings:\n{pro_out}\n\n"
                f"### Claude Opus 4.6 Thinking Architectural Ruling:\n{opus_out}"
            )
            self.queue.queue_task_for_senior_repair(task_id, repair_packet)
            logger.info("Task %s queued for autonomous senior repair turn in worktree.", task_id)

        return verdict
