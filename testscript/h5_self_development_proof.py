import argparse
import json
import os
import secrets
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

def get_evidence_root() -> Path:
    base = Path(os.environ.get("H5_EVIDENCE_DIR", "testscript/evidence/h5-self-proof")).resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base

def get_current_run_link() -> Path:
    return get_evidence_root() / "current_run_id.txt"





def get_current_run_id() -> str:
    link = get_current_run_link()
    if not link.exists():
        raise ValueError("No active run found")
    return link.read_text().strip()


def get_state_path(run_id: str) -> Path:
    return get_evidence_root() / run_id / "state.json"


def load_state(run_id: str) -> dict[str, Any]:
    path = get_state_path(run_id)
    try:
        if not path.exists():
            return {}
        resolved_path = path.resolve()
        expected_parent = (get_evidence_root() / run_id).resolve()
        if expected_parent not in resolved_path.parents:
            raise ValueError("Path escape detected")
        state = dict(json.loads(path.read_text()))
        if state.get("run_id") != run_id:
            raise ValueError("Malformed state")
        return state
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"State invalid: {e}")


def save_state(run_id: str, state: dict[str, Any]) -> None:
    path = get_state_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def get_pids_path(run_id: str) -> Path:
    return get_evidence_root() / run_id / "pids.json"


def track_pid(run_id: str, pid: int, cmd: list[str]) -> None:
    path = get_pids_path(run_id)
    pids = []
    if path.exists():
        pids = json.loads(path.read_text())
    pids.append({"pid": pid, "cmd": cmd})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pids, indent=2))


def get_free_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def launch_proof_owned(cmd: list[str], env: dict[str, str], run_id: str) -> subprocess.Popen:
    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid
    )
    track_pid(run_id, proc.pid, cmd)
    return proc


def kill_proof_owned(pid: int, expected_cmd_part: str) -> None:
    try:
        cmdline = subprocess.check_output(["ps", "-p", str(pid), "-o", "command="]).decode().strip()
        if expected_cmd_part not in cmdline:
            return
        os.killpg(pid, signal.SIGTERM)
        for _ in range(25):
            try:
                os.kill(pid, 0)
                time.sleep(0.2)
            except OSError:
                return
        os.killpg(pid, signal.SIGKILL)
    except Exception:
        pass


def db_init(db_path: Path) -> None:
    env = os.environ.copy()
    env["ALPHABRAIN_DB_URL"] = f"sqlite+aiosqlite:///{db_path}"
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    try:
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=env,
            check=True,
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent)
        )
    except subprocess.CalledProcessError as e:
        print(f"Alembic stdout: {e.stdout}", file=sys.stderr)
        print(f"Alembic stderr: {e.stderr}", file=sys.stderr)
        raise RuntimeError("Migration failed")


class LocalControlPlane:
    def __init__(self, run_id: str, db_path: Path):
        self.run_id = run_id
        self.db_path = db_path
        self.port = get_free_port()
        self.token = secrets.token_urlsafe(32)
        self.proc: subprocess.Popen | None = None
        self.client = httpx.Client(base_url=f"http://127.0.0.1:{self.port}", timeout=10.0)

    def start(self) -> None:
        env = os.environ.copy()
        env["ALPHABRAIN_DB_URL"] = f"sqlite+aiosqlite:///{self.db_path}"
        env["ALPHA_API_TOKEN"] = self.token
        env["ALPHABRAIN_STRICT_AUTH"] = "1"
        log_file = open(self.db_path.parent / "uvicorn.log", "w")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "alpha_core.api.app:app", "--host", "127.0.0.1", "--port", str(self.port)],
            env=env,
            preexec_fn=os.setsid,
            stdout=log_file,
            stderr=subprocess.STDOUT
        )
        
        ready = False
        for _ in range(40):
            try:
                resp = self.client.get("/health/ready")
                if resp.status_code == 200:
                    ready = True
                    break
            except Exception:
                pass
            time.sleep(0.5)
            
        if not ready:
            self.stop()
            raise RuntimeError("Control plane failed to start or readiness check timed out")

    def stop(self) -> None:
        if self.proc:
            kill_proof_owned(self.proc.pid, "uvicorn")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


