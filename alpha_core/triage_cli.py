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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    queue = TaskTriageQueue(
        db_path=args.db_path,
        emergency_lock_path=args.emergency_lock,
    )

    handlers = {
        "list": cmd_list,
        "show": cmd_show,
        "review": cmd_review,
        "approve": cmd_approve,
        "reject": cmd_reject,
        "modify": cmd_modify,
        "emergency-stop": cmd_emergency_stop,
        "emergency-resume": cmd_emergency_resume,
        "emergency-status": cmd_emergency_status,
    }

    handler = handlers.get(args.subcommand)
    if not handler:
        parser.print_help()
        return 1
    return handler(args, queue)


if __name__ == "__main__":
    sys.exit(main())
