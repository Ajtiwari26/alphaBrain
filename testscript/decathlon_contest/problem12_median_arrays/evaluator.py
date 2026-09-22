import sys, time, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("p12", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.find_median_sorted_arrays

# Ground truth test cases
CASES = [
    (1, "Standard Odd Total", [1, 3], [2], 2.0),
    (2, "Standard Even Total", [1, 2], [3, 4], 2.5),
    (3, "First Array Empty", [], [1], 1.0),
    (4, "Second Array Empty", [2], [], 2.0),
    (5, "Both Singletons", [1], [2], 1.5),
    (6, "Disjoint Non-Overlapping", [1, 2, 3], [4, 5, 6, 7], 4.0),
    (7, "Interleaved Duplicates", [1, 2, 2], [2, 3, 4], 2.0),
    (8, "All Identical Elements", [5, 5, 5], [5, 5, 5, 5], 5.0),
    (9, "Negative Numbers", [-5, -3, -1], [-4, -2, 0], -2.5),
    (10, "Extreme Size Asymmetry", [1], [2, 3, 4, 5, 6, 7, 8, 9, 10], 5.5),
    (11, "Large Magnitude Values", [1000000], [2000000], 1500000.0),
    (12, "Stress Scale N=50k, M=50k", list(range(0, 100000, 2)), list(range(1, 100001, 2)), 49999.5),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, a1, a2, exp in CASES:
        t0 = time.perf_counter()
        try:
            got = float(fn(list(a1), list(a2)))
            elapsed = (time.perf_counter() - t0) * 1000.0
            # Asymptotic enforcement: stress test must execute in < 25ms, strictly disallowing O(N+M)
            if abs(got - exp) < 1e-5 and (num != 12 or elapsed < 50):
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.2f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.2f}ms) -> FAIL (exp {exp}, got {got})")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")

    total_time = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {total_time:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 1)
