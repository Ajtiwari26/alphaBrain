#!/usr/bin/env python3
"""
Unrestricted Head-to-Head Showdown: ETTA vs. AGY
Across 2 Ultra-Hard Software Engineering Challenges
Strict 5 Minutes Per Challenge (10 Minutes Total)
"""

import os
import sys
import time
import json
import shutil
import re
import subprocess
from pathlib import Path

BASE_DIR = Path("/Users/ajaytiwari/Desktop/Projects/alphaBrain/testscript/dual_gauntlet")
ARENA_DIR = Path("/tmp/unrestricted_arena")
ETTA_BIN = Path("/Users/ajaytiwari/Desktop/Projects/etta/target/release/etta")
AGY_BIN = Path("/Users/ajaytiwari/.local/bin/agy")
TIMEOUT_PER_ROUND = 300  # 5 minutes

def ensure_settings_json(target_dir: Path):
    agents_dir = target_dir / ".agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    settings_file = agents_dir / "settings.json"
    settings_file.write_text(json.dumps({"permissions": {"allow": ["*"]}}, indent=2))

def extract_code_block(raw_text: str, language: str) -> str:
    """Extract code from markdown block or raw text."""
    pattern = rf"```{language}\s*\n(.*?)\n```"
    matches = re.findall(pattern, raw_text, re.DOTALL)
    if matches:
        return matches[-1].strip()
    generic_matches = re.findall(r"```\s*\n(.*?)\n```", raw_text, re.DOTALL)
    if generic_matches:
        return generic_matches[-1].strip()
    return ""

def setup_round_1():
    for agent in ["etta", "agy"]:
        dest = ARENA_DIR / "c1" / agent
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(BASE_DIR / "challenge_1_ast_math", dest, dirs_exist_ok=True)
        ensure_settings_json(dest)
        
        # Inject buggy simplify.py
        code = (dest / "simplify.py").read_text()
        pow_idx = code.find("def simplify_pow")
        mul_idx = code.find("if isinstance(base, Mul):", pow_idx)
        if mul_idx != -1:
            buggy_branch = """    # BUGGY IMPLEMENTATION: Erroneously distributes power across ALL products,
    # ignoring whether elements are non-commutative!
    if isinstance(base, Mul):
        distributed = [simplify_pow(arg, exp) for arg in base.args]
        return simplify_mul(*distributed)

    return Pow(base, exp)
"""
            code = code[:mul_idx] + buggy_branch
            (dest / "simplify.py").write_text(code)

def setup_round_2():
    for agent in ["etta", "agy"]:
        dest = ARENA_DIR / "c2" / agent
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copytree(BASE_DIR / "challenge_2_rust_mvcc", dest, dirs_exist_ok=True)
        ensure_settings_json(dest)

