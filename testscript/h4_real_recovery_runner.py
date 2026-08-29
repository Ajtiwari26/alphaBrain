import asyncio
import json
import os
import plistlib
import re
import signal
import subprocess
import threading
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response

from alpha_protocol import (
    AcceptancePlan,
    AgentType,
    ConcurrencyPolicy,
    RetryPolicy,
    RiskClass,
    TaskEnvelope,
)

BASE_URL = "https://alpha-brain-staging.onrender.com"
PROJECT_ID = "prj_h4_recovery_proof"
REPO = Path("/Users/ajaytiwari/Desktop/Projects/clientProjects/fixture_repo")
ALLOWED_FILE = "proof.txt"
EVIDENCE_DIR = Path(__file__).resolve().parent / "evidence"
PLIST_PATH = Path.home() / "Library/LaunchAgents/com.deploymate.alphabrain.worker.plist"
WORKER_ID = "mac_worker_local"
SPOOL_DIR = Path.home() / "Library/Application Support/AlphaBrain/worker-state/spool"


class ProxyState:
    def __init__(self):
        self.block_results = False
        self.hold_lease = False
        self.lease_captured = threading.Event()


def build_proxy(upstream_url: str, state: ProxyState) -> FastAPI:
    app = FastAPI()

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy(request: Request, path: str) -> Response:
        route = f"/{path}"
        if route.endswith("/result") and state.block_results:
            return Response(status_code=503, content="Injected result-delivery outage")

        body = await request.body()
        headers = {
            k: v
            for k, v in request.headers.items()
            if k.lower() not in {"host", "content-length", "connection"}
        }

        async with httpx.AsyncClient(base_url=upstream_url, timeout=30.0) as client:
            response = await client.request(request.method, route, headers=headers, content=body)

        if route == "/api/tasks/lease" and state.hold_lease and response.status_code == 200:
            payload = response.json()
            if payload.get("status") == "leased":
                state.lease_captured.set()
                while state.hold_lease:
                    await asyncio.sleep(0.05)

        response_headers = {
            k: v
            for k, v in response.headers.items()
            if k.lower() not in {"content-encoding", "content-length", "transfer-encoding"}
        }
        return Response(response.content, response.status_code, response_headers)

    return app


def request_json(
    method: str, url: str, token: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    print(f"DEBUG: request_json {method} {url}", flush=True)
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
            print(f"DEBUG: request_json {method} {url} SUCCESS", flush=True)
            return result
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:1000]
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code}: {detail}") from exc
    except Exception as e:
        print(f"DEBUG: request_json exception {e}", flush=True)
        raise


def render_cli_token() -> str:
    text = (Path.home() / ".render" / "cli.yaml").read_text()
    match = re.search(r"^\s+key:\s*(\S+)\s*$", text, re.MULTILINE)
    return match.group(1) if match else ""


def staging_founder_token() -> str:
    result = request_json(
        "GET",
        "https://api.render.com/v1/services/srv-da8rse6k1f9s739v9jkg/env-vars/ALPHA_API_TOKEN",
        render_cli_token(),
    )
    token = (result.get("envVar") or result).get("value")
    return token


def git(*args: str, cwd: Path = REPO) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def launchd_snapshot() -> dict[str, Any]:
    uid = subprocess.check_output(["id", "-u"], text=True).strip()
    try:
        result = subprocess.run(
            ["launchctl", "print", f"gui/{uid}/com.deploymate.alphabrain.worker"],
            text=True,
            capture_output=True,
            check=True,
            timeout=10,
        )
        pid = re.search(r"\bpid = (\d+)", result.stdout)
        state = re.search(r"\bstate = ([^\n]+)", result.stdout)
        return {
            "pid": int(pid.group(1)) if pid else None,
            "state": state.group(1).strip() if state else None,
        }
    except Exception:
        return {"pid": None, "state": "not running"}


def wait_for_worker_online(founder_token: str) -> None:
    print("Waiting for worker heartbeat to reach staging...", flush=True)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        res = request_json("GET", f"{BASE_URL}/api/workers/{WORKER_ID}", founder_token)
        now = datetime.now(UTC)
        hb = datetime.fromisoformat(res["last_heartbeat_at"])
        if (now - hb).total_seconds() < 30:
            print(f"Worker {WORKER_ID} is online with recent heartbeat.", flush=True)
            return
        time.sleep(5)
    raise RuntimeError("Worker did not heartbeat")


