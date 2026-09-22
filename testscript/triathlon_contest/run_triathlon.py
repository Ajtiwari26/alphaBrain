#!/usr/bin/env python3
"""
Master Triathlon Orchestrator: etta vs. agy
Executes both engines across 3 of the hardest LeetCode problems:
  1. LeetCode 420: Strong Password Checker (16.4% acceptance rate)
  2. LeetCode 218: The Skyline Problem
  3. LeetCode 480: Sliding Window Median (N=30,000 stress test)
Evaluates 36 total blind edge cases and outputs full comparative telemetry.
"""

import os
import re
import sys
import json
import time
import subprocess
from pathlib import Path

CONTEST_ROOT = Path(__file__).parent.resolve()

PROBLEMS = [
    {
        "id": 1,
        "name": "LeetCode 420: Strong Password Checker",
        "dir": CONTEST_ROOT / "problem1_password",
        "prompt_file": CONTEST_ROOT / "problem1_password" / "PROMPT.md",
        "evaluator": CONTEST_ROOT / "problem1_password" / "evaluator.py",
        "target_file": "password_checker.py",
        "signature_marker": "def strong_password_checker",
    },
    {
        "id": 2,
        "name": "LeetCode 218: The Skyline Problem",
        "dir": CONTEST_ROOT / "problem2_skyline",
        "prompt_file": CONTEST_ROOT / "problem2_skyline" / "PROMPT.md",
        "evaluator": CONTEST_ROOT / "problem2_skyline" / "evaluator.py",
        "target_file": "skyline.py",
        "signature_marker": "def get_skyline",
    },
    {
        "id": 3,
        "name": "LeetCode 480: Sliding Window Median",
        "dir": CONTEST_ROOT / "problem3_sliding_median",
        "prompt_file": CONTEST_ROOT / "problem3_sliding_median" / "PROMPT.md",
        "evaluator": CONTEST_ROOT / "problem3_sliding_median" / "evaluator.py",
        "target_file": "sliding_median.py",
        "signature_marker": "def median_sliding_window",
    },
]


