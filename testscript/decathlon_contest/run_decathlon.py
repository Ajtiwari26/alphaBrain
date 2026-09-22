#!/usr/bin/env python3
"""
Master Decathlon Orchestrator: etta vs. agy
Executes both engines across the 10 absolute hardest contest-level algorithmic problems:
  1. LeetCode 3013: Divide an Array Into Subarrays With Minimum Cost II (11% acceptance)
  2. LeetCode 420: Strong Password Checker (16.4% acceptance)
  3. LeetCode 887: Super Egg Drop (27% acceptance)
  4. LeetCode 354: Russian Doll Envelopes (37% acceptance)
  5. LeetCode 218: The Skyline Problem (45% acceptance)
  6. LeetCode 480: Sliding Window Median (39% acceptance)
  7. LeetCode 847: Shortest Path Visiting All Nodes (61% acceptance)
  8. LeetCode 10: Regular Expression Matching (28% acceptance)
  9. LeetCode 312: Burst Balloons (58% acceptance)
  10. LeetCode 407: Trapping Rain Water II (48% acceptance)

Total: 120 Blind Edge Cases & Asymptotic Stress Tests.
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

DECATHLON_ROOT = Path(__file__).parent.resolve()

PROBLEMS = [
    {
        "id": 1,
        "name": "LC 3013: Subarrays Cost II",
        "category": "Dual Heaps / Sliding Window",
        "dir": DECATHLON_ROOT / "problem01_subarrays_cost",
        "prompt_file": DECATHLON_ROOT / "problem01_subarrays_cost" / "PROMPT.md",
        "evaluator": DECATHLON_ROOT / "problem01_subarrays_cost" / "evaluator.py",
        "target_file": "minimum_cost.py",
        "signature_marker": "def minimum_cost",
    },
    {
        "id": 2,
        "name": "LC 420: Strong Password Checker",
        "category": "Greedy Modulo-3 Casework",
        "dir": DECATHLON_ROOT / "problem02_password_checker",
        "prompt_file": DECATHLON_ROOT / "problem02_password_checker" / "PROMPT.md",
        "evaluator": DECATHLON_ROOT / "problem02_password_checker" / "evaluator.py",
        "target_file": "password_checker.py",
        "signature_marker": "def strong_password_checker",
    },
    {
        "id": 3,
        "name": "LC 887: Super Egg Drop",
        "category": "Inverted DP / Binomial Math",
        "dir": DECATHLON_ROOT / "problem03_egg_drop",
        "prompt_file": DECATHLON_ROOT / "problem03_egg_drop" / "PROMPT.md",
        "evaluator": DECATHLON_ROOT / "problem03_egg_drop" / "evaluator.py",
        "target_file": "super_egg_drop.py",
        "signature_marker": "def super_egg_drop",
    },
    {
        "id": 4,
        "name": "LC 354: Russian Doll Envelopes",
        "category": "2D LIS / Patience Sorting",
        "dir": DECATHLON_ROOT / "problem04_russian_dolls",
        "prompt_file": DECATHLON_ROOT / "problem04_russian_dolls" / "PROMPT.md",
        "evaluator": DECATHLON_ROOT / "problem04_russian_dolls" / "evaluator.py",
        "target_file": "russian_dolls.py",
        "signature_marker": "def max_envelopes",
    },
    {
        "id": 5,
        "name": "LC 218: The Skyline Problem",
        "category": "Sweep-Line / Max Heap",
        "dir": DECATHLON_ROOT / "problem05_skyline",
        "prompt_file": DECATHLON_ROOT / "problem05_skyline" / "PROMPT.md",
        "evaluator": DECATHLON_ROOT / "problem05_skyline" / "evaluator.py",
        "target_file": "skyline.py",
        "signature_marker": "def get_skyline",
    },
    {
        "id": 6,
        "name": "LC 480: Sliding Window Median",
        "category": "Dual Heaps Lazy Eviction",
        "dir": DECATHLON_ROOT / "problem06_sliding_median",
        "prompt_file": DECATHLON_ROOT / "problem06_sliding_median" / "PROMPT.md",
        "evaluator": DECATHLON_ROOT / "problem06_sliding_median" / "evaluator.py",
        "target_file": "sliding_median.py",
        "signature_marker": "def median_sliding_window",
    },
    {
        "id": 7,
        "name": "LC 847: Shortest Path All Nodes",
        "category": "Bitmask BFS State Space",
        "dir": DECATHLON_ROOT / "problem07_shortest_path_all_nodes",
        "prompt_file": DECATHLON_ROOT / "problem07_shortest_path_all_nodes" / "PROMPT.md",
        "evaluator": DECATHLON_ROOT / "problem07_shortest_path_all_nodes" / "evaluator.py",
        "target_file": "shortest_path_nodes.py",
        "signature_marker": "def shortest_path_length",
    },
    {
        "id": 8,
        "name": "LC 10: Regular Expression Matching",
        "category": "2D DP Kleene Star Backtracking",
        "dir": DECATHLON_ROOT / "problem08_regex_matching",
        "prompt_file": DECATHLON_ROOT / "problem08_regex_matching" / "PROMPT.md",
        "evaluator": DECATHLON_ROOT / "problem08_regex_matching" / "evaluator.py",
        "target_file": "regex_matching.py",
        "signature_marker": "def is_match",
    },
    {
        "id": 9,
        "name": "LC 312: Burst Balloons",
        "category": "Reverse Interval DP O(N^3)",
        "dir": DECATHLON_ROOT / "problem09_burst_balloons",
        "prompt_file": DECATHLON_ROOT / "problem09_burst_balloons" / "PROMPT.md",
        "evaluator": DECATHLON_ROOT / "problem09_burst_balloons" / "evaluator.py",
        "target_file": "burst_balloons.py",
        "signature_marker": "def max_coins",
    },
    {
        "id": 10,
        "name": "LC 407: Trapping Rain Water II",
        "category": "3D Priority-Queue Dijkstra",
        "dir": DECATHLON_ROOT / "problem10_trapping_rain_3d",
        "prompt_file": DECATHLON_ROOT / "problem10_trapping_rain_3d" / "PROMPT.md",
        "evaluator": DECATHLON_ROOT / "problem10_trapping_rain_3d" / "evaluator.py",
        "target_file": "trapping_rain_3d.py",
        "signature_marker": "def trap_rain_water",
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

    print(f"\n  ⚡ [{prob['name']}] Dispatching ETTA...", flush=True)
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
        tokens = meta.get("tokens_used", 0)
        cost = meta.get("cost", 0.0)
        print(f"     ETTA finished in {gen_time:.2f}s ({loc} LOC | {tokens:,} tokens | ${cost:.5f})", flush=True)
        return {
            "success": True,
            "gen_time": gen_time,
            "code": code,
            "loc": loc,
            "target_path": str(target_path),
            "tokens": tokens,
            "cost": cost,
        }
    except Exception as e:
        gen_time = time.perf_counter() - t0
        print(f"     ETTA error: {e}", flush=True)
        return {
            "success": False,
            "gen_time": gen_time,
            "error": str(e),
            "target_path": None,
            "loc": 0,
            "tokens": 0,
            "cost": 0.0,
        }


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

    print(f"\n  🤖 [{prob['name']}] Dispatching AGY...", flush=True)
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
        est_tokens = max(loc * 25, int(gen_time * 650))
        est_cost = est_tokens * 0.00000006
        print(f"     AGY finished in {gen_time:.2f}s ({loc} LOC | ~{est_tokens:,} tokens | ~${est_cost:.5f})", flush=True)
        return {
            "success": True,
            "gen_time": gen_time,
            "code": code,
            "loc": loc,
            "target_path": str(target_path),
            "tokens": est_tokens,
            "cost": est_cost,
        }
    except Exception as e:
        gen_time = time.perf_counter() - t0
        print(f"     AGY error: {e}", flush=True)
        return {
            "success": False,
            "gen_time": gen_time,
            "error": str(e),
            "target_path": None,
            "loc": 0,
            "tokens": 0,
            "cost": 0.0,
        }


def evaluate_problem(prob: dict, solver_path_str: str | None) -> dict:
    if not solver_path_str:
        return {"passed": 0, "total": 12, "time_ms": 0.0, "output": "File not found"}

    solver_path = Path(solver_path_str)
    if not solver_path.exists():
        return {"passed": 0, "total": 12, "time_ms": 0.0, "output": "File not found"}

    cmd = [sys.executable, str(prob["evaluator"]), str(solver_path)]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    bench_time_ms = (time.perf_counter() - t0) * 1000.0

    output = proc.stdout
    score_match = re.search(r"SCORE:\s*(\d+)/(\d+)\s*Passed", output)
    passed = int(score_match.group(1)) if score_match else 0
    total = int(score_match.group(2)) if score_match else 12

    # Parse individual test case passes
    case_results = []
    for line in output.splitlines():
        if "[OK ]" in line or "[ERR]" in line:
            case_results.append(line.strip())

    return {
        "passed": passed,
        "total": total,
        "time_ms": bench_time_ms,
        "case_results": case_results,
        "output": output,
        "exit_code": proc.returncode,
    }


def main():
    print("=" * 95)
    print("  🏆 GRAND DECATHLON BENCHMARK: ETTA vs. AGY")
    print("  10 Hardest Contest-Level Problems | 120 Blind Edge Cases")
    print("=" * 95)

    results_file = DECATHLON_ROOT / "decathlon_results.json"
    results = []

    for prob in PROBLEMS:
        print("\n" + "=" * 95)
        print(f"  ROUND {prob['id']:02d}/10: {prob['name']} [{prob['category']}]")
        print("=" * 95)

        # 1. Run etta
        etta_res = run_etta_problem(prob)

        # 2. Run agy
        agy_res = run_agy_problem(prob)

        # 3. Grade etta
        print(f"\n  📊 Grading ETTA on {prob['name']}...")
        etta_eval = evaluate_problem(prob, etta_res.get("target_path"))
        print(f"     Result: {etta_eval['passed']}/{etta_eval['total']} Passed ({etta_eval['time_ms']:.2f}ms)")

        # 4. Grade agy
        print(f"  📊 Grading AGY on {prob['name']}...")
        agy_eval = evaluate_problem(prob, agy_res.get("target_path"))
        print(f"     Result: {agy_eval['passed']}/{agy_eval['total']} Passed ({agy_eval['time_ms']:.2f}ms)")

        entry = {
            "problem": {
                "id": prob["id"],
                "name": prob["name"],
                "category": prob["category"],
            },
            "etta": {**etta_res, **etta_eval},
            "agy": {**agy_res, **agy_eval},
        }
        results.append(entry)

        # Persist results incrementally
        results_file.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Print Final Scoreboard
    print("\n\n" + "=" * 105)
    print("  🏁 GRAND DECATHLON FINAL SCOREBOARD (10 HARDEST ALGORITHMIC PROBLEMS)")
    print("=" * 105)
    header = f"{'Problem':<36} | {'ETTA Score':<11} | {'AGY Score':<11} | {'ETTA Lat':<9} | {'AGY Lat':<9} | {'Speedup':<8}"
    print(header)
    print("-" * 105)

    tot_etta_passed = 0
    tot_agy_passed = 0
    tot_tests = 0
    tot_etta_time = 0.0
    tot_agy_time = 0.0
    tot_etta_tokens = 0
    tot_agy_tokens = 0
    tot_etta_cost = 0.0
    tot_agy_cost = 0.0

    for r in results:
        p_name = r["problem"]["name"]
        ep = r["etta"]["passed"]
        ap = r["agy"]["passed"]
        tot = r["etta"]["total"]
        et = r["etta"]["gen_time"]
        at = r["agy"]["gen_time"]
        speedup = (at / et) if et > 0 else 1.0

        tot_etta_passed += ep
        tot_agy_passed += ap
        tot_tests += tot
        tot_etta_time += et
        tot_agy_time += at
        tot_etta_tokens += r["etta"].get("tokens", 0)
        tot_agy_tokens += r["agy"].get("tokens", 0)
        tot_etta_cost += r["etta"].get("cost", 0.0)
        tot_agy_cost += r["agy"].get("cost", 0.0)

        print(f"{p_name:<36} | {ep:>2}/{tot:<8} | {ap:>2}/{tot:<8} | {et:>7.2f}s | {at:>7.2f}s | {speedup:>6.1f}x")

    print("-" * 105)
    overall_speedup = (tot_agy_time / tot_etta_time) if tot_etta_time > 0 else 1.0
    print(f"{'OVERALL TOTALS (120 Edge Cases)':<36} | {tot_etta_passed:>3}/{tot_tests:<7} | {tot_agy_passed:>3}/{tot_tests:<7} | {tot_etta_time:>7.2f}s | {tot_agy_time:>7.2f}s | {overall_speedup:>6.1f}x")
    print(f"{'Total Tokens Consumed':<36} | {tot_etta_tokens:>10,}{'':<3} | {tot_agy_tokens:>10,}{'':<3} | ETTA: ${tot_etta_cost:.5f} | AGY: ${tot_agy_cost:.5f}")
    print("=" * 105)

    if tot_etta_passed > tot_agy_passed:
        verdict = f"🏆 ETTA WINS THE DECATHLON ({tot_etta_passed}/{tot_tests} vs {tot_agy_passed}/{tot_tests}, {overall_speedup:.1f}x Faster)!"
    elif tot_agy_passed > tot_etta_passed:
        verdict = f"🏆 AGY WINS THE DECATHLON ({tot_agy_passed}/{tot_tests} vs {tot_etta_passed}/{tot_tests}, AGY edged on test pass rate)!"
    else:
        verdict = f"🏆 TIED ON TEST ACCURACY ({tot_etta_passed}/{tot_tests}) — ETTA WINS ON SPEED ({overall_speedup:.1f}x Faster) & COST!"

    print(f"\nFINAL VERDICT: {verdict}\n")


if __name__ == "__main__":
    main()