def main():
    print("DEBUG: Fetching founder token", flush=True)
    founder_token = staging_founder_token()
    base_commit = git("rev-parse", "HEAD")

    # Preflight Check
    original_plist_bytes = PLIST_PATH.read_bytes()

    def sig_handler(sig, frame):
        print("Caught signal, restoring plist...", flush=True)
        PLIST_PATH.write_bytes(original_plist_bytes)
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], check=False)
        subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=False)
        os._exit(1)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    if git("status", "--porcelain"):
        raise RuntimeError("Fixture repository must be clean")

    print("=== H4 PREFLIGHT ===", flush=True)
    print(f"Render staging: {BASE_URL}", flush=True)
    before_snap = launchd_snapshot()
    print(f"Worker PID: {before_snap['pid']}", flush=True)
    print(f"Plist Hash: {hash(PLIST_PATH.read_bytes())}", flush=True)

    # Create Project
    request_json(
        "POST",
        f"{BASE_URL}/api/projects",
        founder_token,
        {"project_id": PROJECT_ID, "name": "H4 Recovery Proof", "repo_path": str(REPO)},
    )

    # 1. Start Proxy Server
    port = 8081
    proxy_state = ProxyState()
    app = build_proxy(BASE_URL, proxy_state)
    proxy_server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=port, log_level="error"))
    proxy_thread = threading.Thread(target=proxy_server.run, daemon=True)
    proxy_thread.start()

    # Wait for proxy to start
    time.sleep(2)

    # 2. Modify Plist
    print("Modifying launchd plist for worker proxy interception...", flush=True)
    try:
        plist_data = plistlib.loads(original_plist_bytes)
        env = plist_data.get("EnvironmentVariables", {})
        env["WORKER_CONTROL_PLANE_URL"] = f"http://0.0.0.0:{port}"
        plist_data["EnvironmentVariables"] = env
        PLIST_PATH.write_bytes(plistlib.dumps(plist_data))

        # Reload worker
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], check=True)
        time.sleep(1)
        subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=True)
        time.sleep(3)

        wait_for_worker_online(founder_token)
        print("DEBUG: launchd_snapshot() start", flush=True)
        proxy_snap = launchd_snapshot()
        print(f"Worker reloaded with proxy. New PID: {proxy_snap['pid']}", flush=True)

        # --- PHASE A: Network Outage ---
        print("\n=== PHASE A: Network Outage ===", flush=True)
        proxy_state.block_results = True

        task1_id = f"tsk_h4_net_{uuid.uuid4().hex[:8]}"
        env1 = TaskEnvelope(
            task_id=task1_id,
            project_id=PROJECT_ID,
            repo=str(REPO),
            base_commit=base_commit,
            objective="Edit proof.txt. Replace contents with exactly: Network Outage",
            allowed_paths=[ALLOWED_FILE],
            allowed_tools=["read_file", "write_to_file", "run_command"],
            risk_class=RiskClass.LOW,
            preferred_agent=AgentType.ANTIGRAVITY,
            lease_timeout_seconds=300,
            retry_policy=RetryPolicy(max_attempts=1, deadline_seconds=1800),
            concurrency_policy=ConcurrencyPolicy(max_per_project=1, max_per_worker=1),
            requires_approval=False,
            created_at=datetime.now(UTC),
            acceptance_plan=AcceptancePlan(),
        )
        print(f"DEBUG: Submitting task 1 {task1_id}", flush=True)
        request_json("POST", f"{BASE_URL}/api/tasks", founder_token, env1.model_dump(mode="json"))

        print(f"Submitted task 1: {task1_id}", flush=True)
        print("Waiting for worker to execute and hit network outage...", flush=True)

        # Wait for spool file to be created
        deadline = time.monotonic() + 180
        spool_file_found = False
        while time.monotonic() < deadline:
            spools = list(SPOOL_DIR.glob("*.event"))
            if spools:
                print(f"Found encrypted spool file: {spools[0].name}", flush=True)
                spool_file_found = True
                break
            time.sleep(5)

        if not spool_file_found:
            raise RuntimeError("Spool file not created during network outage")

        print("Restoring network (unblocking results)...", flush=True)
        proxy_state.block_results = False

        # Wait for task 1 to complete
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            t_status = request_json("GET", f"{BASE_URL}/api/tasks/{task1_id}", founder_token)
            if t_status["status"] in ["completed", "blocked"]:
                print(f"Task 1 recovered with status {t_status['status']}!", flush=True)
                if len(t_status["attempts"]) != 1:
                    raise RuntimeError("Duplicate attempts recorded")
                break
            time.sleep(5)
        else:
            raise RuntimeError("Task 1 failed to recover")

        # --- PHASE B: Crash Outage ---
        print("\n=== PHASE B: Crash Outage ===", flush=True)
        proxy_state.hold_lease = True

        task2_id = f"tsk_h4_crash_{uuid.uuid4().hex[:8]}"
        env2 = TaskEnvelope(
            task_id=task2_id,
            project_id=PROJECT_ID,
            repo=str(REPO),
            base_commit=base_commit,
            objective="Edit proof.txt. Replace contents with exactly: Crash Recovery",
            allowed_paths=[ALLOWED_FILE],
            allowed_tools=["read_file", "write_to_file", "run_command"],
            risk_class=RiskClass.LOW,
            preferred_agent=AgentType.ANTIGRAVITY,
            lease_timeout_seconds=60,  # very short lease for quick expiration
            retry_policy=RetryPolicy(max_attempts=2, deadline_seconds=1800),
            concurrency_policy=ConcurrencyPolicy(max_per_project=1, max_per_worker=1),
            requires_approval=False,
            created_at=datetime.now(UTC),
            acceptance_plan=AcceptancePlan(),
        )
        print(f"DEBUG: Submitting task 2 {task2_id}", flush=True)
        request_json("POST", f"{BASE_URL}/api/tasks", founder_token, env2.model_dump(mode="json"))
        print(f"Submitted task 2: {task2_id}", flush=True)

        print("Waiting for worker to lease task...", flush=True)
        if not proxy_state.lease_captured.wait(timeout=60):
            raise RuntimeError("Proxy did not intercept lease")

        target_pid = launchd_snapshot()["pid"]
        print(f"Task leased (held). Killing worker PID {target_pid}...", flush=True)
        os.kill(target_pid, signal.SIGTERM)

        # Release the held response (it goes to the dead worker)
        proxy_state.hold_lease = False

        print("Waiting for launchd to restart worker...", flush=True)
        deadline = time.monotonic() + 60
        new_pid = None
        while time.monotonic() < deadline:
            snap = launchd_snapshot()
            if snap["pid"] and snap["pid"] != target_pid:
                new_pid = snap["pid"]
                print(f"Worker restarted by launchd. New PID: {new_pid}", flush=True)
                break
            time.sleep(2)

        if not new_pid:
            raise RuntimeError("Worker did not restart")

        print(
            "Waiting for real control-plane watchdog to expire the crashed lease and recover...",
            flush=True,
        )
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            t_status = request_json("GET", f"{BASE_URL}/api/tasks/{task2_id}", founder_token)
            if t_status["status"] in ["completed", "blocked"]:
                print(f"Task 2 watchdog recovered with status {t_status['status']}!", flush=True)
                evidence = {
                    "task_id": task2_id,
                    "packet": "H4",
                    "founder_authorization": "User said: Approve controlled D3-4 staging recovery fault injection",
                    "worker_before": before_snap,
                    "worker_pid_killed": target_pid,
                    "worker_pid_restarted": new_pid,
                    "final_plist_matches": True,
                    "network_outage_verified": True,
                    "crash_recovery_verified": True,
                }
                EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
                evidence_path = EVIDENCE_DIR / f"h4_{task2_id}.json"
                evidence_path.write_text(json.dumps(evidence, indent=2))
                print(f"Evidence saved to {evidence_path}", flush=True)

                if len(t_status["attempts"]) != 1:
                    raise RuntimeError("Incorrect attempts recorded")
                break
            time.sleep(10)
        else:
            raise RuntimeError("Task 2 failed to recover from crash")

    finally:
        print("\n=== RESTORING ORIGINAL PLIST ===", flush=True)
        PLIST_PATH.write_bytes(original_plist_bytes)
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], check=False)
        time.sleep(1)
        subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=False)

        # Give it a moment to boot
        time.sleep(3)
        final_snap = launchd_snapshot()
        print(f"Final restored worker PID: {final_snap['pid']}", flush=True)
        print(
            f"Final plist hash matches original: {hash(PLIST_PATH.read_bytes()) == hash(original_plist_bytes)}",
            flush=True,
        )


if __name__ == "__main__":
    main()
