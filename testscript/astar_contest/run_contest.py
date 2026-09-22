#!/usr/bin/env python3
"""
Automated Orchestrator for Head-to-Head Benchmark: etta vs. agy
Executes both engines on identical problem specification, captures timing,
evaluates on 12 blind edge cases, and prints side-by-side comparison report.
"""

import os
import re
import sys
import time
import subprocess
from pathlib import Path

CONTEST_DIR = Path(__file__).parent.resolve()
SPEC_FILE = CONTEST_DIR / "PROMPT_SPECIFICATION.md"
ETTA_WS = CONTEST_DIR / "etta_ws"
AGY_WS = CONTEST_DIR / "agy_ws"
EVALUATOR = CONTEST_DIR / "evaluator.py"


def extract_python_code(raw_output: str) -> str:
    """Extract clean Python code from LLM output, handling fences, trailing JSON, or raw code."""
    # First strip trailing CLI JSON lifecycle metadata if present
    cleaned = re.split(r'\n\{\s*\n?\s*"exit_code"', raw_output)[0]

    # Search for ```python ... ```
    match = re.search(r"```(?:python)?\s*\n(.*?)\n```", cleaned, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Second attempt: find first line with imports or docstring or def
    lines = cleaned.splitlines()
    code_lines = []
    started = False
    for line in lines:
        if any(line.startswith(prefix) for prefix in ("import ", "from ", "def find_shortest_path", '"""', "'''")):
            started = True
        if started:
            code_lines.append(line)

    if code_lines:
        return "\n".join(code_lines).strip()

    return cleaned.strip()


def run_etta() -> tuple[float, str, Path | None, str | None]:
    print("\n" + "=" * 70)
    print("▶ DISPATCHING ETTA (Autonomous Reflex + JEV Governor)")
    print("=" * 70)

    prompt = SPEC_FILE.read_text(encoding="utf-8")
    etta_target = ETTA_WS / "astar_solver.py"
    ETTA_WS.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    cmd = [
        "etta",
        "--headless",
        "--workspace",
        str(ETTA_WS),
        "--goal",
        prompt,
    ]

    print(f"Executing: etta --headless --workspace {ETTA_WS.name} ...")
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=180,
        )
        gen_time = time.perf_counter() - t0
        raw_output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")

        if proc.returncode != 0:
            print(f"etta exited with non-zero code {proc.returncode}")

        code = extract_python_code(raw_output)
        etta_target.write_text(code + "\n", encoding="utf-8")
        print(f"Saved etta candidate to: {etta_target} ({len(code.splitlines())} lines in {gen_time:.2f}s)")
        return gen_time, code, etta_target, None
    except Exception as e:
        gen_time = time.perf_counter() - t0
        print(f"etta execution failed: {e}")
        return gen_time, "", None, str(e)


def run_agy() -> tuple[float, str, Path | None, str | None]:
    print("\n" + "=" * 70)
    print("▶ DISPATCHING AGY (CLI Print Mode, Model: gemini-3.8-flash-high)")
    print("=" * 70)

    spec_text = SPEC_FILE.read_text(encoding="utf-8")
    prompt = (
        "TASK: Implement the complete Python code for astar_solver.py and save it to astar_solver.py in the current directory.\n\n"
        + spec_text
    )
    agy_target = AGY_WS / "astar_solver.py"
    AGY_WS.mkdir(parents=True, exist_ok=True)

    # Remove previous solver if present
    agy_target.unlink(missing_ok=True)

    t0 = time.perf_counter()
    cmd = [
        "agy",
        "-p",
        prompt,
        "--model",
        "gemini-3.8-flash-high",
        "--dangerously-skip-permissions",
    ]

    print(f"Executing: agy -p <prompt> --model gemini-3.8-flash-high --dangerously-skip-permissions in {AGY_WS.name} ...")
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(AGY_WS),
            capture_output=True,
            text=True,
            timeout=180,
        )
        gen_time = time.perf_counter() - t0
        raw_output = proc.stdout

        if proc.returncode != 0:
            print(f"agy exited with non-zero code {proc.returncode}")
            if proc.stderr:
                print(f"agy stderr: {proc.stderr[:300]}")

        # Check if agy created the file directly via tool
        if agy_target.exists() and agy_target.stat().st_size > 50:
            code = agy_target.read_text(encoding="utf-8")
        else:
            # Fallback to stdout extraction
            code = extract_python_code(raw_output)
            agy_target.write_text(code + "\n", encoding="utf-8")

        print(f"Saved agy candidate to: {agy_target} ({len(code.splitlines())} lines in {gen_time:.2f}s)")
        return gen_time, code, agy_target, None
    except Exception as e:
        gen_time = time.perf_counter() - t0
        print(f"agy execution failed: {e}")
        return gen_time, "", None, str(e)


