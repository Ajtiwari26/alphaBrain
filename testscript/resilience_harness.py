"""Hermetic outbound-worker spool and crash-recovery proof.

Uses isolated SQLite control plane and disposable worker state. Never mutates
Render, Supabase, production launchd worker, or repository development DB.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import socket
import subprocess
import tempfile
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alpha_core.db.models import TaskRecord
from alpha_core.state.task_engine import TaskEngine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR = PROJECT_ROOT / "testscript" / "evidence"
FIXTURE_REPO = Path("/Users/ajaytiwari/Desktop/Projects/clientProjects/fixture_repo")
KEYCHAIN_SERVICE = "com.deploymate.alphabrain"
WORKER_ID = "mac_worker_resilience_test"
PROJECT_ID = "prj_resilience_test"


@dataclass
class ProxyState:
    block_results: bool = False
    hold_lease: bool = False
    lease_captured: threading.Event = field(default_factory=threading.Event)


@dataclass
class ManagedProcess:
    process: subprocess.Popen[bytes]
    log_handle: Any


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _keychain_secret(account: str) -> str:
    result = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-s",
            KEYCHAIN_SERVICE,
            "-a",
            account,
            "-w",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    value = result.stdout.strip()
    if not value:
        raise RuntimeError(f"Missing Keychain secret: {account}")
    return value


def _ensure_fixture_repo() -> None:
    FIXTURE_REPO.mkdir(parents=True, exist_ok=True)
    if not (FIXTURE_REPO / ".git").exists():
        subprocess.run(["git", "init"], cwd=FIXTURE_REPO, check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Alpha Resilience Harness",
                "-c",
                "user.email=alpha-resilience@example.test",
                "commit",
                "--allow-empty",
                "-m",
                "Initialize resilience fixture",
            ],
            cwd=FIXTURE_REPO,
            check=True,
            capture_output=True,
        )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=FIXTURE_REPO,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if status:
        raise RuntimeError("Fixture repository must be clean before resilience proof")


def _start_process(
    command: list[str], environment: dict[str, str], log_path: Path
) -> ManagedProcess:
    log_handle = log_path.open("wb")
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    return ManagedProcess(process, log_handle)


def _stop_process(managed: ManagedProcess | None) -> None:
    if managed is None:
        return
    process = managed.process
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    managed.log_handle.close()


def _proxy_app(upstream_url: str, state: ProxyState) -> FastAPI:
    app = FastAPI()

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy(request: Request, path: str) -> Response:
        route = f"/{path}"
        if route.endswith("/result") and state.block_results:
            return Response(status_code=503, content="Injected result-delivery outage")
        body = await request.body()
        headers = {
            key: value
            for key, value in request.headers.items()
            if key.lower() not in {"host", "content-length", "connection"}
        }
        async with httpx.AsyncClient(base_url=upstream_url, timeout=15.0) as client:
            response = await client.request(request.method, route, headers=headers, content=body)
        if route == "/api/tasks/lease" and state.hold_lease and response.status_code == 200:
            payload = response.json()
            if payload.get("status") == "leased":
                state.lease_captured.set()
                while state.hold_lease:
                    await asyncio.sleep(0.05)
        response_headers = {
            key: value
            for key, value in response.headers.items()
            if key.lower() not in {"content-encoding", "content-length", "transfer-encoding"}
        }
        return Response(response.content, response.status_code, response_headers)

    return app


async def _wait_until(
    predicate: Callable[[], Awaitable[Any]], timeout: float, description: str
) -> Any:
    deadline = time.monotonic() + timeout
    last_value: Any = None
    while time.monotonic() < deadline:
        last_value = await predicate()
        if last_value:
            return last_value
        await asyncio.sleep(0.25)
    raise TimeoutError(f"Timed out waiting for {description}; last={last_value!r}")


async def _wait_for_http(url: str) -> None:
    async with httpx.AsyncClient(timeout=2.0) as client:

        async def ready() -> bool:
            try:
                return bool((await client.get(url)).status_code == 200)
            except httpx.HTTPError:
                return False

        await _wait_until(ready, 20, f"HTTP readiness at {url}")


async def _register_project(client: httpx.AsyncClient, api_token: str) -> None:
    response = await client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {api_token}"},
        json={
            "project_id": PROJECT_ID,
            "name": "Hermetic resilience fixture",
            "repo_path": str(FIXTURE_REPO),
        },
    )
    response.raise_for_status()


async def _submit_task(
    client: httpx.AsyncClient, api_token: str, task_id: str, max_attempts: int
) -> None:
    response = await client.post(
        "/api/tasks",
        headers={"Authorization": f"Bearer {api_token}"},
        json={
            "task_id": task_id,
            "project_id": PROJECT_ID,
            "repo": str(FIXTURE_REPO),
            "objective": "Run bounded resilience fixture with execution disabled",
            "allowed_paths": ["."],
            "retry_policy": {
                "max_attempts": max_attempts,
                "backoff_base_seconds": 10,
                "backoff_multiplier": 1,
                "deadline_seconds": 300,
            },
        },
    )
    response.raise_for_status()


async def _task_details(client: httpx.AsyncClient, api_token: str, task_id: str) -> dict[str, Any]:
    response = await client.get(
        f"/api/tasks/{task_id}",
        headers={"Authorization": f"Bearer {api_token}"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Task details response is not an object")
    return payload


async def _expire_then_recover_lease(database_url: str, task_id: str) -> dict[str, Any]:
    """Inject elapsed time, then use production recovery methods unchanged."""
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            task = await session.get(TaskRecord, task_id)
            if task is None or task.status != "leased":
                raise RuntimeError("Crash task was not leased before process death")
            task.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await session.commit()
        async with session_factory() as session:
            recovered = await TaskEngine.timeout_expired_leases(session)
            await session.commit()
            task = await session.get(TaskRecord, task_id)
            if recovered != 1 or task is None or task.status != "retryable_failed":
                raise RuntimeError("Lease watchdog did not schedule retry")
            retry_at = task.next_eligible_at
        await asyncio.sleep(10.25)
        async with session_factory() as session:
            released = await TaskEngine.release_due_retries(session)
            await session.commit()
            task = await session.get(TaskRecord, task_id)
            if released != 1 or task is None or task.status != "queued":
                raise RuntimeError("Retry scheduler did not return task to queue")
            return {
                "expired_leases_recovered": recovered,
                "due_retries_released": released,
                "retry_scheduled_at": retry_at.isoformat() if retry_at else None,
                "final_recovery_state": task.status,
            }
    finally:
        await engine.dispose()


def _worker_environment(proxy_url: str, temp_dir: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "ENV": "test",
            "WORKER_ID": WORKER_ID,
            "WORKER_STATE_DIR": str(temp_dir / "worker-state"),
            "WORKTREE_BASE_DIR": str(temp_dir / "worktrees"),
            "WORKER_USE_KEYCHAIN": "true",
            "WORKER_ALLOW_LOCAL_DB": "false",
            "ANTIGRAVITY_EXECUTION_ENABLED": "false",
            "WORKER_CONTROL_PLANE_URL": proxy_url,
            "ALLOWED_REPO_ROOTS": str(FIXTURE_REPO.parent),
            "WORKER_HTTP_TIMEOUT_SECONDS": "3",
            "WORKER_HEARTBEAT_SECONDS": "1",
        }
    )
    return environment


def _write_evidence(name: str, payload: dict[str, Any]) -> None:
    destination = EVIDENCE_DIR / name
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


async def run_proof() -> None:
    _ensure_fixture_repo()
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    worker_token = _keychain_secret("worker-token")
    _keychain_secret("worker-spool-fernet-key")
    api_token = secrets.token_urlsafe(32)
    signing_secret = secrets.token_urlsafe(32)

    with tempfile.TemporaryDirectory(prefix="alphabrain-resilience-") as raw_temp:
        temp_dir = Path(raw_temp)
        database_url = f"sqlite+aiosqlite:///{temp_dir / 'control-plane.db'}"
        api_port, proxy_port = _free_port(), _free_port()
        api_url = f"http://127.0.0.1:{api_port}"
        proxy_url = f"http://127.0.0.1:{proxy_port}"
        state = ProxyState()
        proxy_server = uvicorn.Server(
            uvicorn.Config(
                _proxy_app(api_url, state),
                host="127.0.0.1",
                port=proxy_port,
                log_level="warning",
            )
        )
        proxy_thread = threading.Thread(target=proxy_server.run, daemon=True)
        api_process: ManagedProcess | None = None
        worker_process: ManagedProcess | None = None
        api_environment = os.environ.copy()
        api_environment.update(
            {
                "ENV": "test",
                "DATABASE_URL": database_url,
                "ALPHA_API_TOKEN": api_token,
                "ALPHA_WORKER_TOKEN": worker_token,
                "ALPHA_SIGNING_SECRET": signing_secret,
                "PUBLIC_BASE_URL": api_url,
                "CORS_ORIGINS": api_url,
                "ALLOWED_REPO_ROOTS": str(FIXTURE_REPO.parent),
                "WORKER_ALLOW_LOCAL_DB": "true",
                "ANTIGRAVITY_EXECUTION_ENABLED": "false",
            }
        )
        try:
            api_process = _start_process(
                [
                    str(PROJECT_ROOT / ".venv/bin/uvicorn"),
                    "alpha_core.api.app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(api_port),
                ],
                api_environment,
                temp_dir / "api.log",
            )
            proxy_thread.start()
            await _wait_for_http(f"{api_url}/health/live")
            await _wait_for_http(f"{proxy_url}/health/live")
            async with httpx.AsyncClient(base_url=api_url, timeout=10.0) as client:
                await _register_project(client, api_token)
                worker_process = _start_process(
                    [str(PROJECT_ROOT / ".venv/bin/python"), "-m", "alpha_worker", "run"],
                    _worker_environment(proxy_url, temp_dir),
                    temp_dir / "worker-spool.log",
                )

                state.block_results = True
                spool_task_id = f"tsk_spool_{uuid.uuid4().hex[:8]}"
                await _submit_task(client, api_token, spool_task_id, 1)
                spool_dir = temp_dir / "worker-state" / "spool"

                async def pending_spool() -> list[Path]:
                    return sorted(spool_dir.glob("*.event")) if spool_dir.exists() else []

                spool_files = await _wait_until(pending_spool, 30, "encrypted result spool")
                if spool_task_id.encode() in spool_files[0].read_bytes():
                    raise RuntimeError("Spool encryption exposed raw task ID")
                state.block_results = False

                async def spool_replayed_once() -> bool:
                    details = await _task_details(client, api_token, spool_task_id)
                    return not await pending_spool() and len(details.get("attempts", [])) == 1

                await _wait_until(spool_replayed_once, 30, "exactly-once spool replay")
                spool_details = await _task_details(client, api_token, spool_task_id)
                _write_evidence(
                    "spool_proof.json",
                    {
                        "proof_scope": "hermetic_local_control_plane",
                        "database": "isolated_sqlite",
                        "task_id": spool_task_id,
                        "encrypted_at_rest": True,
                        "raw_task_id_absent": True,
                        "spool_drained_after_ack": True,
                        "persisted_attempt_count": len(spool_details["attempts"]),
                        "final_status": spool_details["status"],
                    },
                )

                state.hold_lease = True
                crash_task_id = f"tsk_crash_{uuid.uuid4().hex[:8]}"
                await _submit_task(client, api_token, crash_task_id, 2)
                captured = await asyncio.to_thread(state.lease_captured.wait, 30)
                if not captured:
                    raise TimeoutError("Worker did not lease crash-proof task")
                _stop_process(worker_process)
                worker_process = None
                recovery = await _expire_then_recover_lease(database_url, crash_task_id)
                state.hold_lease = False
                worker_process = _start_process(
                    [str(PROJECT_ROOT / ".venv/bin/python"), "-m", "alpha_worker", "run"],
                    _worker_environment(proxy_url, temp_dir),
                    temp_dir / "worker-crash-restart.log",
                )

                async def recovered_once() -> bool:
                    details = await _task_details(client, api_token, crash_task_id)
                    return len(details.get("attempts", [])) == 1

                await _wait_until(recovered_once, 30, "single post-crash result")
                crash_details = await _task_details(client, api_token, crash_task_id)
                _write_evidence(
                    "crash_proof.json",
                    {
                        "proof_scope": "hermetic_local_control_plane",
                        "database": "isolated_sqlite",
                        "fault": "worker_terminated_after_control_plane_lease",
                        "task_id": crash_task_id,
                        **recovery,
                        "persisted_attempt_count": len(crash_details["attempts"]),
                        "duplicate_results": len(crash_details["attempts"]) - 1,
                        "final_status": crash_details["status"],
                    },
                )
        finally:
            state.hold_lease = False
            _stop_process(worker_process)
            _stop_process(api_process)
            proxy_server.should_exit = True
            if proxy_thread.is_alive():
                proxy_thread.join(timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Run disposable fault injections")
    arguments = parser.parse_args()
    if not arguments.run:
        parser.error("explicit --run is required")
    asyncio.run(run_proof())


if __name__ == "__main__":
    main()
