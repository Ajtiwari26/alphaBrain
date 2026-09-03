import asyncio
import httpx
import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
import os

BASE_URL = "https://alpha-brain-staging.onrender.com"

def get_keychain_token():
    try:
        output = subprocess.check_output(
            ["security", "find-generic-password", "-s", "com.deploymate.alphabrain", "-a", "alpha-api-token", "-w"],
            text=True
        )
        return output.strip()
    except subprocess.CalledProcessError:
        raise RuntimeError("Could not read alpha-api-token from Keychain")

async def main():
    token = get_keychain_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 1. Create a dummy project
    project_id = f"prj_p64_{uuid.uuid4().hex[:8]}"
    project_payload = {
        "project_id": project_id,
        "name": "P6.4 Test Project",
        "repo_path": os.getcwd(),
        "worktree_path": os.getcwd(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Creating project...", flush=True)
        r = await client.post(f"{BASE_URL}/api/projects", json=project_payload, headers=headers)
        if r.status_code not in (200, 201) and r.status_code != 409:
            print(f"Failed to create project: {r.status_code} {r.text}", flush=True)
            return
        
        # 2. Enqueue an idempotent task
        task_id = f"tsk_p64_{uuid.uuid4().hex[:8]}"
        task_payload = {
            "task_id": task_id,
            "project_id": project_id,
            "repo": os.getcwd(),
            "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip(),
            "objective": "Lint the codebase",
            "description": "Run a dry-run linter check on the codebase. Do NOT write any files. Output the linter results.",
            "status": "pending",
            "priority": "normal",
            "allowed_tools": ["read_file", "run_command"],
            "allowed_paths": ["."],
            "risk_class": "low",
            "preferred_agent": "antigravity",
            "lease_timeout_seconds": 300,
            "retry_policy": {"max_attempts": 1, "deadline_seconds": 600},
            "concurrency_policy": {"max_per_project": 1, "max_per_worker": 1},
            "requires_approval": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "acceptance_plan": {
                "required_gates": ["unit_test"],
                "commands": [
                    {
                        "gate_type": "unit_test",
                        "executable": "pytest",
                        "args": ["--version"]
                    }
                ]
            }
        }
        
        print(f"Enqueuing task {task_id}...", flush=True)
        r = await client.post(f"{BASE_URL}/api/tasks", json=task_payload, headers=headers)
        if r.status_code not in (200, 201):
            print(f"Failed to enqueue task: {r.status_code} {r.text}", flush=True)
            return
            
        print("Task enqueued. Waiting for completion...", flush=True)
        
        # 3. Poll for completion
        deadline = time.time() + 300
        while time.time() < deadline:
            r = await client.get(f"{BASE_URL}/api/tasks/{task_id}", headers=headers)
            if r.status_code == 200:
                task = r.json()
                status = task.get("status")
                print(f"Status: {status}", flush=True)
                if status in ("completed", "failed", "blocked"):
                    print(f"Final status: {status}", flush=True)
                    
                    # Get execution events
                    r_events = await client.get(f"{BASE_URL}/api/tasks/{task_id}/events", headers=headers)
                    if r_events.status_code == 200:
                        with open("testscript/evidence/p6_4_trace.json", "w") as f:
                            json.dump(r_events.json(), f, indent=2)
                        print("Trace saved to testscript/evidence/p6_4_trace.json", flush=True)
                    
                    if status == "completed":
                        print("P6.4 PROOF SUCCESSFUL", flush=True)
                        return
                    else:
                        print("P6.4 PROOF FAILED", flush=True)
                        return
            
            await asyncio.sleep(5)
            
        print("Timed out waiting for task completion.", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
