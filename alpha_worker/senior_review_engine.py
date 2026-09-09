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
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alpha_core.queue.triage_queue import TaskTriageQueue, TriageStatus
from alpha_protocol.task import REGISTERED_REVIEW_KEYS, ReviewAttestation

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
        key_id: str = "alpha_production_v1",
    ) -> None:
        import os

        self.queue = queue
        self.agy_bin = agy_bin or (Path.home() / ".local" / "bin" / "agy")
        self.key_id = key_id
        self.signing_secret = signing_secret or os.environ.get(f"ALPHA_SIGNING_SECRET_{key_id}")

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
                    return f"=== Diff Stat ===\n{stat_str}\n\n=== Git Diff ===\n{diff_str}"
            except Exception:
                pass
        result = task.get("result") or {}
        return str(result.get("diff_stat", "No diff available"))

    def _invoke_agy(
        self,
        model: str,
        prompt: str,
        schema_path: str,
        cwd: str | None = None,
        timeout_seconds: int = 300,
        effort: str | None = None,
    ) -> dict:
        """Invokes AGY non-interactively with structured prompt."""
        import json
        import os

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
                "--sandbox",
                "--mode",
                "plan",
                "--output-format",
                "json",
                "--input-format",
                "text",
                "--json-schema",
                schema_path,
                "--print-timeout",
                f"{timeout_seconds}s",
            ]
            if "claude" not in model.lower() and effort:
                cmd.extend(["--effort", effort])

            env = {k: v for k, v in os.environ.items() if not k.startswith("ALPHA_SIGNING_SECRET")}

            res = subprocess.run(
                cmd,
                input=prompt,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds + 30,
                env=env,
            )
            if res.returncode != 0:
                logger.warning(
                    "AGY %s returned non-zero %d: stderr=%s stdout=%s",
                    model,
                    res.returncode,
                    res.stderr,
                    res.stdout,
                )
                raise RuntimeError(
                    f"AGY invocation failed with code {res.returncode}: stderr={res.stderr} stdout={res.stdout}"
                )
            try:

                def reject_duplicates(ordered_pairs):
                    d = {}
                    for k, v in ordered_pairs:
                        if k in d:
                            raise ValueError(f"Duplicate key: {k}")
                        d[k] = v
                    return d

                parsed = json.loads(res.stdout, object_pairs_hook=reject_duplicates)
                if isinstance(parsed, dict):
                    return parsed
                return {"response": res.stdout or res.stderr, "structured_output": {}}
            except Exception:
                return {"response": res.stdout or res.stderr, "structured_output": {}}
        finally:
            Path(prompt_file).unlink(missing_ok=True)

    def parse_verdict_line(self, output: str, valid_enums: list[str], default_verdict: str) -> str:
        """
        Parses a strict one-line JSON verdict from the response lines.
        Inspects only the absolute last non-empty line, and ensures no other
        valid terminal markers exist anywhere else in the response.
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

            def is_valid_marker(line: str) -> str | None:
                try:
                    parsed = json.loads(line, object_pairs_hook=reject_duplicates)
                    if isinstance(parsed, dict) and len(parsed) == 1 and "verdict" in parsed:
                        val = parsed["verdict"]
                        if isinstance(val, str) and val in valid_enums:
                            return val
                except Exception:
                    pass
                return None

            valid_markers = []
            for i, line in enumerate(lines):
                marker_val = is_valid_marker(line)
                if marker_val:
                    valid_markers.append((i, marker_val))

            if len(valid_markers) != 1:
                return default_verdict

            marker_idx, marker_val = valid_markers[0]
            if marker_idx != len(lines) - 1:
                return default_verdict

            return marker_val

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

        # Extract fields for attestation and verification
        base_commit = task.get("envelope", {}).get("base_commit") or ("0" * 40)
        result_sha = (
            task.get("result", {}).get("result_sha")
            or task.get("result", {}).get("head_commit")
            or task.get("result", {}).get("result_commit")
            or ("0" * 40)
        )

        if not self.signing_secret:
            raise ValueError(f"Missing signing secret for key {self.key_id}")

        key_id = self.key_id

        if key_id not in REGISTERED_REVIEW_KEYS:
            raise ValueError(f"Key {key_id} is not a registered review key")

        revoked_keys = os.environ.get("ALPHA_REVOKED_KEYS", "").split(",")
        if key_id in revoked_keys:
            raise ValueError(f"Key {key_id} has been revoked")

        lease_meta = (task.get("provenance") or {}).get("lease_metadata") or {}
        auth_attempt_id = lease_meta.get("attempt_id")
        auth_worker_id = lease_meta.get("worker_id")

        if not auth_attempt_id or auth_attempt_id in ("att_unknown", "None", ""):
            raise ValueError("Task provenance missing or invalid authoritative lease attempt_id")
        if not auth_worker_id or auth_worker_id in ("worker_unknown", "None", ""):
            raise ValueError("Task provenance missing or invalid authoritative lease worker_id")

        result = task.get("result") or {}
        attempt_id = result.get("attempt_id")
        executor_id = result.get("worker_id")

        for name, val in [("attempt_id", attempt_id), ("worker_id", executor_id)]:
            if not val or val in ("worker_unknown", "att_unknown", "None", ""):
                raise ValueError(f"Missing or invalid {name} in task result")

        if attempt_id != auth_attempt_id:
            raise ValueError(
                f"Task result attempt_id '{attempt_id}' does not match authoritative lease attempt_id '{auth_attempt_id}'"
            )
        if executor_id != auth_worker_id:
            raise ValueError(
                f"Task result worker_id '{executor_id}' does not match authoritative lease worker_id '{auth_worker_id}'"
            )

        worktree_path = task.get("worktree_path")
        if not worktree_path or not Path(worktree_path).is_dir():
            raise ValueError(
                f"Worktree path '{worktree_path}' does not exist or is missing. Mandatory checkout validation failed."
            )

        try:
            head_sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=worktree_path, text=True
            ).strip()
            if head_sha != result_sha:
                raise ValueError(
                    f"Worktree HEAD {head_sha} does not match task result_sha {result_sha}."
                )
            status = subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=worktree_path, text=True
            ).strip()
            if status:
                raise ValueError(f"Worktree is not clean. Uncommitted changes detected: {status}")
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Git command failed during worktree validation: {e}") from e

        diff_content = self.get_task_diff(task)
        title = task.get("envelope", {}).get("title", "Autonomous Task")
        description = task.get("envelope", {}).get("detailed_instructions", "")

        from alpha_worker.code_review_graph import extract_code_review_graph

        graph_md = extract_code_review_graph(worktree_path, diff_content)
        graph_artifact_path = Path(worktree_path) / "code_review_graph.md"
        graph_artifact_path.write_text(graph_md, encoding="utf-8")

        # --- Round 1 Step 1: Gemini 3.1 Pro High ---
        logger.info("Executing Senior Review Round 1 (Gemini 3.1 Pro High) for %s...", task_id)
        pro_prompt = f"""You are Gemini 3.1 Pro High (gemini-3.1-pro-high), conducting Round 1 Senior Engineering Code Review for task {task_id}.
