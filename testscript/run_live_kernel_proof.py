import argparse
import asyncio
import json
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alpha_core.db.connection import Base
from alpha_core.state.task_engine import TaskEngine
from alpha_protocol import AcceptancePlan, AgentType, GateCommand, GateType, RiskClass, TaskEnvelope
from alpha_worker.daemon import AlphaWorkerDaemon

CLIENT_PROJECTS_ROOT = Path("/Users/ajaytiwari/Desktop/Projects/clientProjects")


def is_safe_subpath(target: Path, root: Path) -> bool:
    try:
        resolved_target = target.resolve(strict=False)
        resolved_root = root.resolve(strict=False)
        resolved_target.relative_to(resolved_root)
        return True
    except ValueError:
        return False


def validate_prefix(prefix: str) -> None:
    if not prefix:
        raise ValueError("Security error: Project ID prefix cannot be empty")
    if len(prefix) > 64:
        raise ValueError(
            f"Security error: Project ID prefix '{prefix}' exceeds maximum length of 64"
        )
    if not re.match(r"^[A-Za-z0-9\-_]+$", prefix):
        raise ValueError(
            f"Security error: Project ID prefix '{prefix}' contains invalid characters (must be alphanumeric, hyphen, or underscore)"
        )


def setup_git_repository(project_path: Path) -> None:
    gitignore_path = project_path / ".gitignore"
    with gitignore_path.open("w") as f:
        f.write(
            ".alpha_live_run\nlive_kernel.db\nlive_kernel.db-journal\nlive_kernel.db-wal\nlive_kernel.db-shm\n"
        )

    try:
        subprocess.run(
            ["git", "init"], cwd=project_path, check=True, capture_output=True, text=True
        )
        subprocess.run(
            ["git", "add", ".gitignore"],
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit from live proof harness"],
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True,
        )

        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True,
        )
        if status_result.stdout.strip():
            raise RuntimeError(
                f"Git status is not clean after init: {status_result.stdout.strip()}"
            )

        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_path,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Git setup failed: command '{' '.join(e.cmd)}' returned {e.returncode}. stderr: {e.stderr}"
        ) from e


def create_safe_project_dir(prefix: str = "alpha-kernel-status") -> Path:
    validate_prefix(prefix)

    run_id = str(uuid.uuid4())[:8]

    CLIENT_PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)

    proj_dir_str = tempfile.mkdtemp(prefix=f"{prefix}-{run_id}-", dir=CLIENT_PROJECTS_ROOT)
    proj_dir = Path(proj_dir_str)

    if not is_safe_subpath(proj_dir, CLIENT_PROJECTS_ROOT):
        raise ValueError(
            f"Security error: Resolved project path {proj_dir.resolve(strict=False)} escapes root {CLIENT_PROJECTS_ROOT.resolve(strict=False)}"
        )

    marker_path = proj_dir / ".alpha_live_run"
    with marker_path.open("w") as f:
        json.dump(
            {
                "schema": "1.0",
                "run_id": run_id,
                "resolved_path": str(proj_dir.resolve(strict=False)),
            },
            f,
        )

    return proj_dir


def perform_cleanup(target_dir: Path):
    if not target_dir.exists():
        return

    if not is_safe_subpath(target_dir, CLIENT_PROJECTS_ROOT):
        raise ValueError(f"Security error: Refusing to clean path outside root: {target_dir}")

    marker_path = target_dir / ".alpha_live_run"
    if not marker_path.exists():
        raise ValueError(
            f"Security error: Refusing to clean directory without ownership marker: {target_dir}"
        )

    try:
        with marker_path.open("r") as f:
            marker_data = json.load(f)
    except Exception:
        raise ValueError(
            f"Security error: Refusing to clean directory with malformed ownership marker: {target_dir}"
        ) from None

    if marker_data.get("schema") != "1.0":
        raise ValueError(
            f"Security error: Refusing to clean directory with mismatched marker schema: {target_dir}"
        )

    expected_path = marker_data.get("resolved_path")
    actual_path = str(target_dir.resolve(strict=False))

    if expected_path != actual_path:
        raise ValueError(
            f"Security error: Refusing to clean directory with mismatched path in marker: {target_dir}"
        )

    if not marker_data.get("run_id"):
        raise ValueError(
            f"Security error: Refusing to clean directory with missing run_id in marker: {target_dir}"
        )

    shutil.rmtree(target_dir)


