#!/usr/bin/env python3
"""
Runs concurrent senior-research, senior-plan, and approve across all remaining epics (E1..E7)
"""

import concurrent.futures
import subprocess

TASKS = [
    ("E1", "tsk_eva_13c288859a81"),
    ("E2", "tsk_eva_aca04ab95ffe"),
    ("E3", "tsk_eva_5f7f03060e86"),
    ("E4", "tsk_eva_5786b037f554"),
    ("E5", "tsk_eva_29ba2dc8c16f"),
    ("E6", "tsk_eva_7a385b637168"),
    ("E7", "tsk_eva_c57aaa9710fb"),
]

PYTHON = "/Users/ajaytiwari/Desktop/Projects/alphaBrain/.venv/bin/python"

def process_task(epic_name, task_id):
    snapshot_path = f"/tmp/snapshot_{epic_name.lower()}.json"
    print(f"[{epic_name}] Starting senior-research for {task_id}...")

    # 1. Senior Research
    res = subprocess.run(
        [PYTHON, "-m", "alpha_core.triage_cli", "senior-research", task_id, "--output", snapshot_path],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        return f"[{epic_name}] Research failed: {res.stderr}"

    print(f"[{epic_name}] Research complete. Starting senior-plan...")

    # 2. Senior Plan
    res = subprocess.run(
        [PYTHON, "-m", "alpha_core.triage_cli", "senior-plan", task_id, "--snapshot", snapshot_path],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        return f"[{epic_name}] Plan failed: {res.stderr}"

    print(f"[{epic_name}] Plan complete. Executing founder approval...")

    # 3. Approve
    res = subprocess.run(
        [PYTHON, "-m", "alpha_core.triage_cli", "approve", task_id],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        return f"[{epic_name}] Approve failed: {res.stderr}"

    return f"[{epic_name}] Successfully APPROVED for worker intake!"

def main():
    print(f"Dispatching Senior Planning across {len(TASKS)} epics in parallel...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=7) as executor:
        futures = {executor.submit(process_task, epic, tid): epic for epic, tid in TASKS}
        for future in concurrent.futures.as_completed(futures):
            epic = futures[future]
            try:
                result = future.result()
                print(result)
            except Exception as exc:
                print(f"[{epic}] Generated an exception: {exc}")

if __name__ == "__main__":
    main()