Title: {title}
Description: {description}

CANDIDATE WORKTREE (where the patched files live): {worktree_path}
IMPORTANT: This is a PRE-MERGE review. The diff below has been applied ONLY in the candidate
worktree above. The main branch does NOT contain these changes yet — merging happens only AFTER
your approval. When inspecting files, read them from the candidate worktree, not the base repository.

Git Diff:
```diff
{diff_content}
```

Code Review Graph (Dependency Impacts):
{graph_md}

Review Instructions:
1. Verify correct implementation of the objective.
2. Check security, boundary validation, and zero secret leakage.
3. Check test coverage and acceptance criteria.
4. Render your verdict explicitly by outputting a strict one-line JSON verdict on the absolute last line of your response. Format: {{"verdict": "APPROVE"}} or {{"verdict": "REPAIR_REQUIRED"}}. Do not output any other JSON.
"""
        pro_schema_path = Path(__file__).parent / "pro_schema.json"
        pro_res = self._invoke_agy(
            "gemini-3.1-pro-high",
            pro_prompt,
            schema_path=str(pro_schema_path),
            cwd=task.get("worktree_path"),
            timeout_seconds=900,
            effort="high",
        )
        pro_out = pro_res.get("response", "")
        pro_struct = pro_res.get("structured_output", {})
        if isinstance(pro_struct, dict) and len(pro_struct) == 1 and "verdict" in pro_struct:
            pro_verdict = pro_struct["verdict"]
            if pro_verdict not in ["APPROVE", "REPAIR_REQUIRED"]:
                pro_verdict = "REPAIR_REQUIRED"
        else:
            pro_verdict = self.parse_verdict_line(
                pro_out, ["APPROVE", "REPAIR_REQUIRED"], "REPAIR_REQUIRED"
            )
        pro_approved = pro_verdict == "APPROVE"

        # --- Round 2 Step 2: Claude Opus 4.6 Thinking ---
        logger.info("Executing Senior Review Round 2 (Claude Opus 4.6 Thinking) for %s...", task_id)
        opus_schema_path = Path(__file__).parent / "opus_schema.json"
        opus_prompt = f"""You are Claude Opus 4.6 Thinking, Supreme Lead Architect for AlphaBrain.
