import sys, time, random, importlib.util
from pathlib import Path

def load_solver(p):
    spec = importlib.util.spec_from_file_location("p01", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.minimum_cost

def naive_min_cost(nums, k, dist):
    n = len(nums)
    needed = k - 1
    min_sum = float('inf')
    for i in range(1, n - needed + 1):
        win = nums[i : min(n, i + dist + 1)]
        if len(win) >= needed:
            s = sum(sorted(win)[:needed])
            if s < min_sum:
                min_sum = s
    return nums[0] + min_sum

random.seed(42)
S_NUMS = [random.randint(1, 1000) for _ in range(10000)]
S_K, S_DIST = 100, 500
S_EXP = naive_min_cost(S_NUMS, S_K, S_DIST)

CASES = [
    (1, "Standard Case 1", [1,3,2,6,4,2], 3, 3, 5),
    (2, "Standard Case 2", [10,1,2,2,2,1], 4, 3, 15),
    (3, "Minimal k=2", [10, 8, 3, 5, 2], 2, 2, 12),
    (4, "k equals array length", [1, 2, 3], 3, 2, 6),
    (5, "dist equals 1", [5, 4, 3, 2, 1], 3, 2, 8),
    (6, "Uniform identical elements", [7, 7, 7, 7, 7, 7], 3, 3, 21),
    (7, "Strictly increasing sequence", [1, 2, 3, 4, 5, 6, 7], 3, 3, 6),
    (8, "Strictly decreasing sequence", [10, 9, 8, 7, 6, 5], 4, 4, 28),
    (9, "Large distance window", [1, 10, 20, 30, 2, 3, 4], 4, 5, 10),
    (10, "Minimum valid window size", [5, 1, 2], 3, 2, 8),
    (11, "Large element values", [1000000, 500000, 200000, 800000], 3, 2, 1700000),
    (12, "Stress Test N=10,000, k=100", S_NUMS, S_K, S_DIST, S_EXP),
]

if __name__ == '__main__':
    fn = load_solver(Path(sys.argv[1]))
    passed = 0
    t_start = time.perf_counter()
    for num, name, *args in CASES:
        exp = args[-1]
        t0 = time.perf_counter()
        try:
            got = fn(*args[:-1])
            elapsed = (time.perf_counter() - t0) * 1000.0
            if got == exp and (num != 12 or elapsed < 2500):
                print(f"[OK ] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> PASS")
                passed += 1
            else:
                print(f"[ERR] Case {num:02d}: {name:<35} ({elapsed:.1f}ms) -> FAIL (exp {exp}, got {got})")
        except Exception as e:
            print(f"[ERR] Case {num:02d}: {name:<35} -> FAIL ({e})")
    tot = (time.perf_counter() - t_start) * 1000.0
    print(f"SCORE: {passed}/{len(CASES)} Passed | Total: {tot:.2f}ms")
    sys.exit(0 if passed == len(CASES) else 2)
