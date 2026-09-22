"""
Blind Evaluator for Problem 2: The Skyline Problem (LeetCode 218).
Contains 12 ruthless edge cases testing start/end coordinate collisions,
submerged buildings, touching edges, and 32-bit integer boundaries.
"""

import sys
import time
import importlib.util
from pathlib import Path


def load_solver(solver_path: Path):
    if not solver_path.exists():
        raise FileNotFoundError(f"Solver file not found: {solver_path}")
    spec = importlib.util.spec_from_file_location("skyline_candidate", solver_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "get_skyline"):
        raise AttributeError(f"Module {solver_path} is missing get_skyline function")
    return module.get_skyline


TEST_CASES = [
    # 1. Standard city with overlaps
    (
        1,
        "Standard Multi-Building City",
        [[2, 9, 10], [3, 7, 15], [5, 12, 12], [15, 20, 10], [19, 24, 8]],
        [[2, 10], [3, 15], [7, 12], [12, 0], [15, 10], [20, 8], [24, 0]],
    ),
    # 2. Adjacent touching buildings of identical height (must merge)
    (
        2,
        "Adjacent Equal-Height Buildings",
        [[0, 2, 3], [2, 5, 3]],
        [[0, 3], [5, 0]],
    ),
    # 3. Same start and end coordinates with distinct heights
    (
        3,
        "Identical Span Multiple Heights",
        [[1, 2, 1], [1, 2, 2], [1, 2, 3]],
        [[1, 3], [2, 0]],
    ),
    # 4. Same start/end, taller building obscures shorter ones
    (
        4,
        "Same Span Obscuration",
        [[2, 4, 7], [2, 4, 5], [2, 4, 6]],
        [[2, 7], [4, 0]],
    ),
    # 5. Exact duplicate buildings
    (
        5,
        "Exact Duplicate Buildings",
        [[1, 5, 3], [1, 5, 3]],
        [[1, 3], [5, 0]],
    ),
    # 6. Interlocking periodic skyline with height transitions
    (
        6,
        "Interlocking Periodic Skyline",
        [[0, 5, 7], [5, 10, 7], [5, 10, 12], [10, 15, 7], [15, 20, 7], [15, 20, 12], [20, 25, 7]],
        [[0, 7], [5, 12], [10, 7], [15, 12], [20, 7], [25, 0]],
    ),
    # 7. Multiple fully overlapping buildings of equal height
    (
        7,
        "Overlapping Same-Height Cascade",
        [[0, 3, 3], [1, 5, 3], [2, 4, 3], [3, 7, 3]],
        [[0, 3], [7, 0]],
    ),
    # 8. Dominant tall building completely enveloping three shorter buildings
    (
        8,
        "Dominant Tall Enclosing Shorter",
        [[1, 10, 9], [2, 5, 6], [4, 8, 7], [6, 9, 5]],
        [[1, 9], [10, 0]],
    ),
    # 9. Disjoint isolated towers with gaps between them
    (
        9,
        "Disjoint Gapped Towers",
        [[1, 2, 1], [3, 4, 1]],
        [[1, 1], [2, 0], [3, 1], [4, 0]],
    ),
    # 10. Max 32-bit integer boundaries
    (
        10,
        "Max 32-Bit Integer Coordinates",
        [[0, 2147483647, 2147483647]],
        [[0, 2147483647], [2147483647, 0]],
    ),
    # 11. Empty input
    (
        11,
        "Empty Input Array",
        [],
        [],
    ),
    # 12. Step down at junction (start of lower matches end of higher)
    (
        12,
        "Step Down Junction",
        [[1, 3, 4], [3, 5, 2]],
        [[1, 4], [3, 2], [5, 0]],
    ),
]


def run_evaluation(solver_fn):
    results = []
    for num, name, inp, expected in TEST_CASES:
        t0 = time.perf_counter()
        try:
            got = solver_fn([list(b) for b in inp])
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
        print("Usage: python evaluator.py <path_to_skyline.py>")
        sys.exit(1)

    solver_file = Path(sys.argv[1])
    try:
        fn = load_solver(solver_file)
    except Exception as e:
        print(f"FAILED TO LOAD SOLVER: {e}")
        sys.exit(1)

    print(f"\n=======================================================================")
    print(f"  BLIND EVALUATION: Problem 2 - The Skyline Problem ({solver_file.parent.name})")
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