def run_round_1():
    print("\n" + "="*70)
    print("🚀 ROUND 1: CHALLENGE 1 (PYTHON AST NON-COMMUTATIVE MATH)")
    print("="*70)
    print("Timeout:  300s (5.0 minutes)")
    print("Mode:     Unrestricted (Full tools, shell, and python execution)")
    print("Oracle:   10 Hidden Adversarial Test Cases (c1_hidden_oracle.py)")
    print("-"*70)

    setup_round_1()

    etta_dir = ARENA_DIR / "c1" / "etta"
    agy_dir = ARENA_DIR / "c1" / "agy"

    etta_log = ARENA_DIR / "c1" / "etta.log"
    agy_log = ARENA_DIR / "c1" / "agy.log"

    etta_f = open(etta_log, "w", encoding="utf-8")
    agy_f = open(agy_log, "w", encoding="utf-8")

    c1_etta_goal = (
        "In ./simplify.py, fix def simplify_pow(base, exp) so that: "
        "1. Exponents and bases can be either Number or int/float. Extract numeric values: "
        "exp_val = exp.value if isinstance(exp, Number) else exp if isinstance(exp, (int, float)) else None. "
        "base_val = base.value if isinstance(base, Number) else base if isinstance(base, (int, float)) else None. "
        "If exp_val == 0 return Number(1). If exp_val == 1 return base. If both are numeric, return Number(base_val ** exp_val). "
        "2. For nested powers (isinstance(base, Pow)), multiply exponents with Number(a * b) and simplify. "
        "3. For products (isinstance(base, Mul)), distribute power individually over commutative factors/scalars: [simplify_pow(c, exp) for c in c_factors]. "
        "If len(nc_factors) > 1, keep non-commutative factors grouped intact as Pow(Mul(*nc_factors), exp). If len(nc_factors) == 1, distribute onto it. "
        "Check commutativity with getattr(f, 'is_commutative', True). "
        "4. Use file::replace or file::write to update ./simplify.py, run python3 tests/test_public_repro.py, and finish with TASK_COMPLETE."
    )
    
    agy_target = (agy_dir / "simplify.py").resolve()
    agy_test = (agy_dir / "tests" / "test_public_repro.py").resolve()
    c1_agy_prompt = f"""You are tasked with fixing a critical bug in this local repository.
The target file to edit is located at absolute path: {agy_target}.
The reproduction test is located at: {agy_test}.
Run python3 {agy_test} to observe the failure.
Notice that (A * B)**2 is erroneously simplified to A**2 * B**2 when A and B are non-commutative (such as MatrixSymbol or non-commutative Symbol).
Use replace_file_content on {agy_target} to fix simplify_pow so that:
1. Non-commutative powers are NOT distributed across non-commuting elements: Pow(Mul(A, B), 2) stays intact.
2. Commutative scalars and factors can still distribute: (2 * x * A * B)**2 -> 4 * x**2 * (A * B)**2.
3. Nested powers multiply correctly: ((A * B)**2)**3 -> (A * B)**6.
4. Generic non-commutative Symbol("P", commutative=False) is preserved.
5. python3 {agy_test} passes cleanly with zero failures.
Immediately open {agy_target} and apply the fix."""

    # Launch ETTA
    etta_cmd = [
        str(ETTA_BIN),
        "--headless",
        "--workspace", str(etta_dir),
        "--goal", c1_etta_goal
    ]
    t0_etta = time.time()
    etta_proc = subprocess.Popen(etta_cmd, cwd=str(etta_dir), stdout=etta_f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True)

    # Launch AGY
    agy_cmd = [
        str(AGY_BIN),
        "-p", c1_agy_prompt,
        "--model", "gemini-3.8-flash-high",
        "--dangerously-skip-permissions",
        "--effort", "high"
    ]
    t0_agy = time.time()
    agy_proc = subprocess.Popen(agy_cmd, cwd=str(agy_dir), stdout=agy_f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True)

    competitors = [
        {"name": "ETTA", "proc": etta_proc, "f": etta_f, "log": etta_log, "dir": etta_dir, "t0": t0_etta, "done": False, "duration": 0},
        {"name": "AGY",  "proc": agy_proc,  "f": agy_f,  "log": agy_log,  "dir": agy_dir,  "t0": t0_agy,  "done": False, "duration": 0},
    ]

    start_time = time.time()
    while True:
        time.sleep(3)
        elapsed = int(time.time() - start_time)
        remaining = max(0, TIMEOUT_PER_ROUND - elapsed)

        all_done = True
        status_line = f"[{elapsed:3d}s / {TIMEOUT_PER_ROUND}s] "
        for c in competitors:
            if not c["done"]:
                ret = c["proc"].poll()
                if ret is not None:
                    c["done"] = True
                    c["duration"] = time.time() - c["t0"]
                    status_line += f"{c['name']}: ✅ FINISHED ({c['duration']:.1f}s) | "
                elif elapsed >= TIMEOUT_PER_ROUND:
                    c["proc"].kill()
                    c["done"] = True
                    c["duration"] = TIMEOUT_PER_ROUND
                    status_line += f"{c['name']}: ⏱️ TIMEOUT | "
                else:
                    all_done = False
                    sz = c["log"].stat().st_size if c["log"].exists() else 0
                    status_line += f"{c['name']}: 🏃 RUNNING ({sz}B) | "
            else:
                status_line += f"{c['name']}: DONE | "

        print(status_line)
        if all_done or elapsed >= TIMEOUT_PER_ROUND:
            break

    for c in competitors:
        c["f"].close()

    # Check if delivered artifact exists for audit logging
    etta_art = etta_dir / ".etta" / "artifacts" / "delivered_artifact.txt"
    if etta_art.exists():
        print(f"  [ETTA Engine] Generated artifact ({etta_art.stat().st_size} bytes)")

    # Evaluate Round 1
    print("\n" + "="*70)
    print("📊 ROUND 1 EVALUATION: HIDDEN ORACLE AUDIT")
    print("="*70)

    oracle_script = BASE_DIR / "oracle" / "c1_hidden_oracle.py"
    r1_results = []
    for c in competitors:
        # 1. Public test
        pub_res = subprocess.run([sys.executable, "tests/test_public_repro.py"], cwd=str(c["dir"]), capture_output=True, text=True)
        pub_passed = (pub_res.returncode == 0)

        # 2. Hidden oracle
        orc_res = subprocess.run([sys.executable, str(oracle_script), str(c["dir"])], capture_output=True, text=True)
        try:
            orc_data = json.loads(orc_res.stdout)
        except Exception:
            orc_data = {"passed": 0, "failed": 10, "errors": [orc_res.stderr]}

        # 3. Diff check
        diff = subprocess.run(["git", "diff", "simplify.py"], cwd=str(c["dir"]), capture_output=True, text=True).stdout

        r1_results.append({
            "agent": c["name"],
            "duration": round(c["duration"], 2),
            "public_passed": pub_passed,
            "oracle_score": f"{orc_data['passed']}/10",
            "oracle_passed": orc_data["passed"],
            "oracle_failed": orc_data["failed"],
            "errors": orc_data["errors"][:3],
            "diff_lines": len(diff.splitlines())
        })

    print(json.dumps(r1_results, indent=2))
    return r1_results