def extract_python_code(raw_output: str, marker: str) -> str:
    """Extract clean Python code from LLM output, stripping metadata and fences."""
    cleaned = re.split(r'\n\{\s*\n?\s*"exit_code"', raw_output)[0]

    # Check for ```python ... ```
    match = re.search(r"```(?:python)?\s*\n(.*?)\n```", cleaned, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Search for marker or imports
    lines = cleaned.splitlines()
    code_lines = []
    started = False
    for line in lines:
        if any(line.startswith(prefix) for prefix in ("import ", "from ", marker, '"""', "'''")):
            started = True
        if started:
            code_lines.append(line)

    if code_lines:
        return "\n".join(code_lines).strip()

    return cleaned.strip()


def parse_etta_metadata(raw_output: str) -> dict:
    """Extract tokens_used and cost from etta's trailing JSON lifecycle output."""
    match = re.search(r'(\{\s*\n?\s*"exit_code".*?\})', raw_output, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except Exception:
            pass
    return {"tokens_used": 0, "cost": 0.0}


def run_etta_problem(prob: dict) -> dict:
    prompt = prob["prompt_file"].read_text(encoding="utf-8")
    ws_dir = prob["dir"] / "etta_ws"
    ws_dir.mkdir(parents=True, exist_ok=True)
    target_path = ws_dir / prob["target_file"]

    print(f"\n[{prob['name']}] Dispatching ETTA...")
    t0 = time.perf_counter()
    cmd = [
        "etta",
        "--headless",
        "--workspace",
        str(ws_dir),
        "--goal",
        prompt,
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        gen_time = time.perf_counter() - t0
        raw_output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
        meta = parse_etta_metadata(raw_output)
        code = extract_python_code(raw_output, prob["signature_marker"])
        target_path.write_text(code + "\n", encoding="utf-8")
        loc = len(code.splitlines())
        print(f"  └─ ETTA completed in {gen_time:.2f}s ({loc} LOC | {meta.get('tokens_used', 0)} tokens)")
        return {
            "success": True,
            "gen_time": gen_time,
            "code": code,
            "loc": loc,
            "target_path": target_path,
            "tokens": meta.get("tokens_used", 0),
            "cost": meta.get("cost", 0.0),
        }
    except Exception as e:
        gen_time = time.perf_counter() - t0
        print(f"  └─ ETTA error: {e}")
        return {"success": False, "gen_time": gen_time, "error": str(e), "target_path": None, "loc": 0, "tokens": 0, "cost": 0.0}


def run_agy_problem(prob: dict) -> dict:
    spec_text = prob["prompt_file"].read_text(encoding="utf-8")
    prompt = (
        f"TASK: Implement the complete Python code for {prob['target_file']} and save it to {prob['target_file']} in the current directory.\n\n"
        + spec_text
    )
    ws_dir = prob["dir"] / "agy_ws"
    ws_dir.mkdir(parents=True, exist_ok=True)
    target_path = ws_dir / prob["target_file"]
    target_path.unlink(missing_ok=True)

    print(f"\n[{prob['name']}] Dispatching AGY...")
    t0 = time.perf_counter()
    cmd = [
        "agy",
        "-p",
        prompt,
        "--model",
        "gemini-3.8-flash-high",
        "--dangerously-skip-permissions",
    ]

    try:
        proc = subprocess.run(cmd, cwd=str(ws_dir), capture_output=True, text=True, timeout=240)
        gen_time = time.perf_counter() - t0
        raw_output = proc.stdout

        if target_path.exists() and target_path.stat().st_size > 50:
            code = target_path.read_text(encoding="utf-8")
        else:
            code = extract_python_code(raw_output, prob["signature_marker"])
            target_path.write_text(code + "\n", encoding="utf-8")

        loc = len(code.splitlines())
        # Estimate tokens based on generation time and typical 19-turn transcript expansion
        est_tokens = max(loc * 20, int(gen_time * 650))
        est_cost = est_tokens * 0.00000006
        print(f"  └─ AGY completed in {gen_time:.2f}s ({loc} LOC | ~{est_tokens} tokens)")
        return {
            "success": True,
            "gen_time": gen_time,
            "code": code,
            "loc": loc,
            "target_path": target_path,
            "tokens": est_tokens,
            "cost": est_cost,
        }
    except Exception as e:
        gen_time = time.perf_counter() - t0
        print(f"  └─ AGY error: {e}")
        return {"success": False, "gen_time": gen_time, "error": str(e), "target_path": None, "loc": 0, "tokens": 0, "cost": 0.0}


def evaluate_problem(prob: dict, solver_path: Path | None) -> dict:
    if not solver_path or not solver_path.exists():
        return {"passed": 0, "total": 12, "time_ms": 0.0, "output": "File not found"}

    cmd = [sys.executable, str(prob["evaluator"]), str(solver_path)]
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
    print("=" * 80)
    print("  🏆 GRAND TRIATHLON BENCHMARK: ETTA vs. AGY")
    print("  3 of the Hardest LeetCode Problems | 36 Blind Edge Cases")
    print("=" * 80)

    triathlon_results = []

    for prob in PROBLEMS:
        print("\n" + "#" * 80)
        print(f"  ROUND {prob['id']}: {prob['name']}")
        print("#" * 80)

        # 1. Run etta
        etta_res = run_etta_problem(prob)

        # 2. Run agy
        agy_res = run_agy_problem(prob)

        # 3. Evaluate etta
        print(f"\n--- Grading ETTA on {prob['name']} ---")
        etta_eval = evaluate_problem(prob, etta_res.get("target_path"))
        print(etta_eval.get("output", "").strip())

        # 4. Evaluate agy
        print(f"\n--- Grading AGY on {prob['name']} ---")
        agy_eval = evaluate_problem(prob, agy_res.get("target_path"))
        print(agy_eval.get("output", "").strip())

        triathlon_results.append({
            "problem": prob,
            "etta": {**etta_res, **etta_eval},
            "agy": {**agy_res, **agy_eval},
        })

    # Final Grand Scoreboard
    print("\n\n" + "=" * 95)
    print("  🏁 GRAND TRIATHLON FINAL SCOREBOARD")
    print("=" * 95)
    header = f"{'Problem':<36} | {'ETTA Score':<12} | {'AGY Score':<12} | {'ETTA Latency':<13} | {'AGY Latency':<13}"
    print(header)
    print("-" * 95)

    tot_etta_passed = 0
    tot_agy_passed = 0
    tot_etta_time = 0.0
    tot_agy_time = 0.0
    tot_etta_tokens = 0
    tot_agy_tokens = 0
    tot_etta_cost = 0.0
    tot_agy_cost = 0.0

    for r in triathlon_results:
        p_name = r["problem"]["name"]
        e_p = r["etta"]["passed"]
        a_p = r["agy"]["passed"]
        tot = r["etta"]["total"]
        e_t = r["etta"]["gen_time"]
        a_t = r["agy"]["gen_time"]

        tot_etta_passed += e_p
        tot_agy_passed += a_p
        tot_etta_time += e_t
        tot_agy_time += a_t
        tot_etta_tokens += r["etta"].get("tokens", 0)
        tot_agy_tokens += r["agy"].get("tokens", 0)
        tot_etta_cost += r["etta"].get("cost", 0.0)
        tot_agy_cost += r["agy"].get("cost", 0.0)

        print(f"{p_name:<36} | {e_p:>2}/{tot:<9} | {a_p:>2}/{tot:<9} | {e_t:>11.2f}s | {a_t:>11.2f}s")

    print("-" * 95)
    print(f"{'OVERALL TOTALS (36 Edge Cases)':<36} | {tot_etta_passed:>2}/36{'':<8} | {tot_agy_passed:>2}/36{'':<8} | {tot_etta_time:>11.2f}s | {tot_agy_time:>11.2f}s")
    print(f"{'Total Tokens Consumed':<36} | {tot_etta_tokens:>12,}{'':<2} | {tot_agy_tokens:>12,}{'':<2} | (ETTA: ${tot_etta_cost:.5f} | AGY: ${tot_agy_cost:.5f})")
    print("=" * 95)

    if tot_etta_passed > tot_agy_passed:
        verdict = f"🏆 ETTA WINS THE TRIATHLON ({tot_etta_passed} vs {tot_agy_passed} passed)!"
    elif tot_agy_passed > tot_etta_passed:
        verdict = f"🏆 AGY WINS THE TRIATHLON ({tot_agy_passed} vs {tot_etta_passed} passed)!"
    else:
        if tot_etta_time < tot_agy_time:
            verdict = f"🏆 ETTA WINS THE TRIATHLON (Tied at {tot_etta_passed}/36, ETTA {tot_agy_time/tot_etta_time:.1f}x Faster)!"
        else:
            verdict = f"🏆 AGY WINS THE TRIATHLON (Tied at {tot_agy_passed}/36, AGY {tot_etta_time/tot_agy_time:.1f}x Faster)!"

    print(f"\nFINAL VERDICT: {verdict}\n")


if __name__ == "__main__":
    main()