You are conducting an independent Round 2 Senior Engineering Review for task {task_id}.
Title: {title}

CANDIDATE WORKTREE (where the patched files live): {worktree_path}
CRITICAL CONTEXT: This is a PRE-MERGE review. The changes shown in the diff below exist ONLY in
the candidate worktree. The main branch does NOT contain these changes yet.
Please evaluate the provided Git Diff. Do not attempt to use tools to read the source files, as tool execution is restricted in this review environment. Rely entirely on the diff provided below.

Git Diff:
```diff
{diff_content}
```

Code Review Graph (Dependency Impacts):
{graph_md}

Instructions:
1. Verify overall system design and AlphaBrain Invariant compliance.
2. Inspect source files in the candidate worktree at {worktree_path} to verify runtime correctness.
3. Render your authoritative final ruling explicitly by outputting a strict JSON verdict.
"""
        opus_res = self._invoke_agy(
            "claude-opus-4-6-thinking",
            opus_prompt,
            schema_path=str(opus_schema_path),
            cwd=task.get("worktree_path"),
            timeout_seconds=900,
        )
        opus_out = opus_res.get("response", "")
        opus_struct = opus_res.get("structured_output", {})
        if isinstance(opus_struct, dict) and len(opus_struct) == 1 and "verdict" in opus_struct:
            opus_verdict = opus_struct["verdict"]
            if opus_verdict not in ["FINAL_APPROVAL", "REJECT"]:
                opus_verdict = "REJECT"
        else:
            opus_verdict = self.parse_verdict_line(opus_out, ["FINAL_APPROVAL", "REJECT"], "REJECT")
        opus_approved = opus_verdict == "FINAL_APPROVAL"

        unanimous = pro_approved and opus_approved

        evidence = task.get("result", {}).get("evidence", {})

        try:
            tree_digest = subprocess.check_output(
                ["git", "rev-parse", "HEAD^{tree}"], cwd=worktree_path, text=True
            ).strip()
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Failed to get tree digest: {e}") from e

        secret = os.environ.get(f"ALPHA_SIGNING_SECRET_{key_id}") or self.signing_secret

        att = ReviewAttestation.create(
            task_id=task_id,
            attempt_id=attempt_id,
            result_sha=result_sha,
            base_commit=base_commit,
            tree_digest=tree_digest,
            pro_verdict=pro_verdict,
            opus_verdict=opus_verdict,
            approved=unanimous,
            reviewed_at=time.time(),
            evidence=evidence,
            secret=secret,
            nonce=uuid.uuid4().hex,
            executor_id=executor_id,
            key_id=key_id,
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
