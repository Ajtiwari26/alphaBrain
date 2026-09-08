"""
alpha_core/triage_cli.py
Human-in-the-Loop (HITL) CLI for AlphaBrain Task Triage Queue and Safety Gate.

Supports inspecting, reviewing, approving, rejecting, and modifying tasks in the
TaskTriageQueue, as well as managing the emergency stop tombstone.

Entry point:
    python -m alpha_core.triage <command> [options]
    or
    python -m alpha_core.triage_cli <command> [options]
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

from alpha_core.queue.triage_queue import (
    DEFAULT_DB_PATH,
    DEFAULT_EMERGENCY_LOCK,
    EmergencyStopActiveError,
    TaskTriageQueue,
    TriageStatus,
)
from alpha_core.safety.gate import SafetyGate


def _format_timestamp(ts: float | None) -> str:
    if not ts:
        return "-"
    try:
        return datetime.datetime.fromtimestamp(ts, tz=datetime.UTC).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        print("No tasks found.")
        return
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    sep_line = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    print(header_line)
    print(sep_line)
    for row in rows:
        print(" | ".join(row[i].ljust(col_widths[i]) for i in range(len(row))))


def _atomic_write_json(filepath: Path, data: dict):
    import tempfile

    filepath.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=filepath.parent, prefix=".tmp", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, filepath)
        # fsync the parent directory to ensure the directory entry is durable
        try:
            dir_fd = os.open(filepath.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            os.fsync(dir_fd)
            os.close(dir_fd)
        except OSError:
            pass  # Some platforms/filesystems do not support directory fsync
    except Exception:
        os.remove(tmp_path)
        raise


def cmd_list(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    status_filter = None
    if args.status and args.status.lower() != "all":
        try:
            status_filter = TriageStatus(args.status.lower())
        except ValueError:
            print(
                f"Error: Invalid status '{args.status}'. Choices: {[s.value for s in TriageStatus]} or 'all'",
                file=sys.stderr,
            )
            return 1

    tasks = queue.list_tasks(status=status_filter, limit=args.limit)

    if args.json:
        print(json.dumps(tasks, indent=2, default=str))
        return 0

    headers = ["Task ID", "Status", "Project ID", "Title", "Created (UTC)", "Safety"]
    rows = []
    for t in tasks:
        env = t.get("envelope", {})
        verdict = t.get("safety_verdict") or "-"
        title = env.get("objective") or env.get("title", "-")
        rows.append(
            [
                t["id"][:12] + "...",
                t["status"],
                env.get("project_id", "-")[:15],
                title[:35],
                _format_timestamp(t.get("created_at")),
                verdict,
            ]
        )
    _print_table(headers, rows)
    return 0


def cmd_show(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    task = queue.get_task(args.task_id)
    if not task:
        print(f"Error: Task '{args.task_id}' not found.", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(task, indent=2, default=str))
        return 0

    env = task.get("envelope", {})
    prov = task.get("provenance", {})
    res = task.get("result")

    print("=" * 70)
    print(f"Task ID:         {task['id']}")
    print(f"Status:          {task['status'].upper()}")
    print(f"Created At:      {_format_timestamp(task.get('created_at'))}")
    print(f"Updated At:      {_format_timestamp(task.get('updated_at'))}")
    print(f"Content Hash:    {task.get('content_hash')}")
    print("-" * 70)
    print("PROVENANCE:")
    print(f"  Meeting ID:    {prov.get('meeting_id')}")
    print(f"  Speaker:       {prov.get('speaker_id') or 'N/A'}")
    print(f"  Model:         {prov.get('extraction_model')}")
    print(f"  Confidence:    {prov.get('extraction_confidence')}")
    print(f"  Excerpt:       {prov.get('transcript_excerpt')}")
    print("-" * 70)
    print("SAFETY AUDIT:")
    print(f"  Verdict:       {task.get('safety_verdict') or 'PENDING'}")
    print(f"  Reason:        {task.get('safety_reason') or 'N/A'}")
    print("-" * 70)
    print("ENVELOPE DETAILS:")
    print(f"  Project ID:    {env.get('project_id')}")
    print(f"  Repo:          {env.get('repo')}")
    print(f"  Title:         {env.get('objective') or env.get('title')}")
    print(f"  Allowed Paths: {', '.join(env.get('allowed_paths', []))}")
    commands = env.get("acceptance_plan", {}).get("commands", [])
    if commands:
        print("  Commands:")
        for c in commands:
            exe = c.get("executable", "")
            cmd_args = " ".join(c.get("args", []))
            print(f"    - {exe} {cmd_args}".strip())
    criteria = env.get("acceptance_plan", {}).get("criteria", [])
    if criteria:
        print("  Criteria:")
        for cr in criteria:
            print(f"    - {cr}")
    if res:
        print("-" * 70)
        print("EXECUTION RESULT:")
        print(f"  Result Status: {res.get('status')}")
        if res.get("error"):
            print(f"  Error:         {res.get('error')}")
    audit = prov.get("audit_history", [])
    if audit:
        print("-" * 70)
        print("AUDIT HISTORY:")
        for entry in audit:
            print(
                f"  [{_format_timestamp(entry.get('timestamp'))}] {entry.get('action')}: {entry.get('notes')}"
            )
    print("=" * 70)
    return 0


def cmd_export_audit(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    task = queue.get_task(args.task_id)
    if not task:
        print(f"Error: Task '{args.task_id}' not found.", file=sys.stderr)
        return 1

    from alpha_core.security import redact_dict

    prov = task.get("provenance", {})
    res = task.get("result", {})

    audit_data = {
        "schema_version": "1.0",
        "exported_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "task_id": task["id"],
        "status": task["status"],
        "created_at": task.get("created_at"),
        "updated_at": task.get("updated_at"),
        "provenance": redact_dict(prov) if isinstance(prov, dict) else prov,
        "execution_history": redact_dict(res) if isinstance(res, dict) else res,
    }

    output_path = getattr(args, "output", None) or f"audit_export_{task['id']}.json"
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(audit_data, f, indent=2, default=str, sort_keys=True)
        print(f"Audit exported successfully to {output_path}")
    except OSError as e:
        print(f"Error: Could not write to {output_path} - {e}", file=sys.stderr)
        return 1

    return 0


def cmd_review(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    task = queue.get_task(args.task_id)
    if not task:
        print(f"Error: Task '{args.task_id}' not found.", file=sys.stderr)
        return 1

    safety_gate = SafetyGate()
    verdict = safety_gate.evaluate_envelope(task["envelope"])

    if args.json:
        print(
            json.dumps(
                {
                    "task_id": args.task_id,
                    "passed": verdict.passed,
                    "status": verdict.verdict,
                    "reason": verdict.reason,
                    "violations": verdict.violations,
                },
                indent=2,
            )
        )
        return 0

    status_str = "APPROVED" if verdict.passed else "REJECTED"
    print(f"Safety Gate Review Verdict for '{args.task_id}': {status_str}")
    if verdict.reason:
        print(f"Reason: {verdict.reason}")
    if verdict.violations:
        print("Violations:")
        for v in verdict.violations:
            print(f"  - {v}")
    return 0 if verdict.passed else 2


def cmd_approve(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    task = queue.get_task(args.task_id)
    if not task:
        print(f"Error: Task '{args.task_id}' not found.", file=sys.stderr)
        return 1

    if queue.is_emergency_stopped():
        print("Error: Emergency stop is active. Cannot approve tasks.", file=sys.stderr)
        return 1

    safety_gate = SafetyGate()
    verdict = safety_gate.evaluate_envelope(task["envelope"])
    if not verdict.passed and not args.force:
        print(
            f"Error: Safety Gate rejected task '{args.task_id}' (Reason: {verdict.reason}).\n"
            "Cannot approve rejected task without --force.",
            file=sys.stderr,
        )
        return 2

    notes = args.notes or "Operator approved via CLI"
    success = queue.approve_task(
        args.task_id,
        safety_verdict=verdict.verdict,
        safety_reason=notes,
    )
    if not success:
        print(
            f"Error: Failed to approve task '{args.task_id}'. Ensure status is 'pending_review'.",
            file=sys.stderr,
        )
        return 1

    if args.json:
        print(json.dumps({"task_id": args.task_id, "status": "approved", "notes": notes}))
    else:
        print(f"Task '{args.task_id}' successfully APPROVED for worker intake.")
    return 0


def cmd_retry(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    task = queue.get_task(args.task_id)
    if not task:
        print(f"Error: Task '{args.task_id}' not found.", file=sys.stderr)
        return 1

    if queue.is_emergency_stopped():
        print("Error: Emergency stop is active. Cannot retry tasks.", file=sys.stderr)
        return 1

    notes = getattr(args, "notes", None) or "Operator triggered retry via CLI"
    success = queue.retry_task(args.task_id, operator_notes=notes)
    if not success:
        print(
            f"Error: Failed to retry task '{args.task_id}'. Ensure status is 'failed'.",
            file=sys.stderr,
        )
        return 1

    if getattr(args, "json", False):
        print(json.dumps({"task_id": args.task_id, "status": "approved", "notes": notes}))
    else:
        print(f"Task '{args.task_id}' successfully reset from FAILED to APPROVED for retry.")
    return 0


def cmd_reject(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    task = queue.get_task(args.task_id)
    if not task:
        print(f"Error: Task '{args.task_id}' not found.", file=sys.stderr)
        return 1

    success = queue.reject_task(args.task_id, reason=args.reason)
    if not success:
        print(
            f"Error: Failed to reject task '{args.task_id}'. Current status: {task['status']}",
            file=sys.stderr,
        )
        return 1

    if args.json:
        print(json.dumps({"task_id": args.task_id, "status": "rejected", "reason": args.reason}))
    else:
        print(f"Task '{args.task_id}' marked as REJECTED: {args.reason}")
    return 0


def cmd_modify(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    task = queue.get_task(args.task_id)
    if not task:
        print(f"Error: Task '{args.task_id}' not found.", file=sys.stderr)
        return 1

    allowed_paths = None
    if args.allowed_paths:
        allowed_paths = [p.strip() for p in args.allowed_paths.split(",") if p.strip()]

    try:
        success = queue.modify_task(
            args.task_id,
            allowed_paths=allowed_paths,
            title=args.title,
            description=args.description,
            reviewer_notes=args.notes or "Operator modified envelope via CLI",
        )
    except EmergencyStopActiveError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if not success:
        print(
            f"Error: Could not modify task '{args.task_id}'. Task must be in 'pending_review' status.",
            file=sys.stderr,
        )
        return 1

    # Automatically re-evaluate safety gate
    updated_task = queue.get_task(args.task_id)
    if not updated_task:
        print(f"Error: Task '{args.task_id}' not found after modification.", file=sys.stderr)
        return 1

    safety_gate = SafetyGate()
    verdict = safety_gate.evaluate_envelope(updated_task["envelope"])

    if args.json:
        print(
            json.dumps(
                {
                    "task_id": args.task_id,
                    "modified": True,
                    "safety_passed": verdict.passed,
                    "safety_verdict": verdict.verdict,
                    "safety_reason": verdict.reason,
                    "safety_violations": verdict.violations,
                },
                indent=2,
            )
        )
        return 0

    print(f"Task '{args.task_id}' successfully modified.")
    status_str = "APPROVED" if verdict.passed else "REJECTED"
    print(f"Re-evaluated Safety Gate: {status_str}")
    if verdict.reason:
        print(f"Reason: {verdict.reason}")
    if verdict.violations:
        for v in verdict.violations:
            print(f"  - {v}")
    return 0


def cmd_emergency_stop(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    lock_path = queue.emergency_stop(reason=args.reason or "operator_requested_via_cli")
    if args.json:
        print(
            json.dumps({"emergency_stop": True, "lock_path": str(lock_path), "reason": args.reason})
        )
    else:
        print(f"🚨 EMERGENCY STOP ACTIVATED: {lock_path}")
        print("All worker leasing and automated task intake are suspended.")
    return 0


def cmd_emergency_resume(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    removed = queue.emergency_resume()
    if args.json:
        print(json.dumps({"emergency_stop": False, "resumed": removed}))
    else:
        if removed:
            print("✅ EMERGENCY STOP CLEARED. Task intake and worker leasing resumed.")
        else:
            print("Emergency stop was not active.")
    return 0


def cmd_emergency_status(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    status_info = queue.get_emergency_status()
    if args.json:
        print(json.dumps(status_info, indent=2))
        return 0

    if status_info["active"]:
        print(f"🚨 EMERGENCY STOP IS ACTIVE (lockfile: {status_info['lock_path']})")
        print(f"   Reason:    {status_info.get('reason')}")
        print(f"   Activated: {_format_timestamp(status_info.get('timestamp'))}")
    else:
        print("✅ System Operational. Emergency stop is NOT active.")
    return 0


def cmd_worker_cycle(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    from alpha_worker.triage_dispatcher import TriageTaskDispatcher

    dispatcher = TriageTaskDispatcher(queue=queue)
    if queue.is_emergency_stopped():
        msg = "Emergency stop active. Worker execution halted."
        if args.json:
            print(json.dumps({"error": msg, "emergency_stop": True}))
        else:
            print(f"🚨 {msg}", file=sys.stderr)
        return 1

    proposal = dispatcher.execute_next_cycle()
    if not proposal:
        if args.json:
            print(json.dumps({"status": "idle", "task": None}))
        else:
            print("No approved tasks available in triage queue.")
        return 0

    if args.json:
        print(json.dumps({"status": "completed", "pr_proposal": proposal.to_dict()}, indent=2))
    else:
        print("=" * 60)
        print(f"✅ Worker executed task: {proposal.task_id}")
        print(f"Branch:      {proposal.branch_name}")
        print(f"Head Commit: {proposal.head_commit}")
        print(f"Title:       {proposal.title}")
        print(f"Gates Pass:  {proposal.gates_passed}")
        print("=" * 60)
    return 0


def cmd_admit(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    from alpha_core.eva.spec_extractor import EvaSpecificationExtractor, ExtractedSpecification

    prompt_text = args.prompt.strip()

    # If full manual flags are provided, use them; otherwise, let Eva extract autonomously!
    if getattr(args, "objective", None) and getattr(args, "allowed_paths", None):
        allowed_paths = [p.strip() for p in args.allowed_paths.split(",") if p.strip()]
        criteria = (
            [c.strip() for c in args.criteria.split(",") if c.strip()]
            if getattr(args, "criteria", None)
            else []
        )
        spec = ExtractedSpecification(
            title=prompt_text,
            summary=args.objective,
            requirements=[args.objective],
            acceptance_criteria=criteria,
            allowed_paths=allowed_paths,
            required_gates=["unit_test", "lint"],
            confidence_score=0.99,
            is_actionable=True,
        )
    else:
        print("🧠 Invoking Eva to autonomously extract engineering specification from prompt...")
        extractor = EvaSpecificationExtractor()
        extracted = extractor.extract_from_transcript(prompt_text)
        if not extracted or not extracted.is_actionable:
            print(
                "❌ Eva marked the prompt as non-actionable or could not extract an engineering task.",
                file=sys.stderr,
            )
            return 1
        spec = extracted
        if getattr(args, "allowed_paths", None):
            spec.allowed_paths = [p.strip() for p in args.allowed_paths.split(",") if p.strip()]
        elif not spec.allowed_paths:
            spec.allowed_paths = ["alpha_core/triage_cli.py", "alpha_worker/", "testscript/"]

    import hashlib
    import time

    from alpha_core.eva.task_proposer import EvaTaskProposer
    from alpha_core.queue.triage_queue import TaskProvenance, TriageStatus

    repo = str(Path.cwd().resolve())
    proposer = EvaTaskProposer()
    import subprocess

    # Resolve HEAD to strict 40-char SHA
    base_commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()

    envelope = proposer.build_task_envelope(
        spec=spec,
        project_id=args.project_id,
        repo=repo,
        base_commit=base_commit_sha,
    )

    if getattr(args, "depends_on", None):
        from alpha_protocol.task import TaskDependency, TaskStatus

        depends_on = [d.strip() for d in args.depends_on.split(",") if d.strip()]
        for d in depends_on:
            envelope.dependencies.append(
                TaskDependency(task_id=d, required_status=TaskStatus.COMPLETED)
            )

    envelope_dict = envelope.model_dump(mode="json")
    envelope_dict["acceptance_criteria"] = spec.acceptance_criteria
    envelope_dict["title"] = spec.title

    content_hash = hashlib.sha256(
        json.dumps(envelope_dict, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    ).hexdigest()

    provenance = TaskProvenance(
        meeting_id="cli_admit",
        speaker_id="founder_cli",
        utterance_timestamp=time.time(),
        transcript_excerpt=prompt_text,
        extraction_model="gemini-3.1-pro-high",
        extraction_confidence=1.0,
        eva_session_id="eva_livekit_consumer",
        created_at=time.time(),
        content_hash=content_hash,
    )

    task_id = queue.enqueue_task(
        task_id=envelope.task_id,
        envelope=envelope_dict,
        provenance=provenance,
        initial_status=TriageStatus.PENDING_REVIEW,
    )

    if args.json:
        print(json.dumps({"task_id": task_id, "status": "pending_review", "title": spec.title}))
    else:
        print("=" * 65)
        print("📥 Task Admitted into AlphaBrain Triage Queue!")
        print(f"Task ID:        {task_id}")
        print(f"Title:          {spec.title}")
        print(f"Summary:        {spec.summary}")
        print("Status:         pending_review")
        print(f"Allowed paths:  {', '.join(spec.allowed_paths)}")
        print(f"Criteria:       {', '.join(spec.acceptance_criteria)}")
        print("=" * 65)
        print("\nNext Autonomous Steps:")
        print(f"  1. Review Safety:  .venv/bin/python -m alpha_core.triage_cli review {task_id}")
        print(f"  2. Founder Approve:.venv/bin/python -m alpha_core.triage_cli approve {task_id}")
        print("  3. Worker Cycle:   .venv/bin/python -m alpha_core.triage_cli worker-cycle")
    return 0


def cmd_senior_review(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    from alpha_worker.senior_review_engine import SeniorReviewEngine

    key_id_arg = getattr(args, "key_id", None)
    key_id = (
        key_id_arg
        if isinstance(key_id_arg, str)
        else os.environ.get("ALPHA_REVIEW_KEY_ID", "alpha_production_v1")
    )
    engine = SeniorReviewEngine(queue=queue, key_id=key_id)
    try:
        verdict = engine.execute_senior_review(args.task_id)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(verdict.to_dict(), indent=2))
        return 0 if verdict.approved else 1

    print("=" * 70)
    print(f"🏛️  2-Round Senior Engineering Review for Task: {verdict.task_id}")
    print(f"Round 1 (Gemini 3.1 Pro High):      {verdict.pro_verdict}")
    print(f"Round 2 (Claude Opus 4.6 Thinking): {verdict.opus_verdict}")
    print("-" * 70)
    if verdict.approved:
        print("🟢 VERDICT: APPROVED (Certified for Autonomous Merge)")
    else:
        print("🔴 VERDICT: REPAIR_REQUIRED (Merge Blocked)")
    print("=" * 70)
    return 0 if verdict.approved else 1


def cmd_merge(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    task = queue.get_task(args.task_id)
    if not task:
        print(f"Error: Task '{args.task_id}' not found.", file=sys.stderr)
        return 1

    if task["status"] != TriageStatus.COMPLETED.value:
        print(
            f"Error: Task '{args.task_id}' is not completed. Current status: {task['status']}",
            file=sys.stderr,
        )
        return 1

    result = task.get("result") or {}
    if not result.get("gates_passed", False):
        print(
            f"Error: Acceptance gates failed or not run for task '{args.task_id}'.",
            file=sys.stderr,
        )
        return 1

    senior_review = result.get("senior_review") or {}
    if not senior_review.get("approved", False):
        print(
            f"Error: Task '{args.task_id}' has not passed 2-Round Senior Engineering Review (Pro + Opus).\n"
            f"Run '.venv/bin/python -m alpha_core.triage_cli senior-review {args.task_id}' before merging.",
            file=sys.stderr,
        )
        return 1

    worktree_path = task.get("worktree_path")
    branch_name = task.get("branch_name")
    repo_path = task.get("envelope", {}).get("repo", ".")

    if not branch_name:
        print(f"Error: Missing branch name in task record '{args.task_id}'.", file=sys.stderr)
        return 1

    # A3: SLSA Provenance check - compare branch tip to result_sha
    result_sha = result.get("result_sha")
    if not result_sha:
        result_sha = senior_review.get("result_sha")

    if not result_sha:
        print(
            "Error: Missing result_sha. Immutable result binding is required for promotion.",
            file=sys.stderr,
        )
        return 1

    attestation_dict = senior_review.get("attestation") or (senior_review.get("details") or {}).get(
        "attestation"
    )
    if not attestation_dict:
        print("Error: Missing cryptographically signed ReviewAttestation.", file=sys.stderr)
        return 1

    import os

    import pydantic

    from alpha_protocol.task import ReviewAttestation

    try:
        att = ReviewAttestation(**attestation_dict)
    except pydantic.ValidationError as e:
        if "Attestation has expired" in str(e):
            print("Error: Review attestation has expired (TTL exceeded).", file=sys.stderr)
        else:
            print(f"Error: Invalid ReviewAttestation format. {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: Invalid ReviewAttestation format. {e}", file=sys.stderr)
        return 1

    from alpha_protocol.task import REGISTERED_REVIEW_KEYS

    if att.key_id not in REGISTERED_REVIEW_KEYS:
        print(f"Error: Unknown or unregistered key_id '{att.key_id}'.", file=sys.stderr)
        return 1

    revoked_keys = os.environ.get("ALPHA_REVOKED_KEYS", "").split(",")
    if att.key_id in revoked_keys:
        print(f"Error: Attestation signed with a revoked key_id '{att.key_id}'.", file=sys.stderr)
        return 1

    signing_secret = os.environ.get(f"ALPHA_SIGNING_SECRET_{att.key_id}")
    if not signing_secret:
        print(f"Error: Missing specific signing secret for key_id '{att.key_id}'.", file=sys.stderr)
        return 1

    if not att.verify(signing_secret):
        print("Error: ReviewAttestation signature verification failed.", file=sys.stderr)
        return 1

    legacy_nonce_file = Path(repo_path) / ".alphabrain" / "seen_nonces.txt"
    promotions_dir = Path(repo_path) / ".alphabrain" / "promotions"

    if att.task_id != args.task_id:
        print(
            f"Error: Attestation task_id '{att.task_id}' does not match target task_id '{args.task_id}'.",
            file=sys.stderr,
        )
        return 1

    if att.result_sha != result_sha:
        print(
            f"Error: Attestation result_sha '{att.result_sha}' does not match expected result_sha '{result_sha}'.",
            file=sys.stderr,
        )
        return 1

    expected_base_commit = task.get("envelope", {}).get("base_commit")
    if att.base_commit != expected_base_commit:
        print(
            f"Error: Attestation base_commit '{att.base_commit}' does not match task base_commit '{expected_base_commit}'.",
            file=sys.stderr,
        )
        return 1

    if not att.approved or att.pro_verdict != "APPROVE" or att.opus_verdict != "FINAL_APPROVAL":
        print(
            "Error: Attestation indicates senior review was not approved or contains inconsistent verdicts.",
            file=sys.stderr,
        )
        return 1

    expected_evidence_digest = ReviewAttestation.compute_evidence_digest(result.get("evidence", {}))
    if att.evidence_digest != expected_evidence_digest:
        print(
            f"Error: Attestation evidence_digest '{att.evidence_digest}' does not match task evidence_digest '{expected_evidence_digest}'.",
            file=sys.stderr,
        )
        return 1

    lease_meta = (task.get("provenance") or {}).get("lease_metadata") or {}
    auth_attempt_id = lease_meta.get("attempt_id")
    auth_worker_id = lease_meta.get("worker_id")

    if not auth_attempt_id or auth_attempt_id in ("att_unknown", "None", ""):
        print(
            "Error: Task provenance is missing or has invalid authoritative lease attempt_id.",
            file=sys.stderr,
        )
        return 1

    if not auth_worker_id or auth_worker_id in ("worker_unknown", "None", ""):
        print(
            "Error: Task provenance is missing or has invalid authoritative lease worker_id.",
            file=sys.stderr,
        )
        return 1

    expected_attempt_id = result.get("attempt_id")
    expected_worker_id = result.get("worker_id")

    if not expected_attempt_id or expected_attempt_id in ("att_unknown", "None", ""):
        print("Error: Task result is missing or has invalid attempt_id.", file=sys.stderr)
        return 1

    if not expected_worker_id or expected_worker_id in ("worker_unknown", "None", ""):
        print("Error: Task result is missing or has invalid worker_id.", file=sys.stderr)
        return 1

    if expected_attempt_id != auth_attempt_id:
        print(
            f"Error: Task result attempt_id '{expected_attempt_id}' does not match authoritative lease metadata '{auth_attempt_id}'.",
            file=sys.stderr,
        )
        return 1

    if expected_worker_id != auth_worker_id:
        print(
            f"Error: Task result worker_id '{expected_worker_id}' does not match authoritative lease metadata '{auth_worker_id}'.",
            file=sys.stderr,
        )
        return 1

    if att.attempt_id != auth_attempt_id:
        print(
            f"Error: Attestation attempt_id '{att.attempt_id}' does not match authoritative lease metadata '{auth_attempt_id}'.",
            file=sys.stderr,
        )
        return 1

    if att.executor_id != auth_worker_id:
        print(
            f"Error: Attestation executor_id '{att.executor_id}' does not match authoritative lease metadata '{auth_worker_id}'.",
            file=sys.stderr,
        )
        return 1

    import time

    now = time.time()
    if now >= att.expires_at or now < att.issued_at - 60.0:
        print(
            "Error: Attestation freshness validation failed just before promotion.", file=sys.stderr
        )
        return 1

    print(f"Verifying gates passed and senior review for '{args.task_id}'... OK")
    print(f"Executing fast-forward merge of '{branch_name}' into 'main'...")

    import fcntl

    lock_file_path = Path(repo_path) / ".alphabrain" / "promotion.lock"
    lock_file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_file_path, "w") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(
                "Error: Another promotion is currently in progress. Lock acquisition failed.",
                file=sys.stderr,
            )
            return 1

        now_crit = time.time()
        if now_crit >= att.expires_at or now_crit < att.issued_at - 60.0:
            print(
                "Error: Attestation freshness validation failed inside promotion critical section.",
                file=sys.stderr,
            )
            return 1

        # 1. Legacy nonce check
        if legacy_nonce_file.exists():
            with open(legacy_nonce_file) as f:
                if att.nonce in f.read().splitlines():
                    print(
                        f"Error: Replay attack detected. Nonce '{att.nonce}' has already been used.",
                        file=sys.stderr,
                    )
                    return 1

        promotions_dir.mkdir(parents=True, exist_ok=True)
        nonce_state_file = promotions_dir / f"{att.nonce}.json"

        # 2. State machine check
        if nonce_state_file.exists():
            with open(nonce_state_file) as f:
                try:
                    state_data = json.load(f)
                except json.JSONDecodeError:
                    print("Error: Corrupt durable state found.", file=sys.stderr)
                    return 1

            if (
                state_data.get("task_id") != args.task_id
                or state_data.get("result_sha") != result_sha
                or state_data.get("attempt_id") != auth_attempt_id
                or state_data.get("base_commit") != expected_base_commit
                or state_data.get("evidence_digest") != expected_evidence_digest
                or state_data.get("tree_digest") != att.tree_digest
            ):
                print(
                    f"Error: Replay attack detected. Nonce '{att.nonce}' was used for a different request. "
                    f"State: {state_data.get('tree_digest')}, Att: {att.tree_digest}, "
                    f"State task: {state_data.get('task_id')}, Args task: {args.task_id}, "
                    f"State result: {state_data.get('result_sha')}, Result: {result_sha}, "
                    f"State attempt: {state_data.get('attempt_id')}, Auth attempt: {auth_attempt_id}, "
                    f"State base: {state_data.get('base_commit')}, Expected base: {expected_base_commit}, "
                    f"State evidence: {state_data.get('evidence_digest')}, Expected evidence: {expected_evidence_digest}",
                    file=sys.stderr,
                )
                return 1

            if state_data.get("state") == "FINALIZED":
                if getattr(args, "json", False):
                    print(json.dumps({"task_id": args.task_id, "status": "merged"}))
                else:
                    print(
                        f"✅ Successfully resumed idempotent promotion. Task '{args.task_id}' was already merged."
                    )
                return 0

            if state_data.get("state") in ("RESERVED", "APPLIED"):
                # Recover from crash
                if state_data.get("state") == "RESERVED":
                    try:
                        tip_res = subprocess.run(
                            ["git", "rev-parse", "main"],
                            cwd=repo_path,
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        if tip_res.stdout.strip() == result_sha:
                            state_data["state"] = "APPLIED"
                            _atomic_write_json(nonce_state_file, state_data)
                    except subprocess.CalledProcessError:
                        pass

                if state_data.get("state") == "APPLIED":
                    try:
                        status_res = subprocess.run(
                            ["git", "status", "--porcelain"],
                            cwd=repo_path,
                            capture_output=True,
                            text=True,
                            check=True,
                        )
                        clean_lines = []
                        for line in status_res.stdout.splitlines():
                            if len(line) < 3 or line[2] != " ":
                                continue
                            if line[3:].startswith(".alphabrain/"):
                                continue
                            clean_lines.append(line)

                        if clean_lines:
                            print(
                                "Error: Working tree is not clean. Aborting recovery.",
                                file=sys.stderr,
                            )
                            return 1

                        current_main = subprocess.run(
                            ["git", "rev-parse", "main"],
                            cwd=repo_path,
                            check=True,
                            capture_output=True,
                            text=True,
                        ).stdout.strip()

                        if current_main != result_sha:
                            is_ancestor = subprocess.run(
                                ["git", "merge-base", "--is-ancestor", result_sha, current_main],
                                cwd=repo_path,
                            ).returncode == 0
                            if is_ancestor:
                                print(
                                    "Error: main has advanced beyond result_sha. Aborting recovery.",
                                    file=sys.stderr,
                                )
                                return 1

                        subprocess.run(
                            ["git", "checkout", "main"],
                            cwd=repo_path,
                            check=True,
                            capture_output=True,
                        )
                        subprocess.run(
                            ["git", "reset", "--hard", result_sha],
                            cwd=repo_path,
                            check=True,
                            capture_output=True,
                        )
                    except subprocess.CalledProcessError as e:
                        print(f"Error: Recovery failed.\n{e.stderr}", file=sys.stderr)
                        return 1

                    state_data["state"] = "FINALIZED"
                    _atomic_write_json(nonce_state_file, state_data)

                    if getattr(args, "json", False):
                        print(json.dumps({"task_id": args.task_id, "status": "merged"}))
                    else:
                        print(
                            f"✅ Successfully recovered from crash. Task '{args.task_id}' was already merged."
                        )
                    return 0
        else:
            # 3. Reserve nonce
            state_data = {
                "nonce": att.nonce,
                "task_id": args.task_id,
                "result_sha": result_sha,
                "attempt_id": auth_attempt_id,
                "base_commit": expected_base_commit,
                "evidence_digest": expected_evidence_digest,
                "tree_digest": att.tree_digest,
                "state": "RESERVED",
            }
            _atomic_write_json(nonce_state_file, state_data)

        # 4. Verify branch tips and trees now that we are in the reservation lock and guaranteed not to be a replay
        try:
            tip_res = subprocess.run(
                ["git", "rev-parse", branch_name],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            branch_tip = tip_res.stdout.strip()
            if branch_tip != result_sha:
                print(
                    f"Error: SLSA Provenance Failure. Branch tip {branch_tip} does not match approved result_sha {result_sha}.",
                    file=sys.stderr,
                )
                return 1

            tree_res = subprocess.run(
                ["git", "rev-parse", f"{branch_name}^{{tree}}"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            branch_tree = tree_res.stdout.strip()
            if branch_tree != att.tree_digest:
                print(
                    f"Error: SLSA Provenance Failure. Branch tree {branch_tree} does not match attestation tree_digest {att.tree_digest}.",
                    file=sys.stderr,
                )
                return 1
        except subprocess.CalledProcessError:
            print(f"Error: Could not resolve branch {branch_name} or its tree.", file=sys.stderr)
            return 1

        # 4.5. Fast-forward Ancestry Check
        try:
            ancestry_res = subprocess.run(
                ["git", "merge-base", "--is-ancestor", expected_base_commit, result_sha],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if ancestry_res.returncode != 0:
                print(
                    f"Error: SLSA Provenance Failure. Result commit {result_sha} is not a fast-forward of base {expected_base_commit}.",
                    file=sys.stderr,
                )
                return 1
        except subprocess.CalledProcessError as e:
            print(f"Error: Git ancestry check failed.\n{e.stderr}", file=sys.stderr)
            return 1

        # 5. CAS Destination Base Check and Update
        try:
            status_res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True,
            )
            clean_lines = []
            for line in status_res.stdout.splitlines():
                if len(line) < 3 or line[2] != " ":
                    continue
                if line[3:].startswith(".alphabrain/"):
                    continue
                clean_lines.append(line)

            if clean_lines:
                print("Error: Working tree is not clean. Aborting promotion.", file=sys.stderr)
                return 1

            # Atomic compare and swap of refs/heads/main
            update_res = subprocess.run(
                [
                    "git",
                    "update-ref",
                    "-m",
                    "Atomic promotion",
                    "refs/heads/main",
                    result_sha,
                    expected_base_commit,
                ],
                cwd=repo_path,
                capture_output=True,
                text=True,
            )
            if update_res.returncode != 0:
                print(
                    f"Error: Destination base has advanced or update failed. {update_res.stderr}",
                    file=sys.stderr,
                )
                return 1

            # Transition to APPLIED state
            state_data["state"] = "APPLIED"
            _atomic_write_json(nonce_state_file, state_data)

            # Checkout main and reset to ensure index/working tree are in sync with the new HEAD
            subprocess.run(
                ["git", "checkout", "main"],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "reset", "--hard", result_sha],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"Error: Git operations failed.\n{e.stderr}", file=sys.stderr)
            return 1

        # 6. Finalize state
        state_data["state"] = "FINALIZED"
        _atomic_write_json(nonce_state_file, state_data)

        if worktree_path and Path(worktree_path).exists():
            print(f"Pruning git worktree '{worktree_path}'...")
            try:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", worktree_path],
                    cwd=repo_path,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as e:
                print(
                    f"Warning: Failed to prune worktree '{worktree_path}'.\n{e.stderr}",
                    file=sys.stderr,
                )

        print(f"Deleting task branch '{branch_name}'...")
        try:
            subprocess.run(
                ["git", "branch", "-d", branch_name],
                cwd=repo_path,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"Warning: Failed to delete branch '{branch_name}'.\n{e.stderr}", file=sys.stderr)

    if getattr(args, "json", False):
        print(json.dumps({"task_id": args.task_id, "status": "merged"}))
    else:
        print(f"✅ Successfully merged and pruned task '{args.task_id}'.")

    return 0


def cmd_dag(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    tasks = queue.list_tasks(limit=1000)

    # Build a lookup and graph
    task_map = {t["id"]: t for t in tasks}
    children: dict[str, list[str]] = {t["id"]: [] for t in tasks}

    # Find roots (tasks with no dependencies)
    roots = []
    for t in tasks:
        deps = t.get("envelope", {}).get("dependencies", [])
        if not deps:
            roots.append(t["id"])
        for d in deps:
            dep_id = d.get("task_id")
            if dep_id:
                if dep_id in children:
                    children[dep_id].append(t["id"])
                else:
                    # Dependency doesn't exist in the current subset
                    pass

    if args.json:
        # Just return the graph structure
        print(json.dumps({"tasks": task_map, "graph": children}, indent=2, default=str))
        return 0

    print("Task Dependency DAG:")
    visited = set()

    def print_tree(node_id: str, prefix: str = ""):
        if node_id in visited:
            print(f"{prefix}└── {node_id} (shared — already displayed)")
            return
        visited.add(node_id)

        t = task_map.get(node_id)
        if not t:
            print(f"{prefix}└── {node_id} [NOT FOUND]")
            return

        status = t.get("status", "unknown")
        print(f"{prefix}└── {node_id} [{status.upper()}]")

        child_nodes = children.get(node_id, [])
        for i, child_id in enumerate(child_nodes):
            is_last = i == len(child_nodes) - 1
            new_prefix = prefix + ("    " if is_last else "│   ")
            print_tree(child_id, new_prefix)

    for root in roots:
        print_tree(root, "")

    return 0


def cmd_stats(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    stats = queue.get_stats()

    if getattr(args, "json", False):
        print(json.dumps(stats, indent=2))
        return 0

    print("=" * 50)
    print("Pipeline Metrics Summary")
    print("=" * 50)
    print(f"Total Tasks: {stats['total_tasks']}")
    print("-" * 50)
    print("Counts by Status:")
    for st, count in cast(dict[str, int], stats["by_status"]).items():
        print(f"  {st.ljust(15)}: {count}")
    print("-" * 50)
    print("Queue Wait (seconds):")
    print(f"  Average: {cast(dict[str, float], stats['queue_wait_seconds'])['average']:.2f}")
    print(f"  Median:  {cast(dict[str, float], stats['queue_wait_seconds'])['median']:.2f}")
    print("Execution Duration (seconds):")
    print(
        f"  Average: {cast(dict[str, float], stats['execution_duration_seconds'])['average']:.2f}"
    )
    print(f"  Median:  {cast(dict[str, float], stats['execution_duration_seconds'])['median']:.2f}")
    print("=" * 50)

    return 0


def cmd_healing_daemon(args: argparse.Namespace, queue: TaskTriageQueue) -> int:
    try:
        from alpha_worker.ci_healing_daemon import CIHealingDaemon

        daemon = CIHealingDaemon(queue, project_id=args.project_id)

        if args.continuous:
            daemon.run_continuously(interval=args.interval)
        else:
            daemon.run_once()

        if args.json:
            print(json.dumps({"status": "ok", "message": "Healing daemon run completed"}))
        else:
            print("✅ Healing daemon completed.")
        return 0
    except Exception as e:
        import traceback

        if args.json:
            print(json.dumps({"error": str(e), "traceback": traceback.format_exc()}))
        else:
            print(f"❌ Error running healing daemon: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alphabrain triage",
        description="AlphaBrain Task Triage Queue & Safety Review CLI",
    )
    parser.add_argument(
        "--db-path", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite queue database"
    )
    parser.add_argument(
        "--emergency-lock",
        type=Path,
        default=DEFAULT_EMERGENCY_LOCK,
        help="Path to emergency stop lockfile",
    )

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List tasks in the triage queue")
    p_list.add_argument(
        "--status",
        choices=[s.value for s in TriageStatus] + ["all"],
        default="all",
        help="Filter by status",
    )
    p_list.add_argument("--limit", type=int, default=20, help="Maximum number of tasks to return")
    p_list.add_argument("--json", action="store_true", help="Output JSON format")

    # show
    p_show = subparsers.add_parser("show", help="Show full task details")
    p_show.add_argument("task_id", help="ID of the task to view")
    p_show.add_argument("--json", action="store_true", help="Output JSON format")

    # review
    p_review = subparsers.add_parser("review", help="Run SafetyGate verification on a task")
    p_review.add_argument("task_id", help="ID of the task to review")
    p_review.add_argument("--json", action="store_true", help="Output JSON format")

    # approve
    p_approve = subparsers.add_parser("approve", help="Approve task for worker intake")
    p_approve.add_argument("task_id", help="ID of the task to approve")
    p_approve.add_argument("--notes", help="Optional approval notes")
    p_approve.add_argument(
        "--force", action="store_true", help="Force approval overriding safety gate rejection"
    )
    p_approve.add_argument("--json", action="store_true", help="Output JSON format")

    # reject
    p_reject = subparsers.add_parser("reject", help="Reject task with reason")
    p_reject.add_argument("task_id", help="ID of the task to reject")
    p_reject.add_argument("--reason", required=True, help="Reason for rejection")
    p_reject.add_argument("--json", action="store_true", help="Output JSON format")

    # retry
    p_retry = subparsers.add_parser(
        "retry", help="Reset a FAILED task back to APPROVED for worker retry"
    )
    p_retry.add_argument("task_id", help="ID of the failed task to retry")
    p_retry.add_argument("--notes", help="Optional operator retry notes")
    p_retry.add_argument("--json", action="store_true", help="Output JSON format")

    # modify
    p_modify = subparsers.add_parser(
        "modify", help="Safely modify task envelope and re-run SafetyGate"
    )
    p_modify.add_argument("task_id", help="ID of the task to modify")
    p_modify.add_argument("--allowed-paths", help="Comma-separated allowed file paths")
    p_modify.add_argument("--title", help="New task title")
    p_modify.add_argument("--description", help="New task description")
    p_modify.add_argument("--notes", help="Reviewer audit notes")
    p_modify.add_argument("--json", action="store_true", help="Output JSON format")

    # emergency-stop
    p_stop = subparsers.add_parser("emergency-stop", help="Activate emergency stop tombstone")
    p_stop.add_argument("--reason", default="operator_requested", help="Reason for emergency stop")
    p_stop.add_argument("--json", action="store_true", help="Output JSON format")

    # emergency-resume
    p_resume = subparsers.add_parser("emergency-resume", help="Clear emergency stop tombstone")
    p_resume.add_argument("--json", action="store_true", help="Output JSON format")

    # emergency-status
    p_status = subparsers.add_parser("emergency-status", help="Check emergency stop status")
    p_status.add_argument("--json", action="store_true", help="Output JSON format")

    # worker-cycle
    p_worker = subparsers.add_parser(
        "worker-cycle", help="Run a worker polling and execution cycle"
    )
    p_worker.add_argument("--json", action="store_true", help="Output JSON format")

    # admit
    p_admit = subparsers.add_parser("admit", help="Admit a new task into the triage queue")
    p_admit.add_argument("prompt", help="Natural language request or task description")
    p_admit.add_argument("--objective", help="Optional detailed objective")
    p_admit.add_argument("--allowed-paths", help="Optional comma-separated allowed file paths")
    p_admit.add_argument(
        "--criteria",
        help="Optional comma-separated acceptance criteria",
    )
    p_admit.add_argument("--depends-on", help="Optional comma-separated list of dependent task IDs")
    p_admit.add_argument("--project-id", default="alphabrain_dogfood", help="Project ID")
    p_admit.add_argument("--json", action="store_true", help="Output JSON format")

    # senior-review
    p_senior = subparsers.add_parser(
        "senior-review", help="Execute 2-round senior engineering review (Pro + Opus)"
    )
    p_senior.add_argument("task_id", help="ID of the completed task to review")
    p_senior.add_argument("--key-id", default=None, help="Registered signing key identifier")
    p_senior.add_argument("--json", action="store_true", help="Output JSON format")

    # merge
    p_merge = subparsers.add_parser(
        "merge", help="Fast-forward merge a completed task branch and prune worktree"
    )
    p_merge.add_argument("task_id", help="ID of the task to merge")
    p_merge.add_argument(
        "--skip-senior-review", action="store_true", help="Bypass mandatory 2-round senior review"
    )
    p_merge.add_argument("--json", action="store_true", help="Output JSON format")

    # export-audit
    p_export_audit = subparsers.add_parser(
        "export-audit", help="Export full cryptographic provenance and execution history"
    )
    p_export_audit.add_argument("task_id", help="ID of the task to export")
    p_export_audit.add_argument("--output", help="Output JSON file path")

    # dag
    p_dag = subparsers.add_parser("dag", help="Display the task dependency DAG")
    p_dag.add_argument("--json", action="store_true", help="Output JSON format")

    # stats
    p_stats = subparsers.add_parser(
        "stats", help="Compute aggregate pipeline metrics and telemetry"
    )
    p_stats.add_argument("--json", action="store_true", help="Output JSON format")

    # healing-daemon
    p_healing = subparsers.add_parser(
        "healing-daemon", help="Run CIHealingDaemon to orchestrate auto-merge and failure diagnosis"
    )
    p_healing.add_argument(
        "--project-id", default="prj_phase10", help="Project ID for synthesized tasks"
    )
    p_healing.add_argument("--continuous", action="store_true", help="Run continuously in a loop")
    p_healing.add_argument(
        "--interval", type=float, default=10.0, help="Interval in seconds for continuous mode"
    )
    p_healing.add_argument("--json", action="store_true", help="Output JSON format")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    queue = TaskTriageQueue(
        db_path=args.db_path,
        emergency_lock_path=args.emergency_lock,
    )

    handlers = {
        "admit": cmd_admit,
        "list": cmd_list,
        "show": cmd_show,
        "review": cmd_review,
        "approve": cmd_approve,
        "reject": cmd_reject,
        "retry": cmd_retry,
        "modify": cmd_modify,
        "emergency-stop": cmd_emergency_stop,
        "emergency-resume": cmd_emergency_resume,
        "emergency-status": cmd_emergency_status,
        "worker-cycle": cmd_worker_cycle,
        "senior-review": cmd_senior_review,
        "merge": cmd_merge,
        "export-audit": cmd_export_audit,
        "dag": cmd_dag,
        "stats": cmd_stats,
        "healing-daemon": cmd_healing_daemon,
    }

    handler = handlers.get(args.subcommand)
    if not handler:
        parser.print_help()
        return 1
    return handler(args, queue)


if __name__ == "__main__":
    sys.exit(main())
