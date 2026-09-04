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
import subprocess
import sys
from pathlib import Path

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
    envelope = proposer.build_task_envelope(
        spec=spec,
        project_id=args.project_id,
        repo=repo,
        base_commit="HEAD",
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

    engine = SeniorReviewEngine(queue=queue)
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
    skip_sr = getattr(args, "skip_senior_review", False)
    if not senior_review.get("approved", False) and not skip_sr:
        print(
            f"Error: Task '{args.task_id}' has not passed 2-Round Senior Engineering Review (Pro + Opus).\n"
            f"Run '.venv/bin/python -m alpha_core.triage_cli senior-review {args.task_id}' before merging,\n"
            f"or supply --skip-senior-review for emergency operator override.",
            file=sys.stderr,
        )
        return 1

    worktree_path = task.get("worktree_path")
    branch_name = task.get("branch_name")
    repo_path = task.get("envelope", {}).get("repo", ".")

    if not branch_name:
        print(f"Error: Missing branch name in task record '{args.task_id}'.", file=sys.stderr)
        return 1

    print(f"Verifying gates passed and senior review for '{args.task_id}'... OK")
    print(f"Executing fast-forward merge of '{branch_name}' into 'main'...")
    try:
        subprocess.run(
            ["git", "checkout", "main"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )
        res = subprocess.run(
            ["git", "merge", "--ff-only", branch_name],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )
        if res.stdout.strip():
            print(res.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"Error: Fast-forward merge failed.\n{e.stderr}", file=sys.stderr)
        return 1

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
    children = {t["id"]: [] for t in tasks}

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
    import statistics

    tasks = queue.list_tasks(limit=100000)
    total_count = len(tasks)
    status_counts = {s.value: 0 for s in TriageStatus}

    queue_waits = []
    exec_durations = []

    for t in tasks:
        status = t.get("status")
        if status in status_counts:
            status_counts[status] += 1

        telemetry = queue.get_task_telemetry(t["id"])

        qw = telemetry.get("queue_wait_seconds")
        if qw is not None:
            queue_waits.append(qw)

        ed = telemetry.get("execution_duration_seconds")
        if ed is not None:
            exec_durations.append(ed)

    stats = {
        "total_tasks": total_count,
        "by_status": status_counts,
        "queue_wait_seconds": {
            "average": float(statistics.mean(queue_waits)) if queue_waits else 0.0,
            "median": float(statistics.median(queue_waits)) if queue_waits else 0.0,
        },
        "execution_duration_seconds": {
            "average": float(statistics.mean(exec_durations)) if exec_durations else 0.0,
            "median": float(statistics.median(exec_durations)) if exec_durations else 0.0,
        },
    }

    if getattr(args, "json", False):
        print(json.dumps(stats, indent=2))
        return 0

    print("=" * 50)
    print("Pipeline Metrics Summary")
    print("=" * 50)
    print(f"Total Tasks: {stats['total_tasks']}")
    print("-" * 50)
    print("Counts by Status:")
    for st, count in stats["by_status"].items():
        print(f"  {st.ljust(15)}: {count}")
    print("-" * 50)
    print("Queue Wait (seconds):")
    print(f"  Average: {stats['queue_wait_seconds']['average']:.2f}")
    print(f"  Median:  {stats['queue_wait_seconds']['median']:.2f}")
    print("Execution Duration (seconds):")
    print(f"  Average: {stats['execution_duration_seconds']['average']:.2f}")
    print(f"  Median:  {stats['execution_duration_seconds']['median']:.2f}")
    print("=" * 50)

    return 0


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
    }

    handler = handlers.get(args.subcommand)
    if not handler:
        parser.print_help()
        return 1
    return handler(args, queue)


if __name__ == "__main__":
    sys.exit(main())
