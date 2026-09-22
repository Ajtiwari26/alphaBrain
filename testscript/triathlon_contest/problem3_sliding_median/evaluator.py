"""
Blind Evaluator for Problem 3: Sliding Window Median (LeetCode 480).
Contains 12 ruthless edge cases testing odd/even windows, extreme 32-bit values,
all-duplicate sequences, negative numbers, and a massive N=30,000 stress test
strictly enforcing O(N log K) performance.
"""

import sys
import time
import random
import importlib.util
from pathlib import Path


def load_solver(solver_path: Path):
    if not solver_path.exists():
        raise FileNotFoundError(f"Solver file not found: {solver_path}")
    spec = importlib.util.spec_from_file_location("median_candidate", solver_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "median_sliding_window"):
        raise AttributeError(f"Module {solver_path} is missing median_sliding_window function")
    return module.median_sliding_window


def approx_equal(list_a, list_b, tol=1e-4):
    if len(list_a) != len(list_b):
        return False, f"Length mismatch: {len(list_a)} != {len(list_b)}"
    for i, (a, b) in enumerate(zip(list_a, list_b)):
        if abs(a - b) > tol:
            return False, f"Mismatch at index {i}: expected {b}, got {a}"
    return True, "OK"


# Pre-generate deterministic stress test data
random.seed(42)
STRESS_NUMS = [random.randint(-10000, 10000) for _ in range(30000)]
STRESS_K = 15000

STANDARD_TEST_CASES = [
    # 1. Standard odd window
    (
        1,
        "Standard Odd Window (k=3)",
        [1, 3, -1, -3, 5, 3, 6, 7],
        3,
        [1.0, -1.0, -1.0, 3.0, 5.0, 6.0],
    ),
    # 2. Multiple duplicates in window
    (
        2,
        "Duplicates in Window",
        [1, 2, 3, 4, 2, 3, 1, 4, 2],
        3,
        [2.0, 3.0, 3.0, 3.0, 2.0, 3.0, 2.0],
    ),
    # 3. Even window size
    (
        3,
        "Even Window Size (k=4)",
        [1, 4, 2, 3],
        4,
        [2.5],
    ),
    # 4. Window size 1 (every element is its own median)
    (
        4,
        "Window Size 1 (k=1)",
        [5],
        1,
        [5.0],
    ),
    # 5. Large 32-bit positive integer overflow prevention
    (
        5,
        "Max 32-bit Integer Addition",
        [2147483647, 2147483647],
        2,
        [2147483647.0],
    ),
    # 6. Negative values with negative averages
    (
        6,
        "All Negative Integers",
        [-1, -2, -3, -4, -5],
        2,
        [-1.5, -2.5, -3.5, -4.5],
    ),
    # 7. Uniform repeated array
    (
        7,
        "Uniform Constant Array",
        [1, 1, 1, 1, 1, 1],
        4,
        [1.0, 1.0, 1.0],
    ),
    # 8. Unsorted sequence with odd/even balance flips
    (
        8,
        "Zero-Infused Unsorted Sequence",
        [7, 0, 3, 9, 9, 9, 1, 7, 2, 3],
        6,
        [5.0, 6.0, 8.0, 8.0, 5.0],
    ),
    # 9. Extreme 32-bit mixed signs
    (
        9,
        "Extreme Mixed 32-bit Signs",
        [-2147483648, -2147483648, 2147483647, -2147483648],
        3,
        [-2147483648.0, -2147483648.0],
    ),
    # 10. Two elements, k=1
    (
        10,
        "Minimal Array (k=1)",
        [1, 2],
        1,
        [1.0, 2.0],
    ),
    # 11. Full array window (k = len(nums))
    (
        11,
        "Full Array Window (k=N)",
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        10,
        [5.5],
    ),
]


def run_evaluation(solver_fn):
    results = []
    # Run cases 1 through 11
    for num, name, nums, k, expected in STANDARD_TEST_CASES:
        t0 = time.perf_counter()
        try:
            got = solver_fn(list(nums), k)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            ok, msg = approx_equal(got, expected)
            if ok:
                results.append((num, name, True, None, elapsed_ms))
            else:
                results.append((num, name, False, msg, elapsed_ms))
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            results.append((num, name, False, str(e), elapsed_ms))

    # Case 12: Stress test (N=30,000, K=15,000)
    t0 = time.perf_counter()
    try:
        got = solver_fn(STRESS_NUMS, STRESS_K)
        elapsed = time.perf_counter() - t0
        elapsed_ms = elapsed * 1000.0

        if len(got) != 15001:
            results.append((12, "Stress Test N=30,000, K=15,000", False, f"Expected 15001 outputs, got {len(got)}", elapsed_ms))
        elif abs(got[0] - 87.0) > 1e-4 or abs(got[-1] - (-159.5)) > 1e-4:
            results.append((12, "Stress Test N=30,000, K=15,000", False, f"Check values mismatch: got[0]={got[0]} (exp 87.0), got[-1]={got[-1]} (exp -159.5)", elapsed_ms))
        elif elapsed > 2.5:
            results.append((12, "Stress Test N=30,000, K=15,000", False, f"TLE: Execution took {elapsed:.2f}s (budget: 2.5s; indicates O(N*K) naive approach)", elapsed_ms))
        else:
            results.append((12, f"Stress Test N=30,000, K=15,000 ({elapsed_ms:.1f}ms)", True, None, elapsed_ms))
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        results.append((12, "Stress Test N=30,000, K=15,000", False, str(e), elapsed_ms))

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python evaluator.py <path_to_sliding_median.py>")
        sys.exit(1)

    solver_file = Path(sys.argv[1])
    try:
        fn = load_solver(solver_file)
    except Exception as e:
        print(f"FAILED TO LOAD SOLVER: {e}")
        sys.exit(1)

    print(f"\n=======================================================================")
    print(f"  BLIND EVALUATION: Problem 3 - Sliding Window Median ({solver_file.parent.name})")
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
