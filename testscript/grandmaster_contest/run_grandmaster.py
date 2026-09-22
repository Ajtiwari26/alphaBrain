#!/usr/bin/env python3
"""
Master Grandmaster Olympiad Benchmark Orchestrator: etta vs. agy
Executes both engines across the 5 hardest competitive programming domains (2400-2800 Rating):
  1. G1: CF 713C - Slope Trick / Convex Function Optimization (O(N log N))
  2. G2: CF 165E - SOS Dynamic Programming / Submask Bit Invariants (O(N + B * 2^B))
  3. G3: Dinic's Algorithm on Adversarial Killer Gadgets with Current-Arc Pointers
  4. G4: CF 319C - Convex Hull Trick / Li Chao Tree (O(N) amortized)
  5. G5: CF 427D - Match & Catch / Suffix Automaton DAWG (O((N1 + N2) log Sigma))

All problems feature adversarial counterexamples and strict asymptotic scale constraints.
"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).parent.resolve()
RESULTS_JSON = ROOT_DIR / "grandmaster_results.json"

PROBLEMS = [
    {
        "id": 1,
        "name": "CF 713C: Sonya and Problem (Slope Trick)",
        "category": "Convex Function Optimization",
        "dir": ROOT_DIR / "problem01_slope_trick",
        "prompt_file": ROOT_DIR / "problem01_slope_trick" / "PROMPT.md",
        "evaluator": ROOT_DIR / "problem01_slope_trick" / "evaluator.py",
        "target_file": "slope_trick.py",
        "signature_marker": "def min_operations_increasing",
        "total_cases": 12,
    },
    {
        "id": 2,
        "name": "CF 165E: Compatible Numbers (SOS DP)",
        "category": "Sum Over Subsets Dynamic Programming",
        "dir": ROOT_DIR / "problem02_sos_dp",
        "prompt_file": ROOT_DIR / "problem02_sos_dp" / "PROMPT.md",
        "evaluator": ROOT_DIR / "problem02_sos_dp" / "evaluator.py",
        "target_file": "compatible_numbers.py",
        "signature_marker": "def find_compatible_numbers",
        "total_cases": 11,
    },
    {
        "id": 3,
        "name": "Dinic Flow with Current-Arc Optimization",
        "category": "Adversarial Killer Flow Network",
        "dir": ROOT_DIR / "problem03_dinic_killer",
        "prompt_file": ROOT_DIR / "problem03_dinic_killer" / "PROMPT.md",
        "evaluator": ROOT_DIR / "problem03_dinic_killer" / "evaluator.py",
        "target_file": "max_flow.py",
        "signature_marker": "def max_flow",
        "total_cases": 11,
    },
    {
        "id": 4,
        "name": "CF 319C: Kalila and Dimna (Convex Hull Trick)",
        "category": "Lower Envelope Deque Optimization",
        "dir": ROOT_DIR / "problem04_convex_hull_trick",
        "prompt_file": ROOT_DIR / "problem04_convex_hull_trick" / "PROMPT.md",
        "evaluator": ROOT_DIR / "problem04_convex_hull_trick" / "evaluator.py",
        "target_file": "kalila_dimna.py",
        "signature_marker": "def min_logging_cost",
        "total_cases": 9,
    },
    {
        "id": 5,
        "name": "CF 427D: Match & Catch (Suffix Automaton)",
        "category": "DAWG Linear String Indexing",
        "dir": ROOT_DIR / "problem05_suffix_automaton",
        "prompt_file": ROOT_DIR / "problem05_suffix_automaton" / "PROMPT.md",
        "evaluator": ROOT_DIR / "problem05_suffix_automaton" / "evaluator.py",
        "target_file": "match_catch.py",
        "signature_marker": "def shortest_unique_common_substring",
        "total_cases": 11,
    },
]


def extract_python_code(raw_output: str, marker: str, target_file: str) -> str:
    """Robust extraction supporting framed delivery protocol, markdown blocks, or raw python."""
    # Check 1: Typed framing protocol payload
    framed_match = re.search(
        r"<<<ETTA_ARTIFACT_PAYLOAD>>>\s*\n(.*?)\n<<<ETTA_ARTIFACT_END>>>",
        raw_output,
        re.DOTALL,
    )
    if framed_match:
        return framed_match.group(1).strip()

    # Check 2: Strip trailing JSON lifecycle report
    cleaned = re.split(r'\n\{\s*\n?\s*"exit_code"', raw_output)[0]

    # Check 3: Markdown code blocks
    code_blocks = re.findall(r"```(?:python)?\s*\n(.*?)\n```", cleaned, re.DOTALL)
    if code_blocks:
        for block in code_blocks:
            if marker in block:
                return block.strip()
        return max(code_blocks, key=len).strip()

    # Check 4: Raw python lines
    lines = cleaned.splitlines()
    code_lines = []
    started = False
    for line in lines:
        if any(line.startswith(p) for p in ("import ", "from ", marker, '"""', "'''")):
            started = True
        if started:
            if line.strip().startswith("```"):
                continue
            if line.startswith(target_file) and "def " in line:
                line = line[len(target_file):].strip()
            code_lines.append(line)

    if code_lines:
        return "\n".join(code_lines).strip()

    return cleaned.strip()