async def main(args_list: list[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Run live AlphaBrain AGY execution")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup explicit test directory")
    parser.add_argument("--project-path", type=str, help="Specific project path to cleanup")
    parser.add_argument("--project-id", type=str, help="Suffix for project directory")
    parser.add_argument(
        "--approve-as", type=str, help="Nonempty founder identity to record for approval provenance"
    )

    if args_list is not None:
        args = parser.parse_args(args_list)
    else:
        args = parser.parse_args()

    if args.cleanup:
        print("=== CLEANUP MODE ===")
        if not args.project_path:
            print("Error: --cleanup requires --project-path target")
            return

        target = Path(args.project_path)
        try:
            perform_cleanup(target)
            print(f"Cleaned {target}")
        except Exception as e:
            print(f"Failed to clean {target}: {e}")

        if not args.live:
            return

    if not args.live:
        print("Skipping live run. Use --live to execute the real AGY adapter.")
        return

    if not args.approve_as or not args.approve_as.strip():
        print("Error: --live requires --approve-as <identity> for explicit approval provenance")
        sys.exit(1)

    # Remove DEBUG logging

    founder_identity = args.approve_as.strip()

    print("=== LIVE KERNEL PROOF ===")

    daemon = AlphaWorkerDaemon(worker_id="live-worker")
    adapter = daemon.select_adapter(AgentType.ANTIGRAVITY)
    is_ready, reason = adapter.check_readiness()
    if not is_ready:
        print(f"Readiness check failed: Antigravity adapter is not ready: {reason}")
        sys.exit(1)

    prefix = args.project_id if args.project_id else "alpha-kernel-status"
    try:
        project_path = create_safe_project_dir(prefix)
    except Exception as e:
        print(f"Failed to create secure project directory: {e}")
        sys.exit(1)

    try:
        setup_git_repository(project_path)
    except Exception as e:
        print(f"Failed to setup git repository: {e}")
        sys.exit(1)

    task_id = f"tsk_live_{uuid.uuid4().hex[:8]}"
    db_path = project_path / "live_kernel.db"
    safe_db_url = f"sqlite+aiosqlite:///{db_path}"

    print("--- Run Metadata ---")
    print(f"Project Path: {project_path}")
    print(f"Task ID: {task_id}")
    print(f"DB Endpoint: {safe_db_url}")
    print("--------------------")

    engine = create_async_engine(safe_db_url, echo=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            print("1. Creating project flow...")
            proj = await TaskEngine.create_project(
                session, f"prj_status_live_{task_id}", "Live Status Page", str(project_path)
            )

            print("2. Creating structured brief & frozen task DAG...")
            envelope = TaskEnvelope(
                task_id=task_id,
                project_id=proj.id,
                repo=str(project_path),
                objective="Create a missing P1 documentation file at docs/getting_started.md and a test script at testscript/test_getting_started.sh. You must follow the multi-agent-sdlc protocol precisely. Do NOT mutate .gitignore. Your FINAL output line MUST be exactly 'ALPHA_BRAIN_TASK_DONE' with no other characters.",
                allowed_paths=[
                    "docs/getting_started.md",
                    "testscript/test_getting_started.sh",
                ],
                risk_class=RiskClass.LOW,
                preferred_agent=AgentType.ANTIGRAVITY,
                requires_approval=True,
                retain_worktree_for_preview=True,
                acceptance_plan=AcceptancePlan(
                    require_independent_review=True,
                    required_gates=[GateType.LINT],
                    commands=[
                        GateCommand(
                            gate_type=GateType.LINT,
                            executable="node",
                            args=["-e", "require('fs').readFileSync('docs/getting_started.md')"],
                        )
                    ],
                ),
                base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            )

            print("3. Submitting task through TaskEngine...")
            task = await TaskEngine.submit_task(session, envelope)
            print(f"   Status: {task.status}")

            print("4. Approving task...")
            await TaskEngine.decide_task_approval(
                session, task.id, approved=True, decided_by=founder_identity
            )
            print(f"   Provenance: Task {task.id} explicitly approved by {founder_identity}")
            await session.refresh(task)
            print(f"   Status: {task.status}")

            print("5. Worker leasing and invoking AGY adapter (this may take a while)...")
            await daemon.execute_task_cycle(session)
            await session.commit()

            await session.refresh(task)
            print(f"6. Task processed. Intermediate Status: {task.status}")

            if task.status == "verified":
                print("7. Task is VERIFIED. Pending separate founder review and acceptance.")

            details = task.details_json or {}
            print("   Review-ready Result Evidence:")
            print(f"   Preview Data: {details.get('preview_evidence')}")

            print("Live kernel proof completed.")
            print(f"Project preserved at: {project_path}")
            print(f"Run with --cleanup --project-path {project_path} to remove this run's data.")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