def evaluate_solver(solver_path: Path) -> dict:
    if not solver_path.exists():
        return {"passed": 0, "total": 12, "time_ms": 0.0, "output": "File not found"}

    cmd = [sys.executable, str(EVALUATOR), str(solver_path)]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    bench_time_ms = (time.perf_counter() - t0) * 1000.0

    output = proc.stdout
    score_match = re.search(r"SCORE:\s*(\d+)/(\d+)\s*Passed", output)
    passed = int(score_match.group(1)) if score_match else 0
    total = int(score_match.group(2)) if score_match else 12

    return {
        "passed": passed,
        "total": total,
        "time_ms": bench_time_ms,
        "output": output,
        "exit_code": proc.returncode,
    }


def main():
    print("=======================================================================")
    print("  🏆 HEAD-TO-HEAD BENCHMARK: ETTA vs. AGY (A* SHORTEST PATH)")
    print("=======================================================================")

    # 1. Run etta
    etta_gen_time, etta_code, etta_file, etta_err = run_etta()

    # 2. Run agy
    agy_gen_time, agy_code, agy_file, agy_err = run_agy()

    # 3. Evaluate etta
    print("\n" + "=" * 70)
    print("🔬 EVALUATING ETTA CANDIDATE")
    print("=" * 70)
    etta_eval = evaluate_solver(etta_file) if etta_file else {"passed": 0, "total": 12, "time_ms": 0, "output": etta_err}
    print(etta_eval.get("output", ""))

    # 4. Evaluate agy
    print("\n" + "=" * 70)
    print("🔬 EVALUATING AGY CANDIDATE")
    print("=" * 70)
    agy_eval = evaluate_solver(agy_file) if agy_file else {"passed": 0, "total": 12, "time_ms": 0, "output": agy_err}
    print(agy_eval.get("output", ""))

    # 5. Final Scoreboard
    etta_lines = len(etta_code.splitlines()) if etta_code else 0
    agy_lines = len(agy_code.splitlines()) if agy_code else 0

    print("\n" + "=" * 70)
    print("📊 FINAL BENCHMARK SCOREBOARD")
    print("=" * 70)
    print(f"{'Metric':<30} | {'ETTA':<17} | {'AGY':<17}")
    print("-" * 70)
    print(f"{'Test Cases Passed':<30} | {etta_eval['passed']:>2}/{etta_eval['total']:<14} | {agy_eval['passed']:>2}/{agy_eval['total']:<14}")
    print(f"{'Generation Latency (s)':<30} | {etta_gen_time:>14.2f}s | {agy_gen_time:>14.2f}s")
    print(f"{'Code Size (Lines of Code)':<30} | {etta_lines:>14}  | {agy_lines:>14} ")
    print(f"{'Evaluation Suite Runtime (ms)':<30} | {etta_eval['time_ms']:>12.2f}ms | {agy_eval['time_ms']:>12.2f}ms")
    print("-" * 70)

    if etta_eval['passed'] > agy_eval['passed']:
        winner = "🏆 ETTA WINS (Higher Test Pass Count)"
    elif agy_eval['passed'] > etta_eval['passed']:
        winner = "🏆 AGY WINS (Higher Test Pass Count)"
    else:
        if etta_gen_time < agy_gen_time:
            winner = "🏆 ETTA WINS (Equal Tests Passed, Faster Code Generation)"
        else:
            winner = "🏆 AGY WINS (Equal Tests Passed, Faster Code Generation)"

    print(f"VERDICT: {winner}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
