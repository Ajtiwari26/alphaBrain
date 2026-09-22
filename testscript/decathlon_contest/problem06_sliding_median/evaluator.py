import sys, time, random, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("p06", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.median_sliding_window

random.seed(42)
S_NUMS = [random.randint(-10000, 10000) for _ in range(30000)]
S_K = 15000

CASES = [
    (1, "Standard Odd Window (k=3)", [1, 3, -1, -3, 5, 3, 6, 7], 3, [1.0, -1.0, -1.0, 3.0, 5.0, 6.0]),
    (2, "Duplicates in Window", [1, 2, 3, 4, 2, 3, 1, 4, 2], 3, [2.0, 3.0, 3.0, 3.0, 2.0, 3.0, 2.0]),
    (3, "Even Window Size (k=4)", [1, 4, 2, 3], 4, [2.5]),
    (4, "Window Size 1 (k=1)", [5], 1, [5.0]),
    (5, "Max 32-bit Addition Overflow", [2147483647, 2147483647], 2, [2147483647.0]),
    (6, "All Negative Integers", [-1, -2, -3, -4, -5], 2, [-1.5, -2.5, -3.5, -4.5]),
    (7, "Uniform Constant Array", [1, 1, 1, 1, 1, 1], 4, [1.0, 1.0, 1.0]),
    (8, "Unsorted Balance Flips", [7, 0, 3, 9, 9, 9, 1, 7, 2, 3], 6, [8.0, 6.0, 8.0, 8.0, 5.0]),
    (9, "Extreme Mixed 32-bit Signs", [-2147483648, -2147483648, 2147483647, -2147483648], 3, [-2147483648.0, -2147483648.0]),
    (10, "Minimal Array (k=1)", [1, 2], 1, [1.0, 2.0]),
    (11, "Full Array Window (k=N)", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 10, [5.5]),
    (12, "Stress Test N=30,000, K=15,000", S_NUMS, S_K, None),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, nums, k, exp in CASES:
        t0 = time.perf_counter()
        try:
            got = fn(list(nums), k)
            elapsed = (time.perf_counter() - t0) * 1000.0
            if exp is not None:
                ok = (len(got) == len(exp)) and all(abs(a - b) < 1e-4 for a, b in zip(got, exp))
            else:
                ok = (len(got) == 15001) and abs(got[0] - 87.0) < 1e-4 and abs(got[-1] - (-159.5)) < 1e-4 and elapsed < 2500
            if ok:
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> FAIL")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")
    tot = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {tot:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 2)