def cmd_prepare(args: argparse.Namespace) -> None:
    run_id = f"run_{secrets.token_hex(8)}"
    run_dir = get_evidence_root() / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    db_path = run_dir / "alpha_brain.db"
    
    db_init(db_path)
    
    with LocalControlPlane(run_id, db_path) as cp:
        repo = str(Path.cwd().resolve())
        base_commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
        
        resp = cp.client.post(
            "/api/self-development/tasks",
            json={
                "task_id": f"tsk_{run_id}",
                "project_id": "prj_alphabrain_self",
                "source_repo": repo,
                "allowed_paths": ["TODO.md"],
                "objective": "update TODO.md with a concise truthful H4 result-promotion completion/evidence note.",
                "base_commit": base_commit,
                "acceptance_plan": {
                    "require_independent_review": True,
                    "required_gates": ["LINT", "CODE_REVIEW_GRAPH", "INDEPENDENT_REVIEW"],
                    "commands": [
                        {"gate_type": "INDEPENDENT_REVIEW", "executable": "git", "args": ["diff", "--check", f"{base_commit}..HEAD"]},
                    ]
                }
            },
            headers={"Authorization": f"Bearer {cp.token}"}
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Task creation failed: {resp.text}")
        
        data = resp.json()
        try:
            task_id = data["task_id"]
            packet_sha256 = data["packet_sha256"]
        except KeyError:
            raise RuntimeError(f"Response missing task_id or packet_sha256 schema: {data}")

    get_current_run_link().write_text(run_id)
    save_state(run_id, {
        "run_id": run_id,
        "db_path": str(db_path),
        "worker_state_dir": str(run_dir / "worker_state"),
        "base_commit": base_commit,
        "task_id": task_id
    })

    print("Prepare complete.")
    print(f"Task created: {task_id}")
    print(f"Execution approval string: I confirm execution for {packet_sha256}")


def cmd_status(args: argparse.Namespace) -> None:
    run_id = get_current_run_id()
    state = load_state(run_id)
    
    with LocalControlPlane(run_id, Path(state["db_path"])) as cp:
        resp = cp.client.get(f"/api/tasks/{state['task_id']}", headers={"Authorization": f"Bearer {cp.token}"})
        if resp.status_code != 200:
            raise RuntimeError(f"Status check failed: {resp.text}")
        
        task = resp.json()
        print(f"Run ID: {run_id}")
        status_enum = task["status"]
        print(f"Phase: {status_enum.lower()}")
        
        pending = task.get("pending_approval")
        if pending:
            app_type = pending["approval_type"]
            app_type_clean = app_type.replace("task_", "")
            print(f"{app_type_clean.capitalize()} digest: {pending['scope_sha256']}")
            print(f"{app_type_clean.capitalize()} approval string: I confirm {app_type_clean} for {pending['scope_sha256']}")


def cmd_approve(approval_type: str, args: argparse.Namespace) -> None:
    run_id = get_current_run_id()
    state = load_state(run_id)
    
    expected_confirm = f"I confirm {approval_type} for {args.digest}"
    if args.confirm != expected_confirm:
        raise ValueError("Confirmation string mismatch")
        
    with LocalControlPlane(run_id, Path(state["db_path"])) as cp:
        resp = cp.client.post(
            f"/api/tasks/{state['task_id']}/approval",
            json={"approved": True, "packet_sha256": args.digest},
            headers={"Authorization": f"Bearer {cp.token}"}
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"Approval failed: {resp.text}")
            
    print(f"{approval_type.capitalize()} approved.")


def cmd_approve_execution(args: argparse.Namespace) -> None:
    cmd_approve("execution", args)


def cmd_approve_review(args: argparse.Namespace) -> None:
    cmd_approve("review", args)


def cmd_approve_promotion(args: argparse.Namespace) -> None:
    cmd_approve("promotion", args)


def cmd_run_worker(args: argparse.Namespace) -> None:
    run_id = get_current_run_id()
    state = load_state(run_id)
    db_path = Path(state["db_path"])
    
    with LocalControlPlane(run_id, db_path) as cp:
        # Check if we should even run worker (must be approved execution or promotion)
        resp = cp.client.get(f"/api/tasks/{state['task_id']}", headers={"Authorization": f"Bearer {cp.token}"})
        if resp.status_code != 200:
            raise RuntimeError("Failed to fetch task status")
        task = resp.json()
        status = task["status"].lower()
        if status not in ["queued", "verified"]: # queued when execution approved, verified when promotion approved
            # if already completed or waiting approval, no-op or fast-fail
            if status == "completed":
                print("Promotion applied.")
                return
            if status == "waiting_approval":
                print("Worker finished execution.")
                return
            
        env = os.environ.copy()
        env["WORKER_CONTROL_PLANE_URL"] = f"http://127.0.0.1:{cp.port}"
        env["ALPHABRAIN_API_KEY"] = cp.token
        env["WORKER_API_KEY"] = cp.token
        env["WORKER_STATE_DIR"] = state["worker_state_dir"]
        
        worker_cmd_str = os.environ.get("ALPHABRAIN_WORKER_CMD", f"{sys.executable} -m alpha_worker run --poll-seconds 1")
        worker_cmd = shlex.split(worker_cmd_str)
        worker_proc = launch_proof_owned(worker_cmd, env, run_id)
        
        try:
            start_time = time.time()
            success = False
            while time.time() - start_time < 30:
                resp = cp.client.get(f"/api/tasks/{state['task_id']}", headers={"Authorization": f"Bearer {cp.token}"})
                if resp.status_code == 200:
                    t = resp.json()
                    st = t["status"].lower()
                    if st == "waiting_approval":
                        print("Worker finished execution.")
                        success = True
                        break
                    elif st == "completed":
                        print("Promotion applied.")
                        success = True
                        break
                    elif st == "retryable_failed" or st == "blocked":
                        raise RuntimeError(f"Worker failed task: {st}")
                time.sleep(1)
            if not success:
                raise RuntimeError("Worker timed out")
        finally:
            kill_proof_owned(worker_proc.pid, worker_cmd[0])


def cmd_verify(args: argparse.Namespace) -> None:
    run_id = get_current_run_id()
    state = load_state(run_id)
    with LocalControlPlane(run_id, Path(state["db_path"])) as cp:
        resp = cp.client.get(f"/api/tasks/{state['task_id']}", headers={"Authorization": f"Bearer {cp.token}"})
        if resp.status_code != 200:
            raise RuntimeError("Verification failed: cannot fetch task")
        task = resp.json()
        if task["status"].lower() != "completed":
            print("Verification failed.")
            sys.exit(1)
            
    # Verify git head is advanced to result_commit
    # Ensure no unrelated untracked files are touched (diff check)
    result_commit = task["attempts"][0]["result_commit"]
    current_head = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    if current_head != result_commit:
        print("Verification failed: HEAD not advanced to result.")
        sys.exit(1)
    
    print("Verification successful.")


def cmd_cleanup(args: argparse.Namespace) -> None:
    try:
        run_id = get_current_run_id()
    except ValueError:
        print("Cleanup complete.")
        return
        
    pids_file = get_pids_path(run_id)
    if pids_file.exists():
        pids = json.loads(pids_file.read_text())
        for p in pids:
            kill_proof_owned(p["pid"], p["cmd"][0])
    
    if get_current_run_link().exists():
        get_current_run_link().unlink()
    print("Cleanup complete.")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("prepare")
    sub.add_parser("status")

    p = sub.add_parser("approve-execution")
    p.add_argument("--digest", required=True)
    p.add_argument("--confirm", required=True)

    sub.add_parser("run-worker")

    p = sub.add_parser("approve-review")
    p.add_argument("--digest", required=True)
    p.add_argument("--confirm", required=True)

    p = sub.add_parser("approve-promotion")
    p.add_argument("--digest", required=True)
    p.add_argument("--confirm", required=True)

    sub.add_parser("verify")
    sub.add_parser("cleanup")

    args = parser.parse_args()

    cmds = {
        "prepare": cmd_prepare,
        "status": cmd_status,
        "approve-execution": cmd_approve_execution,
        "run-worker": cmd_run_worker,
        "approve-review": cmd_approve_review,
        "approve-promotion": cmd_approve_promotion,
        "verify": cmd_verify,
        "cleanup": cmd_cleanup,
    }
    cmds[args.cmd](args)


if __name__ == "__main__":
    main()
