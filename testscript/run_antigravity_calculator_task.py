"""Dispatch Alpha Brain's isolated scientific-calculator acceptance task.

This intentional live test creates a fresh project repository and asks Alpha
Brain for a fresh internal Antigravity conversation. It keeps a successful
worktree on localhost; provider creation failures leave no preview running.
"""

import argparse
import asyncio
import fcntl
import json
import socket
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from alpha_protocol import (  # noqa: E402
    AcceptancePlan,
    GateCommand,
    GateType,
    TaskEnvelope,
    TaskStatus,
)
from alpha_worker.adapters.antigravity import AntigravityAdapter  # noqa: E402
from alpha_worker.preview import PreviewSupervisor  # noqa: E402

PROJECT_ID = "prj_scientific_calculator"
TASK_ID = "tsk_scientific_calculator_qa_05"
DEFAULT_REPO = Path("/Users/ajaytiwari/Desktop/Projects/clientProjects/scientific-calculator")

CALCULATOR_CONTRACT = '''"""Acceptance contract for scientific calculator task."""

from pathlib import Path


def test_calculator_has_required_scientific_capabilities():
    html = Path("index.html").read_text().lower()
    required = (
        "scientific calculator", "math.sin", "math.cos", "math.tan", "math.log",
        "math.sqrt", "derivative", "simpson", "deg", "rad", "memory", "aria-label",
    )
    for marker in required:
        assert marker in html, marker
    assert "eval(" not in html
'''

README = """# Alpha Brain Scientific Calculator Test

Isolated repository for an end-to-end Antigravity worker test.
The acceptance contract must remain unchanged.
"""


def run(command: list[str], cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())


def prepare_repository(repo: Path, *, resume_existing: bool = False) -> None:
    """Create dedicated clean Git repository; never reuse another project."""
    if repo.exists():
        expected_files = {"README.md", "calculator_contract_test.py", ".git"}
        actual_files = {item.name for item in repo.iterdir()}
        if resume_existing:
            if not expected_files.issubset(actual_files) or not (repo / "index.html").is_file():
                raise RuntimeError(
                    f"Existing calculator repository is missing required seed files: {repo}."
                )
            if (repo / "calculator_contract_test.py").read_text() != CALCULATOR_CONTRACT:
                raise RuntimeError(
                    "Calculator acceptance contract changed; refusing unsafe task resume."
                )
            return
        if not expected_files.issubset(actual_files) or (repo / "index.html").exists():
            raise RuntimeError(
                f"Refusing existing calculator repository: {repo}. Choose a new --repo path."
            )
        if (repo / "calculator_contract_test.py").read_text() != CALCULATOR_CONTRACT:
            raise RuntimeError(
                "Calculator acceptance contract changed; refusing unsafe task resume."
            )
        return
    repo.mkdir(parents=True)
    (repo / "README.md").write_text(README)
    (repo / "calculator_contract_test.py").write_text(CALCULATOR_CONTRACT)
    run(["git", "init", "-b", "main"], repo)
    run(["git", "config", "user.name", "Alpha Brain Test Worker"], repo)
    run(["git", "config", "user.email", "alpha-worker@local.invalid"], repo)
    run(["git", "add", "README.md", "calculator_contract_test.py"], repo)
    run(["git", "commit", "-m", "test: seed calculator acceptance contract"], repo)


def port_is_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def start_preview(
    worktree: Path,
    port: int,
    task_id: str = TASK_ID,
    project_id: str = PROJECT_ID,
) -> int:
    supervisor = PreviewSupervisor()
    metadata = supervisor.start_preview(
        worktree,
        task_id=task_id,
        project_id=project_id,
        port=port,
    )
    return metadata.pid or 0


@contextmanager
def exclusive_task_lock(task_id: str):
    """Prevent concurrent runners from sending overlapping turns to one project chat."""
    lock_dir = Path("/Users/ajaytiwari/Library/Application Support/AlphaBrain/locks")
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_file = (lock_dir / f"{task_id}.lock").open("w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock_file.close()
        raise RuntimeError(f"Task {task_id} already has an active runner") from exc
    try:
        yield
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()


async def dispatch(repo: Path, port: int) -> dict[str, object]:
    adapter = AntigravityAdapter()
    ready, reason = adapter.check_readiness()
    if not ready:
        raise RuntimeError(reason)

    task = TaskEnvelope(
        task_id=TASK_ID,
        project_id=PROJECT_ID,
        repo=str(repo),
        objective="Build complete Casio-style scientific calculator web page.",
        detailed_instructions="""Create polished responsive index.html with HTML, CSS, and JavaScript only.
Build Casio-like UI with keyboard support and accessible labels. Support arithmetic, parentheses,
percent, pi, e, x², xʸ, square/cube roots, 1/x, abs, floor, ceil, exp, ln, log10, factorial,
memory controls, degree/radian mode, sin/cos/tan, inverse and hyperbolic trigonometry.
Include Calculation Lab for numerical derivative and definite integral using Simpson's rule.
Do not use eval, Function constructors, external CDNs, or frameworks. Keep
calculator_contract_test.py unchanged. Put all new QA under testscript/. Build browser E2E
coverage using Playwright for arithmetic, keyboard input, calculation-lab validation, responsive
layout, and visible error handling. Run every declared gate before completion.
""",
        allowed_paths=["."],
        allowed_tools=["code-review-graph", "read_file", "write_to_file", "run_command"],
        acceptance_plan=AcceptancePlan(
            required_gates=[GateType.UNIT_TEST, GateType.BROWSER_SMOKE],
            commands=[
                GateCommand(
                    gate_type=GateType.UNIT_TEST,
                    executable="pytest",
                    args=["-q", "calculator_contract_test.py"],
                    timeout_seconds=120,
                ),
                GateCommand(
                    gate_type=GateType.BROWSER_SMOKE,
                    executable="node",
                    args=["testscript/browser_e2e_playwright.js"],
                    timeout_seconds=300,
                ),
            ],
        ),
        retain_worktree_for_preview=True,
        base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    )
    worktree = adapter.worktree_mgr.create_or_resume_worktree(str(repo), TASK_ID, "HEAD")
    result = await adapter.execute(task, worktree, "HEAD")
    if result.status != TaskStatus.COMPLETED:
        raise RuntimeError(
            "Task failed: " + "; ".join(result.blockers or ["acceptance gates failed"])
        )

    supervisor = PreviewSupervisor()
    metadata = supervisor.start_preview(
        worktree,
        task_id=task.task_id,
        project_id=task.project_id,
        port=port,
    )
    conversation = next(
        note.partition(": ")[2]
        for note in result.provenance_notes
        if note.startswith("Antigravity project conversation:")
    )
    return {
        "task_id": task.task_id,
        "project_id": task.project_id,
        "conversation": conversation,
        "result_commit": result.result_commit,
        "worktree": str(worktree),
        "preview_url": metadata.url,
        "preview_pid": metadata.pid,
        "preview_status": metadata.status.value,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run live Alpha Brain calculator task")
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument(
        "--resume-existing",
        action="store_true",
        help="Resume only a validated existing calculator repository.",
    )
    args = parser.parse_args()

    repo = args.repo.expanduser().resolve()
    with exclusive_task_lock(TASK_ID):
        prepare_repository(repo, resume_existing=args.resume_existing)
        print(
            json.dumps(
                asyncio.run(dispatch(repo, args.port)),
                default=str,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
