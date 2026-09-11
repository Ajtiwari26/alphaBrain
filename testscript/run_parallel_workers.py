"""
testscript/run_parallel_workers.py
Launches Task 10 (CI Healing Daemon) and Task 11 (Metrics Exporter) concurrently
via ParallelWorkerDispatcher and streams live output logs.
"""

import sys
import time
from pathlib import Path

from alpha_core.queue.triage_queue import TaskTriageQueue, TriageStatus
from alpha_worker.parallel_dispatcher import ParallelWorkerDispatcher


def main() -> int:
    queue = TaskTriageQueue()
    approved_tasks = queue.list_tasks(status=TriageStatus.APPROVED)
    print(f"[*] Found {len(approved_tasks)} approved task(s) in queue:")
    for t in approved_tasks:
        print(f"    - {t['id']}: {t['envelope'].get('title')}")

    if not approved_tasks:
        print("[!] No approved tasks to dispatch. Exiting.")
        return 1

    log_dir = Path.home() / ".alphabrain" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    dispatcher = ParallelWorkerDispatcher(
        queue=queue,
        max_workers=2,
        execution_mode="subprocess",
        timeout_seconds=900,
    )

    dispatched = []
    for _ in range(min(2, len(approved_tasks))):
        tid = dispatcher.lease_and_dispatch_next()
        if tid:
            dispatched.append(tid)
            print(f"[+] Dispatched task to worker pool: {tid}")

    if not dispatched:
        print("[!] Failed to dispatch any tasks.")
        return 1

    print(f"[*] Actively monitoring {len(dispatched)} concurrent task(s)...")

    log_files = {tid: log_dir / f"{tid}.log" for tid in dispatched}
    log_offsets = dict.fromkeys(dispatched, 0)

    while dispatcher.active_count() > 0:
        time.sleep(1.0)
        for tid in dispatched:
            lfile = log_files[tid]
            if lfile.exists():
                try:
                    with open(lfile, encoding="utf-8", errors="replace") as f:
                        f.seek(log_offsets[tid])
                        new_lines = f.read()
                        if new_lines:
                            log_offsets[tid] = f.tell()
                            for line in new_lines.splitlines():
                                print(f"[{tid[:11]}] {line}")
                                sys.stdout.flush()
                except Exception:
                    pass

        reaped = dispatcher.reap_completed_tasks()
        if reaped.get("completed") or reaped.get("failed"):
            print(f"[*] Reaper cycle: completed={reaped.get('completed')}, failed={reaped.get('failed')}")

    for tid in dispatched:
        lfile = log_files[tid]
        if lfile.exists():
            try:
                with open(lfile, encoding="utf-8", errors="replace") as f:
                    f.seek(log_offsets[tid])
                    new_lines = f.read()
                    if new_lines:
                        for line in new_lines.splitlines():
                            print(f"[{tid[:11]}] {line}")
                            sys.stdout.flush()
            except Exception:
                pass

    print("\n[+] All dispatched workers have completed execution.")
    print("=" * 65)
    for tid in dispatched:
        t = queue.get_task(tid)
        st = t.get("status") if t else "unknown"
        print(f"Task {tid} final queue status: {st}")
        if st == "failed" and t:
            print(f"  Error details: {t.get('result', {}).get('error')}")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(main())
