"""Run current local gate snapshot through the real hook in a disposable worktree.

No live task, model, approval, queue or deployment is used. Generated evidence is
kept under testscript/evidence; the temporary checkout is always removed.
"""

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from alpha_worker.adapters.safety_hook import decide  # noqa: E402


def main() -> int:
    evidence = ROOT / "testscript/evidence/sandbox-runtime"
    evidence.mkdir(parents=True, exist_ok=True)
    parent = Path.home() / "Library/Application Support/AlphaBrain/verification"
    parent.mkdir(parents=True, exist_ok=True)

    def git(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True, timeout=30
        )

    results = []
    with tempfile.TemporaryDirectory(prefix="runtime-proof-", dir=parent) as directory:
        wt = Path(directory) / "candidate with spaces"
        git("worktree", "add", "--detach", str(wt), "HEAD")
        try:
            # Test current local repair, not a stale committed copy. Never copy
            # untracked secrets or unrelated generated artifacts.
            changed = set(git("diff", "--name-only", "HEAD").stdout.splitlines())
            changed.add("testscript/test_sandbox_runtime.py")
            for relative in changed:
                source, target = ROOT / relative, wt / relative
                if not source.is_file() or relative.startswith(".env"):
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
            (wt / ".venv").symlink_to(Path(sys.prefix), target_is_directory=True)
            for label, command in (
                ("ruff", "ruff check ."),
                ("pytest", "python -m pytest -q --tb=short --show-capture=no"),
            ):
                decision = decide(
                    {
                        "toolCall": {
                            "name": "run_command",
                            "args": {"Cwd": str(wt), "CommandLine": command},
                        }
                    },
                    wt,
                )
                if decision["decision"] != "allow":
                    raise RuntimeError("Hook refused verification command")
                with (evidence / f"{label}.log").open("w") as output:
                    process = subprocess.Popen(
                        ["/bin/sh", "-c", decision["overwrite"]["CommandLine"]],
                        cwd=wt,
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        text=True,
                        start_new_session=True,
                    )
                    try:
                        code = process.wait(timeout=240)
                    except subprocess.TimeoutExpired:
                        code = 124
                    finally:
                        # Every descendant belongs to this disposable proof.
                        try:
                            os.killpg(process.pid, signal.SIGTERM)
                        except ProcessLookupError:
                            pass
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait(timeout=3)
                results.append({"gate": label, "exit_code": code})
                print(f"Sandbox {label}: exit {code}", flush=True)
        finally:
            # Exact path was created above by this run; no live worktree touched.
            git("worktree", "remove", "--force", str(wt))
    (evidence / "summary.json").write_text(
        json.dumps(
            {"results": results, "live_task_modified": False, "temporary_checkout_removed": True},
            indent=2,
        )
    )
    return int(any(item["exit_code"] for item in results))


if __name__ == "__main__":
    raise SystemExit(main())
