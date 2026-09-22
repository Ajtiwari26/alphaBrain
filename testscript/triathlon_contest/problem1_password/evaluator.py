"""
Blind Evaluator for Problem 1: Strong Password Checker (LeetCode 420).
Contains 12 ruthless edge cases testing length adjustments, missing categories,
and modulo-3 repeating sequence reductions.
"""

import sys
import time
import importlib.util
from pathlib import Path


def load_solver(solver_path: Path):
    if not solver_path.exists():
        raise FileNotFoundError(f"Solver file not found: {solver_path}")
    spec = importlib.util.spec_from_file_location("pwd_candidate", solver_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "strong_password_checker"):
        raise AttributeError(f"Module {solver_path} is missing strong_password_checker function")
    return module.strong_password_checker


TEST_CASES = [
    # 1. Zero length (empty string) -> 6
    (1, "Empty String (Length 0)", "", 6),
    # 2. Single char missing upper and digit -> 5
    (2, "Single Char (Length 1)", "a", 5),
    # 3. Short string with categories -> 3
    (3, "Short String with Categories", "aA1", 3),
    # 4. Perfectly compliant strong password -> 0
    (4, "Already Strong Password", "1337C0d3", 0),
    # 5. Short string with repeat 'aaa' -> 3
    (5, "Short String with 3-Repeat", "aaa", 3),
    # 6. Exact boundary length 6 with 6 repeats and missing 2 categories -> 2
    (6, "Length 6 Full Repeat", "aaaaaa", 2),
    # 7. Length 6 with two separate repeats and missing uppercase -> 2
    (7, "Length 6 Dual Repeats", "aaa111", 2),
    # 8. All digits length 10 -> 3
    (8, "Length 10 All Digits", "1111111111", 3),
    # 9. Length 21 (all identical characters, 1 delete + repeat reduction) -> 7
    (9, "Length 21 Monolithic Repeat", "aaaaaaaaaaaaaaaaaaaaa", 7),
    # 10. Multi-repeat mixed modulo: 2 'b', 15 'a', 4 'c' (len 21) -> 8
    (10, "Length 21 Multi-Repeat Modulo Interplay", "bbaaaaaaaaaaaaaaacccc", 8),
    # 11. Length 21 alternating without repeats, missing lowercase -> 2
    (11, "Length 21 Alternating Missing Lowercase", "ABABABABABABABABABAB1", 2),
    # 12. Length 21 with 1 letter and 20 digits -> 2
    (12, "Length 21 Monodigit with Prefix", "A12345678901234567890", 2),
]


def run_evaluation(solver_fn):
    results = []
    for num, name, inp, expected in TEST_CASES:
        t0 = time.perf_counter()
        try:
            got = solver_fn(inp)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            if got == expected:
                results.append((num, name, True, None, elapsed_ms))
            else:
                results.append((num, name, False, f"Expected {expected}, got {got}", elapsed_ms))
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            results.append((num, name, False, str(e), elapsed_ms))
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python evaluator.py <path_to_password_checker.py>")
        sys.exit(1)

    solver_file = Path(sys.argv[1])
    try:
        fn = load_solver(solver_file)
    except Exception as e:
        print(f"FAILED TO LOAD SOLVER: {e}")
        sys.exit(1)

    print(f"\n=======================================================================")
    print(f"  BLIND EVALUATION: Problem 1 - Strong Password Checker ({solver_file.parent.name})")
    print(f"=======================================================================")

    t_start = time.perf_counter()
    eval_results = run_evaluation(fn)
    total_time = (time.perf_counter() - t_start) * 1000.0

    passed_count = sum(1 for _, _, ok, _, _ in eval_results if ok)
    total_count = len(eval_results)

    for num, name, ok, err, dur in eval_results:
        status_str = "PASS" if ok else "FAIL"
        glyph = "OK " if ok else "ERR"
        print(f"[{glyph}] Case {num:02d}: {name:<42} ({dur:.2f}ms) -> {status_str}")
        if not ok and err:
            print(f"      └─ Error: {err}")

    print(f"-----------------------------------------------------------------------")
    print(f"SCORE: {passed_count}/{total_count} Passed | Total Execution Time: {total_time:.2f}ms")
    print(f"=======================================================================\n")

    sys.exit(0 if passed_count == total_count else 2)