def parse_etta_metadata(raw_output: str) -> dict:
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

    print(f"\n  ⚡ [Problem G{prob['id']}: {prob['name']}] Dispatching ETTA live...", flush=True)
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
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        gen_time = time.perf_counter() - t0
        raw_output = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
        meta = parse_etta_metadata(raw_output)
        code = extract_python_code(raw_output, prob["signature_marker"], prob["target_file"])

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

    print(f"\n  🤖 [Problem G{prob['id']}: {prob['name']}] Dispatching AGY live...", flush=True)
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
        proc = subprocess.run(cmd, cwd=str(ws_dir), capture_output=True, text=True, timeout=300)
        gen_time = time.perf_counter() - t0
        raw_output = proc.stdout

        if target_path.exists() and target_path.stat().st_size > 50:
            code = target_path.read_text(encoding="utf-8")
        else:
            code = extract_python_code(raw_output, prob["signature_marker"], prob["target_file"])
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


def evaluate_solution(evaluator_script: Path, candidate_file: Path) -> dict:
    if not candidate_file or not candidate_file.exists():
        return {
            "passed": 0,
            "total": 12,
            "time_ms": 0.0,
            "case_results": ["File missing"],
            "output": "Candidate file does not exist",
            "exit_code": 1,
        }

    try:
        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, str(evaluator_script), str(candidate_file)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        total_time_ms = (time.perf_counter() - t0) * 1000.0
        stdout = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")

        cases = [line for line in stdout.splitlines() if line.startswith(("[OK ]", "[ERR]"))]
        passed = sum(1 for c in cases if "-> PASS" in c)
        total = len(cases)

        score_match = re.search(r"SCORE:\s*(\d+)/(\d+)", stdout)
        if score_match:
            passed = int(score_match.group(1))
            total = int(score_match.group(2))

        return {
            "passed": passed,
            "total": total if total > 0 else 10,
            "time_ms": total_time_ms,
            "case_results": cases,
            "output": stdout,
            "exit_code": proc.returncode,
        }
    except Exception as e:
        return {
            "passed": 0,
            "total": 10,
            "time_ms": 0.0,
            "case_results": [f"Evaluation crashed: {e}"],
            "output": str(e),
            "exit_code": 2,
        }


def main():
    print("=" * 80)
    print("  👑 GRANDMASTER OLYMPIAD BENCHMARK: ETTA vs. AGY (2400-2800 Rating)")
    print("  Testing 5 novel competitive programming challenges with adversarial traps")
    print("=" * 80)

    results = []
    for prob in PROBLEMS:
        print(f"\n[G{prob['id']}/5] Challenge: {prob['name']} ({prob['category']})")

        # 1. Run ETTA
        etta_res = run_etta_problem(prob)
        etta_eval = evaluate_solution(prob["evaluator"], Path(etta_res["target_path"]) if etta_res.get("target_path") else None)
        etta_res.update(etta_eval)
        print(f"     👉 ETTA Score: {etta_eval['passed']}/{etta_eval['total']} Passed ({etta_eval['time_ms']:.1f}ms)")

        # 2. Run AGY
        agy_res = run_agy_problem(prob)
        agy_eval = evaluate_solution(prob["evaluator"], Path(agy_res["target_path"]) if agy_res.get("target_path") else None)
        agy_res.update(agy_eval)
        print(f"     👉 AGY  Score: {agy_eval['passed']}/{agy_eval['total']} Passed ({agy_eval['time_ms']:.1f}ms)")

        results.append({
            "problem": {
                "id": prob["id"],
                "name": prob["name"],
                "category": prob["category"],
            },
            "etta": etta_res,
            "agy": agy_res,
        })

        RESULTS_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("\n" + "=" * 80)
    print("  GRANDMASTER OLYMPIAD BENCHMARK COMPLETED")
    print(f"  Results saved to: {RESULTS_JSON}")
    print("=" * 80)


if __name__ == "__main__":
    main()