def run_round_2():
    print("\n" + "="*70)
    print("🚀 ROUND 2: CHALLENGE 2 (RUST MVCC CONCURRENCY DEADLOCK & TOCTOU)")
    print("="*70)
    print("Timeout:  300s (5.0 minutes)")
    print("Mode:     Unrestricted (Full tools, shell, and cargo execution)")
    print("Oracle:   Stress Testing Concurrency & Lock Inversion (c2_hidden_oracle_test.rs)")
    print("-"*70)

    setup_round_2()

    etta_dir = ARENA_DIR / "c2" / "etta"
    agy_dir = ARENA_DIR / "c2" / "agy"

    etta_log = ARENA_DIR / "c2" / "etta.log"
    agy_log = ARENA_DIR / "c2" / "agy.log"

    etta_f = open(etta_log, "w", encoding="utf-8")
    agy_f = open(agy_log, "w", encoding="utf-8")

    # In Round 2, both agents receive direct instructions enforcing the global monotonic lock hierarchy
    c2_etta_goal = (
        "In src/lib.rs, fix the concurrency deadlock and dirty read bugs in MvccEngine by enforcing monotonic lock hierarchy: "
        "Rank 1 active_txs, Rank 2 index across methods get, commit, garbage_collect. "
        "1. In garbage_collect(), acquire active_txs.write() FIRST, then index.write() SECOND (matching commit). "
        "2. In get(), acquire active_txs.read() FIRST, then index.read() SECOND (remove inner active_txs acquisition while holding index). "
        "3. In commit(), acquire active_txs.write() FIRST, then index.write() SECOND, and stamp version records in index with commit_id BEFORE marking transaction Committed in active_txs. "
        "4. Use file::replace or file::write on src/lib.rs, run cargo test --test test_public_repro to verify all tests pass, and output TASK_COMPLETE."
    )

    agy_lib = (agy_dir / "src" / "lib.rs").resolve()
    c2_agy_prompt = f"""You are tasked with fixing a critical concurrency bug in this local Rust repository.
The target file to edit is located at absolute path: {agy_lib}.
Run cargo test --test test_public_repro to observe the deadlock and dirty-read failure.
Inspect {agy_lib}. In MvccEngine enforce a global monotonic lock hierarchy: Rank 1 active_txs, Rank 2 index across all methods:
1. Lock Inversion Deadlock: In garbage_collect(), acquire active_txs.write() FIRST, then index.write() SECOND (matching commit).
2. Reader Isolation: In get(), acquire active_txs.read() FIRST, then index.read() SECOND (never acquire active_txs while holding index lock).
3. TOCTOU Dirty Read: In commit(), acquire active_txs.write() first, then index.write(), and update version records with commit_id BEFORE marking TxStatus::Committed.
4. Run cargo test --test test_public_repro to verify that all deadlocks and race conditions are completely resolved.
Immediately open {agy_lib} and apply the fix with replace_file_content."""

    # Launch ETTA only (AGY testing skipped per user rule)
    etta_cmd = [
        str(ETTA_BIN),
        "--headless",
        "--workspace", str(etta_dir),
        "--model", "gemini-3.8-flash-high",
        "--effort", "auto",
        "--goal", c2_etta_goal
    ]
    t0_etta = time.time()
    etta_proc = subprocess.Popen(etta_cmd, cwd=str(etta_dir), stdout=etta_f, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True)

    competitors = [
        {"name": "ETTA", "proc": etta_proc, "f": etta_f, "log": etta_log, "dir": etta_dir, "t0": t0_etta, "done": False, "duration": 0},
    ]

    start_time = time.time()
    while True:
        time.sleep(3)
        elapsed = int(time.time() - start_time)
        remaining = max(0, TIMEOUT_PER_ROUND - elapsed)

        all_done = True
        status_line = f"[{elapsed:3d}s / {TIMEOUT_PER_ROUND}s] "
        for c in competitors:
            if not c["done"]:
                ret = c["proc"].poll()
                if ret is not None:
                    c["done"] = True
                    c["duration"] = time.time() - c["t0"]
                    status_line += f"{c['name']}: ✅ FINISHED ({c['duration']:.1f}s) | "
                elif elapsed >= TIMEOUT_PER_ROUND:
                    c["proc"].kill()
                    c["done"] = True
                    c["duration"] = TIMEOUT_PER_ROUND
                    status_line += f"{c['name']}: ⏱️ TIMEOUT | "
                else:
                    all_done = False
                    sz = c["log"].stat().st_size if c["log"].exists() else 0
                    status_line += f"{c['name']}: 🏃 RUNNING ({sz}B) | "
            else:
                status_line += f"{c['name']}: DONE | "

        print(status_line)
        if all_done or elapsed >= TIMEOUT_PER_ROUND:
            break

    for c in competitors:
        c["f"].close()

    # Check if delivered artifact exists for audit logging
    etta_art = etta_dir / ".etta" / "artifacts" / "delivered_artifact.txt"
    if etta_art.exists():
        print(f"  [ETTA Engine] Generated artifact ({etta_art.stat().st_size} bytes)")

    # Evaluate Round 2
    print("\n" + "="*70)
    print("📊 ROUND 2 EVALUATION: CONCURRENCY STRESS & HIDDEN ORACLE")
    print("="*70)

    oracle_test_path = BASE_DIR / "oracle" / "c2_hidden_oracle_test.rs"
    r2_results = []
    for c in competitors:
        # 1. Public reproduction test
        try:
            pub_res = subprocess.run(["cargo", "test", "--test", "test_public_repro"], cwd=str(c["dir"]), capture_output=True, text=True, timeout=20)
            pub_passed = (pub_res.returncode == 0)
        except subprocess.TimeoutExpired:
            pub_passed = False

        # 2. Hidden oracle test
        target_oracle_test = c["dir"] / "tests" / "c2_hidden_oracle_test.rs"
        shutil.copy(oracle_test_path, target_oracle_test)
        
        try:
            orc_res = subprocess.run(["cargo", "test", "--test", "c2_hidden_oracle_test"], cwd=str(c["dir"]), capture_output=True, text=True, timeout=25)
            orc_passed = (orc_res.returncode == 0)
            orc_out = orc_res.stdout + "\n" + orc_res.stderr
        except subprocess.TimeoutExpired:
            orc_passed = False
            orc_out = "DEADLOCK TIMEOUT (>25s)"

        r2_results.append({
            "agent": c["name"],
            "duration": round(c["duration"], 2),
            "public_passed": pub_passed,
            "oracle_score": "10/10" if orc_passed else "0/10",
            "oracle_passed": 10 if orc_passed else 0,
            "oracle_failed": 0 if orc_passed else 10,
            "error_sample": orc_out.splitlines()[-3:] if not orc_passed else []
        })

    print(json.dumps(r2_results, indent=2))
    return r2_results

def main():
    print("\n" + "#"*70)
    print("   GRANDMASTER HEAD-TO-HEAD: ETTA VS. AGY (UNRESTRICTED GAUNTLET)  ")
    print("#"*70)

    selected_round = None
    if len(sys.argv) > 1:
        if "--round" in sys.argv:
            idx = sys.argv.index("--round")
            if idx + 1 < len(sys.argv):
                selected_round = int(sys.argv[idx + 1])
        elif sys.argv[1].isdigit():
            selected_round = int(sys.argv[1])

    r1, r2 = None, None
    if selected_round == 1:
        r1 = run_round_1()
    elif selected_round == 2:
        r2 = run_round_2()
    else:
        r1 = run_round_1()
        r2 = run_round_2()

    summary = {}
    if r1 is not None:
        summary["round_1_python_ast"] = r1
    if r2 is not None:
        summary["round_2_rust_mvcc"] = r2

    with open(ARENA_DIR / "gauntlet_final_results.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "#"*70)
    print("                   FINAL GAUNTLET SCORECARD                       ")
    print("#"*70)
    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()

